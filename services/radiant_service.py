"""
services/radiant_service.py — Push DICOM files to RadiAnt Viewer via C-STORE.

RadiAnt runs a local DICOM server (C-STORE SCP) that accepts incoming
studies.  We act as an SCU to push files — the study then opens
automatically in RadiAnt's viewer.

If a file uses a compressed transfer syntax (e.g. JPEG-LS) that RadiAnt
doesn't accept, we decompress it to Explicit VR Little Endian before sending.
"""

import os
import glob
import logging
from typing import Tuple, List

import pydicom
from pydicom.uid import (
    ExplicitVRLittleEndian,
    ImplicitVRLittleEndian,
)
from pynetdicom import AE
from pynetdicom.presentation import build_context

import config

logger = logging.getLogger(__name__)

# Standard uncompressed transfer syntaxes that RadiAnt always accepts
UNCOMPRESSED_SYNTAXES = [
    ExplicitVRLittleEndian,
    ImplicitVRLittleEndian,
]


def _prepare_dataset(ds: pydicom.Dataset) -> pydicom.Dataset:
    """
    Ensure the dataset uses an uncompressed transfer syntax.
    If the file is compressed (JPEG-LS, JPEG2000, etc.), decompress it.
    """
    current_ts = ds.file_meta.TransferSyntaxUID if hasattr(ds, 'file_meta') and ds.file_meta else None

    if current_ts and current_ts not in UNCOMPRESSED_SYNTAXES:
        try:
            ds.decompress()
            logger.info("Decompressed dataset from %s to Explicit VR Little Endian", current_ts)
        except Exception as exc:
            logger.warning("Could not decompress dataset (TS=%s): %s", current_ts, exc)
            # Even if decompress fails, force the transfer syntax to uncompressed
            # and hope for the best — RadiAnt may still accept it
            if hasattr(ds, 'file_meta'):
                ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    return ds


def send_to_radiant(
    file_paths: List[str],
) -> Tuple[bool, str, int]:
    """
    Send one or more DICOM files to RadiAnt via C-STORE.
    Automatically decompresses files if needed.

    Returns:
        (success, message, num_sent)
    """
    if not file_paths:
        return False, "No DICOM files to send", 0

    # Step 1: Read all datasets and build the required presentation contexts
    datasets = []
    contexts = []
    seen_contexts = set()

    for fp in file_paths:
        try:
            ds = pydicom.dcmread(fp, force=True)
            ds = _prepare_dataset(ds)
            datasets.append(ds)

            # Build a presentation context for this SOP Class
            sop_class = ds.SOPClassUID
            key = str(sop_class)
            if key not in seen_contexts:
                seen_contexts.add(key)
                ctx = build_context(sop_class, UNCOMPRESSED_SYNTAXES)
                contexts.append(ctx)

        except Exception as exc:
            logger.warning("Could not read %s: %s", fp, exc)
            continue

    if not datasets:
        return False, "No valid DICOM files could be read", 0

    # Step 2: Create AE and associate
    ae = AE(ae_title=config.SCU_AE_TITLE)
    ae.requested_contexts = contexts

    try:
        assoc = ae.associate(
            config.RADIANT_HOST,
            config.RADIANT_PORT,
            ae_title=config.RADIANT_AE_TITLE,
        )
    except Exception as exc:
        msg = f"Could not connect to RadiAnt at {config.RADIANT_HOST}:{config.RADIANT_PORT} — {exc}"
        logger.error(msg)
        return False, msg, 0

    if not assoc.is_established:
        msg = (
            f"Association rejected by RadiAnt. "
            f"Make sure RadiAnt's DICOM server is running on "
            f"{config.RADIANT_HOST}:{config.RADIANT_PORT} "
            f"with AE Title '{config.RADIANT_AE_TITLE}'."
        )
        logger.error(msg)
        return False, msg, 0

    # Step 3: Send each dataset
    sent = 0
    errors = []

    for ds in datasets:
        try:
            status = assoc.send_c_store(ds)
            if status and status.Status == 0x0000:
                sent += 1
            else:
                code = status.Status if status else 0xFFFF
                errors.append(f"status 0x{code:04X}")
        except Exception as exc:
            errors.append(str(exc))

    assoc.release()

    if sent == 0:
        return False, f"No files were accepted by RadiAnt: {'; '.join(errors)}", 0

    msg = f"Sent {sent}/{len(datasets)} file(s) to RadiAnt"
    if errors:
        msg += f" ({len(errors)} error(s))"

    logger.info(msg)
    return True, msg, sent


def collect_study_files(study) -> List[str]:
    """
    Given a DicomStudy model instance, return a list of all DICOM file
    paths belonging to that study — either from the study_folder or the
    single file_path.
    """
    paths: List[str] = []

    # Multi-file study stored in a folder
    if study.study_folder and os.path.isdir(study.study_folder):
        for ext in ("*.dcm", "*.DCM", "*"):
            found = glob.glob(os.path.join(study.study_folder, ext))
            if found:
                for f in found:
                    if os.path.isfile(f):
                        paths.append(f)
                break

    # Single-file study
    elif study.file_path and os.path.isfile(study.file_path):
        paths.append(study.file_path)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for p in paths:
        normed = os.path.normpath(p)
        if normed not in seen:
            seen.add(normed)
            unique.append(normed)

    return unique
