import { Router } from 'express';
import bcrypt from 'bcryptjs';
import { v4 as uuid } from 'uuid';
import { getDB } from '../database/init.js';
import { generateAccessToken, requireAuth } from '../middleware/auth.js';
import { sendVerificationEmail } from '../services/email.js';

const router = Router();

// ── Hoteles de Habbo disponibles ─────────────────
const HOTEL_DOMAINS = {
  es:  'www.habbo.es',
  com: 'www.habbo.com',
  br:  'www.habbo.com.br',
  tr:  'www.habbo.com.tr',
  fi:  'www.habbo.fi',
  de:  'www.habbo.de',
  fr:  'www.habbo.fr',
  it:  'www.habbo.it',
  nl:  'www.habbo.nl',
};

// ── Genera código de verificación de motto ────────
function generateMottoCode() {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; // sin 0/O/1/I
  let code = 'HB-';
  for (let i = 0; i < 6; i++) code += chars[Math.floor(Math.random() * chars.length)];
  return code;
}

// ── POST /auth/pre-register ───────────────────────
// Paso 1: valida email + password, genera código de motto
// El username = nick de Habbo (se asigna en el paso 2)
// NO crea usuario en DB todavía
router.post('/pre-register', async (req, res, next) => {
  try {
    const { email, password } = req.body;
    const ip = req.ip || req.headers['x-forwarded-for'];

    if (!email || !password)
      return res.status(400).json({ error: 'email y password son obligatorios' });
    if (password.length < 8)
      return res.status(400).json({ error: 'La contraseña debe tener al menos 8 caracteres' });

    const db = getDB();

    // Anti-spam
    const recentFromIp = db.prepare(`
      SELECT COUNT(*) as n FROM ip_logs
      WHERE ip = ? AND action = 'register' AND created_at > datetime('now', '-1 hour')
    `).get(ip);
    if (recentFromIp.n >= 5)
      return res.status(429).json({ error: 'Demasiados intentos desde esta IP. Espera un momento.' });

    // Email ya en uso
    const existing = db.prepare('SELECT id FROM users WHERE email = ?').get(email);
    if (existing)
      return res.status(409).json({ error: 'Este email ya tiene una cuenta' });

    // Registro pendiente reciente para el mismo email
    const pendingDup = db.prepare(`
      SELECT id FROM pending_registrations
      WHERE email = ? AND expires_at > datetime('now')
    `).get(email);
    if (pendingDup)
      return res.status(409).json({ error: 'Ya tienes un registro pendiente. Espera 15 minutos o reintenta.' });

    const hash    = await bcrypt.hash(password, 12);
    const code    = generateMottoCode();
    const id      = uuid();
    const expires = new Date(Date.now() + 15 * 60 * 1000).toISOString().replace('T', ' ').split('.')[0];

    db.prepare(`
      INSERT INTO pending_registrations (id, email, password, code, ip, expires_at)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(id, email, hash, code, ip, expires);

    res.json({ pendingId: id, code });
  } catch (err) { next(err); }
});

// ── POST /auth/register ───────────────────────────
// Paso 2: verifica motto en Habbo → crea usuario → envía email
router.post('/register', async (req, res, next) => {
  try {
    const { pendingId, hotel, habboName, ref_code } = req.body;
    const ip = req.ip || req.headers['x-forwarded-for'];

    if (!pendingId || !hotel || !habboName)
      return res.status(400).json({ error: 'pendingId, hotel y habboName son obligatorios' });

    const domain = HOTEL_DOMAINS[hotel.toLowerCase()];
    if (!domain)
      return res.status(400).json({ error: `Hotel '${hotel}' no válido. Usa: ${Object.keys(HOTEL_DOMAINS).join(', ')}` });

    const db = getDB();

    const pending = db.prepare(`
      SELECT * FROM pending_registrations
      WHERE id = ? AND expires_at > datetime('now')
    `).get(pendingId);

    if (!pending)
      return res.status(400).json({ error: 'Registro pendiente no encontrado o expirado. Empieza de nuevo.' });

    // Verificar que el usuario/email siguen libres (puede que alguien más haya registrado mientras tanto)
    const stillFree = db.prepare('SELECT id FROM users WHERE email = ? OR username = ?').get(pending.email, pending.username);
    if (stillFree) {
      db.prepare('DELETE FROM pending_registrations WHERE id = ?').run(pendingId);
      return res.status(409).json({ error: 'Email o nombre de usuario ya en uso' });
    }

    // ── Llamar a la API de Habbo para comprobar el motto ──
    let habboMotto = '';
    let habboUid   = '';
    let habboLook  = '';
    try {
      const habboRes = await fetch(
        `https://${domain}/api/public/users?name=${encodeURIComponent(habboName)}`,
        { signal: AbortSignal.timeout(8000) }
      );
      if (!habboRes.ok) {
        if (habboRes.status === 404)
          return res.status(404).json({ error: `Personaje '${habboName}' no encontrado en habbo.${hotel}` });
        throw new Error(`Habbo API ${habboRes.status}`);
      }
      const habboProfile = await habboRes.json();
      habboMotto = habboProfile.motto   || '';
      habboUid   = habboProfile.uniqueId || habboProfile.name;
      habboLook  = habboProfile.figureString || '';
    } catch (fetchErr) {
      if (fetchErr.name === 'TimeoutError')
        return res.status(503).json({ error: 'La API de Habbo tardó demasiado. Inténtalo de nuevo.' });
      console.error('Habbo API error:', fetchErr.message);
      return res.status(503).json({ error: 'No se pudo conectar a la API de Habbo. Inténtalo en unos segundos.' });
    }

    if (!habboMotto.includes(pending.code)) {
      return res.status(400).json({
        error: `El motto de '${habboName}' no contiene el código de verificación.`,
        hint: `Pon exactamente "${pending.code}" en tu motto de Habbo y vuelve a intentarlo.`,
        currentMotto: habboMotto || '(motto vacío)',
        code: pending.code,
      });
    }

    // El nick de Habbo es el username — comprobar que no esté ya en uso
    const nickTaken = db.prepare('SELECT id FROM users WHERE username = ?').get(habboName);
    if (nickTaken)
      return res.status(409).json({ error: `El nick '${habboName}' ya está registrado en HabboBots.` });

    // ── 1 cuenta por IP ───────────────────────────
    if (process.env.ALLOW_MULTIPLE_ACCOUNTS_PER_IP !== 'true') {
      const ipAccount = db.prepare('SELECT username FROM users WHERE registration_ip = ?').get(ip);
      if (ipAccount) {
        return res.status(409).json({
          error: `Ya existe una cuenta (${ipAccount.username}) registrada desde tu IP. Solo se permite 1 cuenta por IP.`,
          code: 'IP_ALREADY_REGISTERED',
        });
      }
    }

    // ── Crear usuario ──────────────────────────────
    // username = nick de Habbo; habbo_uid = uniqueId estable de Habbo
    const userId      = uuid();
    const emailToken  = uuid();
    const tokenExpiry = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString().replace('T', ' ').split('.')[0];

    // Resolver código de referido
    let referrerId = null;
    const refCode  = ref_code?.trim();
    if (refCode) {
      const referrer = db.prepare('SELECT id FROM users WHERE referral_code=?').get(refCode);
      if (referrer && referrer.id !== userId) referrerId = referrer.id;
    }

    // Generar código de referido único para este nuevo usuario
    const newUserReferralCode = `HB-${userId.slice(0,6).toUpperCase()}`;

    const createUser = db.transaction(() => {
      db.prepare(`
        INSERT INTO users (id, username, email, password, credits, email_verified, referral_code, referred_by, registration_ip)
        VALUES (?, ?, ?, ?, 0, 0, ?, ?, ?)
      `).run(userId, habboName, pending.email, pending.password, newUserReferralCode, referrerId, ip);

      db.prepare('INSERT OR IGNORE INTO user_stats (user_id) VALUES (?)').run(userId);

      // Vincular cuenta Habbo verificada (guarda uniqueId estable)
      db.prepare(`
        INSERT OR IGNORE INTO habbo_accounts (id, user_id, hotel, habbo_name)
        VALUES (?, ?, ?, ?)
      `).run(uuid(), userId, hotel.toLowerCase(), habboName);

      // Guardar identidad con uniqueId de Habbo
      db.prepare(`
        INSERT OR IGNORE INTO habbo_identities (id, user_id, hotel, habbo_uid, current_name)
        VALUES (?, ?, ?, ?, ?)
      `).run(uuid(), userId, hotel.toLowerCase(), habboUid, habboName);

      // Token de email
      db.prepare(`
        INSERT INTO email_tokens (id, user_id, token, expires_at)
        VALUES (?, ?, ?, ?)
      `).run(uuid(), userId, emailToken, tokenExpiry);

      // Log IP
      db.prepare(`INSERT INTO ip_logs (id, user_id, ip, action) VALUES (?, ?, ?, 'register')`)
        .run(uuid(), userId, ip);

      // Borrar el registro pendiente
      db.prepare('DELETE FROM pending_registrations WHERE id = ?').run(pendingId);
    });

    createUser();

    // ── Enviar email de verificación ───────────────
    try {
      await sendVerificationEmail(pending.email, pending.username, emailToken);
    } catch (mailErr) {
      console.error('❌ Error enviando email de verificación:', mailErr.message);
      // No abortamos — el usuario ya fue creado, puede pedir reenvío
    }

    res.status(201).json({
      message: '¡Cuenta creada! Revisa tu email para verificarla antes de iniciar sesión.',
      username: habboName,   // nick de Habbo = username de la plataforma
      email: pending.email,
    });
  } catch (err) { next(err); }
});

