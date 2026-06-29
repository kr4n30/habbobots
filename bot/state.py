"""
state.py — Estado compartido entre main.py (tkinter) y web.py (Flask).
Ambos operan sobre las mismas listas de bots y proxies.
"""
import threading
from collections import deque

# Listas mutables compartidas (se pasan por referencia, no por copia)
bots:    list = []   # list[BotInstance]
proxies: list = []   # list[str]  ← pool global (sin grupo)

# Grupos de proxies: {nombre: {'color': '#hex', 'proxies': [str, ...], '_idx': int}}
proxy_groups: dict = {}

# Proxy rotation (pool global)
_pidx  = 0
_plock = threading.Lock()

# SSE event queue para web.py
sse_q: deque = deque(maxlen=200)

# Hotel activo (clave de constants.HOTELS)
hotel: str = 'habbo.com'


def push_sse(data: dict):
    """Encola un evento SSE (consumido por web.py /stream)."""
    import json
    sse_q.append(json.dumps(data))


def next_proxy() -> str:
    """Devuelve el siguiente proxy en rotación (thread-safe). 'DIRECT' si no hay."""
    global _pidx
    with _plock:
        if not proxies:
            return 'DIRECT'
        p = proxies[_pidx % len(proxies)]
        _pidx += 1
        return p


def reset_proxy_index():
    global _pidx
    with _plock:
        _pidx = 0


def next_proxy_from_group(group_name: str) -> str:
    """Devuelve el siguiente proxy de un grupo concreto en rotación."""
    with _plock:
        g = proxy_groups.get(group_name)
        if not g or not g.get('proxies'):
            return 'DIRECT'
        pool = g['proxies']
        idx  = g.get('_idx', 0) % len(pool)
        g['_idx'] = idx + 1
        return pool[idx]
