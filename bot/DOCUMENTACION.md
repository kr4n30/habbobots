# Bans BotTools — Documentación

## Estructura de archivos

```
Habbo-Bot-main/
├── main.py            # GUI principal (tkinter)
├── web.py             # Dashboard web (Flask, puerto 5000)
├── state.py           # Estado compartido entre main.py y web.py
├── bot_instance.py    # Clase que representa un bot individual
├── habbo_client.py    # Cliente TCP que habla el protocolo Flash de Habbo
├── sso_retriever.py   # Obtiene el SSO ticket usando las cookies de la cuenta
├── constants.py       # Headers de paquetes, lista de hotels, Sulek auto-fetch
├── accounts.json      # Cuentas guardadas (se genera automáticamente)
├── proxies.txt        # Pool de proxies (opcional)
└── sulek_cache/       # Caché de mensajes descargados de sulek.dev
```

---

## Cómo funciona

### Visión general

El sistema tiene tres capas que se comunican a través de `state.py`:

```
main.py (GUI tkinter)
    └── lanza web.py en hilo daemon → Flask en localhost:5000
    └── gestiona BotInstance[] ← state.bots (lista compartida)

web.py (dashboard navegador)
    └── lee state.bots y state.proxies (misma memoria que main.py)

habbo_client.py (conexión TCP)
    └── una instancia por bot, en su propio hilo
    └── actualiza BotInstance.status / log_buffer en tiempo real
```

---

### Flujo de conexión de un bot

Cuando pulsas **▶ Connect**, ocurren estos pasos en orden (todo en un hilo separado para no bloquear la GUI):

```
1. PREPARAR
   main.py._connect_bot(inst)
   └── inst.set_status('Preparing')
   └── elige proxy: grupo asignado → pool global → DIRECT

2. SSO TICKET
   sso_retriever.get_sso_ticket(cookies, proxy)
   └── POST https://www.habbo.com/api/client/clientnative/url
       con cookies: session.id + browser_token
   └── devuelve un ticket temporal: "300-47b8ef..."
   └── si falla → inst.set_status('Failed')

3. CONEXIÓN TCP
   HabboClientGUI(ticket, proxy, hotel_config, ...)
   └── abre socket TCP → game-us.habbo.com:30000 (o el hotel elegido)
   └── handshake Diffie-Hellman (cifrado RC4)
   └── envía SSO ticket → autenticación
   └── el bot queda "dentro" del juego

4. AUTO-RECONEXIÓN
   hilo en background revisa cada X segundos
   └── si status == 'Disconnected' | 'Failed' → repite desde paso 1
```

---

### Protocolo y headers (constants.py + Sulek)

Habbo usa un protocolo binario propietario sobre TCP. Cada acción es un **paquete** con un ID numérico (header). Estos IDs **cambian con cada actualización del cliente Flash**.

`constants.py` tiene dos clases con todos los IDs:

```python
class Outgoing:   # paquetes que envía el bot → servidor
    SHOUT              = 43
    MOVE_AVATAR        = 2314
    SSO_TICKET         = 30
    ...

class Incoming:   # paquetes que recibe el bot ← servidor
    AUTHENTICATION_OK  = 1378
    ROOM_READY         = 3673
    CHAT               = 3936
    ...
```

#### Auto-actualización con Sulek

Al arrancar `main.py`, se llama automáticamente a `fetch_and_apply_latest_headers()`:

```
1. GET https://api.sulek.dev/releases?variant=flash-windows
   └── obtiene la versión más reciente (ej: WIN63-202606011215)

2. GET https://api.sulek.dev/releases/flash-windows/{version}
   └── obtiene el protocolo (ej: FLASH28)

3. GET https://api.sulek.dev/releases/flash-windows/{version}/messages
   └── descarga todos los IDs de mensajes → sulek_cache/{version}_messages.json
   └── si el archivo ya existe, usa la caché (sin descargar de nuevo)

4. Aplica los IDs a Outgoing.* e Incoming.*  en tiempo real (setattr)
   └── actualiza también RELEASE_VERSION y CLIENT_TYPE globales
```

Si Sulek falla (sin internet, API caída), el bot sigue funcionando con los valores hardcodeados de fallback en `constants.py`. La barra de estado de la GUI muestra el resultado.

---

### Proxies

Soporta dos modos:

