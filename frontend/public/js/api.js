// ===========================
//  HabboBots — API Client
//  Cargado como script clásico (is:inline) → usa window.*
//  /api/* está proxeado a http://localhost:3001/* en dev
// ===========================

(function () {
  const BASE = '/api';

  // ── Helpers internos ──────────────────────────────
  function getToken()   { return sessionStorage.getItem('hb_token'); }
  function setToken(t)  { sessionStorage.setItem('hb_token', t); }
  function clearToken() { sessionStorage.removeItem('hb_token'); }

  async function apiFetch(path, options = {}) {
    const token = getToken();
    const headers = {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    };

    let res;
    try {
      res = await fetch(`${BASE}${path}`, { ...options, headers });
    } catch (e) {
      throw new Error('No se puede conectar al servidor. ¿Está el backend corriendo?');
    }

    let data = {};
    const contentType = res.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      data = await res.json();
    }

    if (!res.ok) {
      const err = new Error(data.error || `Error ${res.status}`);
      err.status = res.status;
      err.data   = data;
      throw err;
    }
    return data;
  }

  // ── Auth token store ──────────────────────────────
  window.Auth = {
    getToken,
    setToken,
    clearToken,
    isLoggedIn: () => !!getToken(),
  };

  // ── Auth API ──────────────────────────────────────
  window.AuthAPI = {
    register: (username, email, password) =>
      apiFetch('/auth/register', { method: 'POST', body: JSON.stringify({ username, email, password }) }),

    login: (identifier, password) =>
      apiFetch('/auth/login', { method: 'POST', body: JSON.stringify({ identifier, password }) }),

    me: () => apiFetch('/auth/me'),

    logout: () => {
      clearToken();
      window.location.href = '/';
    },

    discordURL: () => `${BASE}/auth/discord`,
  };

  // ── Users API ─────────────────────────────────────
  window.UsersAPI = {
    me:      ()      => apiFetch('/users/me'),
    update:  (data)  => apiFetch('/users/me', { method: 'PATCH', body: JSON.stringify(data) }),
    profile: (name)  => apiFetch(`/users/${encodeURIComponent(name)}`),
  };

  // ── Bots API ──────────────────────────────────────
  window.BotsAPI = {
    list:   ()                  => apiFetch('/bots'),
    get:    (id)                => apiFetch(`/bots/${id}`),
    create: (name, hotel, room) => apiFetch('/bots', { method: 'POST', body: JSON.stringify({ name, hotel, room }) }),
    update: (id, data)          => apiFetch(`/bots/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    start:  (id)                => apiFetch(`/bots/${id}/start`, { method: 'POST' }),
    stop:   (id)                => apiFetch(`/bots/${id}/stop`,  { method: 'POST' }),
    delete: (id)                => apiFetch(`/bots/${id}`, { method: 'DELETE' }),
  };

  // ── Credits API ───────────────────────────────────
  window.CreditsAPI = {
    balance:  ()                   => apiFetch('/credits/balance'),
    history:  ()                   => apiFetch('/credits/history'),
    packs:    ()                   => apiFetch('/credits/packs'),
    checkout: (packId, method)     => apiFetch('/credits/checkout', { method: 'POST', body: JSON.stringify({ packId, method }) }),
  };

  // ── Habbo API ─────────────────────────────────────
  window.HabboAPI = {
    profile:       (name, hotel)         => apiFetch(`/habbo/profile/${encodeURIComponent(name)}?hotel=${hotel}`),
    accounts:      ()                    => apiFetch('/habbo/accounts'),
    requestVerify: (hotel)               => apiFetch('/habbo/verify/request', { method: 'POST', body: JSON.stringify({ hotel }) }),
    checkVerify:   (habboName, hotel)    => apiFetch('/habbo/verify/check',   { method: 'POST', body: JSON.stringify({ habboName, hotel }) }),
    removeAccount: (hotel)               => apiFetch(`/habbo/accounts/${hotel}`, { method: 'DELETE' }),
    avatarURL:     (look, hotel = 'com', headonly = 0, size = 'l') =>
      `${BASE}/habbo/avatar?look=${encodeURIComponent(look)}&hotel=${hotel}&headonly=${headonly}&size=${size}`,
  };

  // ── Stats API ─────────────────────────────────────
  window.StatsAPI = {
    overview: ()          => apiFetch('/stats'),
    activity: (days = 30) => apiFetch(`/stats/activity?days=${days}`),
    bots:     ()          => apiFetch('/stats/bots'),
  };

  // ── Auth guard helper ─────────────────────────────
  window.requireLogin = function () {
    if (!getToken()) { window.location.href = '/'; return false; }
    return true;
  };

  // ── Handle Discord OAuth callback ─────────────────
  // Backend redirige a /dashboard?token=xxx tras el login
  (function handleDiscordCallback() {
    const params = new URLSearchParams(window.location.search);
    const token  = params.get('token');
    if (token) {
      setToken(token);
      const url = new URL(window.location.href);
      url.searchParams.delete('token');
      history.replaceState({}, '', url.toString());
    }
  })();

})(); // IIFE — nada se filtra al scope global salvo window.*
