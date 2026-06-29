# EXPLICACIÓN COMPLETA DEL PROYECTO — HabboBOTS

> Este documento explica qué hace cada carpeta, archivo, ruta y función del proyecto,
> cómo se conectan entre sí, y qué editar cuando quieras cambiar algo concreto.

---

## VISIÓN GENERAL: 3 SERVICIOS INDEPENDIENTES

```
┌─────────────────────────────────────────────────────────────────┐
│                         USUARIO EN EL NAVEGADOR                 │
└───────────────────────────────┬─────────────────────────────────┘
                                │ HTTPS (nginx)
         ┌──────────────────────┼───────────────────────┐
         ▼                      ▼                       ▼
  ┌─────────────┐      ┌──────────────────┐    ┌────────────────┐
  │  FRONTEND   │      │    BACKEND       │    │   BOT MANAGER  │
  │  Astro.js   │◄────►│  Node.js/Express │◄──►│    Python      │
  │  Puerto 4321│      │  Puerto 3001     │    │  Puerto 5001   │
  └─────────────┘      └────────┬─────────┘    └────────────────┘
                                │                       │
                          SQLite (DB)           Habbo.es API
                          habbobots.db         (WebSocket)
```

- **Frontend** (Astro): lo que ve el usuario. Llama al backend vía `/api/*`.
- **Backend** (Node.js + Express): toda la lógica de negocio, JWT, pagos, DB.
- **Bot Manager** (Python): se conecta a Habbo y ejecuta acciones reales.

El **frontend** en producción se sirve estático desde nginx.  
El **backend** es el único que toca la base de datos.  
El **bot manager** tiene su propia mini-BD (`bots.db`) para rastrear instancias activas.

---

## 📁 CARPETA: `backend/`

### `backend/.env`
Variables de entorno. **Nunca subir a git.** Contiene:
- `JWT_SECRET` — clave para firmar tokens. Cámbiala en producción.
- `DB_PATH` — ruta al fichero SQLite.
- `SMTP_*` — configuración de email.
- `DISCORD_*` — webhooks y OAuth.
- `VAPID_*` — notificaciones push PWA.
- `BOT_VPS_URL` — URL del bot manager Python (puerto 5001).
- `ALLOW_MULTIPLE_ACCOUNTS_PER_IP` — `false` por defecto: 1 cuenta por IP.

### `backend/src/index.js`
**Punto de entrada del servidor.** Aquí:
- Se crea la app Express.
- Se aplican middlewares globales (CORS, helmet, rate limit, morgan).
- Se montan todas las rutas.
- Se inicializa la base de datos (`initDB()`).
- Se arranca Socket.io (`initSocket()`).
- Se arranca el procesador de pedidos (`startOrderProcessor()`).
- Se arrancan los cron jobs (`startCron()`).

> **¿Dónde añado una nueva ruta?** → Importa el router aquí y haz `app.use('/ruta', router)`.

---

### `backend/src/database/init.js`
Define **todo el esquema SQL** y ejecuta migraciones.

#### Tablas principales:
| Tabla | Para qué sirve |
|---|---|
| `users` | Cuentas de usuario. `role` = user/moderator/admin. `registration_ip` = 1 IP por cuenta. |
| `habbo_accounts` | Cuentas Habbo vinculadas por verificación de motto. 1 por hotel. |
| `habbo_identities` | `uniqueId` estable de Habbo (si el nick cambia, sigue el mismo uid). |
| `bots` | Bots alquilados por cada usuario. `status` = online/offline/busy/error. |
| `products` | Catálogo de servicios de la tienda (respetos, mascotas, llenar sala…). |
| `service_orders` | Pedidos de la tienda. `status` = pending/active/completed/cancelled/failed. |
| `credit_transactions` | Cada movimiento de créditos (compra, gasto, reembolso…). |
| `payments` | Pagos reales (Stripe, PayPal, crypto). Vinculados a un `pack_id`. |
| `tickets` + `ticket_messages` | Sistema de soporte. |
| `coupons` | Códigos de descuento. |
| `affiliates` + `affiliate_rewards` | Programa de afiliados. |
| `bot_logs` | Historial de acciones ejecutadas por cada bot. |
| `push_subscriptions` | Subscripciones PWA para notificaciones push. |
| `ip_logs` | Log de logins y registros por IP (anti-spam). |
| `audit_logs` | Acciones admin (baneos, ajuste de créditos…). |

