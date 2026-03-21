/**
 * api.js — Centralised API client for Hospital PACS
 * Handles auth token storage and all HTTP requests.
 */

const API_BASE = window.location.origin;

/* ── Token helpers ──────────────────────────────────────────────────── */
function getToken() {
  return localStorage.getItem('pacs_token');
}

function setToken(token) {
  localStorage.setItem('pacs_token', token);
}

function clearToken() {
  localStorage.removeItem('pacs_token');
  localStorage.removeItem('pacs_user');
}

function getUser() {
  try {
    return JSON.parse(localStorage.getItem('pacs_user'));
  } catch {
    return null;
  }
}

function setUser(user) {
  localStorage.setItem('pacs_user', JSON.stringify(user));
}

function isLoggedIn() {
  return !!getToken();
}

/* ── Generic fetch wrapper ──────────────────────────────────────────── */
async function apiFetch(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const headers = options.headers || {};

  const token = getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Don't set Content-Type for FormData (browser sets it with boundary)
  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const resp = await fetch(url, { ...options, headers });
  return resp;
}

/* ═══════════════════════════════════════════════════════════════════════
   AUTH
   ═══════════════════════════════════════════════════════════════════════ */

async function apiLogin(username, password) {
  const form = new URLSearchParams();
  form.append('username', username);
  form.append('password', password);

  const resp = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form,
  });

  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.detail || 'Login failed');
  }

  const data = await resp.json();
  setToken(data.access_token);
  return data;
}

async function apiRegister(payload) {
  const resp = await apiFetch('/auth/register', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.detail || 'Registration failed');
  }
  return resp.json();
}

async function apiGetMe() {
  const resp = await apiFetch('/auth/me');
  if (!resp.ok) throw new Error('Session expired');
  return resp.json();
}

/* ═══════════════════════════════════════════════════════════════════════
   USERS / ROLES
   ═══════════════════════════════════════════════════════════════════════ */

async function apiGetRoles() {
  const resp = await apiFetch('/users/roles');
  if (!resp.ok) throw new Error('Could not load roles');
  return resp.json();
}

/* ═══════════════════════════════════════════════════════════════════════
   DICOM STUDIES
   ═══════════════════════════════════════════════════════════════════════ */

async function apiUploadDicomMulti(dicomFiles) {
  const form = new FormData();
  
  // Handle single file or array/FileList
  if (dicomFiles instanceof FileList || Array.isArray(dicomFiles)) {
    for (const file of dicomFiles) {
      form.append('dicom_files', file);
    }
  } else {
    form.append('dicom_files', dicomFiles);
  }

  const resp = await apiFetch('/dicom/upload-multi', {
    method: 'POST',
    body: form,
  });

  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.detail || 'Upload failed');
  }
  return resp.json();
}

async function apiConfirmStudy(studyId, mrNumber) {
  const resp = await apiFetch(`/dicom/confirm/${studyId}`, {
    method: 'POST',
    body: JSON.stringify({ mr_number: mrNumber }),
  });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.detail || 'Confirm failed');
  }
  return resp.json();
}

async function apiConfirmBatch() {
  const resp = await apiFetch('/dicom/confirm-batch', {
    method: 'POST',
  });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.detail || 'Batch confirm failed');
  }
  return resp.json();
}

async function apiGetStudies() {
  const resp = await apiFetch('/dicom/studies');
  if (!resp.ok) throw new Error('Could not load studies');
  return resp.json();
}

async function apiGetAllStudies() {
  const resp = await apiFetch('/dicom/all-studies');
  if (!resp.ok) throw new Error('Could not load PACS studies');
  return resp.json();
}

async function apiGetStudy(id) {
  const resp = await apiFetch(`/dicom/studies/${id}`);
  if (!resp.ok) throw new Error('Study not found');
  return resp.json();
}

async function apiDeleteStudy(id) {
  const resp = await apiFetch(`/dicom/studies/${id}`, { method: 'DELETE' });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.detail || 'Delete failed');
  }
  return resp.json();
}

function getThumbnailUrl(studyId) {
  return `${API_BASE}/dicom/thumbnail/${studyId}`;
}

function getDownloadUrl(studyId) {
  return `${API_BASE}/dicom/download/${studyId}`;
}

async function apiUploadPdf(studyId, pdfFile, notes) {
  const form = new FormData();
  form.append('pdf_file', pdfFile);
  form.append('notes', notes || '');

  const resp = await apiFetch(`/dicom/upload-pdf/${studyId}`, {
    method: 'POST',
    body: form,
  });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.detail || 'PDF upload failed');
  }
  return resp.json();
}

