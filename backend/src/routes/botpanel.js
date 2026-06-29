/**
 * botpanel.js — Proxy admin hacia el web.py del bot manager (puerto 5000)
 *
 * Todas las rutas requieren rol admin/moderator.
 * GET  /admin/botpanel/bots          → GET  http://localhost:5000/api/bots
 * POST /admin/botpanel/connect       → POST http://localhost:5000/api/connect
 * POST /admin/botpanel/disconnect    → POST http://localhost:5000/api/disconnect
 * GET  /admin/botpanel/stream        → SSE  http://localhost:5000/stream
 * GET  /admin/botpanel/bots/:idx/log → GET  http://localhost:5000/api/bots/:idx/log
 * POST /admin/botpanel/action/:name  → POST http://localhost:5000/api/action/:name
 * GET|POST /admin/botpanel/accounts/* → proxy /api/accounts/*
 * GET|POST /admin/botpanel/proxies/* → proxy /api/proxies/*
 * GET|POST /admin/botpanel/hotel     → proxy /api/hotel
 */

import { Router } from 'express';
import jwt from 'jsonwebtoken';
import { getDB } from '../database/init.js';
import { requireAdmin } from '../middleware/auth.js';

const router = Router();

const BOT_URL = () => process.env.BOT_GUI_URL || 'http://localhost:5000';

async function proxyTo(targetPath, req, res) {
  const url = `${BOT_URL()}${targetPath}`;
  try {
    const isGet = req.method === 'GET';
    const opts = {
      method:  req.method,
      headers: { 'Content-Type': 'application/json' },
      signal:  AbortSignal.timeout(10_000),
    };
    if (!isGet && req.body && Object.keys(req.body).length)
      opts.body = JSON.stringify(req.body);

    const upstream = await fetch(url, opts);
    const ct = upstream.headers.get('content-type') || '';
    const data = ct.includes('application/json') ? await upstream.json() : await upstream.text();
    res.status(upstream.status);
    if (typeof data === 'string') res.send(data); else res.json(data);
  } catch (e) {
    res.status(502).json({ error: `Bot manager no disponible: ${e.message}` });
  }
}

// ── SSE stream: auth via ?token= query param (EventSource can't set headers) ─
router.get('/stream', (req, res) => {
  const token = req.query.token;
  if (!token) { res.status(401).json({ error: 'Token requerido' }); return; }
  try {
    const SECRET  = process.env.JWT_SECRET || 'dev_secret_change_me';
    const payload = jwt.verify(token, SECRET);
    const db      = getDB();
    const user    = db.prepare('SELECT * FROM users WHERE id = ?').get(payload.sub);
    if (!user || (user.role !== 'admin' && user.role !== 'moderator')) {
      res.status(403).json({ error: 'Acceso denegado' }); return;
    }
  } catch { res.status(401).json({ error: 'Token inválido' }); return; }

  const upUrl = `${BOT_URL()}/stream`;
  res.setHeader('Content-Type',  'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection',    'keep-alive');
  res.flushHeaders();

  const controller = new AbortController();
  fetch(upUrl, { signal: controller.signal })
    .then(upstream => {
      if (!upstream.body) { res.end(); return; }
      const reader = upstream.body.getReader();
      const pump = () =>
        reader.read().then(({ done, value }) => {
          if (done) { res.end(); return; }
          res.write(Buffer.from(value));
          pump();
        }).catch(() => res.end());
      pump();
    })
    .catch(() => res.end());

  req.on('close', () => controller.abort());
});

// All other routes require admin via Bearer token
router.use(requireAdmin);

// ── Bots & connect ───────────────────────────────────────────────────────────
router.get( '/bots',           (req, res) => proxyTo('/api/bots',         req, res));
router.get( '/bots/:idx/log',  (req, res) => proxyTo(`/api/bots/${req.params.idx}/log`, req, res));
router.post('/connect',        (req, res) => proxyTo('/api/connect',      req, res));
router.post('/disconnect',     (req, res) => proxyTo('/api/disconnect',   req, res));
router.get( '/hotel',          (req, res) => proxyTo('/api/hotel',        req, res));
router.post('/hotel',          (req, res) => proxyTo('/api/hotel',        req, res));
router.post('/headers/refresh',(req, res) => proxyTo('/api/headers/refresh', req, res));

// ── Actions ──────────────────────────────────────────────────────────────────
router.post('/action/:name',   (req, res) => proxyTo(`/api/action/${req.params.name}`, req, res));

// ── Accounts ─────────────────────────────────────────────────────────────────
router.post('/accounts/load',         (req, res) => proxyTo('/api/accounts/load',         req, res));
router.post('/accounts/add',          (req, res) => proxyTo('/api/accounts/add',          req, res));
router.post('/accounts/save',         (req, res) => proxyTo('/api/accounts/save',         req, res));
router.post('/accounts/remove',       (req, res) => proxyTo('/api/accounts/remove',       req, res));
router.post('/accounts/parse_cookie', (req, res) => proxyTo('/api/accounts/parse_cookie', req, res));

// ── Proxies ──────────────────────────────────────────────────────────────────
router.get( '/proxies',              (req, res) => proxyTo('/api/proxies',              req, res));
router.get( '/proxies/list',         (req, res) => proxyTo('/api/proxies/list',         req, res));
router.post('/proxies/load',         (req, res) => proxyTo('/api/proxies/load',         req, res));
router.post('/proxies/save',         (req, res) => proxyTo('/api/proxies/save',         req, res));
router.post('/proxies/add',          (req, res) => proxyTo('/api/proxies/add',          req, res));
router.post('/proxies/delete',       (req, res) => proxyTo('/api/proxies/delete',       req, res));

// ── Proxy groups ─────────────────────────────────────────────────────────────
router.get(   '/proxy-groups',              (req, res) => proxyTo('/api/proxy-groups',              req, res));
router.post(  '/proxy-groups/create',       (req, res) => proxyTo('/api/proxy-groups/create',       req, res));
router.delete('/proxy-groups/:name',        (req, res) => proxyTo(`/api/proxy-groups/${req.params.name}`,         req, res));
router.post(  '/proxy-groups/:name/rename', (req, res) => proxyTo(`/api/proxy-groups/${req.params.name}/rename`,  req, res));
router.post(  '/proxy-groups/:name/add',    (req, res) => proxyTo(`/api/proxy-groups/${req.params.name}/add`,     req, res));
router.post(  '/proxy-groups/:name/remove', (req, res) => proxyTo(`/api/proxy-groups/${req.params.name}/remove`,  req, res));
router.post(  '/proxy-groups/:name/assign', (req, res) => proxyTo(`/api/proxy-groups/${req.params.name}/assign`,  req, res));
router.post(  '/proxy-groups/:name/clear',  (req, res) => proxyTo(`/api/proxy-groups/${req.params.name}/clear`,   req, res));

// ── Bot proxy assignment ──────────────────────────────────────────────────────
router.post('/bots/:idx/proxy',  (req, res) => proxyTo(`/api/bots/${req.params.idx}/proxy`, req, res));
router.post('/bots/group/proxy', (req, res) => proxyTo('/api/bots/group/proxy', req, res));

// ── Nav search & scan ─────────────────────────────────────────────────────────
router.post('/action/nav_search', (req, res) => proxyTo('/api/action/nav_search', req, res));
router.post('/action/scan',       (req, res) => proxyTo('/api/action/scan',       req, res));

export default router;
