/**
 * pages/study_detail.js — Study Detail Page
 */

async function renderStudyDetailPage(container, studyId) {
  container.innerHTML = `
    ${renderNavbar()}
    <div class="page-content">
      <div style="text-align:center; padding:3rem;">
        <div class="spinner spinner-dark" style="width:40px;height:40px;border-width:3px;margin:0 auto 1rem;"></div>
        <div class="text-muted">Loading study details…</div>
      </div>
    </div>
  `;

  try {
    const study = await apiGetStudy(studyId);
    renderStudyDetail(container, study);
  } catch (err) {
    if (err.message === 'Session expired') {
      showToast('Session expired. Please log in again.', 'error');
      clearToken();
      navigateTo('login');
      router();
      return;
    }
    container.innerHTML = `
      ${renderNavbar()}
      <div class="page-content">
        <a href="#dashboard" class="back-link">← Back to Dashboard</a>
        <div class="empty-state">
          <div class="empty-icon">⚠️</div>
          <h4>Study Not Found</h4>
          <p>${escapeHtml(err.message)}</p>
        </div>
      </div>
    `;
  }
}

function renderStudyDetail(container, study) {
  const user = getUser();
  const isDoctor = user && user.role_id === 2;

  container.innerHTML = `
    ${renderNavbar()}
    <div class="page-content">
      <a href="#dashboard" class="back-link" onclick="event.preventDefault(); navigateTo('dashboard'); router();">
        ← Back to Dashboard
      </a>

      <div class="page-title">
        ${escapeHtml(study.modality) || ''} ${escapeHtml(study.body_part) || 'Study'} — ${escapeHtml(study.patient_name) || 'Unknown'}
      </div>

      <div class="card" style="margin-bottom: 1.5rem;">
        <div class="card-body">
          <div class="preview-layout">
            <div class="preview-thumbnail">
              ${study.thumbnail_url
                ? `<img data-auth-src="${study.thumbnail_url}" alt="DICOM Thumbnail" class="auth-img"
                         onerror="this.parentElement.innerHTML='<div class=\\'thumb-placeholder\\'>🩻</div>'">`
                : '<div class="thumb-placeholder">🩻</div>'}
            </div>
            <div>
              <table class="meta-table">
                <tr><td>Patient Name</td><td>${escapeHtml(study.patient_name) || '—'}</td></tr>
                <tr><td>MR Number</td><td><strong>${escapeHtml(study.mr_number)}</strong></td></tr>
                <tr><td>Age / DOB</td><td>${escapeHtml(study.patient_age) || '—'} / ${escapeHtml(study.patient_dob) || '—'}</td></tr>
                <tr><td>Sex</td><td>${escapeHtml(study.patient_sex) || '—'}</td></tr>
                <tr><td>Modality</td><td><span class="badge badge-blue">${escapeHtml(study.modality) || '—'}</span></td></tr>
                <tr><td>Body Part</td><td>${escapeHtml(study.body_part) || '—'}</td></tr>
                <tr><td>Study Date</td><td>${formatDate(study.study_date)}</td></tr>
                <tr><td>Description</td><td>${escapeHtml(study.study_description) || '—'}</td></tr>
                <tr><td>Study UID</td><td style="word-break:break-all; font-size:0.82rem;">${escapeHtml(study.study_instance_uid) || '—'}</td></tr>
                <tr><td>File</td><td>${escapeHtml(study.file_name) || '—'} (${formatFileSize(study.file_size_kb)})</td></tr>
                <tr><td>Upload Date</td><td>${formatDate(study.upload_date)}</td></tr>
                <tr><td>Status</td><td>
                  <span class="badge ${study.status === 'CONFIRMED' ? 'badge-green' : 'badge-yellow'}">
                    ${study.status}
                  </span>
                </td></tr>
                <tr><td>Orthanc</td><td>
                  ${study.sent_to_orthanc
                    ? `<span class="badge badge-green">✓ Sent</span>
                       <span class="text-sm text-muted" style="margin-left:0.5rem;">${escapeHtml(study.orthanc_study_id) || ''}</span>`
                    : '<span class="badge badge-gray">Not sent</span>'}
                </td></tr>
              </table>
            </div>
          </div>
        </div>

        <!-- PDF Reports Section -->
        ${study.pdf_reports && study.pdf_reports.length > 0 ? `
          <div style="border-top:1px solid var(--border-color); padding: 1.25rem 1.5rem;">
            <h4 style="font-size:0.95rem; font-weight:700; margin-bottom:0.75rem;">
              📄 PDF Reports (${study.pdf_reports.length})
            </h4>
            <ul class="pdf-list">
              ${study.pdf_reports.map(r => `
                <li>
                  <span class="pdf-name">📄 ${escapeHtml(r.file_name) || 'report.pdf'}
                    ${r.notes ? `<span class="text-muted text-sm">— ${escapeHtml(r.notes)}</span>` : ''}
                  </span>
                </li>
              `).join('')}
            </ul>
          </div>
        ` : ''}

        <!-- Doctor: Upload PDF -->
        ${isDoctor ? `
          <div style="border-top:1px solid var(--border-color); padding: 1.25rem 1.5rem; background: #FEFCE8;">
            <h4 style="font-size:0.95rem; font-weight:700; margin-bottom:0.75rem;">
              🩺 Attach PDF Report
            </h4>
            <div style="display:flex; gap:1rem; align-items:flex-end; flex-wrap:wrap;">
              <div class="form-group" style="margin-bottom:0; flex:1; min-width:200px;">
                <label>PDF File</label>
                <input type="file" class="form-control" id="detail-pdf-file" accept=".pdf">
              </div>
              <div class="form-group" style="margin-bottom:0; flex:1; min-width:200px;">
                <label>Notes</label>
                <input type="text" class="form-control" id="detail-pdf-notes" placeholder="Optional notes">
              </div>
              <button class="btn btn-green btn-sm" id="btn-attach-pdf"
                      onclick="attachPdfToStudy(${study.id})">
                📎 Attach
              </button>
            </div>
          </div>
        ` : ''}

        <!-- Action Bar -->
        <div class="action-bar">
          <button class="btn btn-green" id="btn-send-orthanc"
                  onclick="sendStudyToOrthanc(${study.id})"
                  ${study.sent_to_orthanc ? 'disabled title="Already sent"' : ''}>
            🟢 ${study.sent_to_orthanc ? 'Sent to Orthanc' : 'Send to Orthanc'}
          </button>
          <button class="btn btn-blue" onclick="downloadAuthFile('/dicom/download/${study.id}', '${escapeHtml(study.file_name) || 'study.dcm'}')"
                  title="Save the file, then drag and drop it onto RadiAnt Viewer">
            🔵 Download for RadiAnt
          </button>
          <button class="btn btn-red" id="btn-delete-study"
                  onclick="confirmDeleteStudy(${study.id})">
            🔴 Delete
          </button>
        </div>
      </div>
    </div>
  `;

  // Load authenticated thumbnail
  loadAllAuthImages(container);
}

