#!/usr/bin/env python3
"""
web.py — NET-CONTROLLER | Habbo Bot Manager (Flask Web Interface)
Uso standalone: python web.py  →  http://localhost:5000
O se lanza automáticamente desde main.py
"""

import json, os, time, random, threading
from flask import Flask, request, jsonify, Response

import state
from bot_instance import BotInstance
from habbo_client import HabboClientGUI
from sso_retriever import get_sso_ticket
import constants as const

# =============================================================================
app = Flask(__name__, static_folder=None)
app.secret_key = 'habbonetcontroller'


# =============================================================================
# HELPERS
# =============================================================================

def _get_hotel(inst: BotInstance) -> dict:
    if isinstance(inst.account_data, list) and inst.account_data:
        h = inst.account_data[0].get('hotel') if isinstance(inst.account_data[0], dict) else None
        if h: return const.HOTELS.get(h, const.HOTELS[state.hotel])
    return const.HOTELS.get(state.hotel, const.HOTELS['habbo.com'])


def _connect_bot(inst: BotInstance):
    def run():
        try:
            inst.set_status('Preparing')
            proxy = state.next_proxy()
            inst.proxy_address = proxy
            hotel = _get_hotel(inst)
            inst.add_log(f'Hotel: {hotel["name"]} | Proxy: {proxy}')
            state.push_sse({'type': 'status', 'index': inst.index, 'status': inst.status})

            sso_proxy = None
            if proxy != 'DIRECT':
                parts = proxy.split(':')
                sso_proxy = (f'socks5://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}'
                             if len(parts) == 4 else f'socks5://{parts[0]}:{parts[1]}')

            ticket = get_sso_ticket(inst.account_data, sso_proxy, base_url=hotel['base_url'])
            if not ticket:
                inst.set_status('Failed'); inst.add_log('❌ SSO ticket failed.')
                state.push_sse({'type': 'status', 'index': inst.index, 'status': 'Failed'}); return

            inst.sso_ticket = ticket; inst.set_status('Connecting')
            state.push_sse({'type': 'status', 'index': inst.index, 'status': 'Connecting'})

            def _log(m):
                inst.add_log(m)
                state.push_sse({'type': 'log', 'index': inst.index, 'msg': m})

            def _status(s):
                inst.set_status(s)
                state.push_sse({'type': 'status', 'index': inst.index, 'status': s})

            client = HabboClientGUI(
                sso_ticket=ticket, bot_index=inst.index, proxy=proxy,
                logger=_log, status_updater=_status,
                mute_updater=inst.set_mute_status,
                admin_auto_leave_enabled=True,
                hotel_config=hotel,
            )
            inst.client = client
            ok = client.connect()
            inst.set_status('Connected' if ok else 'Failed')
            state.push_sse({'type': 'status', 'index': inst.index, 'status': inst.status})
        except Exception as e:
            inst.set_status('Error'); inst.add_log(f'❌ {e}')
            state.push_sse({'type': 'status', 'index': inst.index, 'status': 'Error'})
    threading.Thread(target=run, daemon=True).start()


def _get_clients(target: str = 'all') -> list:
    if target == 'all':
        return [b.client for b in state.bots if b.client and b.client.connected]
    try:
        idx = int(target)
        b = next((x for x in state.bots if x.index == idx), None)
        return [b.client] if b and b.client and b.client.connected else []
    except:
        return []


def _bot_dict(b: BotInstance) -> dict:
    hotel_key = state.hotel
    if isinstance(b.account_data, list) and b.account_data and isinstance(b.account_data[0], dict):
        hotel_key = b.account_data[0].get('hotel', state.hotel)
    return {
        'index':  b.index,
        'name':   b.get_display_name().split(' [')[0],
        'status': b.status,
        'hotel':  hotel_key,
        'proxy':  (b.proxy_address or '-').split(':')[0],
        'log':    list(b.log_buffer)[-20:],
    }


# =============================================================================
# SSE
# =============================================================================
@app.route('/stream')
def stream():
    def generate():
        last = 0
        q = state.sse_q
        while True:
            snap = list(q)
            while last < len(snap):
                yield f'data: {snap[last]}\n\n'
                last += 1
            yield ': ping\n\n'
            time.sleep(1)
    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


# =============================================================================
# BOT STATUS
# =============================================================================
@app.route('/api/bots')
def api_bots():
    conn = sum(1 for b in state.bots if b.status == 'Connected')
    return jsonify({'bots': [_bot_dict(b) for b in state.bots],
                    'connected': conn, 'total': len(state.bots)})

@app.route('/api/bots/<int:idx>/log')
def api_bot_log(idx):
    b = next((x for x in state.bots if x.index == idx), None)
    if not b: return jsonify({'error': 'not found'}), 404
    return jsonify({'log': list(b.log_buffer)})


# =============================================================================
# ACCOUNTS
# =============================================================================

def _parse_cookie_string(raw: str) -> tuple[str, str]:
    """Extrae session.id y browser_token de un string de cookies del navegador."""
    for line in raw.splitlines():
        if line.strip().lower().startswith('cookie:'):
            raw = line.strip(); break
    if raw.lower().startswith('cookie:'):
        raw = raw[7:].strip()
    cookies = {}
    for part in raw.split(';'):
        part = part.strip()
        if '=' in part:
            k, _, v = part.partition('=')
            cookies[k.strip()] = v.strip()
    return cookies.get('session.id', ''), cookies.get('browser_token', '')


@app.route('/api/accounts/load', methods=['POST'])
def api_accounts_load():
    data = request.get_json()
    raw  = data.get('data') if data else None
    if not raw: return jsonify({'error': 'No data'}), 400
    try:
        accounts = json.loads(raw)
        state.bots.clear()
        state.bots.extend(BotInstance(acc, i+1) for i, acc in enumerate(accounts))
        return jsonify({'ok': True, 'count': len(state.bots)})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/accounts/add', methods=['POST'])
def api_accounts_add():
    """Agrega una cuenta individual con cookies del navegador."""
    data         = request.get_json(silent=True) or {}
    name         = data.get('name', '').strip()
    hotel        = data.get('hotel', state.hotel)
    cookie_str   = data.get('cookie_string', '')
    session_id   = data.get('session_id', '').strip()
    browser_token= data.get('browser_token', '').strip()

    # Si viene cookie_string, parsear automáticamente
    if cookie_str and not session_id:
        session_id, browser_token = _parse_cookie_string(cookie_str)

    if not session_id or not browser_token:
        return jsonify({'ok': False, 'error': 'session.id y browser_token requeridos'}), 400

    entry = []
    meta  = {}
    if name:  meta['name']  = name
    if hotel: meta['hotel'] = hotel
    if meta:  entry.append(meta)
    entry.append({'name': 'session.id',    'value': session_id})
    entry.append({'name': 'browser_token', 'value': browser_token})

    idx = max((b.index for b in state.bots), default=0) + 1
    state.bots.append(BotInstance(entry, idx))

    # Guardar accounts.json automáticamente
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), const.ACCOUNTS_FILE)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump([b.account_data for b in state.bots], f, indent=2, ensure_ascii=False)
    except Exception as e:
        return jsonify({'ok': True, 'saved': False, 'warning': str(e), 'index': idx})

    return jsonify({'ok': True, 'saved': True, 'index': idx,
                    'name': name or f'Bot #{idx}'})


@app.route('/api/accounts/save', methods=['POST'])
def api_accounts_save():
    """Guarda state.bots → accounts.json."""
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), const.ACCOUNTS_FILE)
        data = [b.account_data for b in state.bots]
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return jsonify({'ok': True, 'count': len(data)})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/accounts/remove', methods=['POST'])
def api_accounts_remove():
    """Elimina una cuenta por índice."""
    data = request.get_json(silent=True) or {}
    idx  = int(data.get('index', 0))
    inst = next((b for b in state.bots if b.index == idx), None)
    if not inst: return jsonify({'ok': False, 'error': 'not found'}), 404
    if inst.client and inst.client.connected:
        threading.Thread(target=inst.client.disconnect, daemon=True).start()
    state.bots.remove(inst)
    for i, b in enumerate(state.bots): b.index = i + 1
    return jsonify({'ok': True})


@app.route('/api/accounts/parse_cookie', methods=['POST'])
def api_parse_cookie():
    """Parsea un cookie string y devuelve session.id + browser_token."""
    data = request.get_json(silent=True) or {}
    raw  = data.get('cookie_string', '')
    sid, btk = _parse_cookie_string(raw)
    return jsonify({'session_id': sid, 'browser_token': btk,
                    'ok': bool(sid and btk)})


# =============================================================================
# PROXIES
# =============================================================================
@app.route('/api/proxies', methods=['GET'])
def api_proxies_get():
    return jsonify({'proxies': list(state.proxies), 'count': len(state.proxies)})

@app.route('/api/proxies/load', methods=['POST'])
def api_proxies_load():
    data = request.get_json()
    raw  = data.get('data') if data else None
    if not raw: return jsonify({'error': 'No data'}), 400
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    state.proxies.clear(); state.proxies.extend(lines)
    state.reset_proxy_index()
    return jsonify({'ok': True, 'count': len(state.proxies)})

@app.route('/api/proxies/save', methods=['POST'])
def api_proxies_save():
    data = request.get_json()
    raw  = data.get('data', '') if data else ''
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    state.proxies.clear(); state.proxies.extend(lines)
    state.reset_proxy_index()
    try:
        with open('proxies.txt', 'w') as f: f.write('\n'.join(lines))
    except: pass
    return jsonify({'ok': True, 'count': len(lines)})


# =============================================================================
# CONNECTION
# =============================================================================
@app.route('/api/connect', methods=['POST'])
def api_connect():
    data   = request.get_json(silent=True) or {}
    target = str(data.get('target', 'all'))
    split  = int(data.get('split', 0) or 0)

    def run_all():
        count = 0
        for inst in list(state.bots):
            if target != 'all' and str(inst.index) != target: continue
            if inst.status in ('Connected', 'Connecting', 'Preparing'): continue
            _connect_bot(inst)
            count += 1
            time.sleep(2.0 if (split > 0 and count % split == 0) else 1.5)
    threading.Thread(target=run_all, daemon=True).start()
    return jsonify({'ok': True})

@app.route('/api/disconnect', methods=['POST'])
def api_disconnect():
    data   = request.get_json(silent=True) or {}
    target = str(data.get('target', 'all'))
    for b in list(state.bots):
        if target != 'all' and str(b.index) != target: continue
        if b.client: threading.Thread(target=b.client.disconnect, daemon=True).start()
        b.set_status('Disconnected')
    return jsonify({'ok': True})


# =============================================================================
# HOTEL
# =============================================================================
@app.route('/api/hotel', methods=['GET', 'POST'])
def api_hotel():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        h = data.get('hotel', 'habbo.com')
        if h in const.HOTELS: state.hotel = h
        return jsonify({'ok': True, 'hotel': state.hotel})
    return jsonify({'hotel': state.hotel, 'hotels': list(const.HOTELS.keys()),
                    'names': {k: v['name'] for k, v in const.HOTELS.items()}})


@app.route('/api/headers/refresh', methods=['POST'])
def api_headers_refresh():
    """Recarga los IDs de paquetes desde api.sulek.dev en tiempo real."""
    res = const.fetch_and_apply_latest_headers(verbose=True)
    return jsonify(res)


# =============================================================================
# PROXY PER-BOT
# =============================================================================

