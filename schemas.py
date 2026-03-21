"""
schemas.py — Pydantic v2 request / response models for all API endpoints.
These are kept separate from SQLAlchemy models (models.py) intentionally.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, field_validator


# ══════════════════════════════════════════════════════════════════════════════
#  Auth
# ══════════════════════════════════════════════════════════════════════════════

class UserRegister(BaseModel):
    username  : str
    email     : EmailStr
    full_name : str
    password  : str
    role_id   : int = 4    # default: patient

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class UserLogin(BaseModel):
    username : str
    password : str


class Token(BaseModel):
    access_token : str
    token_type   : str = "bearer"


class TokenData(BaseModel):
    user_id  : Optional[int] = None
    username : Optional[str] = None
    role_id  : Optional[int] = None


# ══════════════════════════════════════════════════════════════════════════════
#  User
# ══════════════════════════════════════════════════════════════════════════════

class RoleOut(BaseModel):
    id   : int
    name : str

    model_config = {"from_attributes": True}


class UserOut(BaseModel):
    id              : int
    username        : str
    email           : str
    full_name       : str
    role_id         : int
    role            : Optional[RoleOut] = None
    is_active       : bool
    created_at      : datetime
    last_orthanc_id : Optional[int] = None

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    email     : Optional[EmailStr] = None
    full_name : Optional[str]      = None
    is_active : Optional[bool]     = None


# ══════════════════════════════════════════════════════════════════════════════
#  DICOM Study
# ══════════════════════════════════════════════════════════════════════════════

class DicomPreviewResponse(BaseModel):
    """Returned right after DICOM upload — before the user clicks Save."""
    temp_study_id       : int
    patient_name        : Optional[str]
    patient_id_dicom    : Optional[str]
    patient_age         : Optional[str]
    patient_dob         : Optional[str]
    patient_sex         : Optional[str]
    study_date          : Optional[str]
    study_time          : Optional[str]
    study_description   : Optional[str]
    modality            : Optional[str]
    body_part           : Optional[str]
    accession_number    : Optional[str]
    study_instance_uid  : Optional[str]
    series_instance_uid : Optional[str]
    sop_instance_uid    : Optional[str]
    file_name           : Optional[str]
    file_size_kb        : Optional[float]
    thumbnail_url       : Optional[str]



class DicomStudyOut(BaseModel):
    id                  : int
    mr_number           : Optional[str] = None
    patient_name        : Optional[str]
    patient_age         : Optional[str]
    patient_dob         : Optional[str]
    patient_sex         : Optional[str]
    study_date          : Optional[str]
    study_description   : Optional[str]
    modality            : Optional[str]
    body_part           : Optional[str]
    study_instance_uid  : Optional[str]
    file_name           : Optional[str]
    file_size_kb        : Optional[float]
    thumbnail_url       : Optional[str] = None
    num_files           : int = 1
    uploader_id         : int
    uploader_name       : Optional[str] = None
    upload_date         : datetime
    status              : str
    sent_to_orthanc     : bool
    orthanc_instance_id : Optional[str]
    orthanc_study_id    : Optional[str]
    pdf_reports         : List[PdfReportOut] = []

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════════════════════
#  PDF Report
# ══════════════════════════════════════════════════════════════════════════════

class PdfReportOut(BaseModel):
    id          : int
    study_id    : int
    file_name   : Optional[str]
    file_url    : Optional[str] = None
    notes       : Optional[str]
    upload_date : datetime

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════════════════════
#  Orthanc
# ══════════════════════════════════════════════════════════════════════════════

class OrthancStudySummary(BaseModel):
    orthanc_id          : str
    patient_name        : Optional[str]
    patient_id          : Optional[str]
    study_date          : Optional[str]
    study_description   : Optional[str]
    modality            : Optional[str]
    study_instance_uid  : Optional[str] = None
    # Flags for "sent by us"
    sent_by_us          : bool = False
    local_study_id      : Optional[int] = None
    sent_by_user        : Optional[str] = None


class SendOrthancResponse(BaseModel):
    success             : bool
    message             : str
    orthanc_instance_id : Optional[str] = None
    orthanc_study_id    : Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
#  Orthanc Server Credentials
# ══════════════════════════════════════════════════════════════════════════════

class OrthancServerCreate(BaseModel):
    name       : str
    url        : str
    username   : str = ""
    password   : str = ""
    is_default : bool = False


class OrthancServerUpdate(BaseModel):
    name       : Optional[str]  = None
    url        : Optional[str]  = None
    username   : Optional[str]  = None
    password   : Optional[str]  = None
    is_default : Optional[bool] = None


class OrthancServerOut(BaseModel):
    id         : int
    user_id    : int
    name       : str
    url        : str
    username   : str
    password   : str
    is_default : bool
    created_at : datetime

    model_config = {"from_attributes": True}


class OrthancTestResult(BaseModel):
    success : bool
    message : str
    version : Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
#  Generic
# ══════════════════════════════════════════════════════════════════════════════

class MessageResponse(BaseModel):
    message : str
    success : bool = True


# Fix forward reference for DicomStudyOut.pdf_reports
DicomStudyOut.model_rebuild()