> **¿Cómo añado una columna nueva?** → Añade un `ALTER TABLE` al array `migrations` al final de `initDB()`. Se ejecuta automáticamente al arrancar; si ya existe, el `try/catch` lo ignora.

---

### `backend/src/middleware/auth.js`
Dos middlewares exportados:
- **`requireAuth`**: verifica JWT → mete el usuario en `req.user`. Si el token falla → 401.
- **`requireAdmin`**: llama a `requireAuth` y además comprueba que `role === 'admin' || 'moderator'` → 403 si no.

> **¿Cómo proteger una nueva ruta?** → `router.get('/mi-ruta', requireAuth, handler)` o `requireAdmin`.

---

### `backend/src/routes/` — Todas las rutas API

Cada archivo es un Express Router. Se montan en `index.js`.

#### `auth.js` → `/auth/*`
| Endpoint | Qué hace |
|---|---|
| `POST /auth/pre-register` | Paso 1 del registro: valida email+password, genera código de motto Habbo, guarda en `pending_registrations`. |
| `POST /auth/register` | Paso 2: verifica motto en la API de Habbo, crea usuario, vincula cuenta Habbo. **Aquí va el bloqueo 1 IP = 1 cuenta.** |
| `GET /auth/verify-email` | Marca email como verificado desde el link del correo. |
| `POST /auth/resend-email` | Reenvía email de verificación. |
| `POST /auth/login` | Login por email+password. Devuelve JWT. |
| `GET /auth/discord` | Redirige a OAuth de Discord. |
| `GET /auth/discord/callback` | Callback de Discord: crea o vincula usuario. |
| `GET /auth/me` | Devuelve el usuario autenticado (necesita JWT). |

> **¿Quiero cambiar el flujo de registro?** → Edita `auth.js`. El flujo de 2 pasos (pre-register → verify motto → register) está aquí.

#### `users.js` → `/users/*`
- `GET /users/me` — perfil propio completo (con créditos, hoteles, stats).
- `PATCH /users/me` — actualizar username/email/avatar.
- `GET /users/:nameOrId` — perfil público de otro usuario.
- `/users/2fa/*` — configurar TOTP (autenticación en dos pasos).

#### `bots.js` → `/bots/*`
- `GET /bots` — lista los bots del usuario autenticado.
- `POST /bots` — crea/alquila un nuevo bot (descuenta créditos, llama al VPS).
- `DELETE /bots/:id` — cancela un bot (reembolso proporcional, para el VPS).
- `POST /bots/:id/action` — ejecuta una acción en el bot (mover, saludar, emote…). Guarda en `bot_logs`.
- `GET /bots/:id/logs` — historial de acciones del bot.

#### `admin.js` → `/admin/*`
Solo accesible con `requireAdmin`.
- `GET /admin/overview` — estadísticas generales del dashboard admin.
- `GET /admin/users` — lista usuarios con filtros (search, role, banned, page).
- `PATCH /admin/users/:id` — editar usuario (créditos, rol, banear).
- `GET /admin/orders` — todos los pedidos.
- `PATCH /admin/orders/:id` — cambiar estado de un pedido.
- `GET /admin/logs` — audit log general.
- `GET /admin/reviews` — todas las reseñas.
- `GET /admin/bots` — todos los bots del sistema.
- `DELETE /admin/bots/:id` — forzar eliminación.
- `GET /admin/vps-status` — ping al bot manager + estadísticas de pools.
- `POST /admin/vps/command` — enviar comando raw al VPS.
- `POST /admin/users/:id/set-role` — cambiar rol de un usuario.

#### `products.js` → `/products/*`
- `GET /products` — catálogo de productos activos.
- `POST /products` (admin) — crear producto.
- `PATCH /products/:id` (admin) — editar producto.
- `DELETE /products/:id` (admin) — desactivar producto.

#### `credits.js` → `/credits/*`
- `GET /credits/packs` — packs de créditos disponibles para comprar.
- `POST /credits/purchase` — iniciar compra (Stripe/PayPal/crypto).
- `POST /credits/stripe/webhook` — callback de Stripe.
- `GET /credits/transactions` — historial de transacciones del usuario.

