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
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List, Any, Dict, Optional

from database import get_db
from models import DicomStudy, User, OrthancServer
from schemas import (
    SendOrthancResponse, OrthancStudySummary, MessageResponse,
    OrthancServerCreate, OrthancServerUpdate, OrthancServerOut,
    OrthancTestResult,
)
from auth.security import get_current_user
from services.orthanc_service import (
    upload_to_orthanc,
    list_orthanc_studies,
    get_orthanc_study_detail,
    download_dicom_from_orthanc,
    check_orthanc_health,
)
import config
from datetime import datetime

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
    """Retrieve all DICOM studies currently stored in the user's active Orthanc."""
    creds = _get_active_creds(current_user, db)
    success, message, studies = list_orthanc_studies(creds)

    if not success:
        raise HTTPException(503, f"Could not retrieve studies from Orthanc: {message}")

    return [
        OrthancStudySummary(
            orthanc_id        = s.get("orthanc_id"),
            patient_name      = s.get("patient_name"),
            patient_id        = s.get("patient_id"),
            study_date        = s.get("study_date"),
            study_description = s.get("study_description"),
            modality          = s.get("modality"),
        )
        for s in studies
    ]


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