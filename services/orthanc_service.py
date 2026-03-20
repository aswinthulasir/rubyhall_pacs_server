"""
services/orthanc_service.py — Wrapper around Orthanc's REST API.

Covers:
  - Uploading a DICOM file to Orthanc (/instances)
  - Listing studies stored in Orthanc (/studies)
  - Retrieving detailed study metadata from Orthanc
  - Downloading a DICOM instance from Orthanc
"""

import logging
from typing import List, Optional, Dict, Any, Tuple

import httpx

import config

logger = logging.getLogger(__name__)

# Base auth tuple reused across every call
_AUTH = (config.ORTHANC_USERNAME, config.ORTHANC_PASSWORD)
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


# ══════════════════════════════════════════════════════════════════════════════
#  Internal helpers
# ══════════════════════════════════════════════════════════════════════════════

def _get(path: str) -> httpx.Response:
    url = f"{config.ORTHANC_URL}{path}"
    return httpx.get(url, auth=_AUTH, timeout=_TIMEOUT)


def _post_bytes(path: str, data: bytes, content_type: str = "application/dicom") -> httpx.Response:
    url = f"{config.ORTHANC_URL}{path}"
    return httpx.post(
        url,
        content=data,
        headers={"Content-Type": content_type},
        auth=_AUTH,
        timeout=_TIMEOUT,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  Public API
# ══════════════════════════════════════════════════════════════════════════════

def upload_to_orthanc(dicom_file_path: str) -> Tuple[bool, str, Optional[str], Optional[str]]:
    """
    Upload a local DICOM file to Orthanc.

    Returns:
        (success, message, orthanc_instance_id, orthanc_study_id)
    """
    try:
        with open(dicom_file_path, "rb") as f:
            dicom_bytes = f.read()

        resp = _post_bytes("/instances", dicom_bytes)

        if resp.status_code in (200, 201):
            data             = resp.json()
            instance_id      = data.get("ID")
            orthanc_study_id = data.get("ParentStudy")
            logger.info("Uploaded to Orthanc: instance=%s study=%s", instance_id, orthanc_study_id)
            return True, "Successfully uploaded to Orthanc", instance_id, orthanc_study_id

        logger.warning("Orthanc upload failed: HTTP %s — %s", resp.status_code, resp.text)
        return False, f"Orthanc returned HTTP {resp.status_code}: {resp.text}", None, None

    except FileNotFoundError:
        msg = f"DICOM file not found: {dicom_file_path}"
        logger.error(msg)
        return False, msg, None, None
    except httpx.ConnectError:
        msg = "Cannot connect to Orthanc at " + config.ORTHANC_URL
        logger.error(msg)
        return False, msg, None, None
    except Exception as exc:
        logger.exception("Unexpected error during Orthanc upload")
        return False, str(exc), None, None


def list_orthanc_studies() -> Tuple[bool, str, List[Dict[str, Any]]]:
    """
    Retrieve all studies currently stored in Orthanc.

    Returns:
        (success, message, list_of_study_summaries)
    """
    try:
        # Get list of study IDs
        resp = _get("/studies")
        if resp.status_code != 200:
            return False, f"Orthanc returned HTTP {resp.status_code}", []

        study_ids: List[str] = resp.json()
        studies = []

        for sid in study_ids:
            detail_resp = _get(f"/studies/{sid}")
            if detail_resp.status_code != 200:
                continue

            d = detail_resp.json()
            main       = d.get("MainDicomTags", {})
            pt         = d.get("PatientMainDicomTags", {})

            studies.append({
                "orthanc_id"       : sid,
                "patient_name"     : pt.get("PatientName"),
                "patient_id"       : pt.get("PatientID"),
                "study_date"       : main.get("StudyDate"),
                "study_description": main.get("StudyDescription"),
                "modality"         : ", ".join(d.get("RequestedTags", {}).get("ModalitiesInStudy", "").split("\\")),
                "series_count"     : len(d.get("Series", [])),
                "study_instance_uid": main.get("StudyInstanceUID"),
            })

        return True, f"Retrieved {len(studies)} studies from Orthanc", studies

    except httpx.ConnectError:
        msg = "Cannot connect to Orthanc at " + config.ORTHANC_URL
        logger.error(msg)
        return False, msg, []
    except Exception as exc:
        logger.exception("Error fetching Orthanc studies")
        return False, str(exc), []


def get_orthanc_study_detail(orthanc_study_id: str) -> Tuple[bool, str, Optional[Dict]]:
    """
    Retrieve full metadata for a single study from Orthanc.
    """
    try:
        resp = _get(f"/studies/{orthanc_study_id}")
        if resp.status_code == 200:
            return True, "OK", resp.json()
        return False, f"HTTP {resp.status_code}", None
    except httpx.ConnectError:
        return False, "Cannot connect to Orthanc", None
    except Exception as exc:
        return False, str(exc), None


def download_dicom_from_orthanc(orthanc_instance_id: str) -> Tuple[bool, str, Optional[bytes]]:
    """
    Download the raw DICOM bytes for a specific instance from Orthanc.
    Used to proxy the file to the frontend for local RadiAnt viewing.
    """
    try:
        resp = _get(f"/instances/{orthanc_instance_id}/file")
        if resp.status_code == 200:
            return True, "OK", resp.content
        return False, f"HTTP {resp.status_code}", None
    except httpx.ConnectError:
        return False, "Cannot connect to Orthanc", None
    except Exception as exc:
        return False, str(exc), None


def check_orthanc_health() -> Dict[str, Any]:
    """
    Check if Orthanc is reachable and return its system information.
    """
    try:
        resp = _get("/system")
        if resp.status_code == 200:
            data = resp.json()
            return {
                "online"       : True,
                "version"      : data.get("Version"),
                "name"         : data.get("Name"),
                "storage_size" : data.get("TotalDiskSizeIsMB"),
            }
        return {"online": False, "error": f"HTTP {resp.status_code}"}
    except Exception as exc:
        return {"online": False, "error": str(exc)}