/* ═══════════════════════════════════════════════════════════════════════
   RADIANT VIEWER (C-STORE)
   ═══════════════════════════════════════════════════════════════════════ */

async function apiOpenInRadiant(studyId) {
  const resp = await apiFetch(`/dicom/open-radiant/${studyId}`, { method: 'POST' });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.detail || 'Failed to send to RadiAnt');
  }
  return resp.json();
}

/* ═══════════════════════════════════════════════════════════════════════
   ORTHANC
   ═══════════════════════════════════════════════════════════════════════ */

async function apiOrthancHealth() {
  const resp = await apiFetch('/orthanc/health');
  if (!resp.ok) throw new Error('Orthanc offline');
  return resp.json();
}

async function apiSendToOrthanc(studyId) {
  const resp = await apiFetch(`/orthanc/send/${studyId}`, { method: 'POST' });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.detail || 'Send failed');
  }
  return resp.json();
}

async function apiGetOrthancStudies() {
  const resp = await apiFetch('/orthanc/studies');
  if (!resp.ok) throw new Error('Could not load Orthanc studies');
  return resp.json();
}

async function apiImportFromOrthanc(orthancId) {
  const resp = await apiFetch(`/orthanc/import/${orthancId}`, { method: 'POST' });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || 'Import failed');
  }
  return resp.json();
}

/* ═══════════════════════════════════════════════════════════════════════
   ORTHANC SERVER CREDENTIALS
   ═══════════════════════════════════════════════════════════════════════ */

async function apiGetOrthancServers() {
  const resp = await apiFetch('/orthanc/servers');
  if (!resp.ok) throw new Error('Could not load servers');
  return resp.json();
}

async function apiCreateOrthancServer(payload) {
  const resp = await apiFetch('/orthanc/servers', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.detail || 'Failed to add server');
  }
  return resp.json();
}

async function apiUpdateOrthancServer(serverId, payload) {
  const resp = await apiFetch(`/orthanc/servers/${serverId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.detail || 'Failed to update server');
  }
  return resp.json();
}

async function apiDeleteOrthancServer(serverId) {
  const resp = await apiFetch(`/orthanc/servers/${serverId}`, { method: 'DELETE' });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.detail || 'Failed to delete server');
  }
  return resp.json();
}

async function apiTestOrthancServer(serverId) {
  const resp = await apiFetch(`/orthanc/servers/${serverId}/test`, { method: 'POST' });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.detail || 'Test failed');
  }
  return resp.json();
}

async function apiActivateOrthancServer(serverId) {
  const resp = await apiFetch(`/orthanc/servers/${serverId}/activate`, { method: 'POST' });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.detail || 'Activation failed');
  }
  return resp.json();
}

/* ═══════════════════════════════════════════════════════════════════════
   AUTHENTICATED IMAGE / FILE HELPERS
   ═══════════════════════════════════════════════════════════════════════ */

/**
 * Load an image via fetch with auth headers, then set the img src to a blob URL.
 */
async function loadAuthImage(imgElement, url) {
  try {
    const resp = await apiFetch(url);
    if (!resp.ok) throw new Error('Image load failed');
    const blob = await resp.blob();
    imgElement.src = URL.createObjectURL(blob);
  } catch {
    imgElement.onerror?.();
  }
}

/**
 * Download a file with authentication, then trigger browser download.
 */
async function downloadAuthFile(url, filename) {
  try {
    const resp = await apiFetch(url);
    if (!resp.ok) throw new Error('Download failed');
    const blob = await resp.blob();
    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = blobUrl;
    a.download = filename || 'download';
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      URL.revokeObjectURL(blobUrl);
      a.remove();
    }, 100);
  } catch (err) {
    showToast(err.message || 'Download failed', 'error');
  }
}

/**
 * Open an authenticated PDF in a new browser tab.
 */
async function openAuthPdf(url, filename) {
  try {
    const resp = await apiFetch(url);
    if (!resp.ok) throw new Error('Could not load PDF');
    const blob = await resp.blob();
    const blobUrl = URL.createObjectURL(new Blob([blob], { type: 'application/pdf' }));
    const newTab = window.open(blobUrl, '_blank');
    if (!newTab) {
      downloadAuthFile(url, filename || 'report.pdf');
    }
  } catch (err) {
    showToast(err.message || 'Could not open PDF', 'error');
  }
}
