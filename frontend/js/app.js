/**
 * app.js — SPA router & shared utilities for Hospital PACS
 */

/* ── Toast notifications ───────────────────────────────────────────────── */
function showToast(message, type = 'info') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${icons[type] || ''}</span> ${message}`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(40px)';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

/* ── Navigation / SPA Router ───────────────────────────────────────────── */
function navigateTo(page) {
  window.location.hash = page;
}

function getCurrentPage() {
  return window.location.hash.replace('#', '') || 'login';
}

/* ── Auth guard ─────────────────────────────────────────────────────────── */
function requireAuth() {
  if (!isLoggedIn()) {
    navigateTo('login');
    return false;
  }
  return true;
}

/* ── Build navbar ──────────────────────────────────────────────────────── */
function renderNavbar() {
  const user = getUser();
  if (!user) return '';

  const roleName = user.role ? user.role.name : 'User';
  const page = getCurrentPage();

  return `
    <nav class="pacs-navbar" id="main-navbar">
      <div class="brand">
        <span class="brand-icon">🏥</span>
        <span>Hospital PACS</span>
      </div>
      <div class="nav-links">
        <a href="#dashboard" class="${page === 'dashboard' ? 'active' : ''}">📊 Dashboard</a>
        <a href="#pacs" class="${page === 'pacs' ? 'active' : ''}">🏥 Show PACS</a>
        <a href="#orthanc" class="${page === 'orthanc' ? 'active' : ''}">🖥️ Orthanc</a>
      </div>
      <div class="user-area">
        <div class="user-info">
          <div class="user-name">${user.full_name}</div>
          <div class="user-role">${roleName}</div>
        </div>
        <button class="btn btn-red btn-sm" onclick="logout()" id="btn-logout">Logout</button>
      </div>
    </nav>
  `;
}

/* ── Logout ─────────────────────────────────────────────────────────────── */
function logout() {
  clearToken();
  navigateTo('login');
  router();
}

/* ── Helpers ────────────────────────────────────────────────────────────── */
function formatDate(dateStr) {
  if (!dateStr) return '—';
  // Handle YYYYMMDD format
  if (/^\d{8}$/.test(dateStr)) {
    return `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`;
  }
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-IN', { year: 'numeric', month: 'short', day: 'numeric' });
  } catch {
    return dateStr;
  }
}

function formatDateTime(dateStr) {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr);
    return d.toLocaleString('en-IN', {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  } catch {
    return dateStr;
  }
}

function formatFileSize(kb) {
  if (!kb) return '—';
  if (kb > 1024) return `${(kb / 1024).toFixed(2)} MB`;
  return `${kb.toFixed(1)} KB`;
}

function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/* ── Open in RadiAnt (C-STORE push) ────────────────────────────────────── */
async function openInRadiant(studyId, event) {
  if (event) { event.preventDefault(); event.stopPropagation(); }
  showToast('Sending to RadiAnt…', 'info');
  try {
    const res = await apiOpenInRadiant(studyId);
    showToast(`✓ ${res.message}`, 'success');
  } catch (err) {
    showToast(`✕ RadiAnt: ${err.message}`, 'error');
  }
}

/* ── Main SPA router ────────────────────────────────────────────────────── */
async function router() {
  const app = document.getElementById('app');
  const page = getCurrentPage();

  // Extract study ID from "study/123"
  const studyMatch = page.match(/^study\/(\d+)$/);

  if (page === 'login') {
    renderLoginPage(app);
  } else if (page === 'register') {
    renderRegisterPage(app);
  } else if (page === 'dashboard') {
    if (!requireAuth()) return;
    renderDashboardPage(app);
  } else if (studyMatch) {
    if (!requireAuth()) return;
    renderStudyDetailPage(app, parseInt(studyMatch[1]));
  } else if (page === 'pacs') {
    if (!requireAuth()) return;
    renderPacsPage(app);
  } else if (page === 'orthanc') {
    if (!requireAuth()) return;
    renderOrthancPage(app);
  } else {
    // Default: redirect to login or dashboard
    if (isLoggedIn()) {
      navigateTo('dashboard');
    } else {
      navigateTo('login');
    }
  }
}

/* ── Boot ────────────────────────────────────────────────────────────────── */
window.addEventListener('hashchange', router);
window.addEventListener('DOMContentLoaded', router);