#### `habbo.js` → `/habbo/*`
- `GET /habbo/profile/:hotel/:name` — consulta el perfil de un nick en la API pública de Habbo.
- `POST /habbo/verify/request` — genera código de motto y lo guarda en `verify_tokens`.
- `POST /habbo/verify/check` — comprueba que el motto del personaje tiene el código → vincula la cuenta.
- `GET /habbo/accounts` — lista las cuentas Habbo vinculadas al usuario.

#### `tickets.js` → `/tickets/*`
- `POST /tickets` — crear ticket de soporte.
- `GET /tickets` — mis tickets (user) / todos (admin).
- `GET /tickets/:id` — detalle con mensajes.
- `POST /tickets/:id/reply` — responder.
- `PATCH /tickets/:id/status` — cambiar estado (admin).

#### `affiliates.js` → `/affiliates/*`
- `GET /affiliates/my` — mis stats de afiliado (referidos, recompensas).
- `POST /affiliates/validate` — valida código de referido.

#### `coupons.js` → `/coupons/*`
- `POST /coupons/validate` — valida un código de cupón y devuelve el descuento.
- `GET /admin/coupons` (admin) — lista todos los cupones.
- `POST /admin/coupons` (admin) — crear cupón.
- `PATCH /admin/coupons/:id` (admin) — activar/desactivar.
- `DELETE /admin/coupons/:id` (admin) — eliminar.

#### `metrics.js` → `/admin/metrics/*`
Solo admin. Devuelve KPIs: usuarios, bots activos, ingresos del mes, churn, datos para gráficas Chart.js.

#### `status.js` → `/status`
**Público — no requiere auth.** Pinga `BOT_VPS_URL/health` y `BOT_GUI_URL/health` en paralelo. Devuelve estado de servicios + incidencias recientes.

#### `push.js` → `/push/*`
- `GET /push/vapid-key` — devuelve la clave pública VAPID para el service worker.
- `POST /push/subscribe` — guarda suscripción push del navegador.
- `POST /push/unsubscribe` — la elimina.

#### `notifications.js` → `/notifications/*`
Notificaciones in-app del usuario (campana en el navbar).

#### `stats.js` → `/stats/*`
Estadísticas públicas del dashboard de usuario.

#### `reviews.js` → `/reviews/*`
- `GET /reviews` — reseñas de la plataforma.
- `POST /reviews` — crear reseña.
- `PATCH /reviews/:id` (admin) — aprobar/rechazar.
- `DELETE /reviews/:id` (admin) — eliminar.

#### `botpanel.js` → `/admin/botpanel/*`
Proxy para el panel de control gráfico del bot manager (puerto 5000).

---

### `backend/src/services/` — Servicios internos

| Archivo | Qué hace |
|---|---|
| `email.js` | Envía emails vía nodemailer (SMTP). Funciones: `sendVerificationEmail`, `sendBotExpiryEmail`, `sendServiceCompletedEmail`. No-op si `SMTP_HOST` no está configurado. |
| `discord.js` | Envía mensajes a webhooks de Discord. `sendDiscordAlert(msg, webhook)`. |
| `push.js` | Envía notificaciones push PWA. `sendPushToUser(userId, {title, body, url})`. Usa VAPID. |
| `cron.js` | Jobs periódicos: cada hora verifica bots que expiran en 24h (email+push), cada 5min monitorea el VPS (Discord si cae), cada 6h limpia bots expirados. |
| `orderProcessor.js` | Procesa pedidos pendientes de la tienda: llama al VPS, cambia estados, envía email de completado. |
| `vps.js` | Abstracción para comunicarse con el bot manager Python (HTTP). |
| `socket.js` | Configura Socket.io para notificaciones en tiempo real al frontend. |
| `credits.js` | Helpers de transacciones de créditos (deducir, añadir, con auditoría). |

---

## 📁 CARPETA: `frontend/`

### `frontend/astro.config.mjs`
Configuración de Astro. Importante:
- Modo `server` (SSR) o `static` — actualmente hybrid/static.
- El proxy `/api/*` → `http://localhost:3001/*` solo en desarrollo. En producción nginx lo hace.

