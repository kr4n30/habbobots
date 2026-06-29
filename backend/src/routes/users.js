import { Router } from 'express';
import bcrypt from 'bcryptjs';
import { getDB } from '../database/init.js';
import { requireAuth } from '../middleware/auth.js';
import * as OTPAuth from 'otpauth';
import QRCode from 'qrcode';

const router = Router();
router.use(requireAuth);

// ── GET /users/me ─────────────────────────────────
router.get('/me', (req, res) => {
  const db = getDB();
  const user = db.prepare(`
    SELECT id, username, email, discord_id, discord_tag, avatar_url, credits, role, created_at, updated_at
    FROM users WHERE id = ?
  `).get(req.user.id);

  const habboAccounts = db.prepare('SELECT hotel, habbo_name, verified_at FROM habbo_accounts WHERE user_id = ?').all(req.user.id);
  const habboIdentities = db.prepare('SELECT hotel, habbo_uid, current_name, verified_at FROM habbo_identities WHERE user_id = ?').all(req.user.id);
  const stats = db.prepare('SELECT * FROM user_stats WHERE user_id = ?').get(req.user.id);
  const botsCount = db.prepare('SELECT COUNT(*) as n FROM bots WHERE user_id = ?').get(req.user.id).n;

  res.json({ user, habboAccounts, habboIdentities, stats, botsCount });
});

// ── PATCH /users/me ───────────────────────────────
router.patch('/me', async (req, res, next) => {
  try {
    const { username, email, currentPassword, newPassword } = req.body;
    const db   = getDB();
    const user = db.prepare('SELECT * FROM users WHERE id = ?').get(req.user.id);

    const updates = [];
    const values  = [];

    if (username && username !== user.username) {
      const taken = db.prepare('SELECT id FROM users WHERE username = ? AND id != ?').get(username, user.id);
      if (taken) return res.status(409).json({ error: 'Nombre de usuario ya en uso' });
      updates.push('username = ?'); values.push(username);
    }
    if (email && email !== user.email) {
      const taken = db.prepare('SELECT id FROM users WHERE email = ? AND id != ?').get(email, user.id);
      if (taken) return res.status(409).json({ error: 'Email ya en uso' });
      updates.push('email = ?'); values.push(email);
    }
    if (newPassword) {
      if (!currentPassword) return res.status(400).json({ error: 'Se requiere la contraseña actual' });
      if (!user.password)   return res.status(400).json({ error: 'Cuenta sin contraseña (OAuth)' });
      const valid = await bcrypt.compare(currentPassword, user.password);
      if (!valid) return res.status(401).json({ error: 'Contraseña actual incorrecta' });
      if (newPassword.length < 8) return res.status(400).json({ error: 'Mínimo 8 caracteres' });
      updates.push('password = ?'); values.push(await bcrypt.hash(newPassword, 12));
    }

    if (updates.length === 0) return res.json({ message: 'Sin cambios' });

    db.prepare(`UPDATE users SET ${updates.join(', ')}, updated_at = datetime('now') WHERE id = ?`)
      .run(...values, user.id);

    const updated = db.prepare('SELECT id, username, email, discord_id, credits, role FROM users WHERE id = ?').get(user.id);
    res.json({ user: updated });
  } catch (err) { next(err); }
});

// ── GET /users/2fa/status ─────────────────────────
router.get('/2fa/status', (req, res) => {
  const db     = getDB();
  const secret = db.prepare('SELECT verified FROM totp_secrets WHERE user_id = ?').get(req.user.id);
  res.json({ enabled: !!(secret?.verified) });
});