// ── GET /auth/verify-email?token=xxx ─────────────
// Paso 3: marca email como verificado
router.get('/verify-email', async (req, res, next) => {
  try {
    const { token } = req.query;
    if (!token)
      return res.status(400).json({ error: 'Token requerido' });

    const db    = getDB();
    const entry = db.prepare(`
      SELECT * FROM email_tokens
      WHERE token = ? AND used = 0 AND expires_at > datetime('now')
    `).get(token);

    if (!entry)
      return res.status(400).json({ error: 'Token inválido o expirado.' });

    db.transaction(() => {
      db.prepare('UPDATE users SET email_verified = 1, updated_at = datetime(\'now\') WHERE id = ?').run(entry.user_id);
      db.prepare('UPDATE email_tokens SET used = 1 WHERE id = ?').run(entry.id);
    })();

    // Redirige al frontend con mensaje de éxito
    const base = process.env.FRONTEND_URL || 'https://kr4n30.tech';
    res.redirect(`${base}/verificar-email?success=1`);
  } catch (err) { next(err); }
});

// ── POST /auth/resend-email ───────────────────────
// Reenvía email de verificación (por email o por token de sesión)
router.post('/resend-email', async (req, res, next) => {
  try {
    const { email } = req.body;
    if (!email)
      return res.status(400).json({ error: 'email es obligatorio' });

    const db   = getDB();
    const user = db.prepare('SELECT * FROM users WHERE email = ?').get(email);

    if (!user)
      return res.status(404).json({ error: 'No existe una cuenta con ese email' });

    if (user.email_verified)
      return res.status(400).json({ error: 'Este email ya está verificado' });

    // Invalidar tokens anteriores y crear uno nuevo
    db.prepare('UPDATE email_tokens SET used = 1 WHERE user_id = ?').run(user.id);

    const newToken = uuid();
    const expiry   = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString().replace('T', ' ').split('.')[0];
    db.prepare(`
      INSERT INTO email_tokens (id, user_id, token, expires_at)
      VALUES (?, ?, ?, ?)
    `).run(uuid(), user.id, newToken, expiry);

    try {
      await sendVerificationEmail(user.email, user.username, newToken);
    } catch (mailErr) {
      console.error('Error enviando email:', mailErr.message);
      return res.status(500).json({ error: 'No se pudo enviar el email. Comprueba la configuración SMTP.' });
    }

    res.json({ message: 'Email de verificación enviado. Revisa tu bandeja de entrada.' });
  } catch (err) { next(err); }
});