**Pool global** — todos los bots rotan por la misma lista en orden cíclico.

**Grupos de proxy** — puedes crear grupos y asignar un grupo a bots concretos. Cada grupo rota de forma independiente.

```
Proxies > Crear grupo "grupo1"
         Añadir proxies al grupo
Dashboard > Seleccionar bots > Assign Sel. > "grupo1"
```

Formato soportado:
```
ip:port
ip:port:usuario:contraseña    ← SOCKS5 con autenticación
```

---

### state.py — Estado compartido

`state.py` es el pegamento entre todos los módulos. Usa listas mutables (pasadas por referencia) para que main.py y web.py operen sobre los mismos objetos en memoria:

```python
bots:         list[BotInstance]   # lista de todos los bots
proxies:      list[str]           # pool global de proxies
proxy_groups: dict                # grupos de proxies con rotación propia
sse_q:        deque               # cola de eventos Server-Sent-Events para web.py
hotel:        str                 # hotel activo por defecto
```

La rotación de proxies es thread-safe con un `threading.Lock`.

---

### BotInstance

Cada cuenta cargada crea un `BotInstance`:

```python
inst.account_data   # lista de cookies + metadata de la cuenta
inst.index          # número del bot (1, 2, 3...)
inst.status         # Idle / Preparing / Connecting / Connected / Disconnected / Failed
inst.client         # referencia al HabboClientGUI activo (o None)
inst.proxy_address  # proxy en uso en este momento
inst.log_buffer     # deque de las últimas 200 líneas de log con timestamp
inst.sso_ticket     # último ticket obtenido
```

---

## Cómo iniciarlo

### Requisitos

```bash
pip install requests flask requests[socks]
```

> `requests[socks]` es necesario para proxies SOCKS5.

### Arrancar

```bash
cd Habbo-Bot-main
python main.py
```

Esto abre la GUI y lanza el dashboard web en `http://localhost:5000` automáticamente.

---

### Añadir una cuenta

**Opción A — Cookie string (recomendado):**

1. Entra a `habbo.com` en Chrome con la cuenta que quieras añadir
2. Abre DevTools (`F12`) → pestaña **Network** → recarga la página (`F5`)
3. Haz clic en cualquier request a `habbo.com` → **Headers** → copia la línea que empieza por `Cookie:`
4. En la GUI: `Accounts → ✚ Add → pega la línea → ⌕ Parse → ✚ Agregar Cuenta`

**Opción B — Manual:**

En `Accounts → ✚ Add → pestaña Manual`, introduce directamente:
- `session.id` — el valor de esa cookie
- `browser_token` — el valor de esa cookie

Ambas se encuentran en `Application → Cookies → https://www.habbo.com` en DevTools.

---

### Conectar bots

```
Dashboard → selecciona bots (Ctrl+A = todos) → ▶ Conn
                                              o
Sidebar → ▶ Connect All  (conecta todos con delay entre ellos)
```

El parámetro **Split** en la topbar de Control indica cada cuántos bots se hace una pausa al conectar en masa (evita flood de conexiones).

---

### Atajos de teclado

| Tecla | Acción |
|-------|--------|
| `F5` | Refrescar UI |
| `Ctrl+A` | Seleccionar todos |
| `Delete` | Desconectar seleccionados |
| `Enter` | Conectar seleccionados |
| `Ctrl+S` | Guardar accounts.json |

---

### Dashboard web

Accesible en `http://localhost:5000` mientras la GUI esté abierta.

Permite ver el estado de todos los bots, enviar comandos, y controlar el spammer desde el navegador, sin necesidad de tener la ventana de tkinter en primer plano.

---

## Resumen del flujo completo

```
python main.py
    │
    ├── Lee habbonet_cfg.ini (geometría de ventana, hotel, opciones)
    ├── Carga accounts.json → crea BotInstance por cada cuenta
    ├── Carga proxies.txt → state.proxies
    ├── Lanza web.py en hilo daemon (Flask :5000)
    ├── Llama a fetch_and_apply_latest_headers() en hilo background
    │       └── Sulek API → actualiza Outgoing/Incoming
    └── Muestra GUI
            │
            └── Usuario pulsa ▶ Connect
                    │
                    ├── sso_retriever → POST habbo.com → SSO ticket
                    ├── HabboClientGUI → TCP handshake → autenticado
                    └── BotInstance.status = 'Connected'
```
