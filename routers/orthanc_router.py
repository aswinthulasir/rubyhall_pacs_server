"""
routers/orthanc_router.py — Endpoints for Orthanc integration + credential management.

Routes:
    # ─── Connection browsing ──────────────────────────────────────────────────
    GET  /orthanc/health                    — Check Orthanc (using user's active server)
    POST /orthanc/send/{study_id}           — Send a local study to Orthanc
    GET  /orthanc/studies                   — List all studies in Orthanc
    GET  /orthanc/studies/{orthanc_id}      — Get detail of one Orthanc study
    GET  /orthanc/download/{study_id}       — Proxy DICOM download from Orthanc

    # ─── Credential management ────────────────────────────────────────────────
    GET    /orthanc/servers                 — List user's saved Orthanc servers
    POST   /orthanc/servers                 — Add a new server
    PUT    /orthanc/servers/{id}            — Update a server
    DELETE /orthanc/servers/{id}            — Delete a server
    POST   /orthanc/servers/{id}/test       — Test connection to a server
    POST   /orthanc/servers/{id}/activate   — Set as active / default server
"""

import os
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List, Any, Dict, Optional

from database import get_db
from models import DicomStudy, User, OrthancServer
from schemas import (
    SendOrthancResponse, OrthancStudySummary, MessageResponse,
    OrthancServerCreate, OrthancServerUpdate, OrthancServerOut,
    OrthancTestResult, DicomStudyOut,
)
from auth.security import get_current_user
from services.orthanc_service import (
    upload_to_orthanc,
    list_orthanc_studies,
    get_orthanc_study_detail,
    download_dicom_from_orthanc,
    check_orthanc_health,
    list_study_instances,
    download_instance_file,
)
from services.dicom_service import (
    extract_metadata,
    generate_thumbnail,
    save_dicom_to_folder,
)
import config
import pydicom
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orthanc", tags=["Orthanc / RadiAnt"])


# ══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _get_active_creds(user: User, db: Session) -> Optional[Dict]:
    """
    Return the credential dict for the user's active Orthanc server,
    or None to fall back to config defaults.
    """
    server = None
    if user.last_orthanc_id:
        server = db.query(OrthancServer).filter(
            OrthancServer.id == user.last_orthanc_id,
            OrthancServer.user_id == user.id,
        ).first()

    if not server:
        # Try the default server
        server = db.query(OrthancServer).filter(
            OrthancServer.user_id == user.id,
            OrthancServer.is_default == True,
        ).first()

    if server:
        return {
            "url": server.url,
            "username": server.username,
            "password": server.password,
        }
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  Health check
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/health")
def orthanc_health(
    current_user: User    = Depends(get_current_user),
    db          : Session = Depends(get_db),
):
    """Ping the user's active Orthanc and return system information."""
    creds = _get_active_creds(current_user, db)
    info = check_orthanc_health(creds)
    if not info.get("online"):
        raise HTTPException(
            status_code=503,
            detail=f"Orthanc is unreachable: {info.get('error', 'Unknown error')}",
        )
    return info