// ── POST /auth/login ──────────────────────────────
router.post('/login', async (req, res, next) => {
  try {
    const { identifier, password } = req.body;
    const ip = req.ip || req.headers['x-forwarded-for'];

    if (!identifier || !password)
      return res.status(400).json({ error: 'email y password son obligatorios' });

    const db   = getDB();
    // Login solo por email (el username = nick Habbo, no se usa para autenticar)
    const user = db.prepare('SELECT * FROM users WHERE email = ?').get(identifier);

    if (!user || !user.password)
      return res.status(401).json({ error: 'Credenciales incorrectas' });

    if (user.is_banned)
      return res.status(403).json({ error: 'Cuenta suspendida', reason: user.ban_reason });

    const valid = await bcrypt.compare(password, user.password);
    if (!valid)
      return res.status(401).json({ error: 'Credenciales incorrectas' });

    if (!user.email_verified)
      return res.status(403).json({
        error: 'Debes verificar tu email antes de iniciar sesión.',
        code: 'EMAIL_UNVERIFIED',
        email: user.email,
      });

    // Log IP
    db.prepare(`INSERT INTO ip_logs (id, user_id, ip, action) VALUES (?, ?, ?, 'login')`)
      .run(uuid(), user.id, ip);

    const token = generateAccessToken(user.id);
    const { password: _pw, ...safeUser } = user;

    res.json({ token, user: safeUser });
  } catch (err) { next(err); }
});

