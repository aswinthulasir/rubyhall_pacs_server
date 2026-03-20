"""
routers/orthanc_router.py — Endpoints for Orthanc and RadiAnt integration.

Routes:
    GET  /orthanc/health                    — Check if Orthanc is reachable
    POST /orthanc/send/{study_id}           — Send a local study to Orthanc
    GET  /orthanc/studies                   — List all studies in Orthanc
    GET  /orthanc/studies/{orthanc_id}      — Get detail of one Orthanc study
    GET  /orthanc/download/{study_id}       — Proxy DICOM download from Orthanc
    GET  /orthanc/radiant-instructions      — How to open in RadiAnt viewer
"""

import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List, Any, Dict

from database import get_db
from models import DicomStudy, User
from schemas import SendOrthancResponse, OrthancStudySummary, MessageResponse
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


# ── Health check ───────────────────────────────────────────────────────────────
@router.get("/health")
def orthanc_health():
    """
    Ping Orthanc and return system information.
    No authentication required — useful for the frontend status badge.
    """
    info = check_orthanc_health()
    if not info.get("online"):
        raise HTTPException(
            status_code=503,
            detail=f"Orthanc is unreachable: {info.get('error', 'Unknown error')}",
        )
    return info


# ── Send local study to Orthanc ───────────────────────────────────────────────
@router.post("/send/{study_id}", response_model=SendOrthancResponse)
def send_to_orthanc(
    study_id     : int,
    current_user : User    = Depends(get_current_user),
    db           : Session = Depends(get_db),
):
    """
    Push a confirmed DICOM study from local storage to Orthanc.
    Sends ALL files in the study folder (all slices).
    Updates the study record with the Orthanc instance/study IDs.
    """
    study = db.query(DicomStudy).filter(
        DicomStudy.id          == study_id,
        DicomStudy.uploader_id == current_user.id,
        DicomStudy.status      == "CONFIRMED",
    ).first()

    if not study:
        raise HTTPException(404, "Confirmed study not found or not owned by you")

    # Collect all DICOM files to upload
    files_to_send = []
    if study.study_folder and os.path.isdir(study.study_folder):
        # Send every file in the study folder
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

    # Upload all files
    last_instance_id = None
    last_study_id = None
    sent_count = 0

    for fpath in files_to_send:
        success, message, instance_id, orthanc_study_id = upload_to_orthanc(fpath)
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


# ── List studies from Orthanc ─────────────────────────────────────────────────
@router.get("/studies", response_model=List[OrthancStudySummary])
def get_orthanc_studies(
    current_user: User = Depends(get_current_user),
):
    """Retrieve all DICOM studies currently stored in Orthanc."""
    success, message, studies = list_orthanc_studies()

    if not success:
        raise HTTPException(
            status_code=503,
            detail=f"Could not retrieve studies from Orthanc: {message}",
        )

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


# ── Single Orthanc study detail ───────────────────────────────────────────────
@router.get("/studies/{orthanc_id}")
def get_one_orthanc_study(
    orthanc_id   : str,
    current_user : User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return the full raw metadata JSON for a specific Orthanc study."""
    success, message, data = get_orthanc_study_detail(orthanc_id)

    if not success:
        raise HTTPException(503, f"Orthanc error: {message}")

    return data


# ── Download DICOM from Orthanc (proxy) ───────────────────────────────────────
@router.get("/download/{study_id}")
def download_from_orthanc(
    study_id     : int,
    current_user : User    = Depends(get_current_user),
    db           : Session = Depends(get_db),
):
    """
    Proxy-download the DICOM file from Orthanc for a study that was previously
    sent there. Useful to re-download or open in RadiAnt.
    """
    study = db.query(DicomStudy).filter(DicomStudy.id == study_id).first()
    if not study:
        raise HTTPException(404, "Study not found")

    if not study.orthanc_instance_id:
        raise HTTPException(400, "This study has not been sent to Orthanc yet")

    success, message, dicom_bytes = download_dicom_from_orthanc(study.orthanc_instance_id)

    if not success:
        raise HTTPException(503, f"Could not download from Orthanc: {message}")

    filename = study.file_name or f"orthanc_{study.orthanc_instance_id}.dcm"
    return Response(
        content      = dicom_bytes,
        media_type   = "application/dicom",
        headers      = {"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── RadiAnt instructions ──────────────────────────────────────────────────────
@router.get("/radiant-instructions")
def radiant_instructions(current_user: User = Depends(get_current_user)):
    """
    Return instructions for connecting RadiAnt DICOM Viewer to this system.
    RadiAnt is a desktop app that connects to an Orthanc DICOM node.
    """
    return {
        "instructions": [
            "1. Install RadiAnt DICOM Viewer from https://www.radiantviewer.com",
            "2. In RadiAnt, go to: Tools → PACS Configuration",
            "3. Add a new PACS server with the following details:",
            f"   - Address : {config.ORTHANC_URL.replace('http://', '').split(':')[0]}",
            "   - Port     : 4242 (Orthanc DICOM port — enable in Orthanc config)",
            "   - AET      : ORTHANC",
            "4. Alternatively, download the DICOM file via the /dicom/download/{id} endpoint",
            "   and drag-and-drop it onto the RadiAnt window.",
        ],
        "orthanc_url"     : config.ORTHANC_URL,
        "direct_download" : "Use GET /dicom/download/{study_id} to download locally for RadiAnt.",
    }