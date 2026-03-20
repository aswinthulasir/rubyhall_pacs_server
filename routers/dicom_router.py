"""
routers/dicom_router.py — DICOM file upload and study management endpoints.

Two-step upload flow:
  1. POST /dicom/upload-multi  → parse files, return preview (status=PENDING)
  2. POST /dicom/confirm-batch → save permanently (status=CONFIRMED)

Other routes:
  GET  /dicom/studies              — current user's CONFIRMED studies
  GET  /dicom/all-studies          — ALL users' CONFIRMED studies (Show PACS)
  GET  /dicom/studies/{id}         — single study detail
  GET  /dicom/thumbnail/{id}       — serve thumbnail image
  GET  /dicom/download/{id}        — download raw DICOM file
  DELETE /dicom/studies/{id}       — soft-delete study
  POST /dicom/upload-pdf/{study_id} — attach PDF report (doctors only)
"""

import os
import uuid
from datetime import datetime
from typing import List

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException,
    UploadFile, status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import DicomStudy, PdfReport, User
from schemas import (
    DicomPreviewResponse, DicomStudyOut,
    DicomConfirmRequest, PdfReportOut, MessageResponse,
)
from auth.security import get_current_user, require_doctor
from services.dicom_service import (
    process_dicom_upload,
    save_pdf_file,
    delete_file_if_exists,
    delete_folder_if_exists,
    save_dicom_to_folder,
    extract_metadata,
    generate_thumbnail,
)
import config
import pydicom

router = APIRouter(prefix="/dicom", tags=["DICOM Studies"])

# Maximum allowed file sizes
MAX_DICOM_BYTES = 200 * 1024 * 1024   # 200 MB
MAX_PDF_BYTES   =  20 * 1024 * 1024   #  20 MB


