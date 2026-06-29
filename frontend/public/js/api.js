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
    preRegister: (email, password) =>
      apiFetch('/auth/pre-register', { method: 'POST', body: JSON.stringify({ email, password }) }),
    register: (pendingId, hotel, habboName, referralCode) =>
      apiFetch('/auth/register', { method: 'POST', body: JSON.stringify({ pendingId, hotel, habboName, referralCode }) }),
    verifyEmail: (token) =>
      apiFetch(`/auth/verify-email?token=${encodeURIComponent(token)}`),
    resendEmail: (email) =>
      apiFetch('/auth/resend-email', { method: 'POST', body: JSON.stringify({ email }) }),
    login: (identifier, password) =>
      apiFetch('/auth/login', { method: 'POST', body: JSON.stringify({ identifier, password }) }),
    me: () => apiFetch('/auth/me'),
    logout: () => { clearToken(); window.location.href = '/'; },
    discordURL: () => `${BASE}/auth/discord`,
  };

  // ── Users API ─────────────────────────────────────
  window.UsersAPI = {
    me:           ()      => apiFetch('/users/me'),
    update:       (data)  => apiFetch('/users/me', { method: 'PATCH', body: JSON.stringify(data) }),
    profile:      (name)  => apiFetch(`/users/${encodeURIComponent(name)}`),
    totpStatus:   ()      => apiFetch('/users/2fa/status'),
    totpSetup:    ()      => apiFetch('/users/2fa/setup', { method: 'POST' }),
    totpVerify:   (code)  => apiFetch('/users/2fa/verify', { method: 'POST', body: JSON.stringify({ code }) }),
    totpDisable:  (code)  => apiFetch('/users/2fa/disable', { method: 'POST', body: JSON.stringify({ code }) }),
  };

  // ── Bots API ──────────────────────────────────────
  window.BotsAPI = {
    list:   ()                              => apiFetch('/bots'),
    plans:  ()                              => apiFetch('/bots/plans'),
    get:    (id)                            => apiFetch(`/bots/${id}`),
    create: (name, hotel, room, duration, quantity) =>
      apiFetch('/bots', { method: 'POST', body: JSON.stringify({ name, hotel, room, duration, quantity }) }),
    update: (id, data)                      => apiFetch(`/bots/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    start:  (id)                            => apiFetch(`/bots/${id}/start`, { method: 'POST' }),
    stop:   (id)                            => apiFetch(`/bots/${id}/stop`,  { method: 'POST' }),
    delete: (id)                            => apiFetch(`/bots/${id}`, { method: 'DELETE' }),
    action: (id, action, params = {})       => apiFetch(`/bots/${id}/action`, { method: 'POST', body: JSON.stringify({ action, params }) }),
    logs:   (id, limit = 50)               => apiFetch(`/bots/${id}/logs?limit=${limit}`),
  };

  // ── Credits API ───────────────────────────────────
  window.CreditsAPI = {
    balance:        ()                              => apiFetch('/credits/balance'),
    history:        ()                              => apiFetch('/credits/history'),
    packs:          ()                              => apiFetch('/credits/packs'),
    payments:       ()                              => apiFetch('/credits/payments'),
    paymentStatus:  (id)                            => apiFetch(`/credits/payments/${id}`),
    checkout:       (packId, method, currency, couponCode) => apiFetch('/credits/checkout', {
      method: 'POST',
      body: JSON.stringify({ packId, method, currency, ...(couponCode ? { couponCode } : {}) }),
    }),
    capturePaypal:  (paymentId)                     => apiFetch(`/credits/paypal/capture?paymentId=${paymentId}`),
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

  // ── Products / Services API ───────────────────────
  window.ProductsAPI = {
    list:    (hotel)   => apiFetch(`/products${hotel ? `?hotel=${hotel}` : ''}`),
    get:     (id)      => apiFetch(`/products/${id}`),
    order:   (id, hotel, habboName, notes, botCount, duration, roomId) => apiFetch(`/products/${id}/order`, {
      method: 'POST',
      body: JSON.stringify({ hotel, habboName, notes, bot_count: botCount, duration, room_id: roomId }),
    }),
    myOrders: () => apiFetch('/products/orders/my'),
  };

  // ── Stats API ─────────────────────────────────────
  window.StatsAPI = {
    overview:    ()           => apiFetch('/stats'),
    activity:    (days = 30)  => apiFetch(`/stats/activity?days=${days}`),
    bots:        ()           => apiFetch('/stats/bots'),
    leaderboard: (by, hotel)  => apiFetch(`/stats/leaderboard?by=${by||'credits'}${hotel?`&hotel=${hotel}`:''}`),
  };

  // ── Admin API ─────────────────────────────────────
  window.AdminAPI = {
    overview:      ()             => apiFetch('/admin/overview'),
    users:         (params = {})  => apiFetch(`/admin/users?${new URLSearchParams(params)}`),
    updateUser:    (id, data)     => apiFetch(`/admin/users/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    setRole:       (id, role)     => apiFetch(`/admin/users/${id}/set-role`, { method: 'POST', body: JSON.stringify({ role }) }),
    orders:        (params = {})  => apiFetch(`/admin/orders?${new URLSearchParams(params)}`),
    updateOrder:   (id, status, notes) => apiFetch(`/admin/orders/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status, notes }) }),
    products:      ()             => apiFetch('/admin/products'),
    createProduct: (data)         => apiFetch('/admin/products', { method: 'POST', body: JSON.stringify(data) }),
    updateProduct: (id, data)     => apiFetch(`/admin/products/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    uploadProductImage: (id, file) => {
      const fd = new FormData(); fd.append('image', file);
      const token = getToken();
      return fetch(`${BASE}/admin/products/${id}/upload-image`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
      }).then(r => r.json());
    },
    logs:          (params = {})  => apiFetch(`/admin/logs?${new URLSearchParams(params)}`),
    reviews:       ()             => apiFetch('/admin/reviews'),
    // Bots
    bots:          (params = {})  => apiFetch(`/admin/bots?${new URLSearchParams(params)}`),
    deleteBot:     (id)           => apiFetch(`/admin/bots/${id}`, { method: 'DELETE' }),
    updateBot:     (id, data)     => apiFetch(`/admin/bots/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    vpsStatus:     ()             => apiFetch('/admin/vps-status'),
    vpsCommand:    (command, botId, extra = {}) => apiFetch('/admin/vps/command', {
      method: 'POST', body: JSON.stringify({ command, botId, ...extra }),
    }),
    // Métricas
    metrics:       (period = '30d') => apiFetch(`/admin/metrics?period=${period}`),
    // Cupones
    coupons:       ()             => apiFetch('/coupons'),
    createCoupon:  (data)         => apiFetch('/coupons', { method: 'POST', body: JSON.stringify(data) }),
    updateCoupon:  (id, data)     => apiFetch(`/coupons/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    deleteCoupon:  (id)           => apiFetch(`/coupons/${id}`, { method: 'DELETE' }),
    // Tickets admin
    tickets:       (params = {})  => apiFetch(`/tickets/admin/all?${new URLSearchParams(params)}`),
    replyTicket:   (id, message)  => apiFetch(`/tickets/${id}/reply`, { method: 'POST', body: JSON.stringify({ message }) }),
    setTicketStatus: (id, status) => apiFetch(`/tickets/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  };

  // ── Reviews API ───────────────────────────────────
  window.ReviewsAPI = {
    forProduct: (productId)            => apiFetch(`/reviews/product/${productId}`),
    my:         ()                     => apiFetch('/reviews/my'),
    create:     (order_id, rating, comment) => apiFetch('/reviews', { method: 'POST', body: JSON.stringify({ order_id, rating, comment }) }),
    delete:     (id)                   => apiFetch(`/reviews/${id}`, { method: 'DELETE' }),
  };

  // ── Affiliates API ────────────────────────────────
  window.AffiliatesAPI = {
    my:           ()     => apiFetch('/affiliates/my'),
    validate:     (code) => apiFetch(`/affiliates/validate/${encodeURIComponent(code)}`),
    markReward:   ()     => apiFetch('/affiliates/mark-reward', { method: 'POST' }),
  };

  // ── Coupons API (usuario) ─────────────────────────
  window.CouponsAPI = {
    validate: (code) => apiFetch('/coupons/validate', { method: 'POST', body: JSON.stringify({ code }) }),
  };

  // ── Tickets API (usuario) ─────────────────────────
  window.TicketsAPI = {
    create:    (subject, message, order_id) => apiFetch('/tickets', {
      method: 'POST', body: JSON.stringify({ subject, message, order_id }),
    }),
    my:        ()          => apiFetch('/tickets/my'),
    get:       (id)        => apiFetch(`/tickets/${id}`),
    reply:     (id, msg)   => apiFetch(`/tickets/${id}/reply`, { method: 'POST', body: JSON.stringify({ message: msg }) }),
    close:     (id)        => apiFetch(`/tickets/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status: 'closed' }) }),
  };

  // ── Push / PWA API ────────────────────────────────
  window.PushAPI_HB = {
    subscribe:   (subscription) => apiFetch('/push/subscribe', {
      method: 'POST', body: JSON.stringify(subscription),
    }),
    unsubscribe: ()             => apiFetch('/push/unsubscribe', { method: 'POST' }),
    vapidKey:    ()             => apiFetch('/push/vapid-key'),
  };

  // ── Public Status API (sin auth) ──────────────────
  window.StatusAPI = {
    get: () => fetch('/api/status').then(r => r.json()),
  };

})();