# ══════════════════════════════════════════════════════════════════════════════
#  Send local study to Orthanc
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/send/{study_id}", response_model=SendOrthancResponse)
def send_to_orthanc(
    study_id     : int,
    current_user : User    = Depends(get_current_user),
    db           : Session = Depends(get_db),
):
    """Push a confirmed DICOM study from local storage to the user's active Orthanc."""
    study = db.query(DicomStudy).filter(
        DicomStudy.id          == study_id,
        DicomStudy.uploader_id == current_user.id,
        DicomStudy.status      == "CONFIRMED",
    ).first()

    if not study:
        raise HTTPException(404, "Confirmed study not found or not owned by you")

    creds = _get_active_creds(current_user, db)

    # Collect all DICOM files to upload
    files_to_send = []
    if study.study_folder and os.path.isdir(study.study_folder):
        for fname in os.listdir(study.study_folder):
            fpath = os.path.join(study.study_folder, fname)
            if os.path.isfile(fpath):
                files_to_send.append(fpath)
    elif study.file_path and os.path.isfile(study.file_path):
        files_to_send.append(study.file_path)
    else:
        raise HTTPException(400, "DICOM file(s) not found on disk")

    if not files_to_send:
        raise HTTPException(400, "No DICOM files found for this study")

    last_instance_id = None
    last_study_id = None
    sent_count = 0
    message = ""

    for fpath in files_to_send:
        success, message, instance_id, orthanc_study_id = upload_to_orthanc(fpath, creds)
        if success:
            last_instance_id = instance_id
            last_study_id = orthanc_study_id
            sent_count += 1

    if sent_count > 0:
        study.sent_to_orthanc     = True
        study.orthanc_instance_id = last_instance_id
        study.orthanc_study_id    = last_study_id
        study.orthanc_sent_at     = datetime.utcnow()
        db.commit()
        return SendOrthancResponse(
            success             = True,
            message             = f"Successfully sent {sent_count}/{len(files_to_send)} file(s) to Orthanc",
            orthanc_instance_id = last_instance_id,
            orthanc_study_id    = last_study_id,
        )

    return SendOrthancResponse(
        success             = False,
        message             = f"Failed to send files to Orthanc: {message}",
        orthanc_instance_id = None,
        orthanc_study_id    = None,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  List / detail / download studies from Orthanc
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/studies", response_model=List[OrthancStudySummary])
def get_orthanc_studies(
    current_user: User    = Depends(get_current_user),
    db          : Session = Depends(get_db),
):
    """Retrieve all DICOM studies in Orthanc, cross-referenced with our DB."""
    creds = _get_active_creds(current_user, db)
    success, message, studies = list_orthanc_studies(creds)

    if not success:
        raise HTTPException(503, f"Could not retrieve studies from Orthanc: {message}")

    # Cross-reference: find which orthanc_study_ids we have locally
    local_studies = (
        db.query(DicomStudy)
        .filter(DicomStudy.sent_to_orthanc == True)
        .all()
    )
    # Map: orthanc_study_id -> (local study id, uploader name)
    sent_map: Dict[str, tuple] = {}
    for ls in local_studies:
        if ls.orthanc_study_id:
            uploader_name = None
            if ls.uploader:
                uploader_name = ls.uploader.full_name
            sent_map[ls.orthanc_study_id] = (ls.id, uploader_name)

    result = []
    for s in studies:
        orthanc_id = s.get("orthanc_id")
        is_ours = orthanc_id in sent_map
        local_id = sent_map[orthanc_id][0] if is_ours else None
        sender   = sent_map[orthanc_id][1] if is_ours else None

        result.append(OrthancStudySummary(
            orthanc_id         = orthanc_id,
            patient_name       = s.get("patient_name"),
            patient_id         = s.get("patient_id"),
            study_date         = s.get("study_date"),
            study_description  = s.get("study_description"),
            modality           = s.get("modality"),
            study_instance_uid = s.get("study_instance_uid"),
            sent_by_us         = is_ours,
            local_study_id     = local_id,
            sent_by_user       = sender,
        ))

    return result


@router.get("/studies/{orthanc_id}")
def get_one_orthanc_study(
    orthanc_id   : str,
    current_user : User    = Depends(get_current_user),
    db           : Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return the full raw metadata JSON for a specific Orthanc study."""
    creds = _get_active_creds(current_user, db)
    success, message, data = get_orthanc_study_detail(orthanc_id, creds)
    if not success:
        raise HTTPException(503, f"Orthanc error: {message}")
    return data


@router.get("/download/{study_id}")
def download_from_orthanc(
    study_id     : int,
    current_user : User    = Depends(get_current_user),
    db           : Session = Depends(get_db),
):
    """Proxy-download the DICOM file from Orthanc."""
    study = db.query(DicomStudy).filter(DicomStudy.id == study_id).first()
    if not study:
        raise HTTPException(404, "Study not found")

    if not study.orthanc_instance_id:
        raise HTTPException(400, "This study has not been sent to Orthanc yet")

    creds = _get_active_creds(current_user, db)
    success, message, dicom_bytes = download_dicom_from_orthanc(
        study.orthanc_instance_id, creds
    )

    if not success:
        raise HTTPException(503, f"Could not download from Orthanc: {message}")

    filename = study.file_name or f"orthanc_{study.orthanc_instance_id}.dcm"
    return Response(

        content      = dicom_bytes,
        media_type   = "application/dicom",
        headers      = {"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ══════════════════════════════════════════════════════════════════════════════
#  Import study FROM Orthanc into our local PACS
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/import/{orthanc_id}")
def import_from_orthanc(
    orthanc_id   : str,
    current_user : User    = Depends(get_current_user),
    db           : Session = Depends(get_db),
):
    """
    Download all DICOM instances of an Orthanc study and save them
    locally as a new DicomStudy, following the same folder structure.
    """
    creds = _get_active_creds(current_user, db)

    # 1. Get study metadata from Orthanc
    ok, msg, study_data = get_orthanc_study_detail(orthanc_id, creds)
    if not ok:
        raise HTTPException(503, f"Could not fetch study from Orthanc: {msg}")

    # 2. List all instances
    ok, msg, instance_ids = list_study_instances(orthanc_id, creds)
    if not ok or len(instance_ids) == 0:
        raise HTTPException(400, f"No instances found in Orthanc study: {msg}")

    # 3. Download each instance and save to a local study folder
    study_folder_name = f"study_{uuid.uuid4().hex[:12]}"
    study_folder_path = os.path.join(config.DICOM_DIR, study_folder_name)

    first_meta = None
    first_thumb = None
    first_saved_path = None
    total_size_kb = 0.0
    file_count = 0

    for inst_id in instance_ids:
        success, file_bytes = download_instance_file(inst_id, creds)
        if not success or not file_bytes:
            logger.warning("Could not download instance %s", inst_id)
            continue

        saved_path, size_kb = save_dicom_to_folder(
            file_bytes, f"{inst_id}.dcm", study_folder_name
        )
        total_size_kb += size_kb
        file_count += 1

        # Extract metadata from the first valid file only
        if first_meta is None:
            try:
                first_saved_path = saved_path
                ds = pydicom.dcmread(saved_path, force=True)
                first_meta = extract_metadata(ds)
                study_uid = first_meta.get("study_instance_uid") or str(uuid.uuid4())
                first_thumb = generate_thumbnail(ds, study_uid)
            except Exception as exc:
                logger.warning("Metadata extraction failed for %s: %s", inst_id, exc)

    if file_count == 0:
        raise HTTPException(500, "Failed to download any instances from Orthanc")

    meta = first_meta or {}
    auto_mr = (meta.get("patient_name") or "IMPORTED").replace(" ", "_").upper()[:50]

    # 4. Create a DicomStudy record
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
        file_path           = first_saved_path or "",
        file_name           = f"{file_count} DICOM file(s)",
        file_size_kb        = round(total_size_kb, 2),
        thumbnail_path      = first_thumb,
        study_folder        = study_folder_path,
        num_files           = file_count,
        uploader_id         = current_user.id,
        status              = "CONFIRMED",
        upload_date         = datetime.utcnow(),
        # Mark it as already in Orthanc
        sent_to_orthanc     = True,
        orthanc_study_id    = orthanc_id,
        orthanc_sent_at     = datetime.utcnow(),
    )
    db.add(study)
    db.commit()
    db.refresh(study)

    return {
        "success": True,
        "message": f"Imported {file_count} file(s) from Orthanc into local PACS",
        "study_id": study.id,
        "patient_name": study.patient_name,
        "num_files": file_count,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Orthanc Server Credential Management
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/servers", response_model=List[OrthancServerOut])
def list_servers(
    current_user: User    = Depends(get_current_user),
    db          : Session = Depends(get_db),
):
    """List all Orthanc servers saved by the current user."""
    servers = (
        db.query(OrthancServer)
        .filter(OrthancServer.user_id == current_user.id)
        .order_by(OrthancServer.created_at.desc())
        .all()
    )
    return servers


@router.post("/servers", response_model=OrthancServerOut, status_code=201)
def create_server(
    payload      : OrthancServerCreate,
    current_user : User    = Depends(get_current_user),
    db           : Session = Depends(get_db),
):
    """Add a new Orthanc server for the current user."""
    # If this is marked as default, clear other defaults first
    if payload.is_default:
        db.query(OrthancServer).filter(
            OrthancServer.user_id == current_user.id,
            OrthancServer.is_default == True,
        ).update({"is_default": False})

    server = OrthancServer(
        user_id    = current_user.id,
        name       = payload.name.strip(),
        url        = payload.url.strip().rstrip("/"),
        username   = payload.username,
        password   = payload.password,
        is_default = payload.is_default,
    )
    db.add(server)
    db.commit()
    db.refresh(server)

    # Auto-activate if first server or default
    if payload.is_default or not current_user.last_orthanc_id:
        current_user.last_orthanc_id = server.id
        db.commit()

    return server


@router.put("/servers/{server_id}", response_model=OrthancServerOut)
def update_server(
    server_id    : int,
    payload      : OrthancServerUpdate,
    current_user : User    = Depends(get_current_user),
    db           : Session = Depends(get_db),
):
    """Update an existing Orthanc server."""
    server = db.query(OrthancServer).filter(
        OrthancServer.id == server_id,
        OrthancServer.user_id == current_user.id,
    ).first()

    if not server:
        raise HTTPException(404, "Server not found")

    if payload.name is not None:
        server.name = payload.name.strip()
    if payload.url is not None:
        server.url = payload.url.strip().rstrip("/")
    if payload.username is not None:
        server.username = payload.username
    if payload.password is not None:
        server.password = payload.password
    if payload.is_default is not None:
        if payload.is_default:
            db.query(OrthancServer).filter(
                OrthancServer.user_id == current_user.id,
                OrthancServer.is_default == True,
                OrthancServer.id != server_id,
            ).update({"is_default": False})
        server.is_default = payload.is_default

    db.commit()
    db.refresh(server)
    return server


@router.delete("/servers/{server_id}", response_model=MessageResponse)
def delete_server(
    server_id    : int,
    current_user : User    = Depends(get_current_user),
    db           : Session = Depends(get_db),
):
    """Delete an Orthanc server."""
    server = db.query(OrthancServer).filter(
        OrthancServer.id == server_id,
        OrthancServer.user_id == current_user.id,
    ).first()

    if not server:
        raise HTTPException(404, "Server not found")

    # If this was the active server, clear the reference
    if current_user.last_orthanc_id == server_id:
        current_user.last_orthanc_id = None

    db.delete(server)
    db.commit()
    return {"message": f"Server '{server.name}' deleted", "success": True}


@router.post("/servers/{server_id}/test", response_model=OrthancTestResult)
def test_server(
    server_id    : int,
    current_user : User    = Depends(get_current_user),
    db           : Session = Depends(get_db),
):
    """Test connectivity to a saved Orthanc server."""
    server = db.query(OrthancServer).filter(
        OrthancServer.id == server_id,
        OrthancServer.user_id == current_user.id,
    ).first()

    if not server:
        raise HTTPException(404, "Server not found")

    creds = {"url": server.url, "username": server.username, "password": server.password}
    info = check_orthanc_health(creds)

    if info.get("online"):
        return OrthancTestResult(
            success=True,
            message=f"Connected to {server.name}",
            version=info.get("version"),
        )
    return OrthancTestResult(
        success=False,
        message=f"Cannot reach {server.name}: {info.get('error', 'Unknown error')}",
    )


@router.post("/servers/{server_id}/activate", response_model=MessageResponse)
def activate_server(
    server_id    : int,
    current_user : User    = Depends(get_current_user),
    db           : Session = Depends(get_db),
):
    """Set a server as the user's active (last-used) Orthanc."""
    server = db.query(OrthancServer).filter(
        OrthancServer.id == server_id,
        OrthancServer.user_id == current_user.id,
    ).first()

    if not server:
        raise HTTPException(404, "Server not found")

    current_user.last_orthanc_id = server.id
    db.commit()
    return {"message": f"'{server.name}' is now your active Orthanc", "success": True}