@app.route('/api/bots/<int:idx>/proxy', methods=['POST'])
def api_bot_set_proxy(idx):
    """Asigna un proxy concreto a un bot."""
    data  = request.get_json(silent=True) or {}
    proxy = data.get('proxy', 'DIRECT').strip() or 'DIRECT'
    inst  = next((b for b in state.bots if b.index == idx), None)
    if not inst:
        return jsonify({'ok': False, 'error': 'bot not found'}), 404
    inst.proxy_address = proxy
    inst.add_log(f'Proxy → {proxy}')
    state.push_sse({'type': 'proxy', 'index': idx, 'proxy': proxy})
    return jsonify({'ok': True, 'index': idx, 'proxy': proxy})


@app.route('/api/bots/group/proxy', methods=['POST'])
def api_group_set_proxy():
    """Asigna un proxy a un grupo de bots (lista de índices)."""
    data    = request.get_json(silent=True) or {}
    indices = data.get('indices', [])   # lista de int
    proxy   = data.get('proxy', 'DIRECT').strip() or 'DIRECT'
    count   = 0
    for idx in indices:
        inst = next((b for b in state.bots if b.index == int(idx)), None)
        if inst:
            inst.proxy_address = proxy
            inst.add_log(f'Proxy (grupo) → {proxy}')
            state.push_sse({'type': 'proxy', 'index': inst.index, 'proxy': proxy})
            count += 1
    return jsonify({'ok': True, 'updated': count, 'proxy': proxy})


# =============================================================================
# PROXY LIST MANAGEMENT
# =============================================================================

@app.route('/api/proxies/list', methods=['GET'])
def api_proxies_list():
    """Devuelve la lista de proxies cargados."""
    return jsonify({'proxies': state.proxies, 'count': len(state.proxies)})


@app.route('/api/proxies/add', methods=['POST'])
def api_proxies_add():
    """Añade uno o varios proxies a la lista."""
    data  = request.get_json(silent=True) or {}
    lines = [l.strip() for l in data.get('proxy', '').splitlines() if l.strip()]
    added = 0
    for line in lines:
        if line not in state.proxies:
            state.proxies.append(line)
            added += 1
    return jsonify({'ok': True, 'added': added, 'count': len(state.proxies)})


@app.route('/api/proxies/delete', methods=['POST'])
def api_proxies_delete():
    """Elimina el proxy en la posición indicada (0-based)."""
    data = request.get_json(silent=True) or {}
    idx  = data.get('index')
    if idx is None or not (0 <= int(idx) < len(state.proxies)):
        return jsonify({'ok': False, 'error': 'index out of range'}), 400
    removed = state.proxies.pop(int(idx))
    return jsonify({'ok': True, 'removed': removed, 'count': len(state.proxies)})


# =============================================================================
# PROXY GROUPS
# =============================================================================

_GROUP_COLORS = ['#1a7a3a','#1155aa','#6633aa','#b85c00','#BF2C2C','#8a7200','#4a6a7a','#30728C']

@app.route('/api/proxy-groups', methods=['GET'])
def api_pg_list():
    out = {}
    for name, g in state.proxy_groups.items():
        out[name] = {'color': g.get('color', '#30728C'),
                     'proxies': g.get('proxies', []),
                     'count': len(g.get('proxies', []))}
    return jsonify({'groups': out})


@app.route('/api/proxy-groups/create', methods=['POST'])
def api_pg_create():
    data  = request.get_json(silent=True) or {}
    name  = data.get('name', '').strip()
    color = data.get('color', _GROUP_COLORS[len(state.proxy_groups) % len(_GROUP_COLORS)])
    if not name:
        return jsonify({'ok': False, 'error': 'nombre vacío'}), 400
    if name in state.proxy_groups:
        return jsonify({'ok': False, 'error': 'ya existe'}), 400
    state.proxy_groups[name] = {'color': color, 'proxies': [], '_idx': 0}
    return jsonify({'ok': True, 'name': name, 'color': color})


@app.route('/api/proxy-groups/<name>', methods=['DELETE'])
def api_pg_delete(name):
    state.proxy_groups.pop(name, None)
    return jsonify({'ok': True})


@app.route('/api/proxy-groups/<name>/rename', methods=['POST'])
def api_pg_rename(name):
    data    = request.get_json(silent=True) or {}
    newname = data.get('newname', '').strip()
    if not newname or newname in state.proxy_groups:
        return jsonify({'ok': False, 'error': 'nombre inválido o duplicado'}), 400
    g = state.proxy_groups.pop(name, None)
    if g is None:
        return jsonify({'ok': False, 'error': 'grupo no encontrado'}), 404
    state.proxy_groups[newname] = g
    return jsonify({'ok': True, 'newname': newname})


@app.route('/api/proxy-groups/<name>/add', methods=['POST'])
def api_pg_add(name):
    data  = request.get_json(silent=True) or {}
    lines = [l.strip() for l in data.get('proxies', '').splitlines() if l.strip()]
    if name not in state.proxy_groups:
        return jsonify({'ok': False, 'error': 'grupo no encontrado'}), 404
    pool = state.proxy_groups[name]['proxies']
    added = 0
    for l in lines:
        if l not in pool:
            pool.append(l); added += 1
    return jsonify({'ok': True, 'added': added, 'count': len(pool)})


@app.route('/api/proxy-groups/<name>/remove', methods=['POST'])
def api_pg_remove(name):
    data = request.get_json(silent=True) or {}
    idx  = data.get('index')
    if name not in state.proxy_groups:
        return jsonify({'ok': False, 'error': 'grupo no encontrado'}), 404
    pool = state.proxy_groups[name]['proxies']
    if idx is None or not (0 <= int(idx) < len(pool)):
        return jsonify({'ok': False, 'error': 'índice fuera de rango'}), 400
    removed = pool.pop(int(idx))
    return jsonify({'ok': True, 'removed': removed, 'count': len(pool)})


@app.route('/api/proxy-groups/<name>/assign', methods=['POST'])
def api_pg_assign(name):
    """Asigna proxies del grupo a bots (rotación interna del grupo)."""
    data    = request.get_json(silent=True) or {}
    indices = data.get('indices', [])   # lista de índices de bot
    if name not in state.proxy_groups:
        return jsonify({'ok': False, 'error': 'grupo no encontrado'}), 404
    count = 0
    for idx in indices:
        inst = next((b for b in state.bots if b.index == int(idx)), None)
        if inst:
            proxy = state.next_proxy_from_group(name)
            inst.proxy_address = proxy
            inst.add_log(f'Proxy ({name}) → {proxy}')
            state.push_sse({'type': 'proxy', 'index': inst.index, 'proxy': proxy})
            count += 1
    return jsonify({'ok': True, 'group': name, 'updated': count})


@app.route('/api/proxy-groups/<name>/clear', methods=['POST'])
def api_pg_clear(name):
    if name not in state.proxy_groups:
        return jsonify({'ok': False, 'error': 'grupo no encontrado'}), 404
    state.proxy_groups[name]['proxies'].clear()
    state.proxy_groups[name]['_idx'] = 0
    return jsonify({'ok': True})


# =============================================================================
# ACTION DECORATOR
# =============================================================================
def _action_endpoint(fn):
    from functools import wraps
    @wraps(fn)
    def wrapped():
        data    = request.get_json(silent=True) or {}
        target  = str(data.get('target', 'all'))
        clients = _get_clients(target)
        if not clients:
            return jsonify({'ok': False, 'error': 'No connected clients'})
        errors = []
        for c in clients:
            try: fn(c, data)
            except Exception as e: errors.append(str(e))
        return jsonify({'ok': not errors, 'errors': errors})
    return wrapped


# =============================================================================
# ACTIONS
# =============================================================================
@app.route('/api/action/shout',     methods=['POST'])
@_action_endpoint
def action_shout(c, d):     c.shout(d.get('msg', ''))

@app.route('/api/action/say',       methods=['POST'])
@_action_endpoint
def action_say(c, d):       c.shout(d.get('msg', ''), 0)

@app.route('/api/action/whisper',   methods=['POST'])
@_action_endpoint
def action_whisper(c, d):   c.whisper(d.get('user', ''), d.get('msg', ''))

@app.route('/api/action/motto',     methods=['POST'])
@_action_endpoint
def action_motto(c, d):     c.change_motto(d.get('motto', ''))

@app.route('/api/action/figure',    methods=['POST'])
@_action_endpoint
def action_figure(c, d):    c.update_figure(d.get('gender', 'M'), d.get('figure', ''))

@app.route('/api/action/rand_look', methods=['POST'])
@_action_endpoint
def action_rand_look(c, d):
    g = random.choice(['M', 'F'])
    c.update_figure(g, random.choice(
        const.RANDOM_FIGURES_MALE if g == 'M' else const.RANDOM_FIGURES_FEMALE))

@app.route('/api/action/rand_nick', methods=['POST'])
@_action_endpoint
def action_rand_nick(c, d): c.change_username(c._generate_meme_nick())

@app.route('/api/action/join',      methods=['POST'])
@_action_endpoint
def action_join(c, d):      c.join_room(int(d.get('room', 0)))

@app.route('/api/action/leave',     methods=['POST'])
@_action_endpoint
def action_leave(c, d):     c.quit_room()

@app.route('/api/action/walk',      methods=['POST'])
@_action_endpoint
def action_walk(c, d):      c.walk(int(d.get('x', 5)), int(d.get('y', 5)))

@app.route('/api/action/rand_walk', methods=['POST'])
@_action_endpoint
def action_rand_walk(c, d): c.set_walk_room_aware(True); c.walk_random(2.5)

@app.route('/api/action/stop_walk', methods=['POST'])
@_action_endpoint
def action_stop_walk(c, d): c.stop_random_walk()

@app.route('/api/action/dance',     methods=['POST'])
@_action_endpoint
def action_dance(c, d):     c.dance(int(d.get('style', 1)))

@app.route('/api/action/posture',   methods=['POST'])
@_action_endpoint
def action_posture(c, d):   c.change_posture(int(d.get('posture', 0)))

@app.route('/api/action/sign',      methods=['POST'])
@_action_endpoint
def action_sign(c, d):      c.sign(int(d.get('sign', 1)))

@app.route('/api/action/effect',    methods=['POST'])
@_action_endpoint
def action_effect(c, d):    c.enable_effect(int(d.get('effect', 1)))

@app.route('/api/action/respect',   methods=['POST'])
@_action_endpoint
def action_respect(c, d):
    t = d.get('user', '').lower()
    for u in c.users_in_room.values():
        if u.name.lower() == t or str(u.web_id) == t:
            c.respect_user(u.web_id); break

@app.route('/api/action/friend',    methods=['POST'])
@_action_endpoint
def action_friend(c, d):    c.request_friend(d.get('user', ''))

@app.route('/api/action/copy_looks',methods=['POST'])
@_action_endpoint
def action_copy(c, d):      c.copy_user_looks(d.get('user', ''))

@app.route('/api/action/stalk',     methods=['POST'])
@_action_endpoint
def action_stalk(c, d):
    t = d.get('user', '').lower()
    for u in c.users_in_room.values():
        if u.name.lower() == t: c.walk(u.x, u.y); break

@app.route('/api/action/nav_search', methods=['POST'])
def action_nav_search():
    data    = request.get_json(silent=True) or {}
    target  = str(data.get('target', 'all'))
    cat     = data.get('cat', 'popular')
    q       = data.get('q', '')
    clients = _get_clients(target)
    if not clients: return jsonify({'ok': False, 'error': 'No connected clients'})
    rooms_out = []
    done = threading.Event()
    def cb(rooms):
        for r in rooms:
            rooms_out.append({'id': r.flat_id, 'name': r.room_name,
                              'users': r.user_count, 'max': r.max_user_count})
        done.set()
    clients[0].navigator_callback = cb
    clients[0].search_navigator(cat, q)
    done.wait(timeout=5)
    return jsonify({'ok': True, 'rooms': rooms_out})