### `frontend/public/`
Archivos estáticos servidos directamente:
- `css/style.css` — todos los estilos globales de la aplicación.
- `js/api.js` — cliente de la API. **Un objeto window por cada endpoint.** Se carga en DashLayout.
- `js/main.js` — helpers globales (toast, copyToClipboard, etc.).
- `manifest.json` — manifiesto PWA.
- `sw.js` — service worker: cache offline + manejo de notificaciones push.

### `frontend/src/layouts/`

#### `DashLayout.astro`
El layout de **todas las páginas del dashboard** (sidebar + navbar + contenido).
- Carga `api.js`, `main.js`, `style.css`.
- Navbar: logo, avatar Habbo del usuario (se carga dinámicamente con su nick de Habbo), nombre de usuario.
- Sidebar: links de navegación. Los links de admin solo se muestran si `role === 'admin'` o `'moderator'`.
- **Prop `activePage`**: el link activo en el sidebar.
- El script inline al final: carga el usuario con `AuthAPI.me()`, rellena nombre/avatar, registra el service worker PWA.

> **¿Cómo añado un link al sidebar?** → Busca el bloque `<!-- sidebar -->` en DashLayout.astro y añade el `<a>`. Si es solo para admins, ponlo dentro del bloque `if (role === 'admin')` del script.

#### `AuthLayout.astro`
Layout simple para login/registro (sin sidebar, fondo oscuro con partículas).

---

### `frontend/src/pages/` — Todas las páginas

| Página | URL | Auth | Descripción |
|---|---|---|---|
| `index.astro` | `/` | No | Landing page pública con hero, features y CTA. |
| `home.astro` | `/home` | Sí (user) | Dashboard del usuario: resumen de bots, créditos, pedidos recientes. |
| `dashboard.astro` | `/dashboard` | Sí (admin) | Panel admin: tabs con usuarios, pedidos, productos, tickets, logs, métricas. |
| `bots.astro` | `/bots` | Sí | Lista de bots del usuario con estado en tiempo real. |
| `mi-bot.astro` | `/mi-bot` | Sí | Control de un bot específico: mover a sala, emotes, ver logs. |
| `tienda.astro` | `/tienda` | Sí | Tienda de créditos y servicios. |
| `servicios.astro` | `/servicios` | Sí | Mis servicios activos + catálogo. |
| `perfil.astro` | `/perfil` | Sí | Perfil con avatar Habbo, verificación por motto, stats. |
| `ajustes.astro` | `/ajustes` | Sí | Configuración de cuenta (TOTP, notificaciones…). |
| `afiliados.astro` | `/afiliados` | Sí | Programa de afiliados: link único, stats, referidos. |
| `soporte.astro` | `/soporte` | Sí | Crear ticket de soporte y ver los propios. |
| `metricas.astro` | `/metricas` | Sí (admin) | Métricas avanzadas con gráficas Chart.js. |
| `admin-tickets.astro` | `/admin-tickets` | Sí (admin) | Gestión de todos los tickets de soporte. |
| `admin-cupones.astro` | `/admin-cupones` | Sí (admin) | Gestionar cupones de descuento. |
| `botcontrol.astro` | `/botcontrol` | Sí (admin) | Panel de control del bot manager Python (embed/proxy). |
| `status.astro` | `/status` | **No** | Página pública de estado del sistema en tiempo real. |
| `stats.astro` | `/stats` | No | Estadísticas públicas (usuarios, bots, pedidos). |
| `verificar.astro` | `/verificar` | No | Explica el proceso de verificación Habbo. |
| `verificar-habbo.astro` | `/verificar-habbo` | Sí | Página para vincular cuenta Habbo post-registro. |
| `verificar-email.astro` | `/verificar-email` | No | Confirmación de verificación de email. |

---

### `frontend/public/js/api.js` — El cliente de la API

Cada sección expone un objeto global `window.XxxAPI` con métodos que llaman a `/api/*`:

```
window.AuthAPI      → /auth/*        (login, registro, me)
window.UsersAPI     → /users/*       (perfil, 2FA)
window.BotsAPI      → /bots/*        (lista, crear, acción, logs)
window.CreditsAPI   → /credits/*     (packs, comprar, transacciones)
window.HabboAPI     → /habbo/*       (verificar motto, listar cuentas)
window.ProductsAPI  → /products/*    (catálogo)
window.StatsAPI     → /stats/*       (estadísticas públicas)
window.AdminAPI     → /admin/*       (todo el panel admin)
window.ReviewsAPI   → /reviews/*     (reseñas)
window.AffiliatesAPI→ /affiliates/*  (afiliados)
window.CouponsAPI   → /coupons/*     (validar cupón)
window.TicketsAPI   → /tickets/*     (soporte)
window.PushAPI_HB   → /push/*        (suscribir/desuscribir notificaciones)
window.StatusAPI    → /status        (estado del sistema)
```

> El token JWT se guarda en `sessionStorage` con clave `hb_token`.  
> **¿Dónde añado una nueva llamada a la API?** → Añade un método al objeto correspondiente en `api.js`.

---

## 📁 CARPETA: `bot/`

Este es el núcleo que se conecta realmente a Habbo. Está escrito en Python.

### Archivos principales:

| Archivo | Qué hace |
|---|---|
| `headless_bot_manager.py` | **Servicio principal** (puerto 5001). API Flask para crear/controlar/destruir bots sin interfaz gráfica. El backend Node.js lo llama aquí. |
| `web.py` | **Panel web** (puerto 5000). Interfaz visual Flask para gestionar bots manualmente desde el navegador. Solo para uso admin. |
| `bot_instance.py` | Clase `BotInstance`: representa un bot individual con su estado, logs, cuenta Habbo, proxy asignado. |
| `habbo_client.py` | `HabboClientGUI`: se conecta al WebSocket de Habbo, parsea paquetes, ejecuta comandos. |
| `sso_retriever.py` | Obtiene el SSO ticket de Habbo (necesario para autenticarse). |
| `composers.py` | Funciones para construir paquetes de red Habbo (mover, hablar, emote…). |
| `parsers.py` | Parsea los paquetes que llegan de Habbo (posición de otros usuarios, mensajes…). |
| `habbo_packet.py` | Clase base para los paquetes binarios del protocolo Habbo. |
| `ArcFour.py` / `crypto.py` | Cifrado RC4 que usa el protocolo Habbo. |
| `constants.py` | URLs de hoteles, IDs de paquetes, constantes de configuración. |
| `state.py` | Estado global compartido: lista de bots activos, proxies, hotel activo, cola SSE. |
| `room_map.py` | Lógica de mapa de sala (pathfinding básico para mover bots). |
| `db.py` | SQLite local (`bots.db`) para persistir asignaciones de bots entre reinicios. |
| `shop.py` / `shop.db` | Sistema de tienda interno (legado, puede no usarse). |
| `main.py` | Arranca ambos servidores (headless + web GUI) juntos. |
| `requirements.txt` | Dependencias Python: `flask`, `flask-cors`, `websocket-client`, `requests`, etc. |

### API del Bot Manager (puerto 5001)

El backend Node.js llama a estos endpoints:

| Endpoint | Qué hace |
|---|---|
| `GET /health` | Health check (devuelve `{"status":"ok"}`). |
| `POST /bots/create` | Crea una nueva instancia de bot con las credenciales y sala. |
| `POST /bots/<id>/stop` | Para un bot. |
| `POST /bots/<id>/action` | Ejecuta una acción (mover, emote, hablar, respetar…). |
| `GET /bots` | Lista todos los bots activos con su estado. |
| `GET /bots/<id>` | Estado detallado de un bot específico. |
| `POST /pool/stop-all` | Para todos los bots (mantenimiento). |
| `GET /stats` | Stats globales del pool (activos, en cola, proxies disponibles). |

---

## CÓMO SE CONECTA TODO

### Registro de un usuario nuevo

```
Browser → POST /api/auth/pre-register (email + password)
        ← { pendingId, code }   ← guarda en pending_registrations

Usuario va a Habbo y pone el código en su motto

Browser → POST /api/auth/register (pendingId + hotel + habboName)
        → Backend llama a Habbo API para verificar el motto
        → Crea usuario en SQLite con registration_ip
        → Envía email de verificación
        ← { message: "Cuenta creada" }
```