/* ── Actions ───────────────────────────────────────────────────────────── */
async function sendStudyToOrthanc(studyId) {
  const btn = document.getElementById('btn-send-orthanc');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Sending…';

  try {
    const result = await apiSendToOrthanc(studyId);
    if (result.success) {
      showToast(`Sent to Orthanc! Study ID: ${result.orthanc_study_id || 'OK'}`, 'success');
      // Reload the page
      renderStudyDetailPage(document.getElementById('app'), studyId);
    } else {
      showToast(result.message || 'Send failed', 'error');
      btn.disabled = false;
      btn.innerHTML = '🟢 Send to Orthanc';
    }
  } catch (err) {
    showToast(err.message, 'error');
    btn.disabled = false;
    btn.innerHTML = '🟢 Send to Orthanc';
  }
}

function confirmDeleteStudy(studyId) {
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.id = 'delete-modal';
  overlay.innerHTML = `
    <div class="modal-box">
      <h3>🔴 Delete Study</h3>
      <p>Are you sure you want to delete this study? This will remove the DICOM file from disk. This action cannot be undone.</p>
      <div class="modal-actions">
        <button class="btn btn-outline" onclick="document.getElementById('delete-modal').remove()">
          Cancel
        </button>
        <button class="btn btn-red" id="btn-confirm-delete" onclick="executeDeleteStudy(${studyId})">
          Delete
        </button>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);
}

async function executeDeleteStudy(studyId) {
  const btn = document.getElementById('btn-confirm-delete');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Deleting…';

  try {
    await apiDeleteStudy(studyId);
    document.getElementById('delete-modal')?.remove();
    showToast('Study deleted successfully', 'success');
    navigateTo('dashboard');
    router();
  } catch (err) {
    showToast(err.message, 'error');
    btn.disabled = false;
    btn.innerHTML = 'Delete';
  }
}

async function attachPdfToStudy(studyId) {
  const fileInput = document.getElementById('detail-pdf-file');
  const notesInput = document.getElementById('detail-pdf-notes');
  const btn = document.getElementById('btn-attach-pdf');

  if (!fileInput.files[0]) {
    showToast('Please select a PDF file', 'warning');
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>';

  try {
    await apiUploadPdf(studyId, fileInput.files[0], notesInput.value);
    showToast('PDF report attached ✓', 'success');
    renderStudyDetailPage(document.getElementById('app'), studyId);
  } catch (err) {
    showToast(err.message, 'error');
    btn.disabled = false;
    btn.innerHTML = '📎 Attach';
  }
}
