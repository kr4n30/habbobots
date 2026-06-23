import { Router } from 'express';
import bcrypt from 'bcryptjs';
import { getDB } from '../database/init.js';
import { requireAuth } from '../middleware/auth.js';

const router = Router();

// All user routes require auth
router.use(requireAuth);

// ── GET /users/me ─────────────────────────────────
router.get('/me', (req, res) => {
  const db = getDB();
  const user = db.prepare('SELECT id, username, email, discord_id, discord_tag, avatar_url, credits, role, created_at, updated_at FROM users WHERE id = ?').get(req.user.id);
  const habboAccounts = db.prepare('SELECT hotel, habbo_name, verified_at FROM habbo_accounts WHERE user_id = ?').all(req.user.id);
  const bots = db.prepare('SELECT id, name, hotel, status FROM bots WHERE user_id = ?').all(req.user.id);
  res.json({ user, habboAccounts, botsCount: bots.length });
});

// ── PATCH /users/me ───────────────────────────────
router.patch('/me', async (req, res, next) => {
  try {
    const { username, email, currentPassword, newPassword } = req.body;
    const db   = getDB();
    const user = db.prepare('SELECT * FROM users WHERE id = ?').get(req.user.id);

    const updates = {};
    if (username && username !== user.username) {
      const taken = db.prepare('SELECT id FROM users WHERE username = ? AND id != ?').get(username, user.id);
      if (taken) return res.status(409).json({ error: 'Nombre de usuario ya en uso' });
      updates.username = username;
    }
    if (email && email !== user.email) {
      const taken = db.prepare('SELECT id FROM users WHERE email = ? AND id != ?').get(email, user.id);
      if (taken) return res.status(409).json({ error: 'Email ya en uso' });
      updates.email = email;
    }
    if (newPassword) {
      if (!currentPassword) return res.status(400).json({ error: 'Se requiere la contraseña actual' });
      if (!user.password) return res.status(400).json({ error: 'Cuenta sin contraseña (Discord OAuth)' });
      const valid = await bcrypt.compare(currentPassword, user.password);
      if (!valid) return res.status(401).json({ error: 'Contraseña actual incorrecta' });
      if (newPassword.length < 8) return res.status(400).json({ error: 'La nueva contraseña debe tener al menos 8 caracteres' });
      updates.password = await bcrypt.hash(newPassword, 12);
    }

    if (Object.keys(updates).length === 0) {
      return res.json({ message: 'Sin cambios' });
    }

    const setClause = Object.keys(updates).map(k => `${k} = ?`).join(', ');
    db.prepare(`UPDATE users SET ${setClause}, updated_at = datetime('now') WHERE id = ?`)
      .run(...Object.values(updates), user.id);

    const updated = db.prepare('SELECT id, username, email, discord_id, credits, role FROM users WHERE id = ?').get(user.id);
    res.json({ user: updated });
  } catch (err) { next(err); }
});

// ── GET /users/:username (public profile) ─────────
router.get('/:username', (req, res) => {
  const db   = getDB();
  const user = db.prepare('SELECT id, username, avatar_url, credits, created_at FROM users WHERE username = ?').get(req.params.username);
  if (!user) return res.status(404).json({ error: 'Usuario no encontrado' });

  const habboAccounts = db.prepare('SELECT hotel, habbo_name FROM habbo_accounts WHERE user_id = ?').all(user.id);
  const botCount = db.prepare('SELECT COUNT(*) as n FROM bots WHERE user_id = ?').get(user.id).n;

  res.json({ user, habboAccounts, botCount });
});

export default router;
