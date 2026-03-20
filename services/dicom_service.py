"""
services/dicom_service.py — DICOM file processing utilities.

Responsibilities:
  - Extract patient / study metadata from DICOM tags
  - Generate a JPEG thumbnail from the middle slice
  - Save / clean up uploaded DICOM files
"""

import os
import uuid
import logging
from typing import Optional, Tuple, Dict, Any

import pydicom
import numpy as np
from PIL import Image

import config

logger = logging.getLogger(__name__)

# Ensure storage directories exist at import time
for _dir in (config.DICOM_DIR, config.PDF_DIR, config.THUMBNAIL_DIR):
    os.makedirs(_dir, exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
#  Tag extraction helpers
# ══════════════════════════════════════════════════════════════════════════════

def _safe_tag(ds: pydicom.Dataset, *keywords: str) -> Optional[str]:
    """Return string value of the first tag that exists in ds, else None."""
    for kw in keywords:
        try:
            val = getattr(ds, kw, None)
            if val is not None:
                return str(val).strip()
        except Exception:
            continue
    return None


def extract_metadata(ds: pydicom.Dataset) -> Dict[str, Any]:
    """
    Return a dictionary of human-readable metadata extracted from a DICOM dataset.
    Only tags that are commonly present are attempted; missing tags return None.
    """
    return {
        "patient_name"       : _safe_tag(ds, "PatientName"),
        "patient_id_dicom"   : _safe_tag(ds, "PatientID"),
        "patient_age"        : _safe_tag(ds, "PatientAge"),
        "patient_dob"        : _safe_tag(ds, "PatientBirthDate"),
        "patient_sex"        : _safe_tag(ds, "PatientSex"),
        "study_date"         : _safe_tag(ds, "StudyDate"),
        "study_time"         : _safe_tag(ds, "StudyTime"),
        "study_description"  : _safe_tag(ds, "StudyDescription"),
        "modality"           : _safe_tag(ds, "Modality"),
        "body_part"          : _safe_tag(ds, "BodyPartExamined"),
        "accession_number"   : _safe_tag(ds, "AccessionNumber"),
        "study_instance_uid" : _safe_tag(ds, "StudyInstanceUID"),
        "series_instance_uid": _safe_tag(ds, "SeriesInstanceUID"),
        "sop_instance_uid"   : _safe_tag(ds, "SOPInstanceUID"),
        "sop_class_uid"      : _safe_tag(ds, "SOPClassUID"),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Thumbnail generation
# ══════════════════════════════════════════════════════════════════════════════

def _normalize_array(arr: np.ndarray) -> np.ndarray:
    """Normalize pixel data to 0-255 uint8 for display."""
    arr = arr.astype(np.float32)
    mn, mx = arr.min(), arr.max()
    if mx == mn:
        return np.zeros(arr.shape, dtype=np.uint8)
    arr = (arr - mn) / (mx - mn) * 255.0
    return arr.astype(np.uint8)


def generate_thumbnail(
    ds: pydicom.Dataset,
    study_uid: str,
    size: Tuple[int, int] = (256, 256),
) -> Optional[str]:
    """
    Generate a JPEG thumbnail from the middle slice of the DICOM pixel data.
    Returns the relative file path of the saved thumbnail, or None on failure.
    """
    try:
        pixel_array = ds.pixel_array        # raises if no pixel data

        # Handle multi-frame (pick middle frame)
        if pixel_array.ndim == 3:
            mid = pixel_array.shape[0] // 2
            frame = pixel_array[mid]
        elif pixel_array.ndim == 2:
            frame = pixel_array
        else:
            logger.warning("Unexpected pixel array dimensions: %s", pixel_array.shape)
            return None

        frame_norm = _normalize_array(frame)
        img = Image.fromarray(frame_norm, mode="L")     # grayscale
        img = img.resize(size, Image.LANCZOS)

        # Build a unique filename based on study UID
        safe_uid = (study_uid or str(uuid.uuid4())).replace(".", "_")
        thumb_filename = f"thumb_{safe_uid}.jpg"
        thumb_path = os.path.join(config.THUMBNAIL_DIR, thumb_filename)

        img.save(thumb_path, format="JPEG", quality=75)
        logger.info("Thumbnail saved: %s", thumb_path)
        return thumb_path

    except Exception as exc:
        logger.warning("Thumbnail generation failed: %s", exc)
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  File I/O helpers
# ══════════════════════════════════════════════════════════════════════════════

def save_dicom_file(file_bytes: bytes, original_filename: str) -> Tuple[str, float]:
    """
    Persist raw DICOM bytes to the DICOM upload directory.
    Returns (saved_path, size_in_kb).
    """
    ext = os.path.splitext(original_filename)[1] or ".dcm"
    unique_name = f"{uuid.uuid4().hex}{ext}"
    dest_path   = os.path.join(config.DICOM_DIR, unique_name)

    with open(dest_path, "wb") as f:
        f.write(file_bytes)

    size_kb = len(file_bytes) / 1024.0
    return dest_path, size_kb


def save_pdf_file(file_bytes: bytes, original_filename: str) -> str:
    """
    Persist raw PDF bytes to the PDF upload directory.
    Returns saved_path.
    """
    ext = os.path.splitext(original_filename)[1] or ".pdf"
    unique_name = f"{uuid.uuid4().hex}{ext}"
    dest_path   = os.path.join(config.PDF_DIR, unique_name)

    with open(dest_path, "wb") as f:
        f.write(file_bytes)

    return dest_path


def delete_file_if_exists(path: Optional[str]) -> None:
    """Silently remove a file from disk if it exists."""
    if path and os.path.isfile(path):
        try:
            os.remove(path)
        except OSError as e:
            logger.warning("Could not delete file %s: %s", path, e)


def delete_folder_if_exists(path: Optional[str]) -> None:
    """Silently remove an entire folder from disk if it exists."""
    if path and os.path.isdir(path):
        try:
            import shutil
            shutil.rmtree(path, ignore_errors=True)
        except OSError as e:
            logger.warning("Could not delete folder %s: %s", path, e)


def save_dicom_to_folder(
    file_bytes: bytes, original_filename: str, folder_name: str
) -> Tuple[str, float]:
    """
    Save a DICOM file into a named subfolder under DICOM_DIR.
    Creates the subfolder if it doesn't exist.
    Returns (saved_path, size_in_kb).
    """
    folder_path = os.path.join(config.DICOM_DIR, folder_name)
    os.makedirs(folder_path, exist_ok=True)

    ext = os.path.splitext(original_filename)[1] or ".dcm"
    unique_name = f"{uuid.uuid4().hex}{ext}"
    dest_path = os.path.join(folder_path, unique_name)

    with open(dest_path, "wb") as f:
        f.write(file_bytes)

    size_kb = len(file_bytes) / 1024.0
    return dest_path, size_kb


# ══════════════════════════════════════════════════════════════════════════════
#  Main processing entry-point
# ══════════════════════════════════════════════════════════════════════════════

def process_dicom_upload(
    file_bytes: bytes,
    original_filename: str,
) -> Tuple[str, float, Dict[str, Any], Optional[str]]:
    """
    High-level helper called from the router.

    Steps:
      1. Save DICOM file to disk
      2. Parse with pydicom
      3. Extract metadata
      4. Generate thumbnail

    Returns:
        (saved_path, size_kb, metadata_dict, thumbnail_path)
    """
    saved_path, size_kb = save_dicom_file(file_bytes, original_filename)

    ds = pydicom.dcmread(saved_path, force=True)
    metadata = extract_metadata(ds)

    study_uid    = metadata.get("study_instance_uid") or str(uuid.uuid4())
    thumb_path   = generate_thumbnail(ds, study_uid)

    return saved_path, size_kb, metadata, thumb_path