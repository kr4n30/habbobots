import { Router } from 'express';
import { v4 as uuid } from 'uuid';
import { getDB } from '../database/init.js';
import { requireAuth } from '../middleware/auth.js';

const router = Router();
router.use(requireAuth);

const HOTEL_DOMAINS = {
  es:     'www.habbo.es',
  com:    'www.habbo.com',
  'com.br': 'www.habbo.com.br',
  de:     'www.habbo.de',
  fi:     'www.habbo.fi',
  it:     'www.habbo.it',
  nl:     'www.habbo.nl',
  tr:     'www.habbo.com.tr',
};

// ── GET /habbo/avatar ─────────────────────────────
// Returns the avatar URL for a Habbo user
router.get('/avatar', (req, res) => {
  const { look, hotel = 'com', headonly = '0', size = 'l' } = req.query;
  if (!look) return res.status(400).json({ error: 'look es obligatorio' });

  const base = hotel === 'es'
    ? 'https://www.habbo.es/habbo-imaging/avatarimage'
    : 'https://sandbox.habbo.com/habbo-imaging/avatarimage';

  const url = `${base}?figure=${look}&direction=3&head_direction=3&gesture=nrm&size=${size}&headonly=${headonly}`;
  res.json({ url });
});

// ── GET /habbo/profile/:name ──────────────────────
// Fetches a Habbo user's public profile from the Habbo API
router.get('/profile/:name', async (req, res, next) => {
  try {
    const { hotel = 'es' } = req.query;
    const domain = HOTEL_DOMAINS[hotel];
    if (!domain) return res.status(400).json({ error: 'Hotel no soportado' });

    const apiUrl = `https://${domain}/api/public/users?name=${encodeURIComponent(req.params.name)}`;
    const response = await fetch(apiUrl, {
      headers: { 'User-Agent': 'HabboBots/1.0' },
      signal: AbortSignal.timeout(8000),
    });

    if (!response.ok) {
      return res.status(404).json({ error: 'Usuario no encontrado en Habbo' });
    }

    const data = await response.json();
    res.json({
      name:        data.name,
      motto:       data.motto,
      figureString: data.figureString,
      memberSince: data.memberSince,
      lastAccessTime: data.lastAccessTime,
      hotel,
    });
  } catch (err) {
    if (err.name === 'TimeoutError') {
      return res.status(504).json({ error: 'API de Habbo tardó demasiado' });
    }
    next(err);
  }
});

// ── POST /habbo/verify/request ────────────────────
// Generates a motto verification token for the user
router.post('/verify/request', (req, res) => {
  const { hotel } = req.body;
  if (!hotel || !HOTEL_DOMAINS[hotel]) {
    return res.status(400).json({ error: 'Hotel no soportado' });
  }

  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  let code = 'HB-VERIFY-';
  for (let i = 0; i < 6; i++) code += chars[Math.floor(Math.random() * chars.length)];

  const db = getDB();
  const expiresAt = new Date(Date.now() + 10 * 60 * 1000).toISOString(); // 10 min

  // Remove old tokens for this user+hotel
  db.prepare('DELETE FROM verify_tokens WHERE user_id = ? AND hotel = ?').run(req.user.id, hotel);

  db.prepare(`
    INSERT INTO verify_tokens (id, user_id, hotel, token, expires_at)
    VALUES (?, ?, ?, ?, ?)
  `).run(uuid(), req.user.id, hotel, code, expiresAt);

  res.json({ token: code, expiresAt });
});

// ── POST /habbo/verify/check ──────────────────────
// Checks if the user has set the motto to the verification code
router.post('/verify/check', async (req, res, next) => {
  try {
    const { habboName, hotel } = req.body;
    if (!habboName || !hotel) {
      return res.status(400).json({ error: 'habboName y hotel son obligatorios' });
    }

    const db     = getDB();
    const record = db.prepare(`
      SELECT * FROM verify_tokens
      WHERE user_id = ? AND hotel = ? AND used = 0 AND expires_at > datetime('now')
      ORDER BY expires_at DESC LIMIT 1
    `).get(req.user.id, hotel);

    if (!record) {
      return res.status(400).json({ error: 'Token expirado o no encontrado. Genera uno nuevo.' });
    }

    const domain = HOTEL_DOMAINS[hotel];
    const apiUrl = `https://${domain}/api/public/users?name=${encodeURIComponent(habboName)}`;
    const response = await fetch(apiUrl, {
      headers: { 'User-Agent': 'HabboBots/1.0' },
      signal: AbortSignal.timeout(8000),
    });

    if (!response.ok) {
      return res.status(404).json({ error: 'Usuario no encontrado en Habbo' });
    }

    const profile = await response.json();

    if (!profile.motto?.includes(record.token)) {
      return res.status(400).json({
        error: 'Motto no coincide. Asegúrate de haber guardado el cambio en Habbo.',
        expected: record.token,
        found: profile.motto,
      });
    }

    // Mark token as used
    db.prepare('UPDATE verify_tokens SET used = 1 WHERE id = ?').run(record.id);

    // Upsert verified account
    db.prepare(`
      INSERT INTO habbo_accounts (id, user_id, hotel, habbo_name)
      VALUES (?, ?, ?, ?)
      ON CONFLICT(user_id, hotel) DO UPDATE SET habbo_name = excluded.habbo_name, verified_at = datetime('now')
    `).run(uuid(), req.user.id, hotel, profile.name);

    res.json({
      verified: true,
      habboName: profile.name,
      hotel,
      figureString: profile.figureString,
    });
  } catch (err) {
    if (err.name === 'TimeoutError') {
      return res.status(504).json({ error: 'API de Habbo tardó demasiado' });
    }
    next(err);
  }
});

// ── GET /habbo/accounts ───────────────────────────
router.get('/accounts', (req, res) => {
  const db       = getDB();
  const accounts = db.prepare('SELECT hotel, habbo_name, verified_at FROM habbo_accounts WHERE user_id = ?').all(req.user.id);
  res.json({ accounts });
});

// ── DELETE /habbo/accounts/:hotel ─────────────────
router.delete('/accounts/:hotel', (req, res) => {
  const db = getDB();
  db.prepare('DELETE FROM habbo_accounts WHERE user_id = ? AND hotel = ?').run(req.user.id, req.params.hotel);
  res.json({ message: 'Cuenta desvinculada' });
});

export default router;