// ── GET /auth/discord ─────────────────────────────
router.get('/discord', (req, res) => {
  const params = new URLSearchParams({
    client_id:     process.env.DISCORD_CLIENT_ID,
    redirect_uri:  process.env.DISCORD_CALLBACK_URL,
    response_type: 'code',
    scope:         'identify email',
  });
  res.redirect(`https://discord.com/api/oauth2/authorize?${params}`);
});

// ── GET /auth/discord/callback ────────────────────
router.get('/discord/callback', async (req, res, next) => {
  try {
    const { code } = req.query;
    if (!code) return res.redirect(`${process.env.FRONTEND_URL}/?error=discord_denied`);

    const tokenRes = await fetch('https://discord.com/api/oauth2/token', {
      method:  'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        client_id:     process.env.DISCORD_CLIENT_ID,
        client_secret: process.env.DISCORD_CLIENT_SECRET,
        grant_type:    'authorization_code',
        code,
        redirect_uri:  process.env.DISCORD_CALLBACK_URL,
      }),
    });
    const tokenData = await tokenRes.json();
    if (!tokenData.access_token)
      return res.redirect(`${process.env.FRONTEND_URL}/?error=discord_token`);

    const profileRes = await fetch('https://discord.com/api/users/@me', {
      headers: { Authorization: `Bearer ${tokenData.access_token}` },
    });
    const profile = await profileRes.json();

    const db = getDB();
    let user = db.prepare('SELECT * FROM users WHERE discord_id = ?').get(profile.id);

    if (!user) {
      const byEmail = db.prepare('SELECT * FROM users WHERE email = ?').get(profile.email);
      if (byEmail) {
        db.prepare(`UPDATE users SET discord_id = ?, discord_tag = ?, email_verified = 1, updated_at = datetime('now') WHERE id = ?`)
          .run(profile.id, profile.global_name || profile.username, byEmail.id);
        user = db.prepare('SELECT * FROM users WHERE id = ?').get(byEmail.id);
      } else {
        const id       = uuid();
        const username = profile.global_name || profile.username;
        const avatarUrl = profile.avatar
          ? `https://cdn.discordapp.com/avatars/${profile.id}/${profile.avatar}.png`
          : null;
        // Discord OAuth → email ya verificado automáticamente
        db.prepare(`
          INSERT INTO users (id, username, email, discord_id, discord_tag, avatar_url, credits, email_verified)
          VALUES (?, ?, ?, ?, ?, ?, 0, 1)
        `).run(id, username, profile.email || `${id}@discord.local`,
               profile.id, profile.global_name || profile.username, avatarUrl);
        db.prepare('INSERT OR IGNORE INTO user_stats (user_id) VALUES (?)').run(id);
        user = db.prepare('SELECT * FROM users WHERE id = ?').get(id);
      }
    }

    const jwtToken = generateAccessToken(user.id);

    // Si no tiene Habbo vinculado → verificar primero
    const db2 = getDB();
    const hasHabbo = db2.prepare('SELECT id FROM habbo_accounts WHERE user_id = ?').get(user.id);
    let destPath;
    if (!hasHabbo) {
      destPath = '/verificar-habbo';
    } else if (user.role === 'admin' || user.role === 'moderator') {
      destPath = '/dashboard';
    } else {
      destPath = '/home';
    }
    res.redirect(`${process.env.FRONTEND_URL}${destPath}?token=${jwtToken}`);
  } catch (err) { next(err); }
});

// ── GET /auth/me ──────────────────────────────────
router.get('/me', requireAuth, (req, res) => {
  const { password: _pw, ...safeUser } = req.user;
  res.json({ user: safeUser });
});

// ── POST /auth/logout ─────────────────────────────
router.post('/logout', requireAuth, (_req, res) => {
  res.json({ message: 'Sesión cerrada' });
});

export default router;
