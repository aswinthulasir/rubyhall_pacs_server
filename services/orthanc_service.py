"""
services/orthanc_service.py — Wrapper around Orthanc's REST API.

Now supports **dynamic credentials** so different users can connect to
different Orthanc servers. Falls back to the config-level defaults when
no explicit credentials are provided.
"""

import logging
from typing import List, Optional, Dict, Any, Tuple

import httpx

import config

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


# ══════════════════════════════════════════════════════════════════════════════
#  Internal helpers — now accept dynamic connection info
# ══════════════════════════════════════════════════════════════════════════════

def _build_auth(creds: Optional[Dict] = None):
    if creds:
        return (creds.get("username", ""), creds.get("password", ""))
    return (config.ORTHANC_USERNAME, config.ORTHANC_PASSWORD)


def _build_url(path: str, creds: Optional[Dict] = None) -> str:
    base = creds["url"] if creds else config.ORTHANC_URL
    return f"{base.rstrip('/')}{path}"


def _get(path: str, creds: Optional[Dict] = None) -> httpx.Response:
    return httpx.get(_build_url(path, creds), auth=_build_auth(creds), timeout=_TIMEOUT)


def _post_bytes(path: str, data: bytes, content_type: str = "application/dicom",
                creds: Optional[Dict] = None) -> httpx.Response:
    return httpx.post(
        _build_url(path, creds),
        content=data,
        headers={"Content-Type": content_type},
        auth=_build_auth(creds),
        timeout=_TIMEOUT,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  Public API
# ══════════════════════════════════════════════════════════════════════════════

def upload_to_orthanc(
    dicom_file_path: str,
    creds: Optional[Dict] = None,
) -> Tuple[bool, str, Optional[str], Optional[str]]:
    """
    Upload a local DICOM file to Orthanc.

    Returns:
        (success, message, orthanc_instance_id, orthanc_study_id)
    """
    try:
        with open(dicom_file_path, "rb") as f:
            dicom_bytes = f.read()

        resp = _post_bytes("/instances", dicom_bytes, creds=creds)

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
        base = creds["url"] if creds else config.ORTHANC_URL
        msg = "Cannot connect to Orthanc at " + base
        logger.error(msg)
        return False, msg, None, None
    except Exception as exc:
        logger.exception("Unexpected error during Orthanc upload")
        return False, str(exc), None, None


def list_orthanc_studies(
    creds: Optional[Dict] = None,
) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """
    Retrieve all studies currently stored in Orthanc.
    """
    try:
        resp = _get("/studies", creds=creds)
        if resp.status_code != 200:
            return False, f"Orthanc returned HTTP {resp.status_code}", []

        study_ids: List[str] = resp.json()
        studies = []

        for sid in study_ids:
            detail_resp = _get(f"/studies/{sid}", creds=creds)
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
        base = creds["url"] if creds else config.ORTHANC_URL
        msg = "Cannot connect to Orthanc at " + base
        logger.error(msg)
        return False, msg, []
    except Exception as exc:
        logger.exception("Error fetching Orthanc studies")
        return False, str(exc), []


def get_orthanc_study_detail(
    orthanc_study_id: str,
    creds: Optional[Dict] = None,
) -> Tuple[bool, str, Optional[Dict]]:
    """Retrieve full metadata for a single study from Orthanc."""
    try:
        resp = _get(f"/studies/{orthanc_study_id}", creds=creds)
        if resp.status_code == 200:
            return True, "OK", resp.json()
        return False, f"HTTP {resp.status_code}", None
    except httpx.ConnectError:
        return False, "Cannot connect to Orthanc", None
    except Exception as exc:
        return False, str(exc), None


def download_dicom_from_orthanc(
    orthanc_instance_id: str,
    creds: Optional[Dict] = None,
) -> Tuple[bool, str, Optional[bytes]]:
    """Download the raw DICOM bytes for a specific instance from Orthanc."""
    try:
        resp = _get(f"/instances/{orthanc_instance_id}/file", creds=creds)
        if resp.status_code == 200:
            return True, "OK", resp.content
        return False, f"HTTP {resp.status_code}", None
    except httpx.ConnectError:
        return False, "Cannot connect to Orthanc", None
    except Exception as exc:
        return False, str(exc), None


def list_study_instances(
    orthanc_study_id: str,
    creds: Optional[Dict] = None,
) -> Tuple[bool, str, List[str]]:
    """Return the list of instance IDs belonging to an Orthanc study."""
    try:
        resp = _get(f"/studies/{orthanc_study_id}", creds=creds)
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}", []
        data = resp.json()
        # Orthanc nests instances inside Series
        instance_ids = []
        for series_id in data.get("Series", []):
            sr = _get(f"/series/{series_id}", creds=creds)
            if sr.status_code == 200:
                instance_ids.extend(sr.json().get("Instances", []))
        return True, "OK", instance_ids
    except Exception as exc:
        return False, str(exc), []


def download_instance_file(
    instance_id: str,
    creds: Optional[Dict] = None,
) -> Tuple[bool, Optional[bytes]]:
    """Download one DICOM instance file from Orthanc. Returns (success, bytes)."""
    try:
        resp = _get(f"/instances/{instance_id}/file", creds=creds)
        if resp.status_code == 200:
            return True, resp.content
        return False, None
    except Exception:
        return False, None


def check_orthanc_health(creds: Optional[Dict] = None) -> Dict[str, Any]:
    """Check if Orthanc is reachable and return its system information."""
    try:
        resp = _get("/system", creds=creds)
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