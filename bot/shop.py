#!/usr/bin/env python3
"""
shop.py — Web de ventas / SaaS para Habbo Bot Manager
Corre en puerto 5001 (independiente del bot manager en 5000)

Config necesaria (variables de entorno o shop_config.json):
  DISCORD_CLIENT_ID      — App ID del portal Discord Developer
  DISCORD_CLIENT_SECRET  — Secret de la misma app
  DISCORD_REDIRECT_URI   — Debe coincidir con el callback registrado en Discord
                           ej. http://localhost:5001/auth/callback
  SHOP_SECRET            — Clave secreta de Flask (genera con secrets.token_hex(32))
  FIRST_ADMIN_DISCORD_ID — Discord ID del primer admin (se eleva al arrancar)
"""

import os, json, secrets
from functools import wraps
from flask import (Flask, redirect, request, session,
                   jsonify, url_for, make_response)
import requests as _req
import db

# ── CONFIG ────────────────────────────────────────────────────────────────────
_CFG_FILE = os.path.join(os.path.dirname(__file__), 'shop_config.json')
def _cfg(key, default=''):
    return os.environ.get(key) or (json.load(open(_CFG_FILE)) if os.path.exists(_CFG_FILE) else {}).get(key, default)

DISCORD_CLIENT_ID     = _cfg('DISCORD_CLIENT_ID',     'YOUR_CLIENT_ID')
DISCORD_CLIENT_SECRET = _cfg('DISCORD_CLIENT_SECRET', 'YOUR_CLIENT_SECRET')
DISCORD_REDIRECT_URI  = _cfg('DISCORD_REDIRECT_URI',  'http://localhost:5001/auth/callback')
FIRST_ADMIN_ID        = _cfg('FIRST_ADMIN_DISCORD_ID', '')
SHOP_PORT             = int(_cfg('SHOP_PORT', '5001'))

DISCORD_API   = 'https://discord.com/api/v10'
DISCORD_OAUTH = 'https://discord.com/oauth2/authorize'
DISCORD_TOKEN = 'https://discord.com/api/oauth2/token'

app = Flask(__name__, static_folder=None)
app.secret_key = _cfg('SHOP_SECRET', secrets.token_hex(32))

# Elevar primer admin si está configurado
if FIRST_ADMIN_ID:
    u = db.get_user_by_discord(FIRST_ADMIN_ID)
    if u: db.set_admin(u['id'], True)

# ── AUTH HELPERS ──────────────────────────────────────────────────────────────
def current_user():
    uid = session.get('user_id')
    return db.get_user(uid) if uid else None

def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not current_user():
            session['next'] = request.url
            return redirect('/login')
        return f(*a, **kw)
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        u = current_user()
        if not u or not u['is_admin']:
            return page_error('403 — Sin permisos de administrador'), 403
        return f(*a, **kw)
    return wrapper

def api_auth():
    """Autenticación por API key en header Authorization: Bearer <key>"""
    hdr = request.headers.get('Authorization', '')
    if hdr.startswith('Bearer '):
        return db.get_user_by_api_key(hdr[7:])
    key = request.args.get('api_key') or (request.get_json(silent=True) or {}).get('api_key')
    return db.get_user_by_api_key(key) if key else None

# ── CSS / LAYOUT HELPERS ──────────────────────────────────────────────────────
BASE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Ubuntu+Condensed&family=Open+Sans:wght@400;600&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#c4c0b0;--card:#F2F2EB;--inp:#e8e4d8;
  --teal:#30728C;--dteal:#1d5a72;--lteal:#3C88A6;
  --fg:#1a1a1a;--fm:#4a6a7a;--gr:#1a7a3a;--rd:#BF2C2C;
  --or:#b85c00;--pu:#6633aa;--sep:#3C88A6;
}
body{min-height:100vh;background:var(--bg) url('https://mangetoica.com/gallery_images/homepage/background-mosaiques//bg.png') repeat;
  font:9pt 'Open Sans',Arial,sans-serif;color:var(--fg)}
