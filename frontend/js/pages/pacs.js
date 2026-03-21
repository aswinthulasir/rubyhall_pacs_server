/**
 * pages/pacs.js — Show PACS Page
 * Lists ALL uploaded studies from ALL users with premium dark card design
 */

async function renderPacsPage(container) {
  container.innerHTML = `
    ${renderNavbar()}
    <div class="page-content">
      <div class="page-title">🏥 PACS — All Studies</div>
      <div id="pacs-container">
        <div style="text-align:center; padding: 2rem;">
          <div class="spinner spinner-dark" style="width:32px;height:32px;border-width:3px;margin: 0 auto 0.75rem;"></div>
          <div class="text-muted">Loading all PACS studies…</div>
        </div>
      </div>
    </div>
  `;

  await loadAllPacsStudies();
}

async function loadAllPacsStudies() {
  const container = document.getElementById('pacs-container');
  try {
    const studies = await apiGetAllStudies();
    if (studies.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">📭</div>
          <h4>No Studies in PACS</h4>
          <p>No studies have been uploaded yet.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div class="text-muted" style="margin-bottom:1rem; font-size:0.9rem;">
        Showing <strong>${studies.length}</strong> study/studies from all users
      </div>
      <div class="study-grid">
        ${studies.map(s => renderPacsStudyCard(s)).join('')}
      </div>
    `;

    // Load authenticated images
    loadAllAuthImages(container);

  } catch (err) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">⚠️</div>
        <h4>Error</h4>
        <p>${escapeHtml(err.message)}</p>
      </div>
    `;
  }
}

function renderPacsStudyCard(study) {
  const pdfSection = study.pdf_reports && study.pdf_reports.length > 0
    ? `<div class="pacs-card-pdf">
         <div class="pacs-card-pdf-title">📄 Reports (${study.pdf_reports.length})</div>
         ${study.pdf_reports.map(r => `
           <div class="pacs-card-pdf-item">
             <span>📄 ${escapeHtml(r.file_name) || 'report.pdf'}${r.notes ? ` — <em>${escapeHtml(r.notes)}</em>` : ''}</span>
             <span class="pacs-card-pdf-actions">
               <button class="btn btn-blue btn-sm" style="padding:0.2rem 0.6rem; font-size:0.72rem;" title="View PDF"
                       onclick="event.preventDefault(); event.stopPropagation(); openAuthPdf('${r.file_url}', '${escapeHtml(r.file_name) || 'report.pdf'}')">
                 👁️ View
               </button>
               <button class="btn btn-outline btn-sm" style="padding:0.2rem 0.5rem; font-size:0.72rem;" title="Download PDF"
                       onclick="event.preventDefault(); event.stopPropagation(); downloadAuthFile('${r.file_url}', '${escapeHtml(r.file_name) || 'report.pdf'}')">
                 ⬇️
               </button>
             </span>
           </div>
         `).join('')}
       </div>`
    : '';

  // Doctor-only upload report button
  const user = getUser();
  const isDoctor = user && user.role && (user.role.id === 2 || user.role.name === 'doctor');
  const uploadBtn = isDoctor
    ? `<button class="btn btn-sm" style="background:linear-gradient(135deg,#7c3aed,#a855f7);color:#fff;padding:0.25rem 0.65rem;font-size:0.78rem;border:none;border-radius:6px;cursor:pointer;"
               onclick="event.preventDefault(); event.stopPropagation(); showPacsUploadPdfModal(${study.id})"
               title="Upload PDF report">📎 Upload Report</button>`
    : '';

  return `
    <a href="#study/${study.id}" class="pacs-card" style="text-decoration:none; color:inherit;">
      <div class="pacs-card-thumb">
        ${study.thumbnail_url
      ? `<img data-auth-src="${study.thumbnail_url}" alt="Thumb" class="auth-img"
                   onerror="this.parentElement.innerHTML='<div class=\\'thumb-placeholder\\'>🩻</div>'">` 
      : '<div class="thumb-placeholder">🩻</div>'}
      </div>
      <div class="pacs-card-body">
        <div class="pacs-card-patient">${escapeHtml(study.patient_name) || 'Unknown Patient'}</div>

        <div class="pacs-card-row">
          <span class="icon">👤</span>
          <span>${escapeHtml(study.patient_age) || '—'} · ${escapeHtml(study.patient_sex) || '—'}</span>
          <span class="badge badge-blue" style="margin-left:auto;">${escapeHtml(study.modality) || '—'}</span>
        </div>

        <div class="pacs-card-row">
          <span class="icon">📁</span>
          <span>${study.num_files || 1} file(s) · ${formatFileSize(study.file_size_kb)}</span>
        </div>

        <div class="pacs-card-row">
          <span class="icon">📅</span>
          <span>${formatDateTime(study.upload_date)}</span>
        </div>

        <div class="pacs-card-row">
          <span class="icon">👤</span>
          <span style="color: var(--purple);">Uploaded by: <strong>${escapeHtml(study.uploader_name) || 'Unknown'}</strong></span>
        </div>

        <div class="pacs-card-badges">
          ${study.sent_to_orthanc
      ? '<span class="badge badge-green">✓ Sent to Orthanc</span>'
      : '<span class="badge badge-gray">Not sent</span>'}
          <span class="badge ${study.status === 'CONFIRMED' ? 'badge-green' : 'badge-yellow'}">${study.status}</span>
        </div>
      </div>
      ${pdfSection}
      <div class="pacs-card-footer">
        <span class="text-muted text-sm">Study #${study.id}</span>
        <span style="display:flex; gap:0.5rem; align-items:center;">
          ${uploadBtn}
          <button class="btn btn-blue btn-sm" style="padding:0.25rem 0.6rem; font-size:0.78rem;"
                  onclick="event.preventDefault(); event.stopPropagation(); openInRadiant(${study.id}, event)"
                  title="Open in RadiAnt">🩻 RadiAnt</button>
          <span class="btn btn-blue btn-sm" style="pointer-events:none;">View Details →</span>
        </span>
      </div>
    </a>
  `;
}

/* ── Doctor PDF Upload Modal ─────────────────────────────────────────────── */

function showPacsUploadPdfModal(studyId) {
  document.getElementById('pacs-pdf-modal')?.remove();

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.id = 'pacs-pdf-modal';
  overlay.innerHTML = `
    <div class="modal-box" style="max-width:460px;">
      <h3 style="margin-bottom:1.2rem; font-size:1.1rem;">
        📎 Upload Report — Study #${studyId}
      </h3>
      <form id="pacs-pdf-form">
        <div class="form-group" style="margin-bottom:1rem;">
          <label class="form-label">PDF File <span style="color:var(--red);">*</span></label>
          <input type="file" id="pacs-pdf-file" accept=".pdf,application/pdf"
                 class="form-input" required style="padding:0.4rem; cursor:pointer;">
        </div>
        <div class="form-group" style="margin-bottom:1.4rem;">
          <label class="form-label">Notes (optional)</label>
          <input type="text" id="pacs-pdf-notes" class="form-input"
                 placeholder="e.g. Radiology Report" maxlength="200">
        </div>
        <div style="display:flex; gap:0.75rem; justify-content:flex-end;">
          <button type="button" class="btn btn-outline"
                  onclick="document.getElementById('pacs-pdf-modal').remove()">
            Cancel
          </button>
          <button type="submit" class="btn btn-blue" id="pacs-pdf-submit">
            📤 Upload Report
          </button>
        </div>
      </form>
    </div>
  `;

  document.body.appendChild(overlay);
  overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });

  document.getElementById('pacs-pdf-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const fileInput = document.getElementById('pacs-pdf-file');
    const notes = document.getElementById('pacs-pdf-notes').value.trim();
    const submitBtn = document.getElementById('pacs-pdf-submit');

    if (!fileInput.files.length) { showToast('Please select a PDF file', 'warning'); return; }
    const file = fileInput.files[0];
    if (file.type !== 'application/pdf' && !file.name.endsWith('.pdf')) {
      showToast('Please select a valid PDF file', 'error'); return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = 'Uploading…';
    try {
      await apiUploadPdf(studyId, file, notes);
      showToast('✓ Report uploaded successfully', 'success');
      overlay.remove();
      loadAllPacsStudies();
    } catch (err) {
      showToast(`✕ ${err.message}`, 'error');
      submitBtn.disabled = false;
      submitBtn.textContent = '📤 Upload Report';
    }
  });
}
