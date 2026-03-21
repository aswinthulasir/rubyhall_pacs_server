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
        <span class="btn btn-blue btn-sm" style="pointer-events:none;">View Details →</span>
      </div>
    </a>
  `;
}