// ── POST /users/2fa/setup ─────────────────────────
// Genera secreto TOTP y devuelve QR code en base64
router.post('/2fa/setup', async (req, res, next) => {
  try {
    const db   = getDB();
    const user = db.prepare('SELECT username, email FROM users WHERE id = ?').get(req.user.id);

    // Generar secreto aleatorio
    const totp = new OTPAuth.TOTP({
      issuer:    'HabboBots',
      label:     user.email || user.username,
      algorithm: 'SHA1',
      digits:    6,
      period:    30,
    });

    const secret = totp.secret.base32;

    // Guardar (sin verificar aún)
    db.prepare(`
      INSERT INTO totp_secrets (user_id, secret, verified)
      VALUES (?, ?, 0)
      ON CONFLICT(user_id) DO UPDATE SET secret = ?, verified = 0
    `).run(req.user.id, secret, secret);

    const otpAuthUrl = totp.toString();
    const qrDataUrl  = await QRCode.toDataURL(otpAuthUrl);

    res.json({ secret, otpAuthUrl, qrDataUrl });
  } catch (err) { next(err); }
});

// ── POST /users/2fa/verify ────────────────────────
// Verifica el código e activa 2FA
router.post('/2fa/verify', (req, res) => {
  const { code } = req.body;
  if (!code) return res.status(400).json({ error: 'Código requerido' });

  const db     = getDB();
  const stored = db.prepare('SELECT * FROM totp_secrets WHERE user_id = ?').get(req.user.id);
  if (!stored) return res.status(400).json({ error: 'Primero genera el QR con /2fa/setup' });

  const totp  = new OTPAuth.TOTP({ secret: OTPAuth.Secret.fromBase32(stored.secret), algorithm: 'SHA1', digits: 6, period: 30 });
  const delta = totp.validate({ token: String(code), window: 1 });

  if (delta === null) return res.status(400).json({ error: 'Código incorrecto. Comprueba que el reloj de tu app está sincronizado.' });

  db.prepare('UPDATE totp_secrets SET verified = 1 WHERE user_id = ?').run(req.user.id);
  res.json({ ok: true, message: '2FA activado correctamente' });
});

// ── POST /users/2fa/disable ───────────────────────
router.post('/2fa/disable', (req, res) => {
  const { code } = req.body;
  if (!code) return res.status(400).json({ error: 'Introduce el código actual para desactivar 2FA' });

  const db     = getDB();
  const stored = db.prepare('SELECT * FROM totp_secrets WHERE user_id = ? AND verified = 1').get(req.user.id);
  if (!stored) return res.status(400).json({ error: '2FA no está activado' });

  const totp  = new OTPAuth.TOTP({ secret: OTPAuth.Secret.fromBase32(stored.secret), algorithm: 'SHA1', digits: 6, period: 30 });
  const delta = totp.validate({ token: String(code), window: 1 });
  if (delta === null) return res.status(400).json({ error: 'Código incorrecto' });

  db.prepare('DELETE FROM totp_secrets WHERE user_id = ?').run(req.user.id);
  res.json({ ok: true, message: '2FA desactivado' });
});

// ── GET /users/:username (perfil público) ─────────
router.get('/:username', (req, res) => {
  const db   = getDB();
  const user = db.prepare('SELECT id, username, avatar_url, credits, role, created_at FROM users WHERE username = ?').get(req.params.username);
  if (!user) return res.status(404).json({ error: 'Usuario no encontrado' });

  const habboAccounts = db.prepare('SELECT hotel, habbo_name FROM habbo_accounts WHERE user_id = ?').all(user.id);
  const stats         = db.prepare('SELECT * FROM user_stats WHERE user_id = ?').get(user.id);
  const botCount      = db.prepare('SELECT COUNT(*) as n FROM bots WHERE user_id = ?').get(user.id).n;
  const followers     = db.prepare('SELECT COUNT(*) as n FROM user_follows WHERE following_id = ?').get(user.id).n;
  const following     = db.prepare('SELECT COUNT(*) as n FROM user_follows WHERE follower_id = ?').get(user.id).n;
  const reputation    = db.prepare('SELECT COALESCE(SUM(value),0) as score FROM reputation WHERE to_user = ?').get(user.id).score;

  res.json({ user, habboAccounts, stats, botCount, followers, following, reputation });
});

export default router;
