"""
models.py — SQLAlchemy ORM table definitions for the Hospital PACS system.

Tables:
    roles           — User roles (admin, doctor, lab_assistant, etc.)
    users           — System users with hashed passwords
    dicom_studies   — Uploaded DICOM study records
    pdf_reports     — PDF reports attached to studies (doctors only)
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime,
    ForeignKey, Boolean, Enum, Float,
)
from sqlalchemy.orm import relationship
from database import Base


# ───────────────────────────────────────────────────────────────────────────────
class Role(Base):
    __tablename__ = "roles"

    id   = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)   # admin, doctor, etc.

    users = relationship("User", back_populates="role")

    def __repr__(self):
        return f"<Role id={self.id} name={self.name}>"


# ───────────────────────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    username        = Column(String(100), unique=True, nullable=False, index=True)
    email           = Column(String(200), unique=True, nullable=False)
    full_name       = Column(String(200), nullable=False)
    hashed_password = Column(String(255), nullable=False)   # bcrypt hash
    role_id         = Column(Integer, ForeignKey("roles.id"), nullable=False)
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

    role           = relationship("Role", back_populates="users")
    dicom_studies  = relationship("DicomStudy", back_populates="uploader")
    pdf_reports    = relationship("PdfReport", back_populates="uploader")

    def __repr__(self):
        return f"<User id={self.id} username={self.username} role={self.role_id}>"


# ───────────────────────────────────────────────────────────────────────────────
class DicomStudy(Base):
    __tablename__ = "dicom_studies"

    id                  = Column(Integer, primary_key=True, index=True)

    # ── Hospital identifiers ───────────────────────────────────────────────────
    mr_number           = Column(String(100), nullable=False, index=True)

    # ── DICOM extracted metadata ───────────────────────────────────────────────
    patient_name        = Column(String(200))
    patient_id_dicom    = Column(String(100))         # Patient ID from DICOM tag
    patient_age         = Column(String(20))          # "025Y" style DICOM age
    patient_dob         = Column(String(30))
    patient_sex         = Column(String(10))

    study_date          = Column(String(20))          # YYYYMMDD from DICOM
    study_time          = Column(String(20))
    study_description   = Column(String(300))
    modality            = Column(String(20))          # CT, MR, CR, DX, etc.
    body_part           = Column(String(100))
    accession_number    = Column(String(100))

    # ── DICOM UIDs ─────────────────────────────────────────────────────────────
    study_instance_uid  = Column(String(255), index=True)
    series_instance_uid = Column(String(255))
    sop_instance_uid    = Column(String(255))
    sop_class_uid       = Column(String(255))

    # ── File system ────────────────────────────────────────────────────────────
    file_path           = Column(String(500), nullable=False)
    file_name           = Column(String(300))
    file_size_kb        = Column(Float)
    thumbnail_path      = Column(String(500))
    study_folder        = Column(String(500))               # folder with all slices
    num_files           = Column(Integer, default=1)         # number of DICOM slices

    # ── Uploader info ──────────────────────────────────────────────────────────
    uploader_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
    upload_date         = Column(DateTime, default=datetime.utcnow)

    # ── Lifecycle status ───────────────────────────────────────────────────────
    status = Column(
        Enum("PENDING", "CONFIRMED", "DELETED"),
        default="PENDING",
        nullable=False,
    )

    # ── External PACS ─────────────────────────────────────────────────────────
    orthanc_instance_id = Column(String(255))          # Orthanc's own UUID
    orthanc_study_id    = Column(String(255))
    sent_to_orthanc     = Column(Boolean, default=False)
    orthanc_sent_at     = Column(DateTime)

    # ── Relationships ──────────────────────────────────────────────────────────
    uploader    = relationship("User", back_populates="dicom_studies")
    pdf_reports = relationship("PdfReport", back_populates="study")

    def __repr__(self):
        return f"<DicomStudy id={self.id} mr={self.mr_number} uid={self.study_instance_uid}>"


# ───────────────────────────────────────────────────────────────────────────────
class PdfReport(Base):
    __tablename__ = "pdf_reports"

    id          = Column(Integer, primary_key=True, index=True)
    study_id    = Column(Integer, ForeignKey("dicom_studies.id"), nullable=False)
    uploader_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    file_path   = Column(String(500), nullable=False)
    file_name   = Column(String(300))
    notes       = Column(Text)
    upload_date = Column(DateTime, default=datetime.utcnow)

    study    = relationship("DicomStudy", back_populates="pdf_reports")
    uploader = relationship("User", back_populates="pdf_reports")

    def __repr__(self):
        return f"<PdfReport id={self.id} study_id={self.study_id}>"