# ══════════════════════════════════════════════════════════════════════════════
#  Multi-file Upload — saves ALL slices as ONE study
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/upload-multi", response_model=DicomPreviewResponse, status_code=201)
async def upload_dicom_multi(
    mr_number    : str              = Form(..., description="Hospital MR / Patient Registry Number"),
    dicom_files  : List[UploadFile] = File(..., description="One or more DICOM files (.dcm)"),
    current_user : User             = Depends(get_current_user),
    db           : Session          = Depends(get_db),
):
    """
    Upload multiple DICOM files at once as a SINGLE study.
    All files are saved into a dedicated study folder.
    Returns ONE preview response (metadata from the first valid file).
    """
    # Generate a unique folder name for this study
    study_folder_name = f"study_{uuid.uuid4().hex[:12]}"
    study_folder_path = os.path.join(config.DICOM_DIR, study_folder_name)

    first_meta = None
    first_thumb = None
    first_saved_path = None
    total_size_kb = 0.0
    file_count = 0
    errors = []

    for dicom_file in dicom_files:
        try:
            file_bytes = await dicom_file.read()
            if len(file_bytes) > MAX_DICOM_BYTES:
                errors.append(f"{dicom_file.filename}: exceeds 200 MB limit")
                continue
            if len(file_bytes) == 0:
                errors.append(f"{dicom_file.filename}: empty file")
                continue

            # Save into the study folder
            saved_path, size_kb = save_dicom_to_folder(
                file_bytes, dicom_file.filename or "study.dcm", study_folder_name
            )
            total_size_kb += size_kb
            file_count += 1

            # Extract metadata from the first valid file only
            if first_meta is None:
                first_saved_path = saved_path
                ds = pydicom.dcmread(saved_path, force=True)
                first_meta = extract_metadata(ds)
                study_uid = first_meta.get("study_instance_uid") or str(uuid.uuid4())
                first_thumb = generate_thumbnail(ds, study_uid)

        except Exception as exc:
            errors.append(f"{dicom_file.filename}: {exc}")
            continue

    if file_count == 0:
        raise HTTPException(422, f"All files failed: {'; '.join(errors)}")

    meta = first_meta or {}

    # Create a single study record for all the files
    study = DicomStudy(
        mr_number           = mr_number.strip(),
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
        file_path           = first_saved_path,
        file_name           = f"{file_count} DICOM file(s)",
        file_size_kb        = round(total_size_kb, 2),
        thumbnail_path      = first_thumb,
        study_folder        = study_folder_path,
        num_files           = file_count,
        uploader_id         = current_user.id,
        status              = "PENDING",
    )
    db.add(study)
    db.commit()
    db.refresh(study)

    thumb_url = (
        f"/dicom/thumbnail/{study.id}"
        if first_thumb and os.path.isfile(first_thumb)
        else None
    )

    return DicomPreviewResponse(
        temp_study_id       = study.id,
        mr_number           = study.mr_number,
        patient_name        = study.patient_name,
        patient_id_dicom    = study.patient_id_dicom,
        patient_age         = study.patient_age,
        patient_dob         = study.patient_dob,
        patient_sex         = study.patient_sex,
        study_date          = study.study_date,
        study_time          = study.study_time,
        study_description   = study.study_description,
        modality            = study.modality,
        body_part           = study.body_part,
        accession_number    = study.accession_number,
        study_instance_uid  = study.study_instance_uid,
        series_instance_uid = study.series_instance_uid,
        sop_instance_uid    = study.sop_instance_uid,
        file_name           = study.file_name,
        file_size_kb        = study.file_size_kb,
        thumbnail_url       = thumb_url,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  Confirm / Save
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/confirm/{study_id}", response_model=DicomStudyOut)
def confirm_study(
    study_id     : int,
    payload      : DicomConfirmRequest,
    current_user : User    = Depends(get_current_user),
    db           : Session = Depends(get_db),
):
    """
    Confirm and permanently save the study.
    User may correct the MR Number at this step.
    """
    study = db.query(DicomStudy).filter(
        DicomStudy.id == study_id,
        DicomStudy.uploader_id == current_user.id,
    ).first()

    if not study:
        raise HTTPException(404, "Study not found or not owned by you")
    if study.status == "CONFIRMED":
        raise HTTPException(400, "Study is already confirmed")
    if study.status == "DELETED":
        raise HTTPException(400, "Study has been deleted")

    study.mr_number  = payload.mr_number.strip()
    study.status     = "CONFIRMED"
    study.upload_date = datetime.utcnow()

    db.commit()
    db.refresh(study)
    return _enrich_study(study, db)


# ── Batch confirm ────────────────────────────────────────────────────────────
@router.post("/confirm-batch", response_model=List[DicomStudyOut])
def confirm_batch(
    payload      : DicomConfirmRequest,
    current_user : User    = Depends(get_current_user),
    db           : Session = Depends(get_db),
):
    """
    Confirm ALL pending studies for the current user with the given MR number.
    """
    studies = (
        db.query(DicomStudy).filter(
            DicomStudy.uploader_id == current_user.id,
            DicomStudy.status      == "PENDING",
        ).all()
    )

    if not studies:
        raise HTTPException(404, "No pending studies found")

    results = []
    for study in studies:
        study.mr_number   = payload.mr_number.strip()
        study.status      = "CONFIRMED"
        study.upload_date = datetime.utcnow()
        results.append(study)

    db.commit()
    for s in results:
        db.refresh(s)

    return [_enrich_study(s, db) for s in results]


# ══════════════════════════════════════════════════════════════════════════════
#  Study Listing & Detail
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/studies", response_model=List[DicomStudyOut])
def list_studies(
    current_user : User    = Depends(get_current_user),
    db           : Session = Depends(get_db),
):
    """Return all CONFIRMED studies uploaded by the current user (dashboard)."""
    studies = (
        db.query(DicomStudy)
        .filter(
            DicomStudy.uploader_id == current_user.id,
            DicomStudy.status      == "CONFIRMED",
        )
        .order_by(DicomStudy.upload_date.desc())
        .all()
    )
    return [_enrich_study(s, db) for s in studies]


@router.get("/all-studies", response_model=List[DicomStudyOut])
def list_all_studies(
    current_user : User    = Depends(get_current_user),
    db           : Session = Depends(get_db),
):
    """Return ALL CONFIRMED studies from ALL users (Show PACS page)."""
    studies = (
        db.query(DicomStudy)
        .options(joinedload(DicomStudy.uploader))
        .filter(DicomStudy.status == "CONFIRMED")
        .order_by(DicomStudy.upload_date.desc())
        .all()
    )
    return [_enrich_study(s, db) for s in studies]


@router.get("/studies/{study_id}", response_model=DicomStudyOut)
def get_study(
    study_id     : int,
    current_user : User    = Depends(get_current_user),
    db           : Session = Depends(get_db),
):
    """Retrieve full detail of a single study."""
    study = db.query(DicomStudy).filter(
        DicomStudy.id == study_id,
    ).first()

    if not study:
        raise HTTPException(404, "Study not found")
    return _enrich_study(study, db)


# ══════════════════════════════════════════════════════════════════════════════
#  Thumbnail & Download
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/thumbnail/{study_id}")
def get_thumbnail(
    study_id     : int,
    current_user : User    = Depends(get_current_user),
    db           : Session = Depends(get_db),
):
    """Serve the JPEG thumbnail for a DICOM study."""
    study = db.query(DicomStudy).filter(
        DicomStudy.id == study_id,
    ).first()

    if not study:
        raise HTTPException(404, "Study not found")
    if not study.thumbnail_path or not os.path.isfile(study.thumbnail_path):
        raise HTTPException(404, "Thumbnail not available")

    return FileResponse(study.thumbnail_path, media_type="image/jpeg")


@router.get("/download/{study_id}")
def download_dicom(
    study_id     : int,
    current_user : User    = Depends(get_current_user),
    db           : Session = Depends(get_db),
):
    """
    Download the raw DICOM file.
    Used to open locally in RadiAnt or other desktop viewers.
    """
    study = db.query(DicomStudy).filter(
        DicomStudy.id == study_id,
    ).first()

    if not study:
        raise HTTPException(404, "Study not found")
    if not study.file_path or not os.path.isfile(study.file_path):
        raise HTTPException(404, "DICOM file not found on disk")

    filename = study.file_name or f"study_{study_id}.dcm"
    return FileResponse(
        study.file_path,
        media_type    = "application/dicom",
        filename      = filename,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  Delete
# ══════════════════════════════════════════════════════════════════════════════

@router.delete("/studies/{study_id}", response_model=MessageResponse)
def delete_study(
    study_id     : int,
    current_user : User    = Depends(get_current_user),
    db           : Session = Depends(get_db),
):
    """Soft-delete a study (marks status=DELETED, removes files from disk)."""
    study = db.query(DicomStudy).filter(
        DicomStudy.id          == study_id,
        DicomStudy.uploader_id == current_user.id,
    ).first()

    if not study:
        raise HTTPException(404, "Study not found")

    # Remove the entire study folder if present, otherwise just the single file
    if study.study_folder:
        delete_folder_if_exists(study.study_folder)
    else:
        delete_file_if_exists(study.file_path)

    delete_file_if_exists(study.thumbnail_path)

    study.status         = "DELETED"
    study.file_path      = None
    study.thumbnail_path = None
    study.study_folder   = None
    db.commit()

    return {"message": f"Study {study_id} deleted successfully", "success": True}


# ══════════════════════════════════════════════════════════════════════════════
#  PDF Report Upload (doctors only)
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/upload-pdf/{study_id}",
    response_model=PdfReportOut,
    status_code=201,
    dependencies=[Depends(require_doctor)],
)
async def upload_pdf_report(
    study_id     : int,
    notes        : str       = Form(""),
    pdf_file     : UploadFile = File(...),
    current_user : User       = Depends(get_current_user),
    db           : Session    = Depends(get_db),
):
    """
    Attach a PDF radiology report to an existing DICOM study.
    Only users with the Doctor role (role_id=2) may call this endpoint.
    """
    # Verify study exists
    study = db.query(DicomStudy).filter(DicomStudy.id == study_id).first()
    if not study:
        raise HTTPException(404, "Study not found")

    # Validate file type
    if not (
        pdf_file.content_type == "application/pdf"
        or (pdf_file.filename or "").lower().endswith(".pdf")
    ):
        raise HTTPException(400, "Only PDF files are accepted")

    file_bytes = await pdf_file.read()
    if len(file_bytes) > MAX_PDF_BYTES:
        raise HTTPException(413, "PDF exceeds 20 MB limit")

    saved_path = save_pdf_file(file_bytes, pdf_file.filename or "report.pdf")

    report = PdfReport(
        study_id    = study_id,
        uploader_id = current_user.id,
        file_path   = saved_path,
        file_name   = pdf_file.filename,
        notes       = notes.strip() or None,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


# ══════════════════════════════════════════════════════════════════════════════
#  Private helpers
# ══════════════════════════════════════════════════════════════════════════════

def _enrich_study(study: DicomStudy, db: Session) -> DicomStudyOut:
    """Attach a public thumbnail_url and uploader_name to the study."""
    thumb_url = (
        f"/dicom/thumbnail/{study.id}"
        if study.thumbnail_path and os.path.isfile(study.thumbnail_path)
        else None
    )

    # Get uploader name
    uploader_name = None
    if study.uploader:
        uploader_name = study.uploader.full_name
    else:
        uploader = db.query(User).filter(User.id == study.uploader_id).first()
        if uploader:
            uploader_name = uploader.full_name

    out = DicomStudyOut.model_validate(study)
    out.thumbnail_url = thumb_url
    out.uploader_name = uploader_name
    return out