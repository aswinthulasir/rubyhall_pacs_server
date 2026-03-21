"""
services/dicom_scp.py — DICOM C-STORE SCP (receiver).

Runs a background DICOM server that accepts incoming C-STORE requests
from RadiAnt, Orthanc, or any other DICOM SCU.

Received DICOM instances are:
  1. Saved to disk in study folders (grouped by StudyInstanceUID)
  2. Recorded in the database as DicomStudy entries (status=CONFIRMED)
  3. Thumbnails are generated from the first file of each study
"""

import os
import uuid
import logging
import threading
from datetime import datetime
from typing import Dict, Any

import pydicom
from pynetdicom import AE, evt, AllStoragePresentationContexts
from pynetdicom.events import Event

import config
from database import SessionLocal
from models import DicomStudy
from services.dicom_service import (
    extract_metadata,
    generate_thumbnail,
    save_dicom_to_folder,
)

logger = logging.getLogger("dicom_scp")

# Track in-progress associations: assoc_id -> { study_uid: { folder, files, meta, ... } }
_active_receives: Dict[int, Dict[str, Any]] = {}
_lock = threading.Lock()


def _handle_store(event: Event) -> int:
    """
    Called for every incoming C-STORE request (one DICOM instance).
    Save the file and track metadata for later DB creation.
    """
    try:
        ds = event.dataset
        ds.file_meta = event.file_meta  # Attach file_meta for proper saving

        study_uid = str(getattr(ds, "StudyInstanceUID", "")) or str(uuid.uuid4())
        assoc_id = id(event.assoc)

        # Create a study folder name (deterministic per study_uid within this association)
        with _lock:
            if assoc_id not in _active_receives:
                _active_receives[assoc_id] = {}

            assoc_studies = _active_receives[assoc_id]

            if study_uid not in assoc_studies:
                folder_name = f"study_{uuid.uuid4().hex[:12]}"
                assoc_studies[study_uid] = {
                    "folder_name": folder_name,
                    "folder_path": os.path.join(config.DICOM_DIR, folder_name),
                    "file_count": 0,
                    "total_size_kb": 0.0,
                    "first_saved_path": None,
                    "first_meta": None,
                    "first_thumb": None,
                }

            study_info = assoc_studies[study_uid]
            folder_name = study_info["folder_name"]

        # Save the DICOM file to the study folder
        instance_uid = str(getattr(ds, "SOPInstanceUID", uuid.uuid4().hex))
        filename = f"{instance_uid}.dcm"

        # Convert dataset to bytes for saving
        from io import BytesIO
        buffer = BytesIO()
        pydicom.dcmwrite(buffer, ds, write_like_original=False)
        file_bytes = buffer.getvalue()

        saved_path, size_kb = save_dicom_to_folder(file_bytes, filename, folder_name)

        with _lock:
            study_info["file_count"] += 1
            study_info["total_size_kb"] += size_kb

            # Extract metadata from the first file
            if study_info["first_meta"] is None:
                study_info["first_saved_path"] = saved_path
                study_info["first_meta"] = extract_metadata(ds)
                thumb_uid = study_info["first_meta"].get("study_instance_uid") or str(uuid.uuid4())
                study_info["first_thumb"] = generate_thumbnail(ds, thumb_uid)

        logger.debug("Received instance %s for study %s (%d files so far)",
                      instance_uid[:12], study_uid[:12], study_info["file_count"])

        return 0x0000  # Success

    except Exception as exc:
        logger.error("Error handling C-STORE: %s", exc, exc_info=True)
        return 0xC000  # Failure


def _handle_release(event: Event):
    """
    Called when the association is released (sender is done).
    Create DicomStudy records for all received studies.
    """
    assoc_id = id(event.assoc)

    with _lock:
        studies = _active_receives.pop(assoc_id, {})

    if not studies:
        return

    logger.info("Association released — creating %d study record(s)", len(studies))

    db = SessionLocal()
    try:
        for study_uid, info in studies.items():
            if info["file_count"] == 0:
                continue

            meta = info["first_meta"] or {}
            auto_mr = (meta.get("patient_name") or "RECEIVED").replace(" ", "_").upper()[:50]

            study = DicomStudy(
                mr_number           = auto_mr,
                patient_name        = meta.get("patient_name"),
                patient_id_dicom    = meta.get("patient_id_dicom"),
                patient_age         = meta.get("patient_age"),
                patient_dob         = meta.get("patient_dob"),
                patient_sex         = meta.get("patient_sex"),
                study_date          = meta.get("study_date"),
                study_time          = meta.get("study_time"),
                study_description   = meta.get("study_description"),
                modality            = meta.get("modality"),
                body_part           = meta.get("body_part"),
                accession_number    = meta.get("accession_number"),
                study_instance_uid  = meta.get("study_instance_uid"),
                series_instance_uid = meta.get("series_instance_uid"),
                sop_instance_uid    = meta.get("sop_instance_uid"),
                sop_class_uid       = meta.get("sop_class_uid"),
                file_path           = info["first_saved_path"] or "",
                file_name           = f"{info['file_count']} DICOM file(s)",
                file_size_kb        = round(info["total_size_kb"], 2),
                thumbnail_path      = info["first_thumb"],
                study_folder        = info["folder_path"],
                num_files           = info["file_count"],
                uploader_id         = 1,  # System/admin user
                status              = "CONFIRMED",
                upload_date         = datetime.utcnow(),
            )
            db.add(study)
            logger.info(
                "Created study: %s — %s (%d files, %.1f KB)",
                meta.get("patient_name", "Unknown"),
                meta.get("modality", "?"),
                info["file_count"],
                info["total_size_kb"],
            )

        db.commit()
    except Exception as exc:
        logger.error("Failed to create study records: %s", exc, exc_info=True)
        db.rollback()
    finally:
        db.close()


# ── Global SCP server reference ─────────────────────────────────────────────

_scp_server = None
_scp_thread = None


def start_scp():
    """Start the DICOM C-STORE SCP in a background thread."""
    global _scp_server, _scp_thread

    ae = AE(ae_title=config.SCP_AE_TITLE)

    # Accept ALL storage SOP classes
    ae.supported_contexts = AllStoragePresentationContexts

    handlers = [
        (evt.EVT_C_STORE, _handle_store),
        (evt.EVT_RELEASED, _handle_release),
    ]

    logger.info(
        "Starting DICOM SCP: AE Title '%s' on port %d",
        config.SCP_AE_TITLE, config.SCP_PORT,
    )

    _scp_server = ae.start_server(
        ("0.0.0.0", config.SCP_PORT),
        block=False,
        evt_handlers=handlers,
    )

    logger.info(
        "DICOM SCP is running — RadiAnt can send to: "
        "IP=127.0.0.1  Port=%d  AE Title='%s'",
        config.SCP_PORT, config.SCP_AE_TITLE,
    )


def stop_scp():
    """Gracefully shut down the SCP server."""
    global _scp_server
    if _scp_server:
        logger.info("Shutting down DICOM SCP server...")
        _scp_server.shutdown()
        _scp_server = None
