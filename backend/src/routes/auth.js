import { Router } from 'express';
import bcrypt from 'bcryptjs';
import { v4 as uuid } from 'uuid';
import { getDB } from '../database/init.js';
import { generateAccessToken, requireAuth } from '../middleware/auth.js';

const router = Router();

// ── POST /auth/register ───────────────────────────
router.post('/register', async (req, res, next) => {
  try {
    const { username, email, password } = req.body;

    if (!username || !email || !password) {
      return res.status(400).json({ error: 'username, email y password son obligatorios' });
    }
    if (password.length < 8) {
      return res.status(400).json({ error: 'La contraseña debe tener al menos 8 caracteres' });
    }

    const db = getDB();

    const existing = db.prepare('SELECT id FROM users WHERE email = ? OR username = ?').get(email, username);
    if (existing) {
      return res.status(409).json({ error: 'Email o nombre de usuario ya en uso' });
    }

    const hash = await bcrypt.hash(password, 12);
    const id   = uuid();

    db.prepare(`
      INSERT INTO users (id, username, email, password, credits)
      VALUES (?, ?, ?, ?, 0)
    `).run(id, username, email, hash);

    const token = generateAccessToken(id);
    const user  = db.prepare('SELECT id, username, email, credits, role, created_at FROM users WHERE id = ?').get(id);

    res.status(201).json({ token, user });
  } catch (err) { next(err); }
});

// ── POST /auth/login ──────────────────────────────
router.post('/login', async (req, res, next) => {
  try {
    const { identifier, password } = req.body; // identifier = email OR username

    if (!identifier || !password) {
      return res.status(400).json({ error: 'identifier y password son obligatorios' });
    }

    const db   = getDB();
    const user = db.prepare('SELECT * FROM users WHERE email = ? OR username = ?').get(identifier, identifier);

    if (!user || !user.password) {
      return res.status(401).json({ error: 'Credenciales incorrectas' });
    }

    const valid = await bcrypt.compare(password, user.password);
    if (!valid) {
      return res.status(401).json({ error: 'Credenciales incorrectas' });
    }

    const token = generateAccessToken(user.id);
    const { password: _pw, ...safeUser } = user;

    res.json({ token, user: safeUser });
  } catch (err) { next(err); }
});

// ── GET /auth/discord ─────────────────────────────
// Redirects to Discord OAuth
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

    // Exchange code for token
    const tokenRes = await fetch('https://discord.com/api/oauth2/token', {
      method: 'POST',
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
    if (!tokenData.access_token) {
      return res.redirect(`${process.env.FRONTEND_URL}/?error=discord_token`);
    }

    // Get Discord user info
    const profileRes = await fetch('https://discord.com/api/users/@me', {
      headers: { Authorization: `Bearer ${tokenData.access_token}` },
    });
    const profile = await profileRes.json();

    const db = getDB();
    let user = db.prepare('SELECT * FROM users WHERE discord_id = ?').get(profile.id);

    if (!user) {
      // Check if email is already taken by a different account
      const byEmail = db.prepare('SELECT * FROM users WHERE email = ?').get(profile.email);
      if (byEmail) {
        // Link Discord to existing account
        db.prepare('UPDATE users SET discord_id = ?, discord_tag = ?, updated_at = datetime("now") WHERE id = ?')
          .run(profile.id, profile.global_name || profile.username, byEmail.id);
        user = db.prepare('SELECT * FROM users WHERE id = ?').get(byEmail.id);
      } else {
        // Create new account
        const id = uuid();
        const username = profile.global_name || profile.username;
        db.prepare(`
          INSERT INTO users (id, username, email, discord_id, discord_tag, avatar_url, credits)
          VALUES (?, ?, ?, ?, ?, ?, 0)
        `).run(
          id, username, profile.email || `${id}@discord.local`,
          profile.id,
          profile.global_name || profile.username,
          profile.avatar
            ? `https://cdn.discordapp.com/avatars/${profile.id}/${profile.avatar}.png`
            : null,
        );
        user = db.prepare('SELECT * FROM users WHERE id = ?').get(id);
      }
    }

    const jwt = generateAccessToken(user.id);
    // Redirect to frontend with token in query (frontend stores it)
    res.redirect(`${process.env.FRONTEND_URL}/dashboard?token=${jwt}`);
  } catch (err) { next(err); }
});

// ── GET /auth/me ──────────────────────────────────
router.get('/me', requireAuth, (req, res) => {
  const { password: _pw, ...safeUser } = req.user;
  res.json({ user: safeUser });
});

// ── POST /auth/logout ─────────────────────────────
router.post('/logout', requireAuth, (_req, res) => {
  // JWT is stateless; client just discards the token.
  // If using refresh tokens, delete them here.
  res.json({ message: 'Sesión cerrada' });
});

export default router;