### Alquilar un bot

```
Browser → POST /api/bots (hotel, name, room, duration)
        → Backend descuenta créditos (credit_transactions)
        → Backend llama a POST http://BOT_VPS_URL/bots/create
        → Bot manager lanza instancia Python
        → Backend guarda el bot en SQLite con status 'online'
        ← { bot }
```

### Ejecutar acción en el bot

```
Browser → POST /api/bots/:id/action { action: "emote", params: { id: 1 } }
        → Backend valida que el bot pertenece al usuario
        → Backend llama a POST http://BOT_VPS_URL/bots/:vpsId/action
        → Bot manager envía paquete WebSocket a Habbo
        → Backend guarda el resultado en bot_logs
        ← { ok: true, result: "..." }
```

### Notificación push cuando el bot expira

```
cron.js (cada hora)
  → Busca bots con expires_at entre ahora y +25h y expiry_notified = 0
  → push.js → sendPushToUser → web-push → navegador del usuario
  → email.js → nodemailer → inbox del usuario
  → Marca expiry_notified = 1
```

### Page de estado pública

```
Browser → GET /api/status (sin auth)
        → Backend hace fetch en paralelo a:
            BOT_VPS_URL/health
            BOT_GUI_URL/health
        → Consulta bots activos, pedidos de hoy, incidencias
        ← { services: [...], stats: {...}, incidents: [...] }
```

---

## GUÍA RÁPIDA: ¿QUÉ EDITO SI QUIERO…?

| Objetivo | Archivo(s) a editar |
|---|---|
| Cambiar el precio de un servicio | `backend/src/database/init.js` → función `seedDefaultProducts()` (o desde el panel admin en `/dashboard` → Productos) |
| Añadir un nuevo tipo de acción del bot | `bot/composers.py` (añade la función), `bot/headless_bot_manager.py` (añade al handler de `/action`), `backend/src/routes/bots.js` (opcional: validación) |
| Añadir una nueva página al frontend | Crea `frontend/src/pages/mi-pagina.astro` usando `DashLayout`. Añade el link en `DashLayout.astro` → sidebar. |
| Añadir una nueva llamada API | Backend: `backend/src/routes/xxx.js`. Frontend: `frontend/public/js/api.js`. |
| Cambiar el diseño visual global | `frontend/public/css/style.css` (variables CSS: `--bg-dark`, `--blue-primary`, `--gradient-main`, etc.) |
| Añadir un campo nuevo a la tabla `users` | `backend/src/database/init.js` → array `migrations`: `'ALTER TABLE users ADD COLUMN nuevo_campo TEXT'` |
| Cambiar el texto de los emails | `backend/src/services/email.js` → cada función tiene el HTML del email. |
| Añadir un nuevo webhook de Discord | `backend/src/services/discord.js` + añade la variable en `.env`. |
| Cambiar la comisión de afiliados | `backend/src/routes/affiliates.js` — busca el porcentaje de recompensa. |
| Activar/desactivar el límite de 1 cuenta por IP | `backend/.env` → `ALLOW_MULTIPLE_ACCOUNTS_PER_IP=true` |
| Añadir un nuevo hotel de Habbo | `backend/src/routes/auth.js` → objeto `HOTEL_DOMAINS`. `bot/constants.py` → `HOTELS`. |
| Ver qué hace cada acción del bot | `bot/composers.py` — cada función es una acción. |

---

## TECNOLOGÍAS USADAS

| Capa | Tecnología |
|---|---|
| Frontend | Astro.js 4, HTML/CSS/JS vanilla, Chart.js (CDN) |
| Backend | Node.js 20+, Express 4, Socket.io, jsonwebtoken, bcryptjs, nodemailer, web-push |
| Base de datos | SQLite vía better-sqlite3 (sin servidor, un fichero `.db`) |
| Bot manager | Python 3.11+, Flask, flask-cors, websocket-client |
| Auth | JWT (Bearer token en localStorage) + verificación Habbo por motto |
| Emails | SMTP propio vía nodemailer |
| Push | Web Push API (VAPID) — `web-push` npm |
| Discord | Webhooks vía fetch (sin SDK) |
| Despliegue | nginx (reverse proxy) + systemd (servicios) |
