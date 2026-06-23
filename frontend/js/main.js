// ===========================
//  HabboBots - Main JS
// ===========================

// Tab switching (login <-> register)
function switchTab(tab) {
  document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.auth-form').forEach(f => f.classList.remove('active'));
  document.querySelector(`[data-tab="${tab}"]`).classList.add('active');
  document.querySelector(`#form-${tab}`).classList.add('active');
}

// Password visibility toggle
function togglePassword(inputId) {
  const input = document.getElementById(inputId);
  const icon  = document.getElementById(inputId + '-icon');
  if (input.type === 'password') {
    input.type = 'text';
    if (icon) icon.innerHTML = eyeOffIcon();
  } else {
    input.type = 'password';
    if (icon) icon.innerHTML = eyeIcon();
  }
}

function eyeIcon() {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`;
}
function eyeOffIcon() {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>`;
}

// Username availability check (mock)
function checkUsername(val) {
  const status = document.getElementById('username-status');
  if (!status) return;
  if (val.length < 3) { status.textContent = ''; return; }
  setTimeout(() => {
    const taken = ['admin', 'habbo', 'root', 'test'];
    if (taken.includes(val.toLowerCase())) {
      status.innerHTML = `<span style="color:var(--danger)">✗ Usuario no disponible</span>`;
    } else {
      status.innerHTML = `<span style="color:var(--success)">✓ Disponible</span>`;
    }
  }, 400);
}

// Habbo avatar loader
function loadHabboAvatar(look, hotel = 'com') {
  const base = hotel === 'es'
    ? 'https://www.habbo.es/habbo-imaging/avatarimage'
    : 'https://sandbox.habbo.com/habbo-imaging/avatarimage';
  return `${base}?figure=${look}&direction=3&head_direction=3&gesture=nrm&size=l`;
}

// Copy to clipboard
function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    showToast('Copiado al portapapeles', 'success');
  });
}

// Toast notifications
function showToast(msg, type = 'info') {
  const container = document.getElementById('toast-container') || createToastContainer();
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span>${msg}</span>
    <button onclick="this.parentElement.remove()">×</button>
  `;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3500);
}

function createToastContainer() {
  const div = document.createElement('div');
  div.id = 'toast-container';
  div.style.cssText = `
    position:fixed; bottom:1.5rem; right:1.5rem; z-index:9999;
    display:flex; flex-direction:column; gap:.5rem;
  `;
  document.body.appendChild(div);
  return div;
}

// Mobile sidebar toggle
function toggleSidebar() {
  const sidebar = document.querySelector('.sidebar');
  if (sidebar) sidebar.classList.toggle('open');
}

// On DOM ready
document.addEventListener('DOMContentLoaded', () => {
  // Add toast styles dynamically
  const style = document.createElement('style');
  style.textContent = `
    .toast {
      display:flex; align-items:center; justify-content:space-between; gap:1rem;
      padding:.75rem 1.2rem; border-radius:10px; min-width:260px;
      backdrop-filter:blur(12px); font-family:'Rajdhani',sans-serif;
      font-size:.9rem; font-weight:500; animation:slideIn .3s ease;
    }
    .toast-info    { background:rgba(0,195,255,.15); border:1px solid rgba(0,195,255,.3); color:#00c3ff; }
    .toast-success { background:rgba(0,255,163,.15); border:1px solid rgba(0,255,163,.3); color:#00ffa3; }
    .toast-warning { background:rgba(255,190,0,.15);  border:1px solid rgba(255,190,0,.3);  color:#ffbe00; }
    .toast-danger  { background:rgba(255,51,102,.15); border:1px solid rgba(255,51,102,.3); color:#ff3366; }
    .toast button  { background:none; border:none; cursor:pointer; color:inherit; font-size:1.1rem; opacity:.6; }
    .toast button:hover { opacity:1; }
    @keyframes slideIn { from { transform:translateX(100%); opacity:0; } to { transform:translateX(0); opacity:1; } }

    /* Mobile sidebar */
    @media (max-width:768px) {
      .sidebar {
        position:fixed; left:-260px; top:64px; z-index:200;
        transition:left .3s; height:calc(100vh - 64px);
      }
      .sidebar.open { left:0; }
    }
  `;
  document.head.appendChild(style);
});
