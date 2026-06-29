#!/usr/bin/env python3
"""
browser_helper.py — Mini navegador de login para Bans BotTools.
argv[1] = URL base del hotel   (ej: https://www.habbo.es)
argv[2] = nombre del hotel     (ej: habbo.es)
Salida stdout: una linea JSON con session_id y browser_token.

Login form analizado (AngularJS):
  - form.login-form__form
  - input[name=email] / input[name=password]
  - button.habbo-login-button[name=loginButton]
  - hCaptcha: iframe[data-hcaptcha-widget-id]
      * invisible (checkbox-invisible) = auto, no requiere usuario
      * visible   (challenge)          = usuario debe resolverlo
"""
import sys, json, threading, time

# UA de Chrome real — Edge WebView2 expone "WebView/1.0" por defecto
CHROME_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/125.0.0.0 Safari/537.36'
)

# hCaptcha: distingue invisible (auto) de visible (requiere usuario)
# - 'none'      => no hay captcha
# - 'invisible' => captcha invisible, no pausar polling
# - 'visible'   => challenge visible, pausar polling
_JS_CAPTCHA_STATE = """(function(){
  var frames = document.querySelectorAll('iframe[data-hcaptcha-widget-id]');
  if (!frames.length) return 'none';
  for (var i = 0; i < frames.length; i++) {
    var src = frames[i].src || '';
    var vis = frames[i].style.display !== 'none' && frames[i].style.visibility !== 'hidden';
    if (src.indexOf('checkbox-invisible') === -1 && vis) return 'visible';
  }
  return 'invisible';
})()"""

# Detecta si el form de login sigue visible (si desaparece = login OK o redirect)
_JS_FORM_GONE = """(!document.querySelector('form.login-form__form'))"""

# Barra de estado flotante (pointer-events:none = no interfiere con clicks)
_JS_BAR = """(function(){
  if (document.getElementById('__bbt_bar')) return;
  var b = document.createElement('div');
  b.id = '__bbt_bar';
  b.style.cssText = [
    'position:fixed','top:0','left:0','right:0','z-index:2147483647',
    'background:#1d5a72','color:#c8eeff',
    'font:bold 12px Segoe UI,sans-serif',
    'padding:5px 14px','display:flex','align-items:center','gap:10px',
    'box-shadow:0 2px 6px rgba(0,0,0,.5)','pointer-events:none'
  ].join(';');
  b.innerHTML = '<span style="background:#30728C;padding:2px 8px;border-radius:3px;color:#fff">BBT</span>'
              + '<span id="__bbt_msg">Iniciando...</span>';
  document.body && document.body.insertBefore(b, document.body.firstChild);
})()"""

def _js_set_msg(txt):
    safe = txt.replace("'", "\\'")
    return ("(function(){"
            "var e=document.getElementById('__bbt_msg');"
            "if(e)e.textContent='" + safe + "';"
            "})();")


def main():
    base_url   = sys.argv[1] if len(sys.argv) > 1 else 'https://www.habbo.com'
    hotel_name = sys.argv[2] if len(sys.argv) > 2 else 'habbo.com'

    try:
        import webview
    except ImportError:
        print(json.dumps({'session_id': None, 'browser_token': None,
                          'error': 'pywebview no instalado — pip install pywebview'}))
        sys.exit(1)

    result        = {'session_id': None, 'browser_token': None}
    _done         = threading.Event()
    _poll_started = threading.Event()

    # ------------------------------------------------------------------
    def _extract(w):
        # Metodo 1: get_cookies() — incluye httpOnly via Edge WebView2 API
        try:
            for c in (w.get_cookies() or []):
                nm  = c.get('name', '')  if isinstance(c, dict) else getattr(c, 'name', '')
                val = c.get('value', '') if isinstance(c, dict) else getattr(c, 'value', '')
                if nm == 'session.id':    result['session_id']    = val
                if nm == 'browser_token': result['browser_token'] = val
        except Exception:
            pass
        # Metodo 2: document.cookie — fallback (no-httpOnly)
        if not (result['session_id'] and result['browser_token']):
            try:
                cs = w.evaluate_js('document.cookie') or ''
                for part in cs.split(';'):
                    k, _, v = part.strip().partition('=')
                    if k.strip() == 'session.id':    result['session_id']    = v.strip()
                    if k.strip() == 'browser_token': result['browser_token'] = v.strip()
            except Exception:
                pass
        return bool(result['session_id'] and result['browser_token'])

    def _js(w, code):
        try: return w.evaluate_js(code)
        except Exception: return None

    # ------------------------------------------------------------------
    def _poll(w):
        time.sleep(1.5)
        _js(w, _JS_BAR)
        _js(w, _js_set_msg('Inicia sesion en ' + hotel_name + ' y pulsa Conectar'))

        cap_was_visible = False

        for cycle in range(300):   # max 10 min (2s/ciclo)
            if _done.is_set():
                break

            cap_state = _js(w, _JS_CAPTCHA_STATE) or 'none'

            # hCaptcha VISIBLE (challenge real) — pausar para no robar foco
            if cap_state == 'visible':
                if not cap_was_visible:
                    cap_was_visible = True
                    _js(w, _js_set_msg('hCaptcha visible — resuelve el challenge manualmente'))
                time.sleep(5)
                continue

            # hCaptcha invisible — se resuelve solo, no pausar
            if cap_was_visible and cap_state != 'visible':
                cap_was_visible = False
                _js(w, _js_set_msg('Challenge resuelto — completando login...'))

            # Form desaparecio = posible redirect post-login (senal rapida)
            form_gone = bool(_js(w, _JS_FORM_GONE))
            if form_gone and cycle > 2:
                _js(w, _js_set_msg('Login detectado — extrayendo cookies...'))

            # Reinyectar barra tras posibles redirects de la SPA
            _js(w, _JS_BAR)

            # Extraccion principal de cookies
            if _extract(w):
                _done.set()
                _js(w, _js_set_msg('Cookies capturadas — puedes cerrar esta ventana'))
                _js(w, "document.title='Listo — cierra la ventana';")
                break

            if cycle % 5 == 0:
                _js(w, _js_set_msg('Esperando login en ' + hotel_name + '...'))

            time.sleep(2)

    # ------------------------------------------------------------------
    # UA realista antes de crear la ventana
    try:
        import webview as _wv
        _wv.settings['user_agent'] = CHROME_UA
    except Exception:
        pass

    win = webview.create_window(
        'Bans BotTools  |  ' + hotel_name + '  |  Inicia sesion y cierra cuando termines',
        url=base_url,
        width=1200, height=820,
        min_size=(920, 650),
    )

    def _on_loaded():
        # Solo arrancar el hilo una vez (ignora recargas y redirects)
        if not _poll_started.is_set():
            _poll_started.set()
            threading.Thread(target=_poll, args=(win,), daemon=True).start()

    win.events.loaded += _on_loaded
    webview.start()

    _extract(win)   # intento final al cerrar
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