a{color:var(--teal);text-decoration:none}
a:hover{text-decoration:underline}
/* TOPNAV */
#topnav{background:var(--dteal);border-bottom:2px solid #000;display:flex;align-items:center;padding:0 20px;height:48px;gap:16px}
#topnav .brand{font:bold 13pt 'Ubuntu Condensed',sans-serif;color:#fff;text-shadow:1px 1px 0 #000;letter-spacing:1px}
#topnav .brand span{color:#b8ffd8}
#topnav nav{flex:1;display:flex;gap:4px;margin-left:16px}
#topnav nav a{color:#9cc8d8;font-size:8.5pt;padding:6px 10px;border-radius:4px;transition:background .15s,color .15s}
#topnav nav a:hover,#topnav nav a.active{background:rgba(255,255,255,.12);color:#fff;text-decoration:none}
#topnav .user-chip{display:flex;align-items:center;gap:6px;color:#fff;font-size:8.5pt}
#topnav .user-chip img{width:26px;height:26px;border-radius:50%;border:2px solid #fff4}
#topnav .user-chip .credits-badge{background:#1a7a3a;border:1px solid #000;border-radius:10px;padding:2px 8px;font-size:7.5pt;font-weight:bold;color:#b8ffd8}
#topnav .btn-login{background:var(--teal);color:#fff;border:2px solid #000;border-radius:4px;padding:5px 14px;font-size:8.5pt;font-weight:bold;cursor:pointer;transition:filter .15s}
#topnav .btn-login:hover{filter:brightness(1.15)}
/* CONTAINER */
.container{max-width:1060px;margin:0 auto;padding:24px 16px}
/* CARD */
.card{background:var(--card);border-radius:8px;border:2px solid #000;box-shadow:1px 1px 6px rgba(0,0,0,.3);margin-bottom:16px;overflow:hidden}
.card-hdr{padding:8px 12px;background:var(--teal);color:#fff;font:bold 9.5pt 'Ubuntu Condensed',sans-serif;text-shadow:1px 1px 0 #000;border-bottom:2px solid #000;display:flex;align-items:center;gap:8px}
.card-body{padding:12px 14px}
/* TABLE */
.tbl{width:100%;border-collapse:collapse;font-size:8pt}
.tbl th{background:var(--teal);color:#fff;padding:7px 10px;text-align:left;border-bottom:2px solid #000;font-family:'Ubuntu Condensed',sans-serif;font-size:9pt;text-shadow:1px 1px 0 #000}
.tbl td{padding:6px 10px;border-bottom:1px solid #d8d4c4}
.tbl tr:hover td{background:#dde9f0}
/* BUTTONS */
.btn{display:inline-block;border:2px solid #000;border-radius:4px;padding:6px 14px;font:bold 8.5pt 'Open Sans',sans-serif;cursor:pointer;transition:filter .15s,border-color .15s;text-decoration:none}
.btn:hover{filter:brightness(1.12);border-color:#fff;text-decoration:none}
.btn-teal{background:var(--teal);color:#fff}
.btn-gr{background:#1a7a3a;color:#fff}
.btn-rd{background:#BF2C2C;color:#fff}
.btn-or{background:#b85c00;color:#fff}
.btn-pu{background:#6633aa;color:#fff}
.btn-sm{padding:3px 10px;font-size:7.5pt}
.btn-lg{padding:10px 24px;font-size:10pt}
/* INPUTS */
input[type=text],input[type=email],input[type=number],input[type=password],textarea,select{
  background:var(--inp);color:var(--fg);border:1px solid var(--lteal);
  outline:none;padding:6px 8px;font:8.5pt 'Open Sans',sans-serif;border-radius:4px;width:100%}
input:focus,textarea:focus,select:focus{border-color:var(--teal);box-shadow:0 0 0 2px rgba(48,114,140,.2)}
label.lbl{display:block;color:var(--fm);font-size:8pt;margin-bottom:3px}
.form-group{margin-bottom:10px}
/* BADGES */
.badge{display:inline-block;border-radius:10px;padding:2px 8px;font-size:7pt;font-weight:bold;border:1px solid rgba(0,0,0,.3)}
.badge-gr{background:#1a7a3a;color:#fff}
.badge-rd{background:#BF2C2C;color:#fff}
.badge-or{background:#b85c00;color:#fff}
.badge-ye{background:#8a7200;color:#fff}
.badge-bl{background:#1155aa;color:#fff}
.badge-teal{background:var(--teal);color:#fff}
/* FLASH */
.flash{padding:9px 14px;border-radius:4px;border:2px solid #000;margin-bottom:12px;font-size:8.5pt}
.flash-ok{background:#d8f4e0;color:#1a5a2a;border-color:#1a7a3a}
.flash-err{background:#fad8d8;color:#5a1a1a;border-color:#BF2C2C}
.flash-info{background:#daeaf4;color:#1a3a4a;border-color:var(--teal)}
/* GRID */
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.grid-3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.grid-4{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
@media(max-width:700px){.grid-2,.grid-3,.grid-4{grid-template-columns:1fr}}
/* PRICING CARD */
.pkg-card{background:var(--card);border:2px solid #000;border-radius:10px;box-shadow:2px 2px 8px rgba(0,0,0,.3);overflow:hidden;display:flex;flex-direction:column;position:relative;transition:transform .15s,box-shadow .15s}
.pkg-card:hover{transform:translateY(-3px);box-shadow:3px 5px 16px rgba(0,0,0,.4)}
.pkg-tag{position:absolute;top:10px;right:10px;font-size:7pt;font-weight:bold;padding:2px 8px;border-radius:10px;border:1px solid rgba(0,0,0,.3);color:#fff}
.pkg-hdr{padding:16px 14px 10px;border-bottom:2px solid #000;text-align:center}
.pkg-name{font:bold 14pt 'Ubuntu Condensed',sans-serif;text-shadow:1px 1px 0 #000;color:#fff;letter-spacing:.5px}
.pkg-credits{font-size:26pt;font-weight:bold;color:#fff;line-height:1.1}
.pkg-bonus{font-size:8pt;color:rgba(255,255,255,.8)}
.pkg-body{padding:14px;flex:1;display:flex;flex-direction:column;gap:8px}
.pkg-price{font-size:20pt;font-weight:bold;color:var(--fg);text-align:center}
.pkg-price span{font-size:9pt;font-weight:normal;color:var(--fm)}
.pkg-footer{padding:0 14px 14px}
/* STAT BOXES */
.stat-box{background:var(--card);border:2px solid #000;border-radius:8px;padding:14px;box-shadow:1px 1px 4px rgba(0,0,0,.25);display:flex;flex-direction:column;gap:4px}
.stat-val{font-size:22pt;font-weight:bold;color:var(--teal);font-family:'Ubuntu Condensed',sans-serif}
.stat-lbl{font-size:8pt;color:var(--fm)}
/* HERO */
#hero{background:linear-gradient(135deg,#1d5a72 0%,#30728C 60%,#3C88A6 100%);border-bottom:3px solid #000;padding:48px 20px;text-align:center;color:#fff}
#hero h1{font:bold 28pt 'Ubuntu Condensed',sans-serif;text-shadow:2px 2px 0 #000;letter-spacing:1px}
#hero h1 span{color:#b8ffd8}
#hero p{font-size:11pt;color:rgba(255,255,255,.85);margin:12px auto;max-width:560px;line-height:1.6}
#hero .cta{display:flex;gap:10px;justify-content:center;margin-top:20px;flex-wrap:wrap}
/* FOOTER */
#footer{background:#1a2a32;border-top:2px solid #000;padding:16px 20px;text-align:center;color:#4a7a8a;font-size:8pt;margin-top:32px}
/* TX STATUS */
.tx-pending{color:#8a7200;font-weight:bold}
.tx-completed{color:#1a7a3a;font-weight:bold}
.tx-rejected{color:#BF2C2C;font-weight:bold}
/* TABS */
.tabs{display:flex;gap:2px;border-bottom:2px solid var(--teal);margin-bottom:14px}
.tab-btn{padding:7px 16px;cursor:pointer;color:var(--fm);font-size:8.5pt;font-weight:bold;background:transparent;border:none;border-bottom:2px solid transparent;margin-bottom:-2px;transition:color .15s}
.tab-btn.active{color:var(--teal);border-bottom-color:var(--teal)}
.tab-btn:hover{color:var(--teal)}
.tab-pane{display:none}.tab-pane.active{display:block}
"""

def _nav(active='', user=None):
    links = [
        ('/', 'Inicio', ''),
        ('/pricing', 'Precios', 'pricing'),
        ('/dashboard', 'Mi Panel', 'dashboard'),
    ]
    nav_html = ''.join(
        f'<a href="{href}" class="{"active" if p==active else ""}">{label}</a>'
        for href, label, p in links
    )
    if user:
        av = f'<img src="https://cdn.discordapp.com/avatars/{user["discord_id"]}/{user["avatar"]}.png" onerror="this.style.display=\'none\'">' if user['avatar'] else ''
        badge = f'<span class="credits-badge">⬡ {user["credits"]:,} cr.</span>'
        right = f'{av}<span>{user["username"]}</span>{badge}'
        if user['is_admin']:
            right += '<a href="/admin" class="btn btn-or btn-sm" style="margin-left:6px">Admin</a>'
        right += '<a href="/logout" class="btn btn-rd btn-sm" style="margin-left:6px">Salir</a>'
        user_html = f'<div class="user-chip">{right}</div>'
    else:
        user_html = '<a href="/login" class="btn-login">Entrar con Discord</a>'
    return f'<div id="topnav"><div class="brand">HABBO <span>NET</span></div><nav>{nav_html}</nav>{user_html}</div>'

def _layout(title, body, active='', flash='', user=None):
    flash_html = f'<div class="container">{flash}</div>' if flash else ''
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — Habbo Net</title>
<style>{BASE_CSS}</style>
</head><body>
{_nav(active, user)}
{flash_html}
{body}
<div id="footer">Habbo Net &copy; 2025 &nbsp;|&nbsp; Habbo Hotel&reg; es marca de Sulake/Azerion &nbsp;|&nbsp; Plataforma independiente</div>
</body></html>"""

def _flash(msg, kind='ok'):
    return f'<div class="flash flash-{kind}">{msg}</div>'


# ── PUBLIC ROUTES ─────────────────────────────────────────────────────────────

@app.route('/')
def index():
    u = current_user()
    pkgs = db.all_packages()
    pkg_cards = ''
    for p in pkgs:
        tag = f'<span class="pkg-tag" style="background:{p["color"]}">{p["tag"]}</span>' if p['tag'] else ''
        bonus = f'+{p["bonus"]} bonus' if p['bonus'] else 'Sin bono'
        pkg_cards += f"""
        <div class="pkg-card">
          {tag}
          <div class="pkg-hdr" style="background:{p['color']}">
            <div class="pkg-name">{p['name']}</div>
            <div class="pkg-credits">{p['credits']:,}</div>
            <div class="pkg-bonus">{bonus} cr.</div>
          </div>
          <div class="pkg-body">
            <div class="pkg-price">{p['price_eur']:.2f}€ <span>/ pago único</span></div>
            <div style="font-size:8pt;color:var(--fm);text-align:center">{p['credits']+p['bonus']:,} créditos totales</div>
          </div>
          <div class="pkg-footer">
            <a href="/buy/{p['id']}" class="btn btn-teal btn-lg" style="width:100%;text-align:center;background:{p['color']}">Comprar</a>
          </div>
        </div>"""

    body = f"""
    <div id="hero">
      <h1>HABBO <span>BOT MANAGER</span></h1>
      <p>Automatiza tus bots de Habbo Hotel con el sistema más completo. Gestión multi-cuenta, proxies por grupo, control total desde web o app de escritorio.</p>
      <div class="cta">
        <a href="/pricing" class="btn btn-gr btn-lg">Ver Precios</a>
        <a href="/login" class="btn btn-teal btn-lg">Empezar Gratis</a>
      </div>
    </div>
    <div class="container">
      <div style="text-align:center;margin:24px 0 12px">
        <span style="font:bold 14pt 'Ubuntu Condensed',sans-serif;color:var(--dteal)">■ PAQUETES DE CRÉDITOS</span>
      </div>
      <div class="grid-4">{pkg_cards}</div>
      <div class="grid-3" style="margin-top:24px">
        <div class="card">
          <div class="card-hdr">⊞ Multi-cuenta</div>
          <div class="card-body" style="font-size:8.5pt;color:var(--fm);line-height:1.6">Gestiona cientos de cuentas simultáneamente desde un solo panel web o aplicación de escritorio.</div>
        </div>
        <div class="card">
          <div class="card-hdr">◈ Proxies por grupo</div>
          <div class="card-body" style="font-size:8.5pt;color:var(--fm);line-height:1.6">Organiza tus proxies en grupos independientes y asígnalos a conjuntos de bots con rotación automática.</div>
        </div>
        <div class="card">
          <div class="card-hdr">⊙ Control en tiempo real</div>
          <div class="card-body" style="font-size:8.5pt;color:var(--fm);line-height:1.6">SSE live updates, log viewer por bot, spam, movimiento, identidad y navigator desde el panel web.</div>
        </div>
      </div>
    </div>"""
    return _layout('Inicio', body, '', user=u)


@app.route('/pricing')
def pricing():
    u = current_user()
    pkgs = db.all_packages()
    rows = ''
    for p in pkgs:
        tag = f'<span class="badge badge-teal">{p["tag"]}</span>' if p['tag'] else ''
        rows += f"""
        <div class="pkg-card">
          <div class="pkg-hdr" style="background:{p['color']}">
            <div class="pkg-name">{p['name']} {tag}</div>
            <div class="pkg-credits">{p['credits']:,} cr.</div>
            <div class="pkg-bonus">{f"+{p['bonus']} bono" if p['bonus'] else "Sin bono"}</div>
          </div>
          <div class="pkg-body">
            <div class="pkg-price">{p['price_eur']:.2f}€</div>
            <ul style="font-size:8pt;color:var(--fm);line-height:2;list-style:none;padding:0">
              <li>✅ {p['credits']:,} créditos base</li>
              {'<li>🎁 +'+str(p["bonus"])+' créditos bono</li>' if p['bonus'] else ''}
              <li>✅ Total: <b>{p['credits']+p['bonus']:,} cr.</b></li>
              <li>✅ Sin caducidad</li>
              <li>✅ Soporte por Discord</li>
            </ul>
          </div>
          <div class="pkg-footer">
            <a href="/buy/{p['id']}" class="btn btn-lg" style="width:100%;text-align:center;background:{p['color']};color:#fff;border:2px solid #000">Comprar ahora</a>
          </div>
        </div>"""

    body = f"""
    <div class="container">
      <div class="card-hdr" style="border-radius:8px 8px 0 0;margin-top:16px">■ PLANES Y PRECIOS</div>
      <div class="grid-4" style="margin-top:14px">{rows}</div>
      <div class="card" style="margin-top:20px">
        <div class="card-hdr">❓ Preguntas frecuentes</div>
        <div class="card-body">
          <div class="grid-2" style="font-size:8.5pt;color:var(--fm);line-height:1.7">
            <div><b style="color:var(--fg)">¿Los créditos caducan?</b><br>No. Los créditos no tienen fecha de expiración.</div>
            <div><b style="color:var(--fg)">¿Cómo se paga?</b><br>El pago se confirma manualmente por el admin. Contacta por Discord tras comprar.</div>
            <div><b style="color:var(--fg)">¿Hay reembolsos?</b><br>Se estudia caso por caso. Contacta con soporte.</div>
            <div><b style="color:var(--fg)">¿Puedo usar la API?</b><br>Sí. Desde tu panel puedes generar API keys para integrar con tus scripts.</div>
          </div>
        </div>
      </div>
    </div>"""
    return _layout('Precios', body, 'pricing', user=u)


# ── DISCORD AUTH ──────────────────────────────────────────────────────────────

@app.route('/login')
def login():
    state = secrets.token_hex(16)
    session['oauth_state'] = state
    params = (
        f'?client_id={DISCORD_CLIENT_ID}'
        f'&redirect_uri={DISCORD_REDIRECT_URI}'
        f'&response_type=code'
        f'&scope=identify+email'
        f'&state={state}'
        f'&prompt=none'
    )
    return redirect(DISCORD_OAUTH + params)


@app.route('/auth/callback')
def auth_callback():
    error = request.args.get('error')
    if error:
        return redirect('/?flash=err:' + error)

    code  = request.args.get('code', '')
    state = request.args.get('state', '')
    if state != session.pop('oauth_state', None):
        return redirect('/?flash=err:state_mismatch')

    # intercambiar code por token
    token_r = _req.post(DISCORD_TOKEN, data={
        'client_id':     DISCORD_CLIENT_ID,
        'client_secret': DISCORD_CLIENT_SECRET,
        'grant_type':    'authorization_code',
        'code':          code,
        'redirect_uri':  DISCORD_REDIRECT_URI,
    }, headers={'Content-Type': 'application/x-www-form-urlencoded'})

    if token_r.status_code != 200:
        return redirect('/?flash=err:token_fail')

    token_data = token_r.json()
    access_token = token_data.get('access_token')

    # obtener info del usuario
    user_r = _req.get(f'{DISCORD_API}/users/@me',
                      headers={'Authorization': f'Bearer {access_token}'})
    if user_r.status_code != 200:
        return redirect('/?flash=err:user_fail')

    d = user_r.json()
    user = db.upsert_user(
        discord_id    = d['id'],
        username      = d['username'],
        discriminator = d.get('discriminator', '0'),
        avatar        = d.get('avatar'),
        email         = d.get('email'),
    )

    # elevar primer admin si coincide
    if FIRST_ADMIN_ID and d['id'] == FIRST_ADMIN_ID and not user['is_admin']:
        db.set_admin(user['id'], True)
        user = db.get_user(user['id'])

    session['user_id'] = user['id']
    next_url = session.pop('next', '/dashboard')
    return redirect(next_url)


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


# ── USER DASHBOARD ────────────────────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    u = current_user()
    txs = db.get_transactions(u['id'], limit=30)
    keys = db.list_api_keys(u['id'])
    flash_msg = ''
    new_key = session.pop('new_api_key', None)
    if new_key:
        flash_msg = _flash(f'🔑 Tu nueva API key (guárdala, no se mostrará de nuevo):<br><code style="background:#1a2a32;color:#b8ffd8;padding:4px 8px;border-radius:4px;font-size:9pt;word-break:break-all">{new_key}</code>', 'info')

    tx_rows = ''
    for t in txs:
        delta_str = f'+{t["credits_delta"]:,}' if t['credits_delta'] > 0 else f'{t["credits_delta"]:,}'
        delta_color = 'var(--gr)' if t['credits_delta'] > 0 else 'var(--rd)'
        status_cls = {'pending': 'tx-pending', 'completed': 'tx-completed', 'rejected': 'tx-rejected'}.get(t['status'], '')
        type_label = {'purchase': '🛒 Compra', 'grant': '🎁 Admin', 'consume': '⚡ Uso', 'refund': '↩ Reembolso'}.get(t['type'], t['type'])
        tx_rows += f"""<tr>
          <td style="color:var(--fm);font-size:7.5pt">{t['created_at'][:16]}</td>
          <td>{type_label}</td>
          <td>{t['pkg_name'] or t['description'] or '—'}</td>
          <td style="font-weight:bold;color:{delta_color}">{delta_str}</td>
          <td style="color:var(--fm)">{t['credits_after']:,}</td>
          <td><span class="{status_cls}">{t['status']}</span></td>
        </tr>"""

    key_rows = ''
    for k in keys:
        status = '<span class="badge badge-gr">Activa</span>' if k['is_active'] else '<span class="badge badge-rd">Revocada</span>'
        last = k['last_used'][:16] if k['last_used'] else 'Nunca'
        key_rows += f"""<tr>
          <td><code style="font-size:8pt">{k['key_prefix']}…</code></td>
          <td>{k['name']}</td>
          <td>{k['created_at'][:10]}</td>
          <td>{last}</td>
          <td>{status}</td>
          <td>{'<form method="post" action="/dashboard/revoke-key" style="display:inline"><input type="hidden" name="key_id" value="'+str(k["id"])+'"><button type="submit" class="btn btn-rd btn-sm">Revocar</button></form>' if k['is_active'] else ''}</td>
        </tr>"""

    body = f"""
    <div class="container">
      {flash_msg}
      <div class="grid-4" style="margin-bottom:16px">
        <div class="stat-box"><div class="stat-val">⬡ {u['credits']:,}</div><div class="stat-lbl">Créditos disponibles</div></div>
        <div class="stat-box"><div class="stat-val">{len(txs)}</div><div class="stat-lbl">Transacciones</div></div>
        <div class="stat-box"><div class="stat-val">{len(keys)}</div><div class="stat-lbl">API Keys</div></div>
        <div class="stat-box" style="align-items:center;justify-content:center">
          <a href="/pricing" class="btn btn-gr btn-lg">+ Comprar créditos</a>
        </div>
      </div>

      <div class="tabs">
        <button class="tab-btn active" onclick="switchTab(this,'tab-tx')">📋 Transacciones</button>
        <button class="tab-btn" onclick="switchTab(this,'tab-keys')">🔑 API Keys</button>
        <button class="tab-btn" onclick="switchTab(this,'tab-docs')">📖 Documentación API</button>
      </div>

      <div id="tab-tx" class="tab-pane active">
        <div class="card">
          <div class="card-hdr">■ HISTORIAL DE CRÉDITOS</div>
          <div class="card-body" style="padding:0">
            <table class="tbl">
              <thead><tr><th>Fecha</th><th>Tipo</th><th>Descripción</th><th>Créditos</th><th>Saldo</th><th>Estado</th></tr></thead>
              <tbody>{''.join([tx_rows]) if tx_rows else '<tr><td colspan="6" style="text-align:center;color:var(--fm);padding:16px">Sin transacciones aún</td></tr>'}</tbody>
            </table>
          </div>
        </div>
      </div>

      <div id="tab-keys" class="tab-pane">
        <div class="card">
          <div class="card-hdr">■ API KEYS</div>
          <div class="card-body">
            <form method="post" action="/dashboard/create-key" style="display:flex;gap:8px;margin-bottom:12px;align-items:flex-end">
              <div class="form-group" style="flex:1;margin:0">
                <label class="lbl">Nombre de la key</label>
                <input type="text" name="key_name" placeholder="Mi script, Bot 1..." style="width:100%">
              </div>
              <button type="submit" class="btn btn-gr">+ Crear Key</button>
            </form>
            <table class="tbl">
              <thead><tr><th>Prefix</th><th>Nombre</th><th>Creada</th><th>Último uso</th><th>Estado</th><th></th></tr></thead>
              <tbody>{''.join([key_rows]) if key_rows else '<tr><td colspan="6" style="text-align:center;color:var(--fm);padding:14px">Sin API keys — crea una arriba</td></tr>'}</tbody>
            </table>
          </div>
        </div>
      </div>

      <div id="tab-docs" class="tab-pane">
        <div class="card">
          <div class="card-hdr">■ DOCUMENTACIÓN DE LA API</div>
          <div class="card-body">
            <p style="color:var(--fm);font-size:8.5pt;margin-bottom:12px">Autenticación: header <code>Authorization: Bearer &lt;api_key&gt;</code> o parámetro <code>?api_key=...</code></p>
            <div style="display:flex;flex-direction:column;gap:12px">
              <div style="background:#1a2a32;border-radius:6px;padding:12px;border:1px solid #3C88A6">
                <div style="color:#b8ffd8;font-size:8pt;font-weight:bold;margin-bottom:6px">GET /api/v1/me</div>
                <div style="color:#9cc8d8;font-size:7.5pt">Devuelve info del usuario y saldo de créditos.</div>
                <pre style="color:#d8f0f8;font-size:7.5pt;margin-top:6px">{{ "discord_id": "...", "username": "...", "credits": 150 }}</pre>
              </div>
              <div style="background:#1a2a32;border-radius:6px;padding:12px;border:1px solid #3C88A6">
                <div style="color:#b8ffd8;font-size:8pt;font-weight:bold;margin-bottom:6px">POST /api/v1/consume</div>
                <div style="color:#9cc8d8;font-size:7.5pt">Consume créditos del usuario. Body JSON: <code style="color:#ffd8b8">{{ "amount": 5, "description": "Bot session" }}</code></div>
                <pre style="color:#d8f0f8;font-size:7.5pt;margin-top:6px">{{ "ok": true, "credits_used": 5, "credits_remaining": 145 }}</pre>
              </div>
              <div style="background:#1a2a32;border-radius:6px;padding:12px;border:1px solid #3C88A6">
                <div style="color:#b8ffd8;font-size:8pt;font-weight:bold;margin-bottom:6px">GET /api/v1/check?amount=10</div>
                <div style="color:#9cc8d8;font-size:7.5pt">Comprueba si el usuario tiene suficientes créditos sin consumirlos.</div>
                <pre style="color:#d8f0f8;font-size:7.5pt;margin-top:6px">{{ "ok": true, "has_enough": true, "credits": 150 }}</pre>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <script>
    function switchTab(btn,id){{
      document.querySelectorAll('.tab-pane').forEach(p=>p.classList.remove('active'));
      document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
      document.getElementById(id).classList.add('active');
      btn.classList.add('active');
    }}
    </script>"""
    return _layout('Mi Panel', body, 'dashboard', user=u)


@app.route('/dashboard/create-key', methods=['POST'])
@login_required
def create_key():
    u = current_user()
    name = request.form.get('key_name', 'API Key').strip() or 'API Key'
    raw = db.create_api_key(u['id'], name)
    session['new_api_key'] = raw
    return redirect('/dashboard#tab-keys')


@app.route('/dashboard/revoke-key', methods=['POST'])
@login_required
def revoke_key():
    u = current_user()
    key_id = request.form.get('key_id', 0)
    db.revoke_api_key(int(key_id), u['id'])
    return redirect('/dashboard#tab-keys')


# ── SHOP / BUY ────────────────────────────────────────────────────────────────

@app.route('/buy/<int:pkg_id>')
@login_required
def buy(pkg_id):
    u = current_user()
    pkg = db.get_package(pkg_id)
    if not pkg:
        return redirect('/pricing')

    total = pkg['credits'] + pkg['bonus']
    body = f"""
    <div class="container" style="max-width:560px">
      <div class="card">
        <div class="card-hdr" style="background:{pkg['color']}">■ CONFIRMAR COMPRA — {pkg['name']}</div>
        <div class="card-body">
          <div style="display:flex;gap:16px;align-items:center;margin-bottom:16px;padding:12px;background:#e8e4d8;border-radius:6px;border:1px solid #3C88A6">
            <div style="text-align:center;flex:1">
              <div style="font-size:22pt;font-weight:bold;color:{pkg['color']}">{total:,}</div>
              <div style="font-size:8pt;color:var(--fm)">créditos totales</div>
            </div>
            <div style="width:1px;background:#3C88A6;align-self:stretch"></div>
            <div style="text-align:center;flex:1">
              <div style="font-size:22pt;font-weight:bold">{pkg['price_eur']:.2f}€</div>
              <div style="font-size:8pt;color:var(--fm)">pago único</div>
            </div>
          </div>
          <div class="flash flash-info" style="font-size:8.5pt">
            ℹ️ <b>Proceso de pago manual:</b> Al confirmar, se creará un pedido pendiente.
            Contacta con el administrador por Discord con tu ID de pedido para completar el pago.
            Los créditos se añadirán una vez confirmado.
          </div>
          <form method="post" action="/buy/{pkg_id}/confirm" style="margin-top:14px;display:flex;gap:8px;justify-content:flex-end">
            <a href="/pricing" class="btn btn-rd">Cancelar</a>
            <button type="submit" class="btn btn-gr btn-lg">✅ Confirmar pedido</button>
          </form>
        </div>
      </div>
    </div>"""
    return _layout(f'Comprar {pkg["name"]}', body, user=u)


@app.route('/buy/<int:pkg_id>/confirm', methods=['POST'])
@login_required
def buy_confirm(pkg_id):
    u = current_user()
    pkg = db.get_package(pkg_id)
    if not pkg:
        return redirect('/pricing')
    tx_id = db.create_purchase_tx(u['id'], pkg_id)
    body = f"""
    <div class="container" style="max-width:560px">
      <div class="card">
        <div class="card-hdr" style="background:#1a7a3a">✅ PEDIDO CREADO</div>
        <div class="card-body" style="text-align:center;padding:24px">
          <div style="font-size:32pt;margin-bottom:8px">📦</div>
          <div style="font-size:14pt;font-weight:bold;margin-bottom:8px">Pedido #{tx_id}</div>
          <div style="font-size:9pt;color:var(--fm);margin-bottom:16px;line-height:1.7">
            Tu pedido ha sido registrado. Para completar el pago,<br>
            contacta con el administrador en Discord e indica tu<br>
            <b>ID de pedido: #{tx_id}</b> y tu usuario: <b>{u['username']}</b>
          </div>
          <a href="/dashboard" class="btn btn-teal">Ir a mi panel</a>
        </div>
      </div>
    </div>"""
    return _layout('Pedido creado', body, user=u)


# ── ADMIN PANEL ───────────────────────────────────────────────────────────────

@app.route('/admin')
@admin_required
def admin():
    u = current_user()
    stats = db.admin_stats()
    pending = db.pending_transactions()
    users = db.all_users(limit=50)

    pending_rows = ''
    for t in pending:
        pkg_info = f'{t["pkg_name"]} — {t["price_eur"]:.2f}€' if t['pkg_name'] else t['description'] or '—'
        pending_rows += f"""<tr>
          <td>#{t['id']}</td>
          <td><b>{t['username']}</b><br><span style="font-size:7pt;color:var(--fm)">{t['discord_id']}</span></td>
          <td>{pkg_info}</td>
          <td style="color:var(--gr);font-weight:bold">+{t['credits_delta']:,}</td>
          <td style="color:var(--fm);font-size:7.5pt">{t['created_at'][:16]}</td>
          <td style="display:flex;gap:4px">
            <form method="post" action="/admin/approve/{t['id']}">
              <button class="btn btn-gr btn-sm">✅ Aprobar</button>
            </form>
            <form method="post" action="/admin/reject/{t['id']}">
              <button class="btn btn-rd btn-sm">✕ Rechazar</button>
            </form>
          </td>
        </tr>"""

    user_rows = ''
    for usr in users:
        admin_badge = '<span class="badge badge-or">Admin</span>' if usr['is_admin'] else ''
        ban_badge = '<span class="badge badge-rd">Baneado</span>' if usr['is_banned'] else ''
        av = f'<img src="https://cdn.discordapp.com/avatars/{usr["discord_id"]}/{usr["avatar"]}.png" style="width:20px;height:20px;border-radius:50%;vertical-align:middle;margin-right:4px" onerror="this.style.display=\'none\'">' if usr['avatar'] else ''
        user_rows += f"""<tr>
          <td>{av}<b>{usr['username']}</b> {admin_badge} {ban_badge}</td>
          <td style="font-size:7.5pt;color:var(--fm)">{usr['discord_id']}</td>
          <td style="font-weight:bold;color:var(--teal)">{usr['credits']:,}</td>
          <td style="color:var(--fm);font-size:7.5pt">{usr['created_at'][:10]}</td>
          <td style="display:flex;gap:3px;flex-wrap:wrap">
            <form method="post" action="/admin/grant" style="display:flex;gap:3px">
              <input type="hidden" name="user_id" value="{usr['id']}">
              <input type="number" name="amount" placeholder="Cr." style="width:60px;padding:3px 5px;font-size:7.5pt">
              <input type="text" name="note" placeholder="Nota" style="width:80px;padding:3px 5px;font-size:7.5pt">
              <button class="btn btn-gr btn-sm">+ Grant</button>
            </form>
            <form method="post" action="/admin/toggle-admin">
              <input type="hidden" name="user_id" value="{usr['id']}">
              <button class="btn btn-or btn-sm">{'Quitar Admin' if usr['is_admin'] else 'Hacer Admin'}</button>
            </form>
            <form method="post" action="/admin/toggle-ban">
              <input type="hidden" name="user_id" value="{usr['id']}">
              <button class="btn btn-rd btn-sm">{'Desbanear' if usr['is_banned'] else 'Banear'}</button>
            </form>
          </td>
        </tr>"""

    body = f"""
    <div class="container">
      <div class="grid-4" style="margin-bottom:16px">
        <div class="stat-box"><div class="stat-val">{stats['total_users']}</div><div class="stat-lbl">Usuarios totales</div></div>
        <div class="stat-box"><div class="stat-val">{stats['total_credits']:,}</div><div class="stat-lbl">Créditos en circulación</div></div>
        <div class="stat-box"><div class="stat-val" style="color:{'var(--rd)' if stats['pending_tx'] else 'var(--gr)'}">{'⚠ ' if stats['pending_tx'] else ''}{stats['pending_tx']}</div><div class="stat-lbl">Pedidos pendientes</div></div>
        <div class="stat-box"><div class="stat-val">{stats['new_today']}</div><div class="stat-lbl">Nuevos hoy</div></div>
      </div>

      <div class="tabs">
        <button class="tab-btn active" onclick="switchTab(this,'tab-pending')">
          ⏳ Pedidos pendientes {'<span class="badge badge-rd">'+str(stats['pending_tx'])+'</span>' if stats['pending_tx'] else ''}
        </button>
        <button class="tab-btn" onclick="switchTab(this,'tab-users')">👥 Usuarios</button>
        <button class="tab-btn" onclick="switchTab(this,'tab-packages')">📦 Paquetes</button>
      </div>

      <div id="tab-pending" class="tab-pane active">
        <div class="card">
          <div class="card-hdr">■ PEDIDOS PENDIENTES DE APROBACIÓN</div>
          <div class="card-body" style="padding:0">
            <table class="tbl">
              <thead><tr><th>#</th><th>Usuario</th><th>Paquete</th><th>Créditos</th><th>Fecha</th><th>Acción</th></tr></thead>
              <tbody>{''.join([pending_rows]) if pending_rows else '<tr><td colspan="6" style="text-align:center;color:var(--fm);padding:16px">Sin pedidos pendientes ✅</td></tr>'}</tbody>
            </table>
          </div>
        </div>
      </div>

      <div id="tab-users" class="tab-pane">
        <div class="card">
          <div class="card-hdr">■ GESTIÓN DE USUARIOS</div>
          <div class="card-body" style="padding:0">
            <table class="tbl">
              <thead><tr><th>Usuario</th><th>Discord ID</th><th>Créditos</th><th>Registro</th><th>Acciones</th></tr></thead>
              <tbody>{user_rows}</tbody>
            </table>
          </div>
        </div>
      </div>

      <div id="tab-packages" class="tab-pane">
        <div class="card">
          <div class="card-hdr">■ PAQUETES DE CRÉDITOS</div>
          <div class="card-body">
            <form method="post" action="/admin/package/save" style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr 1fr 1fr auto;gap:8px;align-items:end;margin-bottom:12px">
              <div><label class="lbl">Nombre</label><input type="text" name="name" placeholder="Pro" required></div>
              <div><label class="lbl">Créditos</label><input type="number" name="credits" placeholder="500" min="1" required></div>
              <div><label class="lbl">Bono</label><input type="number" name="bonus" placeholder="50" min="0"></div>
              <div><label class="lbl">Precio (€)</label><input type="number" name="price_eur" placeholder="17.99" step="0.01" min="0" required></div>
              <div><label class="lbl">Color hex</label><input type="text" name="color" placeholder="#1a7a3a"></div>
              <div><label class="lbl">Tag</label><input type="text" name="tag" placeholder="POPULAR"></div>
              <div><label class="lbl">&nbsp;</label><button class="btn btn-gr" type="submit">+ Crear</button></div>
            </form>
            <table class="tbl" id="pkg-tbl">
              <thead><tr><th>ID</th><th>Nombre</th><th>Créditos</th><th>Bono</th><th>Precio</th><th>Tag</th></tr></thead>
              <tbody id="pkg-tbody"></tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
    <script>
    function switchTab(btn,id){{
      document.querySelectorAll('.tab-pane').forEach(p=>p.classList.remove('active'));
      document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
      document.getElementById(id).classList.add('active');
      btn.classList.add('active');
    }}
    // load packages table
    fetch('/api/admin/packages').then(r=>r.json()).then(d=>{{
      const tb = document.getElementById('pkg-tbody');
      tb.innerHTML = d.packages.map((p,i)=>`<tr>
        <td>#${{p.id}}</td><td><b style="color:${{p.color}}">${{p.name}}</b></td>
        <td>${{p.credits.toLocaleString()}}</td><td>${{p.bonus}}</td>
        <td>${{p.price_eur.toFixed(2)}}€</td><td>${{p.tag||'—'}}</td>
      </tr>`).join('');
    }});
    </script>"""
    return _layout('Admin', body, user=u)


@app.route('/admin/approve/<int:tx_id>', methods=['POST'])
@admin_required
def admin_approve(tx_id):
    db.approve_tx(tx_id, admin_ref='admin_web')
    return redirect('/admin')


@app.route('/admin/reject/<int:tx_id>', methods=['POST'])
@admin_required
def admin_reject(tx_id):
    db.reject_tx(tx_id, reason='admin_rejected')
    return redirect('/admin')


@app.route('/admin/grant', methods=['POST'])
@admin_required
def admin_grant():
    user_id = int(request.form.get('user_id', 0))
    amount  = int(request.form.get('amount', 0))
    note    = request.form.get('note', 'Admin grant').strip() or 'Admin grant'
    if user_id and amount:
        db.add_credits(user_id, amount, description=note, tx_type='grant')
    return redirect('/admin#tab-users')


@app.route('/admin/toggle-admin', methods=['POST'])
@admin_required
def admin_toggle_admin():
    uid = int(request.form.get('user_id', 0))
    usr = db.get_user(uid)
    if usr: db.set_admin(uid, not usr['is_admin'])
    return redirect('/admin#tab-users')


@app.route('/admin/toggle-ban', methods=['POST'])
@admin_required
def admin_toggle_ban():
    uid = int(request.form.get('user_id', 0))
    usr = db.get_user(uid)
    if usr: db.ban_user(uid, not usr['is_banned'])
    return redirect('/admin#tab-users')


@app.route('/admin/package/save', methods=['POST'])
@admin_required
def admin_package_save():
    db.upsert_package(
        name      = request.form.get('name','').strip(),
        credits   = int(request.form.get('credits', 0)),
        bonus     = int(request.form.get('bonus', 0) or 0),
        price_eur = float(request.form.get('price_eur', 0)),
        color     = request.form.get('color', '#30728C').strip() or '#30728C',
        tag       = request.form.get('tag', '').strip(),
    )
    return redirect('/admin#tab-packages')


@app.route('/api/admin/packages')
@admin_required
def api_admin_packages():
    return jsonify({'packages': [dict(p) for p in db.all_packages()]})


# ── REST API (para integración con bot manager) ───────────────────────────────

@app.route('/api/v1/me')
def api_me():
    u = api_auth()
    if not u:
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 401
    return jsonify({
        'ok':          True,
        'discord_id':  u['discord_id'],
        'username':    u['username'],
        'credits':     u['credits'],
        'is_admin':    bool(u['is_admin']),
        'is_banned':   bool(u['is_banned']),
    })


@app.route('/api/v1/check')
def api_check():
    u = api_auth()
    if not u:
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 401
    amount = int(request.args.get('amount', 1))
    return jsonify({
        'ok':          True,
        'has_enough':  u['credits'] >= amount,
        'credits':     u['credits'],
        'requested':   amount,
    })


@app.route('/api/v1/consume', methods=['POST'])
def api_consume():
    u = api_auth()
    if not u:
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 401
    data   = request.get_json(silent=True) or {}
    amount = int(data.get('amount', 1))
    desc   = data.get('description', 'API consume')
    if amount <= 0:
        return jsonify({'ok': False, 'error': 'amount must be > 0'}), 400
    ok, remaining = db.consume_credits(u['id'], amount, desc)
    if not ok:
        return jsonify({'ok': False, 'error': 'Insufficient credits', 'credits': remaining}), 402
    return jsonify({'ok': True, 'credits_used': amount, 'credits_remaining': remaining})


@app.route('/api/v1/transactions')
def api_transactions():
    u = api_auth()
    if not u:
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 401
    limit = min(int(request.args.get('limit', 20)), 100)
    txs = db.get_transactions(u['id'], limit=limit)
    return jsonify({'ok': True, 'transactions': [
        {'id': t['id'], 'type': t['type'], 'delta': t['credits_delta'],
         'balance': t['credits_after'], 'description': t['description'],
         'status': t['status'], 'date': t['created_at']}
        for t in txs
    ]})


# ── MISC ──────────────────────────────────────────────────────────────────────

def page_error(msg):
    body = f'<div class="container" style="text-align:center;padding:48px"><div style="font-size:42pt">⚠</div><div style="font-size:14pt;color:var(--rd);margin:12px 0">{msg}</div><a href="/" class="btn btn-teal">Volver al inicio</a></div>'
    return _layout('Error', body, user=current_user())


@app.errorhandler(404)
def err404(e):
    return page_error('404 — Página no encontrada'), 404


@app.errorhandler(500)
def err500(e):
    return page_error('500 — Error interno del servidor'), 500


# ── ENTRY POINT ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print(f'[SHOP] Iniciando en http://0.0.0.0:{SHOP_PORT}')
    print(f'[SHOP] Discord OAuth redirect: {DISCORD_REDIRECT_URI}')
    if DISCORD_CLIENT_ID == 'YOUR_CLIENT_ID':
        print('[SHOP] ⚠  Configura DISCORD_CLIENT_ID / shop_config.json antes de usar OAuth')
    app.run(debug=False, host='0.0.0.0', port=SHOP_PORT, threaded=True)