@app.route('/api/action/scan', methods=['POST'])
def action_scan():
    data    = request.get_json(silent=True) or {}
    target  = str(data.get('target', 'all'))
    clients = _get_clients(target)
    if not clients: return jsonify({'ok': False, 'error': 'No connected clients'})
    users = [{'name': u.name, 'gender': u.gender, 'index': u.room_index}
             for u in clients[0].users_in_room.values()]
    return jsonify({'ok': True, 'users': users})


# =============================================================================
# HTML FRONTEND (inline)
# =============================================================================
HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>HABBO NET-CONTROLLER</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Ubuntu+Condensed&family=Open+Sans:wght@400;600&display=swap');
:root{
  --bg:#c4c0b0;--bg2:#d0ccbc;--card:#F2F2EB;--inp:#e8e4d8;--btn:#30728C;
  --act:#1d5a72;--fg:#1a1a1a;--fm:#4a6a7a;--cy:#30728C;--gr:#1a7a3a;
  --rd:#BF2C2C;--or:#b85c00;--pu:#6633aa;--bl:#1155aa;--ye:#8a7200;
  --sep:#3C88A6;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg) url('https://mangetoica.com/gallery_images/homepage/background-mosaiques//bg.png') repeat;color:var(--fg);font:9pt 'Open Sans',Arial,sans-serif;display:flex;height:100vh;overflow:hidden}

/* SIDEBAR */
#sidebar{width:155px;min-width:155px;background:#d8d4c4;display:flex;flex-direction:column;border-right:2px solid #3C88A6}
#logo{padding:14px 12px 0}
#logo h1{font-size:12pt;font-weight:bold;color:#30728C;font-family:'Ubuntu Condensed',sans-serif;line-height:1.1;text-shadow:1px 1px 0 rgba(255,255,255,.5)}
#logo p{font-size:7.5pt;color:#4a6a7a;margin-top:2px}
.nav-sep{border:none;border-top:1px solid #3C88A6;margin:12px 8px}
.nav-btn{display:flex;align-items:center;gap:8px;padding:10px 12px;cursor:pointer;color:#4a6a7a;font-size:8.5pt;font-family:'Open Sans',sans-serif;background:transparent;border:none;width:100%;text-align:left;transition:background .15s,color .15s}
.nav-btn:hover{color:#30728C;background:#c8c4b4}
.nav-btn.active{color:#fff;background:#30728C}
#side-stat{padding:8px 12px;font-size:7.5pt;color:#4a6a7a;margin-top:auto}
#web-badge{padding:6px 12px 10px;font-size:7pt;color:#1a7a3a}

/* MAIN */
#main{flex:1;display:flex;flex-direction:column;overflow:hidden}
.topbar{display:flex;align-items:center;background:#30728C;flex-shrink:0;border-bottom:2px solid #000}
.topbar-group{display:flex;align-items:center;gap:6px;padding:7px 10px}
.topbar-sep{width:1px;height:24px;background:var(--sep);margin:0 2px}
.counter{font-weight:bold;font-size:8.5pt;color:#fff}
.counter.gr{color:#b8ffcc}.counter.rd{color:#ffb8b8}
label.chk{display:flex;align-items:center;gap:4px;cursor:pointer;font-size:8pt;color:#fff}
label.chk input{accent-color:#fff}
select{background:#e8e4d8;color:#1a1a1a;border:1px solid #3C88A6;outline:none;padding:4px 6px;font:8.5pt 'Open Sans',sans-serif;cursor:pointer;border-radius:4px}
select option{background:#F2F2EB;color:#1a1a1a}
#tabbar{display:flex;background:#1d5a72;flex-shrink:0;border-bottom:2px solid #000}
.tab-btn{padding:9px 16px;cursor:pointer;color:#9cc8d8;font:bold 8.5pt 'Open Sans',sans-serif;background:transparent;border:none;border-bottom:2px solid transparent;transition:color .15s}
.tab-btn:hover{color:#fff}
.tab-btn.active{color:#fff;border-bottom-color:#fff}
#page-host{flex:1;overflow:auto}
.page{display:none;height:100%;overflow:auto}
.page.visible{display:block}

/* CARDS */
.card{background:var(--card);border-radius:8px;margin:10px 12px;border:2px solid #000;box-shadow:1px 1px 6px rgba(0,0,0,.35)}
.card-hdr{padding:7px 10px 5px;border-bottom:2px solid #000;background:#30728C;color:#fff;font-weight:bold;font-size:8.5pt;font-family:'Ubuntu Condensed',sans-serif;border-top-left-radius:6px;border-top-right-radius:6px;text-shadow:1px 1px 1px #000}
.card-body{padding:8px 10px}

/* TABLE */
.bot-table{width:100%;border-collapse:collapse;font-size:8pt}
.bot-table th{background:#30728C;color:#fff;font-weight:bold;text-align:left;padding:6px 8px;border-bottom:2px solid #000;font-family:'Ubuntu Condensed',sans-serif;font-size:9pt;text-shadow:1px 1px 1px #000}
.bot-table td{padding:5px 8px;border-bottom:1px solid #d8d4c4;color:#1a1a1a}
.bot-table tr:hover td{background:#dde9f0}
.bot-table tr.selected td{background:#c4dff0}
.s-conn{color:#1a7a3a;font-weight:bold}.s-fail{color:#BF2C2C;font-weight:bold}.s-prep{color:#8a7200;font-weight:bold}.s-other{color:#4a6a7a}

/* STATUS DOT */
.sdot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px;vertical-align:middle;flex-shrink:0}
.sdot-conn{background:#1a7a3a;box-shadow:0 0 0 0 rgba(26,122,58,.6);animation:pulse-g 2s infinite}
.sdot-fail{background:#BF2C2C}
.sdot-prep{background:#8a7200;box-shadow:0 0 0 0 rgba(138,114,0,.6);animation:pulse-y 1.2s infinite}
.sdot-other{background:#8aacbc}
@keyframes pulse-g{0%,100%{box-shadow:0 0 0 0 rgba(26,122,58,.5)}50%{box-shadow:0 0 0 4px rgba(26,122,58,0)}}
@keyframes pulse-y{0%,100%{box-shadow:0 0 0 0 rgba(138,114,0,.5)}50%{box-shadow:0 0 0 4px rgba(138,114,0,0)}}

/* BUTTONS */
.btn{border:solid 2px #000;outline:none;cursor:pointer;font:bold 8.5pt 'Open Sans',sans-serif;padding:5px 10px;border-radius:4px;transition:filter .15s,border-color .2s}
.btn:hover{filter:brightness(1.12);border-color:#fff}
.btn-gr{background:#1a7a3a;color:#fff}.btn-rd{background:#BF2C2C;color:#fff}
.btn-bl{background:#1155aa;color:#fff}.btn-or{background:#b85c00;color:#fff}
.btn-pu{background:#6633aa;color:#fff}.btn-ye{background:#8a7200;color:#fff}
.btn-def{background:#30728C;color:#fff}.btn-sm{padding:4px 8px;font-size:8pt}

/* INPUTS */
input[type=text],input[type=number],textarea{background:var(--inp);color:var(--fg);border:1px solid #3C88A6;outline:none;padding:5px 7px;font:8.5pt 'Open Sans',sans-serif;border-radius:4px}
input[type=text]:focus,input[type=number]:focus,textarea:focus{border-color:#30728C;box-shadow:0 0 0 2px rgba(48,114,140,.2)}
input[type=text]::placeholder,textarea::placeholder{color:#7a9aaa}
textarea{resize:vertical;width:100%}

/* LAYOUT */
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:0;height:100%}
.col{padding:10px;display:flex;flex-direction:column;gap:8px;overflow-y:auto}
.sec{background:var(--card);border-radius:8px;border:2px solid #000;box-shadow:1px 1px 4px rgba(0,0,0,.25)}
.sec-hdr{padding:7px 10px 5px;border-bottom:2px solid #000;background:#30728C;color:#fff;font-weight:bold;font-size:8.5pt;font-family:'Ubuntu Condensed',sans-serif;border-top-left-radius:6px;border-top-right-radius:6px;text-shadow:1px 1px 1px #000}
.sec-body{padding:8px 10px}
.row{display:flex;align-items:center;gap:6px;margin-bottom:6px}
.row:last-child{margin-bottom:0}
.listbox{background:var(--inp);border-radius:4px;border:1px solid #3C88A6;overflow-y:auto;font-size:8pt}
.listbox div{padding:4px 8px;cursor:pointer;border-bottom:1px solid #d8d4c4;color:#1a1a1a}
.listbox div:hover{background:#c4dff0;color:#30728C}
.radio-group{display:flex;gap:4px;flex-wrap:wrap}
.radio-group label{background:#30728C;color:#fff;padding:4px 8px;border-radius:4px;border:1px solid #000;cursor:pointer;font-size:8pt;display:flex;align-items:center;gap:4px}
.radio-group input[type=radio]{accent-color:#fff}
#spam-status.on{color:var(--gr);font-weight:bold}
#spam-status.off{color:var(--rd);font-weight:bold}

/* ════ HABBO-STYLE ALERT BOX ════ */
@import url('https://fonts.googleapis.com/css2?family=Ubuntu+Condensed&family=Open+Sans&display=swap');
#habbo-alert-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.8);z-index:9999;align-items:center;justify-content:center}
#habbo-alert-overlay.show{display:flex}
#habbo-box{width:400px;max-width:92vw;border:solid 2px #000;border-radius:10px;background-color:#F2F2EB;box-shadow:2px 2px 14px #000}
#habbo-box-title{display:flex;align-items:center;border:solid 2px #3C88A6;border-bottom:solid 2px #000;border-top-left-radius:8px;border-top-right-radius:8px;background-color:#30728C;padding:6px 8px}
#habbo-box-title h2{flex:1;margin:0 8px;color:#fff;font-size:15px;text-align:center;font-weight:lighter;text-shadow:1px 1px 1px #000;font-family:'Ubuntu Condensed',Consolas,sans-serif}
#habbo-box-cross{cursor:pointer;color:#fff;background-color:#BF2C2C;width:22px;height:22px;border:solid 2px #000;border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:bold;flex-shrink:0;transition:border .3s}
#habbo-box-cross:hover{border-color:#fff}
#habbo-box-content{padding:12px 14px 8px;border:solid 2px #fff;border-bottom-left-radius:8px;border-bottom-right-radius:8px;border-top:none}
#habbo-box-content p{margin:0 0 10px 0;font-family:'Open Sans',sans-serif;color:#222;font-size:13px;line-height:1.55}
#habbo-box-footer{text-align:right}
#habbo-box-footer button{background:#30728C;color:#fff;border:solid 2px #000;border-radius:4px;padding:4px 18px;cursor:pointer;font-family:Consolas,monospace;font-size:12px;transition:background .2s}
#habbo-box-footer button:hover{background:#3C88A6}

/* ════ TOAST NOTIFICATIONS ════ */
#toast-rack{position:fixed;bottom:18px;right:18px;z-index:8888;display:flex;flex-direction:column;gap:6px;pointer-events:none}
.toast{background:#1d5a72;color:#fff;border:2px solid #000;border-radius:6px;padding:8px 14px;font-size:8.5pt;font-family:'Open Sans',sans-serif;box-shadow:2px 2px 10px rgba(0,0,0,.5);opacity:0;transform:translateX(60px);transition:opacity .25s,transform .25s;pointer-events:none;max-width:320px}
.toast.show{opacity:1;transform:translateX(0)}
.toast.ok  {border-left:4px solid #1a7a3a}
.toast.err {border-left:4px solid #BF2C2C;background:#5a1a1a}
.toast.info{border-left:4px solid #30728C}

/* ════ LOG PANEL ════ */
#log-panel{position:fixed;right:0;top:0;bottom:0;width:310px;background:#1a2a32;border-left:2px solid #000;display:none;flex-direction:column;z-index:500;font-family:monospace;font-size:7.5pt}
#log-panel-hdr{background:#30728C;border-bottom:2px solid #000;padding:6px 10px;display:flex;align-items:center;gap:8px;color:#fff;font-family:'Ubuntu Condensed',sans-serif;font-size:10pt;text-shadow:1px 1px 0 #000;flex-shrink:0}
#log-panel-hdr span{flex:1}
#log-panel-close{cursor:pointer;background:#BF2C2C;border:2px solid #000;border-radius:4px;width:20px;height:20px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:bold}
#log-panel-close:hover{border-color:#fff}
#log-panel-body{flex:1;overflow-y:auto;padding:6px 8px;display:flex;flex-direction:column;gap:2px}
.log-line{color:#b8d8e0;line-height:1.45;word-break:break-all}
.log-line.err{color:#ff8888}
.log-line.ok{color:#88ffaa}

/* ════ PROXY GROUPS ════ */
.pg-tag{display:inline-flex;align-items:center;gap:4px;border-radius:10px;padding:2px 8px;font-size:7.5pt;color:#fff;font-weight:bold;border:1px solid rgba(0,0,0,.3);cursor:pointer;transition:filter .15s}
.pg-tag:hover{filter:brightness(1.15)}
.pg-tag.active{box-shadow:0 0 0 2px #fff,0 0 0 4px #000}
.pg-group-card{background:var(--card);border:2px solid #000;border-radius:8px;margin-bottom:6px;box-shadow:1px 1px 4px rgba(0,0,0,.25);overflow:hidden}
.pg-group-hdr{display:flex;align-items:center;gap:6px;padding:5px 8px;font-family:'Ubuntu Condensed',sans-serif;font-size:9pt;border-bottom:1px solid rgba(0,0,0,.2);cursor:pointer;user-select:none}
.pg-group-body{padding:6px 8px;display:none}
.pg-group-body.open{display:block}
</style>
</head>
<body>

<!-- SIDEBAR -->
<div id="sidebar">
  <div id="logo"><h1>NET-CONTROLLER</h1><p>v3.0 - Stable</p></div>
  <hr class="nav-sep">
  <button class="nav-btn active" data-page="dashboard" onclick="showPage(this)"><span>⊞</span> Dashboard &amp; Status</button>
  <button class="nav-btn" data-page="control"   onclick="showPage(this)"><span>⊙</span> Control Deck &amp; Nav</button>
  <button class="nav-btn" data-page="accounts"  onclick="showPage(this)"><span>☰</span> Account Manager</button>
  <button class="nav-btn" data-page="proxies"   onclick="showPage(this)"><span>◈</span> Proxy Manager</button>
  <div id="side-stat">0 / 0 bots</div>
  <div id="web-badge">● WEB activo</div>
</div>

<!-- MAIN -->
<div id="main">

  <!-- TOPBAR DASHBOARD -->
  <div id="topbar-dash" class="topbar">
    <div class="topbar-group">
      <button class="btn btn-gr btn-sm" onclick="connectAll()">▶ Start</button>
      <button class="btn btn-def btn-sm" onclick="disconnectAll()">■ Stop</button>
    </div>
    <div class="topbar-sep"></div>
    <div class="topbar-group">
      <label class="chk"><input type="checkbox" id="auto-rec" checked> Auto Rec.</label>
      <label class="chk"><input type="checkbox" id="anti-admin" checked> Anti-Admin</label>
    </div>
    <div class="topbar-sep"></div>
    <div class="topbar-group">
      <span style="color:var(--fm);font-size:8pt">Split</span>
      <input type="number" id="split-n" value="3" style="width:42px">
    </div>
    <div style="flex:1"></div>
    <div class="topbar-group">
      <span class="counter gr" id="conn-d">CONN: 0</span>
      <span class="counter rd" id="disc-d">DISC: 0</span>
    </div>
  </div>

  <!-- TOPBAR CONTROL -->
  <div id="topbar-ctrl" class="topbar" style="display:none">
    <div class="topbar-group">
      <span style="color:var(--cy);font-weight:bold;font-size:8.5pt">TARGET</span>
      <select id="cmd-target"><option value="all">All Connected</option></select>
      <button class="btn btn-gr btn-sm" onclick="refreshTargets()">↺</button>
    </div>
    <div class="topbar-sep"></div>
    <div class="topbar-group">
      <span style="color:var(--fm);font-size:8pt">Hotel:</span>
      <select id="hotel-sel" onchange="setHotel(this.value)"></select>
    </div>
    <div style="flex:1"></div>
    <div class="topbar-group">
      <span class="counter gr" id="conn-c">CONN: 0</span>
      <span class="counter rd" id="disc-c">DISC: 0</span>
    </div>
  </div>

  <!-- TABBAR -->
  <div id="tabbar" style="display:none">
    <button class="tab-btn active" onclick="showTab(this,'tab-actions')">ACTIONS</button>
    <button class="tab-btn" onclick="showTab(this,'tab-movement')">MOVEMENT</button>
    <button class="tab-btn" onclick="showTab(this,'tab-roomintel')">ROOM INTEL</button>
    <button class="tab-btn" onclick="showTab(this,'tab-spammer')">SPAMMER</button>
  </div>

  <!-- PAGE HOST -->
  <div id="page-host">

    <!-- DASHBOARD -->
    <div id="page-dashboard" class="page visible">
      <!-- search bar -->
      <div style="display:flex;align-items:center;gap:6px;padding:6px 12px 2px">
        <input type="text" id="bot-filter" placeholder="🔍 Filtrar bots..." style="width:180px;font-size:8pt" oninput="renderBots()">
        <span style="color:var(--fm);font-size:7.5pt" id="filter-info"></span>
      </div>
      <div class="card" style="margin-bottom:0;border-bottom-left-radius:0;border-bottom-right-radius:0">
        <div class="card-hdr" style="display:flex;align-items:center;gap:6px">
          <span>■  BOT STATUS</span>
          <span id="sel-badge" style="background:#fff2;border:1px solid #fff6;border-radius:10px;padding:1px 8px;font-size:7.5pt;margin-left:auto;display:none">0 sel.</span>
        </div>
        <div class="card-body" style="padding:0 0 4px">
          <table class="bot-table">
            <thead><tr>
              <th style="width:30px"><input type="checkbox" id="chk-all" onchange="toggleSelAll(this.checked)" title="Select all"></th>
              <th style="width:32px">#</th>
              <th style="width:120px">STATUS</th><th>NAME</th><th>HOTEL</th><th>GRUPO/PROXY</th><th style="width:100px">ACCIONES</th>
            </tr></thead>
            <tbody id="bot-tbody"></tbody>
          </table>
        </div>
      </div>
      <!-- GROUP ACTION BAR -->
      <div id="grp-bar" style="display:none;align-items:center;gap:6px;padding:4px 12px 6px;background:var(--card);border:2px solid #000;border-top:none;border-radius:0 0 8px 8px;margin:0 0 4px;flex-wrap:wrap">
        <span style="color:var(--cy);font-size:8pt;font-weight:bold">SELECCIÓN (<span id="grp-bar-cnt">0</span>):</span>
        <button class="btn btn-gr btn-sm" onclick="connectSel()">▶ Conectar</button>
        <button class="btn btn-rd btn-sm" onclick="disconnectSel()">■ Desconectar</button>
        <div style="width:1px;height:18px;background:#3C88A6;margin:0 2px"></div>
        <span style="color:var(--fm);font-size:8pt">Proxy rápido:</span>
        <select id="grp-proxy-sel" style="font-size:8pt;padding:3px 6px;border:1px solid #3C88A6;border-radius:4px;background:var(--inp);color:var(--fg)"><option value="DIRECT">DIRECT</option></select>
        <button class="btn btn-def btn-sm" onclick="assignProxyToSel()">⇒ Asignar</button>
        <div style="width:1px;height:18px;background:#3C88A6;margin:0 2px"></div>
        <span style="color:var(--fm);font-size:8pt">Grupo:</span>
        <select id="grp-group-sel" style="font-size:8pt;padding:3px 6px;border:1px solid #3C88A6;border-radius:4px;background:var(--inp);color:var(--fg)"><option value="">-- ninguno --</option></select>
        <button class="btn btn-def btn-sm" onclick="assignGroupSelFromBar()">⇒ Asignar grupo</button>
        <button class="btn btn-sm" style="background:#888;color:#fff;margin-left:auto" onclick="selSet.clear();renderBots();updateGrpBar()">✕ Deselect</button>
      </div>
    </div>

    <!-- CONTROL DECK -->
    <div id="page-control" class="page">

      <!-- ACTIONS -->
      <div id="tab-actions" class="two-col">
        <div class="col">
          <div class="sec">
            <div class="sec-hdr">■  COMMUNICATION</div>
            <div class="sec-body">
              <div class="row">
                <input type="text" id="shout-msg" placeholder="Message..." style="flex:1">
                <button class="btn btn-bl btn-sm" onclick="act('shout',{msg:v('shout-msg')})">⇱ SHOUT</button>
                <button class="btn btn-def btn-sm" onclick="act('say',{msg:v('shout-msg')})">SAY</button>
              </div>
              <div class="row">
                <input type="text" id="w-user" placeholder="User" style="width:90px">
                <input type="text" id="w-msg" placeholder="Whisper..." style="flex:1">
                <button class="btn btn-rd btn-sm" onclick="act('whisper',{user:v('w-user'),msg:v('w-msg')})">→</button>
              </div>
            </div>
          </div>
          <div class="sec">
            <div class="sec-hdr">■  IDENTITY CONTROL</div>
            <div class="sec-body">
              <div class="row">
                <input type="text" id="motto-inp" placeholder="Motto..." style="flex:1">
                <button class="btn btn-gr btn-sm" onclick="act('motto',{motto:v('motto-inp')})">Set</button>
              </div>
              <div class="row">
                <span style="color:var(--fm);font-size:8pt">Figure:</span>
                <select id="gender-sel"><option value="M">M</option><option value="F">F</option></select>
                <input type="text" id="figure-inp" placeholder="hr-100-..." style="flex:1">
                <button class="btn btn-gr btn-sm" onclick="act('figure',{gender:v('gender-sel'),figure:v('figure-inp')})">Apply</button>
              </div>
              <div class="row">
                <button class="btn btn-def btn-sm" style="flex:1" onclick="act('rand_look',{})">⊞ Rand Look</button>
                <button class="btn btn-def btn-sm" style="flex:1" onclick="act('rand_nick',{})">✎ Rand Nick</button>
              </div>
            </div>
          </div>
        </div>
        <div class="col">
          <div class="sec">
            <div class="sec-hdr">■  ROOM OPERATIONS</div>
            <div class="sec-body">
              <div class="row"><input type="text" id="room-id" value="80257391" placeholder="Room ID" style="flex:1"></div>
              <div class="row">
                <button class="btn btn-gr btn-sm" style="flex:1" onclick="act('join',{room:v('room-id')})">▶ JOIN</button>
                <button class="btn btn-rd btn-sm" onclick="act('leave',{})">✖ Leave</button>
              </div>
            </div>
          </div>
          <div class="sec">
            <div class="sec-hdr">■  INTERACTION</div>
            <div class="sec-body">
              <div class="row"><input type="text" id="tgt-user" placeholder="Target User (Name/ID)" style="flex:1"></div>
              <div class="row">
                <button class="btn btn-bl btn-sm" style="flex:1" onclick="act('respect',{user:v('tgt-user')})">♥ RESPECT</button>
                <button class="btn btn-def btn-sm" style="flex:1" onclick="act('friend',{user:v('tgt-user')})">+ FRIEND</button>
                <button class="btn btn-pu btn-sm" style="flex:1" onclick="act('copy_looks',{user:v('tgt-user')})">⊕ COPY</button>
              </div>
              <div class="row">
                <button class="btn btn-or btn-sm" style="flex:1" onclick="act('stalk',{user:v('tgt-user')})">⟳ STALK</button>
                <button class="btn btn-def btn-sm" style="flex:1" onclick="act('stop_walk',{})">■ STOP</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- MOVEMENT -->
      <div id="tab-movement" class="two-col" style="display:none">
        <div class="col">
          <div class="sec">
            <div class="sec-hdr">■  WALK</div>
            <div class="sec-body">
              <div class="row">
                <span style="color:var(--cy)">X:</span><input type="number" id="wx" value="5" style="width:50px">
                <span style="color:var(--cy)">Y:</span><input type="number" id="wy" value="5" style="width:50px">
                <button class="btn btn-bl btn-sm" onclick="act('walk',{x:+v('wx'),y:+v('wy')})">WALK</button>
              </div>
              <div class="row">
                <button class="btn btn-gr btn-sm" style="flex:1" onclick="act('rand_walk',{})">↻ Random Walk</button>
                <button class="btn btn-rd btn-sm" style="flex:1" onclick="act('stop_walk',{})">■ Stop</button>
              </div>
            </div>
          </div>
          <div class="sec">
            <div class="sec-hdr">■  DANCE & POSTURE</div>
            <div class="sec-body">
              <div class="row">
                <div class="radio-group">
                  <label><input type="radio" name="dance" value="0"> Stop</label>
                  <label><input type="radio" name="dance" value="1" checked> Normal</label>
                  <label><input type="radio" name="dance" value="2"> Pogo</label>
                  <label><input type="radio" name="dance" value="3"> Duck</label>
                  <label><input type="radio" name="dance" value="4"> Rollie</label>
                </div>
              </div>
              <div class="row">
                <button class="btn btn-pu btn-sm" style="flex:1" onclick="act('dance',{style:+document.querySelector('input[name=dance]:checked').value})">♫ Dance</button>
                <button class="btn btn-def btn-sm" style="flex:1" onclick="act('posture',{posture:1})">Sit</button>
                <button class="btn btn-def btn-sm" style="flex:1" onclick="act('posture',{posture:0})">Stand</button>
              </div>
            </div>
          </div>
        </div>
        <div class="col">
          <div class="sec">
            <div class="sec-hdr">■  SIGN & EFFECTS</div>
            <div class="sec-body">
              <div class="row">
                <span style="color:var(--fm)">Sign (0-14):</span>
                <input type="number" id="sign-v" value="1" style="width:50px">
                <button class="btn btn-ye btn-sm" onclick="act('sign',{sign:+v('sign-v')})">Show</button>
              </div>
              <div class="row">
                <span style="color:var(--fm)">Effect ID:</span>
                <input type="number" id="eff-v" value="1" style="width:50px">
                <button class="btn btn-pu btn-sm" onclick="act('effect',{effect:+v('eff-v')})">Enable</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ROOM INTEL -->
      <div id="tab-roomintel" class="two-col" style="display:none">
        <div class="col">
          <div class="sec" style="flex:1">
            <div class="sec-hdr">■  NAVIGATOR</div>
            <div class="sec-body" style="display:flex;flex-direction:column;gap:6px">
              <div class="row">
                <select id="nav-cat">
                  <option value="popular">popular</option>
                  <option value="official">official</option>
                  <option value="hotel_view">hotel_view</option>
                  <option value="myworld_view">myworld_view</option>
                </select>
                <input type="text" id="nav-q" placeholder="Search..." style="flex:1">
              </div>
              <button class="btn btn-gr btn-sm" onclick="navFetch()">⌕  FETCH</button>
              <div class="listbox" id="nav-list" style="height:200px"></div>
            </div>
          </div>
        </div>
        <div class="col">
          <div class="sec" style="flex:1">
            <div class="sec-hdr">■  MAP & ENTITIES</div>
            <div class="sec-body" style="display:flex;flex-direction:column;gap:6px">
              <button class="btn btn-bl btn-sm" onclick="act('join',{room:v('room-id')})">↺ RELOAD ROOM</button>
              <div class="row">
                <input type="text" id="troll-inp" placeholder="Troll sentence..." style="flex:1">
                <button class="btn btn-or btn-sm" id="troll-btn" onclick="toggleTroll()">●</button>
              </div>
              <button class="btn btn-bl btn-sm" onclick="scanUsers()">⊙ SCAN USERS</button>
              <span style="color:var(--fm);font-size:8pt">Entities:</span>
              <div class="listbox" id="entity-list" style="height:160px"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- SPAMMER -->
      <div id="tab-spammer" class="two-col" style="display:none">
        <div class="col">
          <div class="sec">
            <div class="sec-hdr">■  SPAM CONFIGURATION</div>
            <div class="sec-body">
              <textarea id="spam-msg" rows="4" placeholder="Mensaje... (%nick%, %index%)"></textarea>
              <div class="row" style="margin-top:6px">
                <span style="color:var(--fm)">Interval (s):</span>
                <input type="number" id="spam-ivl" value="5" style="width:55px">
                <span style="color:var(--fm)">Style:</span>
                <input type="number" id="spam-style" value="-1" style="width:50px">
              </div>
              <div class="row">
                <button class="btn btn-gr btn-sm" style="flex:1" onclick="spamStart()">▶ START</button>
                <button class="btn btn-rd btn-sm" style="flex:1" onclick="spamStop()">■ STOP</button>
              </div>
              <div class="row">
                <span style="color:var(--fm)">Sent:</span>
                <span id="spam-cnt" style="color:var(--gr);margin-left:4px">0</span>
                &nbsp;
                <span id="spam-status" class="off">■ STOPPED</span>
              </div>
            </div>
          </div>
        </div>
        <div class="col">
          <div class="sec">
            <div class="sec-hdr">■  VARIABLES</div>
            <div class="sec-body">
              <div class="row"><span style="color:var(--cy);font-weight:bold">%nick%</span>&nbsp;<span style="color:var(--fm)">Username del bot</span></div>
              <div class="row"><span style="color:var(--cy);font-weight:bold">%index%</span>&nbsp;<span style="color:var(--fm)">Índice del bot</span></div>
            </div>
          </div>
        </div>
      </div>

    </div><!-- /page-control -->

    <!-- ACCOUNTS -->
    <div id="page-accounts" class="page">
      <div style="display:flex;align-items:center;gap:8px;padding:10px 12px 4px;flex-wrap:wrap">
        <span style="color:var(--gr);font-size:12pt;font-weight:bold">ACCOUNT MANAGER</span>
        <button class="btn btn-gr btn-sm" onclick="openAddModal()">✚ Add Account</button>
        <label class="btn btn-def btn-sm" style="cursor:pointer">📂 Load JSON
          <input type="file" accept=".json" style="display:none" onchange="loadAccounts(event)">
        </label>
        <button class="btn btn-gr btn-sm" onclick="connectAll()">▶ Connect All</button>
        <button class="btn btn-rd btn-sm" onclick="disconnectAll()">■ Disconnect All</button>
        <button class="btn btn-def btn-sm" onclick="saveAccounts()">💾 Save JSON</button>
      </div>
      <div class="card">
        <div class="card-hdr">■  BOTS</div>
        <div class="card-body" style="padding:0 0 8px">
          <table class="bot-table">
            <thead><tr>
              <th style="width:30px"><input type="checkbox" onchange="toggleSelAll(this.checked)"></th>
              <th style="width:32px">#</th>
              <th>NAME</th><th>STATUS</th><th>HOTEL</th><th>PROXY</th><th style="width:72px">ACTIONS</th>
            </tr></thead>
            <tbody id="acc-tbody"></tbody>
          </table>
        </div>
      </div>
      <div style="display:flex;gap:8px;padding:4px 12px 8px">
        <button class="btn btn-gr btn-sm" onclick="connectSel()">▶ Connect Selected</button>
        <button class="btn btn-rd btn-sm" onclick="disconnectSel()">■ Disconnect Selected</button>
        <span style="color:var(--fm);font-size:8pt;margin-left:6px">Proxy:</span>
        <select id="grp-proxy-sel-acc" style="font-size:8pt;padding:3px 6px;border:1px solid #3C88A6;border-radius:4px;background:var(--inp);color:var(--fg)"><option value="DIRECT">DIRECT</option></select>
        <button class="btn btn-def btn-sm" onclick="assignProxyToSel()">⇒ Asignar</button>
      </div>
    </div>

    <!-- PROXIES -->
    <div id="page-proxies" class="page">
      <div style="display:grid;grid-template-columns:220px 1fr;height:100%;overflow:hidden">

        <!-- LEFT: GROUPS PANEL -->
        <div style="background:#cac6b6;border-right:2px solid #000;display:flex;flex-direction:column;overflow:hidden">
          <div style="background:#1d5a72;color:#fff;padding:8px 10px;font-family:'Ubuntu Condensed',sans-serif;font-size:10pt;font-weight:bold;border-bottom:2px solid #000;text-shadow:1px 1px 0 #000;flex-shrink:0">
            ◈ GRUPOS DE PROXIES
          </div>
          <!-- create group -->
          <div style="padding:8px 8px 0;flex-shrink:0">
            <div class="row" style="margin-bottom:4px">
              <input type="text" id="pg-name-inp" placeholder="Nombre del grupo..." style="flex:1;font-size:8pt">
            </div>
            <div class="row" style="margin-bottom:6px">
              <span style="color:#4a6a7a;font-size:8pt">Color:</span>
              <div id="pg-color-picker" style="display:flex;gap:3px;flex-wrap:wrap"></div>
            </div>
            <button class="btn btn-gr btn-sm" style="width:100%;margin-bottom:6px" onclick="createGroup()">✚ Crear Grupo</button>
            <hr style="border:none;border-top:1px solid #3C88A6;margin:0 0 6px">
          </div>
          <!-- global proxy pool -->
          <div id="pg-global-btn" style="display:flex;align-items:center;gap:6px;padding:6px 8px;cursor:pointer;border-bottom:1px solid #aaa8;font-size:8.5pt;color:#1a1a1a;transition:background .15s"
               onclick="selectGroup(null)" class="pg-group-row">
            <span style="width:10px;height:10px;border-radius:50%;background:#555;border:1px solid #000;flex-shrink:0"></span>
            <span style="flex:1;font-weight:bold">Pool Global</span>
            <span id="pg-global-cnt" style="color:#4a6a7a;font-size:7.5pt">0</span>
          </div>
          <!-- group list -->
          <div id="pg-group-list" style="flex:1;overflow-y:auto"></div>
          <!-- assign footer -->
          <div style="flex-shrink:0;padding:8px;border-top:2px solid #3C88A6;background:#b8b4a4">
            <div style="font-size:7.5pt;color:#4a6a7a;margin-bottom:4px">Asignar a selección de bots:</div>
            <button class="btn btn-def btn-sm" style="width:100%" onclick="assignGroupToSel()">⇒ Asignar grupo activo</button>
          </div>
        </div>

        <!-- RIGHT: PROXY LIST FOR ACTIVE GROUP -->
        <div style="display:flex;flex-direction:column;overflow:hidden">
          <!-- group header -->
          <div id="pg-active-hdr" style="background:#30728C;color:#fff;padding:7px 10px;font-family:'Ubuntu Condensed',sans-serif;font-size:10pt;border-bottom:2px solid #000;text-shadow:1px 1px 0 #000;display:flex;align-items:center;gap:8px;flex-shrink:0">
            <span id="pg-active-name">Pool Global</span>
            <span id="pg-active-cnt" style="font-size:8pt;opacity:.8">0 proxies</span>
            <div style="flex:1"></div>
            <label class="btn btn-sm" style="background:#1155aa;color:#fff;border:2px solid #000;cursor:pointer;padding:3px 8px;font-size:7.5pt">
              📂 Import .txt <input type="file" accept=".txt" style="display:none" onchange="importGroupProxies(event)">
            </label>
            <button class="btn btn-sm" style="background:#1a7a3a;color:#fff;border:2px solid #000;font-size:7.5pt" onclick="exportGroupProxies()">💾 Export</button>
            <button class="btn btn-sm" style="background:#BF2C2C;color:#fff;border:2px solid #000;font-size:7.5pt" onclick="clearGroupProxies()">🗑 Clear</button>
          </div>
          <!-- add proxies form -->
          <div style="padding:8px 10px;border-bottom:1px solid #c4c0b0;background:#dedad0;flex-shrink:0">
            <div style="font-size:7.5pt;color:#4a6a7a;margin-bottom:4px">ip:port &nbsp;|&nbsp; ip:port:user:pass &nbsp;— una por línea</div>
            <div style="display:flex;gap:6px;align-items:flex-end">
              <textarea id="pg-add-text" rows="2" placeholder="1.2.3.4:1080&#10;5.6.7.8:1080:user:pass" style="flex:1;resize:none"></textarea>
              <button class="btn btn-gr btn-sm" onclick="addGroupProxies()">✚ Añadir</button>
            </div>
          </div>
          <!-- proxy table -->
          <div style="flex:1;overflow-y:auto">
            <table class="bot-table" style="font-size:7.5pt">
              <thead><tr>
                <th style="width:32px">#</th>
                <th>PROXY</th>
                <th style="width:80px">BOTS</th>
                <th style="width:50px"></th>
              </tr></thead>
              <tbody id="pg-prx-tbody"></tbody>
            </table>
          </div>
        </div>

      </div>
    </div>

  </div><!-- /page-host -->
</div><!-- /main -->

<!-- TOAST RACK -->
<div id="toast-rack"></div>

<!-- LOG PANEL -->
<div id="log-panel">
  <div id="log-panel-hdr">
    <span id="log-panel-title">LOG — Bot #?</span>
    <div id="log-panel-close" onclick="closeLogPanel()">✕</div>
  </div>
  <div id="log-panel-body"></div>
</div>

<script>
const $ = id => document.getElementById(id);
const v = id => { const el = $(id); return el.tagName === 'SELECT' ? el.value : el.value; };

// ── NAVIGATION ────────────────────────────────────────────────────
function showPage(btn) {
  const page = btn.dataset.page;
  document.querySelectorAll('.page').forEach(p => p.classList.remove('visible'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  $('page-' + page).classList.add('visible');
  btn.classList.add('active');
  $('topbar-dash').style.display = page === 'dashboard' ? 'flex' : 'none';
  $('topbar-ctrl').style.display = page === 'control'   ? 'flex' : 'none';
  $('tabbar').style.display       = page === 'control'   ? 'flex' : 'none';
}

function showTab(btn, tabId) {
  document.querySelectorAll('[id^="tab-"]').forEach(t => t.style.display = 'none');
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  $(tabId).style.display = 'grid';
  btn.classList.add('active');
}

// ── STATUS TABLE ─────────────────────────────────────────────────
let botsState = [], selSet = new Set();

function statusClass(s) {
  if (s === 'Connected') return 's-conn';
  if (/fail|error|ban/i.test(s)) return 's-fail';
  if (/prep|conn/i.test(s)) return 's-prep';
  return 's-other';
}

// ── TOAST ─────────────────────────────────────────────────────────
function toast(msg, type='info', dur=3000) {
  const rack = $('toast-rack');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = msg;
  rack.appendChild(el);
  requestAnimationFrame(() => { requestAnimationFrame(() => el.classList.add('show')); });
  setTimeout(() => {
    el.classList.remove('show');
    setTimeout(() => el.remove(), 300);
  }, dur);
}

// ── LOG PANEL ─────────────────────────────────────────────────────
let logPanelBot = null, logInterval = null;

function openLogPanel(idx) {
  logPanelBot = idx;
  $('log-panel-title').textContent = `LOG — Bot #${idx}`;
  $('log-panel').style.display = 'flex';
  fetchLog(idx);
  clearInterval(logInterval);
  logInterval = setInterval(() => { if (logPanelBot) fetchLog(logPanelBot); }, 2000);
}

function closeLogPanel() {
  $('log-panel').style.display = 'none';
  logPanelBot = null;
  clearInterval(logInterval);
}

async function fetchLog(idx) {
  try {
    const d = await (await fetch(`/api/bots/${idx}/log`)).json();
    const body = $('log-panel-body');
    const wasBottom = body.scrollHeight - body.scrollTop - body.clientHeight < 30;
    body.innerHTML = '';
    (d.log || []).forEach(line => {
      const el = document.createElement('div');
      el.className = 'log-line' + (line.includes('❌')||line.includes('Error')||line.includes('fail') ? ' err' : line.includes('✅')||line.includes('Connected') ? ' ok' : '');
      el.textContent = line;
      body.appendChild(el);
    });
    if (wasBottom) body.scrollTop = body.scrollHeight;
  } catch {}
}

// ── BOT TABLE ─────────────────────────────────────────────────────
function updateGrpBar() {
  const bar = $('grp-bar');
  const badge = $('sel-badge');
  const n = selSet.size;
  if (bar) bar.style.display = n ? 'flex' : 'none';
  if (badge) { badge.textContent = `${n} sel.`; badge.style.display = n ? '' : 'none'; }
  if ($('grp-bar-cnt')) $('grp-bar-cnt').textContent = n;
  const chkAll = $('chk-all');
  if (chkAll) {
    const visCount = botsState.filter(b => botVisible(b)).length;
    chkAll.checked = n > 0 && selSet.size >= visCount && visCount > 0;
    chkAll.indeterminate = n > 0 && n < visCount;
  }
}

function toggleSelAll(checked) {
  selSet.clear();
  if (checked) botsState.filter(b => botVisible(b)).forEach(b => selSet.add(b.index));
  renderBots();
  updateGrpBar();
}

function botVisible(b) {
  const f = ($('bot-filter')||{value:''}).value.toLowerCase();
  if (!f) return true;
  return b.name.toLowerCase().includes(f) || String(b.index).includes(f) || b.status.toLowerCase().includes(f) || b.hotel.toLowerCase().includes(f);
}

function dotClass(s) {
  if (s === 'Connected') return 'sdot sdot-conn';
  if (/fail|error|ban/i.test(s)) return 'sdot sdot-fail';
  if (/prep|conn/i.test(s)) return 'sdot sdot-prep';
  return 'sdot sdot-other';
}

function renderBots() {
  const filter = ($('bot-filter')||{value:''}).value.toLowerCase();
  const visible = botsState.filter(b => botVisible(b));
  if ($('filter-info')) $('filter-info').textContent = filter ? `${visible.length}/${botsState.length}` : '';

  ['bot-tbody', 'acc-tbody'].forEach(id => {
    const tb = $(id); if (!tb) return;
    tb.innerHTML = '';
    visible.forEach(b => {
      const tr = document.createElement('tr');
      const sel = selSet.has(b.index);
      if (sel) tr.classList.add('selected');
      const sc = statusClass(b.status);
      const dc = dotClass(b.status);
      const chk = `<td onclick="event.stopPropagation()"><input type="checkbox" ${sel?'checked':''} onchange="(function(e){e.stopPropagation();selSet.has(${b.index})?selSet.delete(${b.index}):selSet.add(${b.index});renderBots();updateGrpBar()})(event)"></td>`;

      // proxy / group badge
      const grp = botGroup(b.index);
      const grpColor = grp ? (pgState[grp]?.color || '#30728C') : null;
      const proxyCell = grp
        ? `<span class="pg-tag" style="background:${grpColor};font-size:7pt">${grp}</span><span style="font-size:7pt;color:var(--fm);margin-left:4px">${b.proxy||'DIRECT'}</span>`
        : `<span style="font-size:7.5pt;color:${b.proxy==='-'||b.proxy==='DIRECT'?'var(--fm)':'var(--gr)'}">${b.proxy||'DIRECT'}</span>`;

      const actBtns = `<button class="btn btn-sm" style="background:#30728C;color:#fff;padding:2px 5px;font-size:7pt" onclick="event.stopPropagation();openBotProxyDlg(${b.index})">Proxy</button>
        <button class="btn btn-sm" style="background:#1d5a72;color:#fff;padding:2px 5px;font-size:7pt;margin-left:2px" onclick="event.stopPropagation();openLogPanel(${b.index})" title="Ver logs">📋</button>`;

      if (id === 'bot-tbody') {
        tr.innerHTML = `${chk}<td>${b.index}</td><td><span class="${dc}"></span><span class="${sc}">${b.status}</span></td><td>${b.name}</td><td>${b.hotel}</td><td>${proxyCell}</td><td>${actBtns}</td>`;
      } else {
        tr.innerHTML = `${chk}<td>${b.index}</td><td>${b.name}</td><td><span class="${dc}"></span><span class="${sc}">${b.status}</span></td><td>${b.hotel}</td><td>${proxyCell}</td><td>${actBtns}</td>`;
      }
      tr.onclick = () => { selSet.has(b.index) ? selSet.delete(b.index) : selSet.add(b.index); renderBots(); updateGrpBar(); };
      tb.appendChild(tr);
    });
  });
  updateGrpBar();
}

async function refreshBots() {
  try {
    const d = await (await fetch('/api/bots')).json();
    botsState = d.bots;
    const conn = d.connected, disc = d.total - conn;
    ['conn-d','conn-c'].forEach(id => $(id) && ($(id).textContent = `CONN: ${conn}`));
    ['disc-d','disc-c'].forEach(id => $(id) && ($(id).textContent = `DISC: ${disc}`));
    $('side-stat').textContent = `${conn} / ${d.total} bots`;
    renderBots();
  } catch {}
}

// ── SSE ──────────────────────────────────────────────────────────
(function startSSE() {
  const src = new EventSource('/stream');
  src.onmessage = e => {
    try {
      const d = JSON.parse(e.data);
      if (d.type === 'status') {
        const b = botsState.find(x => x.index === d.index);
        if (b) { b.status = d.status; renderBots(); }
      }
    } catch {}
  };
  src.onerror = () => setTimeout(startSSE, 3000);
})();
setInterval(refreshBots, 2500);
refreshBots();

// ── HOTEL ────────────────────────────────────────────────────────
(async function loadHotels() {
  const d = await (await fetch('/api/hotel')).json();
  const sel = $('hotel-sel');
  Object.entries(d.names).forEach(([k, n]) => {
    const o = document.createElement('option');
    o.value = k; o.textContent = n;
    if (k === d.hotel) o.selected = true;
    sel.appendChild(o);
  });
})();

async function setHotel(h) {
  await fetch('/api/hotel', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({hotel:h})});
}

// ── TARGETS ──────────────────────────────────────────────────────
async function refreshTargets() {
  const d = await (await fetch('/api/bots')).json();
  const sel = $('cmd-target');
  sel.innerHTML = '<option value="all">All Connected</option>';
  d.bots.filter(b => b.status === 'Connected').forEach(b => {
    const o = document.createElement('option');
    o.value = b.index; o.textContent = `Bot #${b.index} — ${b.name}`;
    sel.appendChild(o);
  });
}

// ── CONNECTION ───────────────────────────────────────────────────
const post = (url, body) => fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});

async function connectAll()    { await post('/api/connect',    {target:'all', split:+v('split-n')}); }
async function disconnectAll() { await post('/api/disconnect', {target:'all'}); }
async function connectSel()    { for (const i of selSet) await post('/api/connect',    {target:i}); }
async function disconnectSel() { for (const i of selSet) await post('/api/disconnect', {target:i}); }

// ── GROUP PROXY ──────────────────────────────────────────────────
async function assignProxyToSel() {
  const proxy = $('grp-proxy-sel').value;
  if (!selSet.size) { toast('Selecciona bots primero', 'err'); return; }
  const d = await (await post('/api/bots/group/proxy', {indices:[...selSet], proxy})).json();
  if (d.ok) {
    selSet.forEach(idx => { const b = botsState.find(x=>x.index===idx); if(b) b.proxy = proxy.split(':')[0]; });
    renderBots();
    toast(`✅ Proxy asignado a ${d.updated} bot(s)`, 'ok');
  }
}

// ── PER-BOT PROXY DIALOG ─────────────────────────────────────────
function openBotProxyDlg(idx) {
  const bot = botsState.find(b => b.index === idx);
  const proxies = [...($('grp-proxy-sel').options)].map(o => o.value).filter(v => v !== 'DIRECT');
  const opts = ['DIRECT', ...proxies].map(p =>
    `<option value="${p}" ${(bot&&bot.proxy===p.split(':')[0])?'selected':''}>${p}</option>`
  ).join('');
  const html = `<div style="margin-bottom:8px"><b>Bot #${idx}</b> — ${bot?bot.name:''}</div>
    <div style="display:flex;gap:6px;align-items:center">
      <select id="_bpx-sel" style="flex:1;padding:4px;border:1px solid #3C88A6;border-radius:4px">${opts}</select>
      <input type="text" id="_bpx-inp" placeholder="ip:port o ip:port:user:pass" style="flex:1">
    </div>
    <p style="font-size:7.5pt;color:var(--fm);margin-top:4px">Selecciona de la lista o escribe uno nuevo.</p>
    <div style="text-align:right;margin-top:8px">
      <button class="btn btn-gr btn-sm" onclick="applyBotProxy(${idx})">✔ Aplicar</button>
    </div>`;
  showHabboAlert(`Cambiar Proxy — Bot #${idx}`, html);
}

async function applyBotProxy(idx) {
  const sel = $('_bpx-sel'), inp = $('_bpx-inp');
  const proxy = (inp && inp.value.trim()) || (sel && sel.value) || 'DIRECT';
  closeHabboAlert();
  const d = await (await post(`/api/bots/${idx}/proxy`, {proxy})).json();
  if (d.ok) {
    const b = botsState.find(x => x.index === idx);
    if (b) b.proxy = proxy.split(':')[0];
    renderBots();
    toast(`✅ Bot #${idx} → <b>${proxy}</b>`, 'ok');
  } else {
    toast(d.error || 'Error desconocido', 'err');
  }
}

// ── ACTIONS ──────────────────────────────────────────────────────
async function act(endpoint, body) {
  const target = $('cmd-target') ? $('cmd-target').value : 'all';
  const r = await post(`/api/action/${endpoint}`, {target, ...body});
  const d = await r.json();
  if (!d.ok) console.warn('Action error:', d.errors);
}

// ── NAVIGATOR ────────────────────────────────────────────────────
let navRooms = [];
async function navFetch() {
  const target = $('cmd-target').value;
  const d = await (await post('/api/action/nav_search', {target, cat:v('nav-cat'), q:v('nav-q')})).json();
  navRooms = d.rooms || [];
  const lb = $('nav-list'); lb.innerHTML = '';
  navRooms.forEach(rm => {
    const div = document.createElement('div');
    div.textContent = `${rm.users}/${rm.max}  ${rm.name}`;
    div.ondblclick = () => { $('room-id').value = rm.id; act('join', {room:rm.id}); };
    lb.appendChild(div);
  });
}

async function scanUsers() {
  const d = await (await post('/api/action/scan', {target:$('cmd-target').value})).json();
  const lb = $('entity-list'); lb.innerHTML = '';
  (d.users||[]).forEach(u => {
    const div = document.createElement('div');
    div.textContent = `${u.name} (${u.gender}) [${u.index}]`;
    lb.appendChild(div);
  });
}

// ── TROLL ─────────────────────────────────────────────────────────
let trollOn = false, trollTimer = null;
function toggleTroll() {
  trollOn = !trollOn;
  const btn = $('troll-btn');
  btn.style.color = trollOn ? 'var(--gr)' : 'var(--or)';
  btn.style.background = trollOn ? ''#0a3a18' : '#3a1a00';
  if (trollOn) trollLoop(); else clearTimeout(trollTimer);
}
function trollLoop() {
  if (!trollOn) return;
  const m = v('troll-inp'); if (m) act('shout', {msg: m});
  trollTimer = setTimeout(trollLoop, 3000);
}

// ── SPAMMER ──────────────────────────────────────────────────────
let spamOn=false, spamTimer=null, spamCount=0;
function spamStart() {
  if (spamOn) return;
  spamOn = true;
  $('spam-status').textContent='● RUNNING'; $('spam-status').className='on';
  spamLoop();
}
function spamStop() {
  spamOn=false; clearTimeout(spamTimer);
  $('spam-status').textContent='■ STOPPED'; $('spam-status').className='off';
}
function spamLoop() {
  if (!spamOn) return;
  const msg = v('spam-msg'), ivl = (+v('spam-ivl')||5)*1000, style = +v('spam-style');
  if (msg) { act('shout',{msg,style}); $('spam-cnt').textContent = ++spamCount; }
  spamTimer = setTimeout(spamLoop, ivl);
}

// ── LOAD / SAVE ──────────────────────────────────────────────────
function loadAccounts(ev) {
  const file = ev.target.files[0]; if (!file) return;
  const reader = new FileReader();
  reader.onload = async e => {
    const d = await (await post('/api/accounts/load', {data:e.target.result})).json();
    if (d.ok) { refreshBots(); toast(`✅ ${d.count} cuentas cargadas`, 'ok'); }
    else toast('Error: ' + d.error, 'err');
  };
  reader.readAsText(file);
}

// ── PROXY GROUPS JS ───────────────────────────────────────────────
const PG_COLORS = ['#1a7a3a','#1155aa','#6633aa','#b85c00','#BF2C2C','#8a7200','#4a6a7a','#30728C'];
let pgState = {};
let pgActive = null;
let pgColorPick = PG_COLORS[0];
let proxiesState = [];

function botGroup(botIdx) {
  const b = botsState.find(x => x.index === botIdx);
  if (!b || !b.proxy || b.proxy === 'DIRECT' || b.proxy === '-') return null;
  for (const [name, g] of Object.entries(pgState)) {
    if ((g.proxies||[]).some(p => p.split(':')[0] === b.proxy)) return name;
  }
  return null;
}

function initColorPicker() {
  const el = $('pg-color-picker'); if (!el) return;
  el.innerHTML = '';
  PG_COLORS.forEach(c => {
    const dot = document.createElement('div');
    dot.style.cssText = `width:14px;height:14px;border-radius:50%;background:${c};border:2px solid ${c===pgColorPick?'#fff':'transparent'};cursor:pointer;box-shadow:0 0 0 1px #000`;
    dot.onclick = () => { pgColorPick = c; initColorPicker(); };
    el.appendChild(dot);
  });
}

function renderGroupList() {
  const el = $('pg-group-list'); if (!el) return;
  el.innerHTML = '';
  const globalActive = pgActive === null;
  const gb = $('pg-global-btn');
  if (gb) { gb.style.background = globalActive ? '#c4dff0' : ''; gb.style.fontWeight = globalActive ? 'bold' : 'normal'; }

  Object.entries(pgState).forEach(([name, g]) => {
    const active = pgActive === name;
    const div = document.createElement('div');
    div.style.cssText = `display:flex;align-items:center;gap:6px;padding:6px 8px;cursor:pointer;border-bottom:1px solid rgba(0,0,0,.1);font-size:8.5pt;color:#1a1a1a;background:${active?'#c4dff0':''};transition:background .12s`;
    div.onmouseenter = () => { if (!active) div.style.background = '#dde9f0'; };
    div.onmouseleave = () => { div.style.background = active ? '#c4dff0' : ''; };
    div.innerHTML = `<span style="width:10px;height:10px;border-radius:50%;background:${g.color};border:1px solid #000;flex-shrink:0"></span>
      <span style="flex:1;font-weight:${active?'bold':'normal'}">${name}</span>
      <span style="color:#4a6a7a;font-size:7.5pt">${(g.proxies||[]).length}</span>
      <button onclick="event.stopPropagation();deleteGroup('${name.replace(/'/g,"\\'")}')" style="background:#BF2C2C;color:#fff;border:1px solid #000;border-radius:3px;padding:1px 5px;font-size:7pt;cursor:pointer">&#x2715;</button>`;
    div.onclick = () => selectGroup(name);
    el.appendChild(div);
  });

  // populate group selectors everywhere
  ['grp-group-sel'].forEach(sid => {
    const sel = $(sid); if (!sel) return;
    const prev = sel.value;
    sel.innerHTML = '<option value="">-- ninguno --</option>';
    Object.keys(pgState).forEach(n => {
      const o = document.createElement('option'); o.value = n; o.textContent = n;
      if (n === prev) o.selected = true;
      sel.appendChild(o);
    });
  });

  // populate proxy quick-selectors from all groups + global
  const allProxies = [...new Set([...proxiesState, ...Object.values(pgState).flatMap(g=>g.proxies||[])])];
  ['grp-proxy-sel','grp-proxy-sel-acc'].forEach(sid => {
    const sel = $(sid); if (!sel) return;
    const prev = sel.value;
    sel.innerHTML = '<option value="DIRECT">DIRECT</option>';
    allProxies.forEach(p => {
      const o = document.createElement('option'); o.value = p; o.textContent = p;
      if (p === prev) o.selected = true;
      sel.appendChild(o);
    });
  });
}

async function renderActivePgProxies() {
  const tb = $('pg-prx-tbody'); if (!tb) return;
  let proxies = [];
  if (pgActive === null) {
    proxies = proxiesState;
  } else {
    proxies = pgState[pgActive]?.proxies || [];
  }
  $('pg-active-cnt').textContent = `${proxies.length} proxies`;
  tb.innerHTML = '';
  if (!proxies.length) {
    tb.innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--fm);padding:12px;font-size:8pt">Sin proxies — usa el formulario para a&#xf1;adir</td></tr>`;
    return;
  }
  proxies.forEach((p, i) => {
    const bots = botsState.filter(b => b.proxy && p.split(':')[0] === b.proxy).map(b => '#'+b.index).join(', ');
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${i+1}</td>
      <td style="font-family:monospace;font-size:7.5pt;color:#1a6a30">${p}</td>
      <td style="font-size:7pt;color:var(--fm)">${bots||'&#x2014;'}</td>
      <td><button class="btn btn-rd btn-sm" style="padding:1px 6px;font-size:7pt" onclick="removeGroupProxy(${i})">&#x1f5d1;</button></td>`;
    tb.appendChild(tr);
  });
}

async function refreshGroups() {
  const [dg, dp] = await Promise.all([
    fetch('/api/proxy-groups').then(r=>r.json()),
    fetch('/api/proxies/list').then(r=>r.json())
  ]);
  pgState = dg.groups || {};
  proxiesState = dp.proxies || [];
  if ($('pg-global-cnt')) $('pg-global-cnt').textContent = proxiesState.length;
  renderGroupList();
  renderActivePgProxies();
}

function selectGroup(name) {
  pgActive = name;
  $('pg-active-name').textContent = name === null ? 'Pool Global' : name;
  const color = name === null ? '#30728C' : (pgState[name]?.color || '#30728C');
  $('pg-active-hdr').style.background = color;
  renderGroupList();
  renderActivePgProxies();
}

async function createGroup() {
  const name = $('pg-name-inp').value.trim();
  if (!name) { toast('Escribe un nombre para el grupo', 'err'); return; }
  const d = await (await post('/api/proxy-groups/create', {name, color: pgColorPick})).json();
  if (d.ok) {
    $('pg-name-inp').value = '';
    await refreshGroups();
    selectGroup(name);
    toast(`Grupo <b>${name}</b> creado`, 'ok');
  } else { toast(d.error || 'Error', 'err'); }
}

async function deleteGroup(name) {
  await fetch(`/api/proxy-groups/${encodeURIComponent(name)}`, {method:'DELETE'});
  if (pgActive === name) { pgActive = null; $('pg-active-name').textContent = 'Pool Global'; }
  await refreshGroups();
  toast(`Grupo <b>${name}</b> eliminado`, 'info');
}

async function addGroupProxies() {
  const text = $('pg-add-text')?.value.trim();
  if (!text) return;
  let d;
  if (pgActive === null) {
    d = await (await post('/api/proxies/add', {proxy: text})).json();
  } else {
    d = await (await post(`/api/proxy-groups/${encodeURIComponent(pgActive)}/add`, {proxies: text})).json();
  }
  if (d.ok) {
    if ($('pg-add-text')) $('pg-add-text').value = '';
    await refreshGroups();
    toast(`&#x2705; ${d.added||''} proxy(s) a&#xf1;adido(s)`, 'ok');
  }
}

async function removeGroupProxy(idx) {
  let d;
  if (pgActive === null) {
    d = await (await post('/api/proxies/delete', {index: idx})).json();
  } else {
    d = await (await post(`/api/proxy-groups/${encodeURIComponent(pgActive)}/remove`, {index: idx})).json();
  }
  if (d.ok) await refreshGroups();
}

function importGroupProxies(ev) {
  const file = ev.target.files[0]; if (!file) return;
  ev.target.value = '';
  const reader = new FileReader();
  reader.onload = async e => {
    if ($('pg-add-text')) $('pg-add-text').value = e.target.result;
    await addGroupProxies();
  };
  reader.readAsText(file);
}

function exportGroupProxies() {
  const proxies = pgActive === null ? proxiesState : (pgState[pgActive]?.proxies || []);
  const blob = new Blob([proxies.join('\n')], {type:'text/plain'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
  a.download = `proxies_${pgActive||'global'}.txt`; a.click();
}

async function clearGroupProxies() {
  if (pgActive === null) {
    for (let i = proxiesState.length - 1; i >= 0; i--)
      await post('/api/proxies/delete', {index: i});
  } else {
    await post(`/api/proxy-groups/${encodeURIComponent(pgActive)}/clear`, {});
  }
  await refreshGroups();
  toast('Pool limpiado', 'info');
}

async function assignGroupToSel() {
  if (!selSet.size) { toast('Selecciona bots primero', 'err'); return; }
  if (pgActive === null) { toast('Selecciona un grupo, no el pool global', 'err'); return; }
  const d = await (await post(`/api/proxy-groups/${encodeURIComponent(pgActive)}/assign`, {indices:[...selSet]})).json();
  if (d.ok) { await refreshBots(); toast(`✅ Grupo <b>${pgActive}</b> → ${d.updated} bot(s)`, 'ok'); }
}

async function assignGroupSelFromBar() {
  const name = $('grp-group-sel')?.value;
  if (!name) { toast('Selecciona un grupo', 'err'); return; }
  if (!selSet.size) { toast('Selecciona bots primero', 'err'); return; }
  const d = await (await post(`/api/proxy-groups/${encodeURIComponent(name)}/assign`, {indices:[...selSet]})).json();
  if (d.ok) { await refreshBots(); toast(`✅ Grupo <b>${name}</b> → ${d.updated} bot(s)`, 'ok'); }
}

// init on load
initColorPicker();
refreshGroups();

</script>

<!-- HABBO ALERT -->
<div id="habbo-alert-overlay">
  <div id="habbo-box">
    <div id="habbo-box-title">
      <span id="habbo-box-icon" style="font-size:18px;flex-shrink:0">&#x2139;</span>
      <h2 id="habbo-box-ttl">Info</h2>
      <div id="habbo-box-cross" onclick="closeHabboAlert()">&#x2715;</div>
    </div>
    <div id="habbo-box-content">
      <p id="habbo-box-msg"></p>
      <div id="habbo-box-footer"><button onclick="closeHabboAlert()">OK</button></div>
    </div>
  </div>
</div>

<!-- ADD ACCOUNT MODAL -->
<div id="add-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.8);z-index:999;align-items:center;justify-content:center">
  <div style="background:#F2F2EB;border:solid 2px #000;border-radius:10px;width:520px;max-width:96vw;box-shadow:2px 2px 14px #000">
    <div style="display:flex;align-items:center;background:#30728C;border:solid 2px #3C88A6;border-bottom:solid 2px #000;border-top-left-radius:8px;border-top-right-radius:8px;padding:6px 8px">
      <span style="flex:1;color:#fff;font-weight:lighter;font-size:14pt;text-align:center;font-family:'Ubuntu Condensed',sans-serif;text-shadow:1px 1px 1px #000;margin-left:22px">AGREGAR CUENTA</span>
      <div onclick="closeAddModal()" style="cursor:pointer;color:#fff;background:#BF2C2C;width:22px;height:22px;border:solid 2px #000;border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:bold;flex-shrink:0" onmouseover="this.style.borderColor='#fff'" onmouseout="this.style.borderColor='#000'">&#x2715;</div>
    </div>
    <div style="padding:16px">
      <div class="row" style="margin-bottom:8px">
        <span style="color:var(--fm);font-size:8pt;width:110px;flex-shrink:0">Nombre (opcional):</span>
        <input type="text" id="add-name" placeholder="Mi Bot" style="flex:1">
      </div>
      <div class="row" style="margin-bottom:12px">
        <span style="color:var(--fm);font-size:8pt;width:110px;flex-shrink:0">Hotel:</span>
        <select id="add-hotel" style="flex:1"></select>
      </div>
      <div style="border-top:1px solid var(--sep);margin-bottom:12px"></div>
      <div style="display:flex;gap:4px;margin-bottom:12px">
        <button id="tab-cookie-btn" class="btn btn-def btn-sm" onclick="switchAddTab('cookie')" style="background:var(--act)">Cookie String</button>
        <button id="tab-manual-btn" class="btn btn-def btn-sm" onclick="switchAddTab('manual')">Manual</button>
      </div>
      <div id="add-tab-cookie">
        <p style="color:var(--fm);font-size:8pt;margin-bottom:6px">
          DevTools (F12) &#x2192; Network &#x2192; Headers &#x2192; <b style="color:var(--cy)">Cookie:</b> &mdash; copia y pega aqu&#xed;:
        </p>
        <textarea id="add-cookie-str" rows="4" placeholder="session.id=abc123; browser_token=xyz789; ..."></textarea>
        <div style="display:flex;align-items:center;gap:12px;margin-top:8px">
          <button class="btn btn-bl btn-sm" onclick="parseCookies()">&#x2315; Parsear</button>
          <span id="parse-sid" style="font-size:8pt;color:var(--fm)">session.id: &mdash;</span>
          <span id="parse-btk" style="font-size:8pt;color:var(--fm)">browser_token: &mdash;</span>
        </div>
      </div>
      <div id="add-tab-manual" style="display:none">
        <div class="row" style="margin-bottom:8px">
          <span style="color:var(--fm);font-size:8pt;width:120px;flex-shrink:0">session.id:</span>
          <input type="text" id="add-sid" placeholder="Valor de session.id" style="flex:1">
        </div>
        <div class="row">
          <span style="color:var(--fm);font-size:8pt;width:120px;flex-shrink:0">browser_token:</span>
          <input type="text" id="add-btk" placeholder="Valor de browser_token" style="flex:1">
        </div>
      </div>
    </div>
    <div style="display:flex;justify-content:flex-end;gap:8px;padding:10px 16px;border-top:1px solid var(--sep)">
      <button class="btn btn-def btn-sm" onclick="closeAddModal()">Cancelar</button>
      <button class="btn btn-gr btn-sm" onclick="submitAddAccount()">&#x271A; Agregar</button>
    </div>
  </div>
</div>

<script>
let _addTab = 'cookie', _parsedSid = '', _parsedBtk = '';

function openAddModal() {
  const sel = $('add-hotel');
  if (!sel.options.length) {
    fetch('/api/hotel').then(r=>r.json()).then(d => {
      Object.entries(d.names).forEach(([k,n]) => {
        const o = document.createElement('option'); o.value=k; o.textContent=n;
        if (k===d.hotel) o.selected=true; sel.appendChild(o);
      });
    });
  }
  $('add-modal').style.display='flex';
}
function closeAddModal() {
  $('add-modal').style.display='none';
  $('add-cookie-str').value=''; $('add-sid').value=''; $('add-btk').value='';
  $('parse-sid').textContent='session.id: —'; $('parse-btk').textContent='browser_token: —';
  $('parse-sid').style.color='var(--fm)'; $('parse-btk').style.color='var(--fm)';
  _parsedSid=''; _parsedBtk='';
}
function switchAddTab(tab) {
  _addTab=tab;
  $('add-tab-cookie').style.display = tab==='cookie'?'':'none';
  $('add-tab-manual').style.display = tab==='manual'?'':'none';
  $('tab-cookie-btn').style.background = tab==='cookie'?'var(--act)':'#30728C';
  $('tab-manual-btn').style.background = tab==='manual'?'var(--act)':'#30728C';
}
function parseCookies() {
  const raw=$('add-cookie-str').value;
  const get=name=>{ const m=raw.match(new RegExp(name+'=([^;\\s]+)')); return m?m[1]:''; };
  _parsedSid=get('session\\.id'); _parsedBtk=get('browser_token');
  $('parse-sid').textContent='session.id: '+(_parsedSid?_parsedSid.slice(0,14)+'...':'—');
  $('parse-btk').textContent='browser_token: '+(_parsedBtk?_parsedBtk.slice(0,10)+'...':'—');
  $('parse-sid').style.color=_parsedSid?'var(--gr)':'var(--rd)';
  $('parse-btk').style.color=_parsedBtk?'var(--gr)':'var(--rd)';
}
async function submitAddAccount() {
  let sid='',btk='';
  if (_addTab==='cookie') { if(!_parsedSid) parseCookies(); sid=_parsedSid; btk=_parsedBtk; }
  else { sid=$('add-sid').value.trim(); btk=$('add-btk').value.trim(); }
  if (!sid||!btk) { toast('Faltan session.id o browser_token','err'); return; }
  const d=await(await post('/api/accounts/add',{name:$('add-name').value.trim(),hotel:$('add-hotel').value,session_id:sid,browser_token:btk})).json();
  if (d.ok) { closeAddModal(); refreshBots(); toast('✅ Cuenta a\xf1adida: '+d.name,'ok'); }
  else toast(d.error||'Error','err');
}
async function saveAccounts() {
  const d=await(await post('/api/accounts/save',{})).json();
  if (d.ok) toast('✅ '+d.count+' cuentas guardadas','ok');
  else toast(d.error||'Error al guardar','err');
}

function showHabboAlert(title, msg, icon) {
  $('habbo-box-ttl').textContent=title;
  $('habbo-box-msg').innerHTML=msg;
  if(icon) $('habbo-box-icon').textContent=icon;
  $('habbo-alert-overlay').classList.add('show');
}
function closeHabboAlert() { $('habbo-alert-overlay').classList.remove('show'); }
document.addEventListener('keydown', e=>{ if(e.key==='Escape'){closeHabboAlert();} });
</script>

"""


@app.route('/')
def index():
    return HTML


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)
