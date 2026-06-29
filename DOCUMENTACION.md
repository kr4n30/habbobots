# HabboBots — Documentación completa

> Plataforma web para gestionar bots en Habbo Hotel. Usuarios se registran, verifican su cuenta de Habbo, compran créditos y contratan servicios automatizados (respetos, mascotas, llenar salas, raids, trades).

---

## Índice

1. [Estructura del proyecto](#1-estructura-del-proyecto)
2. [Stack tecnológico](#2-stack-tecnológico)
3. [Flujo de registro y autenticación](#3-flujo-de-registro-y-autenticación)
4. [Frontend — páginas y rutas](#4-frontend--páginas-y-rutas)
5. [Backend — endpoints API](#5-backend--endpoints-api)
6. [Base de datos — tablas](#6-base-de-datos--tablas)
7. [Variables de entorno](#7-variables-de-entorno)
8. [Despliegue en VPS](#8-despliegue-en-vps)
9. [Scripts de deploy automático](#9-scripts-de-deploy-automático)
10. [Infraestructura VPS](#10-infraestructura-vps)

---

## 1. Estructura del proyecto

```
Página Web HabboBOTS/
│
├── habbobots/                        ← Proyecto principal
│   ├── frontend/                     ← Astro (sitio estático)
│   │   ├── src/
│   │   │   ├── layouts/
│   │   │   │   ├── AuthLayout.astro  ← Layout para login/registro
│   │   │   │   └── DashLayout.astro  ← Layout con navbar + sidebar
│   │   │   └── pages/
│   │   │       ├── index.astro       ← Login / Registro
│   │   │       ├── home.astro        ← Página principal usuarios
│   │   │       ├── verificar-habbo.astro ← Verificación motto Habbo
│   │   │       ├── verificar-email.astro ← Confirmación email
│   │   │       ├── servicios.astro   ← Catálogo + pedir servicios
│   │   │       ├── tienda.astro      ← Comprar créditos
│   │   │       ├── bots.astro        ← Gestión de bots
│   │   │       ├── perfil.astro      ← Perfil de usuario
│   │   │       ├── stats.astro       ← Estadísticas
│   │   │       ├── verificar.astro   ← Verificar Habbo (panel)
│   │   │       └── dashboard.astro   ← Panel admin (solo admins)
│   │   ├── public/
│   │   │   ├── js/
│   │   │   │   ├── api.js            ← Cliente API global (window.*)
│   │   │   │   └── main.js           ← UI helpers (showToast, tabs…)
│   │   │   ├── css/
│   │   │   │   └── style.css         ← Estilos globales
│   │   │   └── assets/images/
│   │   │       ├── logo.gif          ← Logo animado
│   │   │       └── bg.png            ← Fondo panel bienvenida
│   │   ├── dist/                     ← Build estático (generado)
│   │   ├── astro.config.mjs
│   │   └── package.json
│   │
│   ├── backend/                      ← Node.js / Express API
│   │   ├── src/
│   │   │   ├── index.js              ← Entry point, monta rutas
│   │   │   ├── database/
│   │   │   │   └── init.js           ← SQLite schema + seed
│   │   │   ├── middleware/
│   │   │   │   └── auth.js           ← JWT verify, requireAuth, requireAdmin
│   │   │   ├── routes/
│   │   │   │   ├── auth.js           ← Registro, login, Discord OAuth, email
│   │   │   │   ├── users.js          ← Perfil, actualizar datos
│   │   │   │   ├── habbo.js          ← Verificación motto, cuentas Habbo
│   │   │   │   ├── bots.js           ← CRUD bots
│   │   │   │   ├── credits.js        ← Balance, historial, packs, checkout
│   │   │   │   ├── products.js       ← Catálogo servicios, pedidos
│   │   │   │   └── stats.js          ← Estadísticas usuario + online count
│   │   │   └── services/
│   │   │       ├── email.js          ← Nodemailer (envío emails)
│   │   │       └── credits.js        ← addCredits, chargeCredits (transacciones)
│   │   ├── data/
│   │   │   └── habbobots.db          ← Base de datos SQLite
│   │   ├── .env                      ← Variables de entorno (no subir a git)
│   │   ├── .env.example              ← Plantilla de variables
│   │   └── package.json
│   │
│   └── INSTALAR-VPS.md               ← Guía de instalación en VPS
│
├── deploy.py                         ← Auto-deploy Python (recomendado)
├── deploy-watch.ps1                  ← Auto-deploy PowerShell (alternativo)
└── DOCUMENTACION.md                  ← Este archivo
```

---

## 2. Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Frontend | **Astro** (output estático), CSS variables, JS vanilla |
| Backend | **Node.js + Express**, ESM (`"type": "module"`) |
| Base de datos | **SQLite** via `better-sqlite3` (síncrono) |
| Autenticación | **JWT** (`jsonwebtoken`), guardado en `sessionStorage` como `hb_token` |
| OAuth | **Discord OAuth2** (API moderna: `global_name`) |
| Email | **Nodemailer** (SMTP, compatible OVH / Gmail / cualquier proveedor) |
| Servidor | **Nginx** como reverse proxy + servir estáticos |
| Proceso | **PM2** para mantener el backend activo |
| Dominio | `kr4n30.tech` con **Cloudflare** (proxy naranja, SSL Flexible) |
| VPS | Ubuntu 22.04 — IP `51.210.43.18` |

---

## 3. Flujo de registro y autenticación

### Registro con email (3 pasos)

```
1. POST /api/auth/pre-register
   → Recibe: email, password
   → Valida que el email no exista
   → Genera código HB-XXXXXX
   → Guarda en pending_registrations (expira 15 min)
   → Devuelve: { pendingId, code }

2. POST /api/auth/register
   → Recibe: pendingId, hotel, habboName
   → Llama a API pública de Habbo para comprobar que el motto contiene el código
   → Si coincide: crea usuario en DB (username = nick de Habbo, email_verified=0)
   → Guarda habbo_accounts + habbo_identities con uniqueId estable
   → Crea email_token (TTL 24h) y envía email de verificación
   → Devuelve: { message, username, email }

3. GET /api/auth/verify-email?token=xxx
   → Marca email_verified=1 en el usuario
   → Redirige a /verificar-email?success=1
```

### Registro con Discord

```
GET /api/auth/discord → redirige a Discord
GET /api/auth/discord/callback
   → Intercambia code por token
   → Busca usuario por discord_id o email
   → Si no existe: crea usuario (email_verified=1 automático)
   → Comprueba si tiene habbo_accounts
   → Sin Habbo: redirige a /verificar-habbo?token=JWT
   → Con Habbo: redirige a /home?token=JWT (o /dashboard si admin)
```

### Verificación de Habbo (Discord o post-login)

```
POST /api/habbo/verify/request
   → Genera código HB-VERIFY-XXXXXX (TTL 10 min)
   → Guarda en verify_tokens

POST /api/habbo/verify/check
   → Llama a API de Habbo para comprobar motto
   → Guarda en habbo_accounts + habbo_identities (uniqueId estable)
```

### Login

```
POST /api/auth/login
   → Solo por email + password (el nick Habbo es el username visible, no sirve para login)
   → Comprueba email_verified = 1
   → Devuelve JWT → guardado en sessionStorage como hb_token
   → Frontend redirige según rol: admin/moderator → /dashboard, user → /home
```

### Guards de páginas

- Todas las páginas con **DashLayout** comprueban:
  1. Que hay token en `sessionStorage` → sino redirige a `/`
  2. Que el usuario tiene al menos una `habbo_account` → sino redirige a `/verificar-habbo`
- `/dashboard` comprueba además que el rol sea `admin` o `moderator`

---

## 4. Frontend — páginas y rutas

| URL | Archivo | Acceso | Descripción |
|-----|---------|--------|-------------|
| `/` | `index.astro` | Público | Login + Registro multi-paso |
| `/home` | `home.astro` | Usuario | Servicios disponibles + pedidos recientes |
| `/servicios` | `servicios.astro` | Usuario | Catálogo completo + historial |
| `/tienda` | `tienda.astro` | Usuario | Comprar créditos (Stripe/PayPal/ingame) |
| `/bots` | `bots.astro` | Usuario | Gestión de bots propios |
| `/perfil` | `perfil.astro` | Usuario | Datos de perfil |
| `/stats` | `stats.astro` | Usuario | Estadísticas personales |
| `/verificar` | `verificar.astro` | Usuario | Vincular/gestionar cuentas Habbo |
| `/verificar-habbo` | `verificar-habbo.astro` | Usuario | Verificación Habbo (obligatoria tras Discord) |
| `/verificar-email` | `verificar-email.astro` | Público | Confirmación de email (enlace del correo) |
| `/dashboard` | `dashboard.astro` | Admin | Panel de administración |

### Layouts

- **`AuthLayout.astro`** — para páginas públicas (login, verificar-email). Sin sidebar.
- **`DashLayout.astro`** — para todas las páginas autenticadas. Incluye navbar, sidebar, guard de token y guard de Habbo. Muestra el enlace "Admin Panel" solo si `user.role === 'admin'` o `'moderator'`.

### Cliente API (`/public/js/api.js`)

Cargado como script clásico (`is:inline`) en todos los layouts. Expone objetos globales:

```js
window.Auth          // getToken, setToken, clearToken, isLoggedIn
window.AuthAPI       // preRegister, register, verifyEmail, resendEmail, login, me, logout, discordURL
window.UsersAPI      // me, update, profile
window.BotsAPI       // list, get, create, update, start, stop, delete
window.CreditsAPI    // balance, history, packs, checkout
window.HabboAPI      // profile, accounts, requestVerify, checkVerify, removeAccount, avatarURL
window.ProductsAPI   // list, get, order, myOrders
window.StatsAPI      // overview, activity, bots
```

Todas las llamadas van a `/api/*` que Nginx proxea al backend en `localhost:3001`.

---

## 5. Backend — endpoints API

### `/api/auth` — Autenticación

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| POST | `/auth/pre-register` | No | Paso 1 registro: valida email/pass, genera código motto |
| POST | `/auth/register` | No | Paso 2: verifica motto Habbo, crea usuario, envía email |
| GET | `/auth/verify-email` | No | Paso 3: activa cuenta con token del email |
| POST | `/auth/resend-email` | No | Reenvía email de verificación |
| POST | `/auth/login` | No | Login con email + password |
| GET | `/auth/discord` | No | Inicia flujo OAuth Discord |
| GET | `/auth/discord/callback` | No | Callback Discord, crea/vincula usuario |
| GET | `/auth/me` | Sí | Devuelve datos del usuario autenticado |
| POST | `/auth/logout` | Sí | Cierra sesión (limpia token en cliente) |

### `/api/users` — Usuarios

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/users/me` | Sí | Perfil completo del usuario |
| PATCH | `/users/me` | Sí | Actualizar datos de perfil |
| GET | `/users/:username` | Sí | Perfil público de otro usuario |

### `/api/habbo` — Cuentas Habbo

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/habbo/avatar` | Sí | URL de avatar Habbo por figure string |
| GET | `/habbo/profile/:name` | Sí | Perfil público de un personaje Habbo |
| POST | `/habbo/verify/request` | Sí | Genera código de verificación (motto) |
| POST | `/habbo/verify/check` | Sí | Verifica motto y vincula cuenta Habbo |
| GET | `/habbo/accounts` | Sí | Lista cuentas Habbo vinculadas del usuario |
| DELETE | `/habbo/accounts/:hotel` | Sí | Desvincula cuenta Habbo de un hotel |

### `/api/credits` — Créditos

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/credits/balance` | Sí | Saldo actual de créditos |
| GET | `/credits/history` | Sí | Últimas 50 transacciones |
| GET | `/credits/packs` | Sí | Packs disponibles: Starter 500cr / Pro 1200cr / Elite 3500cr |
| POST | `/credits/checkout` | Sí | Inicia compra de un pack |

### `/api/products` — Servicios

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/products` | No | Lista productos activos (filtra por `?hotel=`) |
| GET | `/products/orders/my` | Sí | Pedidos del usuario (registrar antes de `/:id`) |
| GET | `/products/:id` | No | Detalle de un producto |
| POST | `/products/:id/order` | Sí | Realizar pedido (descuenta créditos) |

### `/api/bots` — Bots

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/bots` | Sí | Lista bots del usuario |
| POST | `/bots` | Sí | Crear bot |
| GET | `/bots/:id` | Sí | Detalle de bot |
| PATCH | `/bots/:id` | Sí | Actualizar bot |
| POST | `/bots/:id/start` | Sí | Arrancar bot |
| POST | `/bots/:id/stop` | Sí | Parar bot |
| DELETE | `/bots/:id` | Sí | Eliminar bot |

### `/api/stats` — Estadísticas

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/stats/online` | No | Usuarios activos en los últimos 5 minutos |
| GET | `/stats` | Sí | Stats del usuario (bots, créditos, pedidos…) |
| GET | `/stats/activity` | Sí | Actividad últimos N días |
| GET | `/stats/bots` | Sí | Stats de bots del usuario |

### `/api/health`

```
GET /health → { status: "ok", timestamp: "..." }
```

---

## 6. Base de datos — tablas

Base de datos: SQLite en `backend/data/habbobots.db`

### `users`
| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | TEXT PK | UUID |
| username | TEXT UNIQUE | Nick de Habbo (asignado al verificar) |
| email | TEXT UNIQUE | Email de registro |
| password | TEXT | Hash bcrypt (null para OAuth) |
| discord_id | TEXT UNIQUE | ID de Discord (si usó OAuth) |
| discord_tag | TEXT | Nombre de Discord |
| avatar_url | TEXT | URL avatar Discord |
| credits | INTEGER | Saldo de créditos |
| role | TEXT | `user` / `moderator` / `admin` |
| is_banned | INTEGER | 0/1 |
| ban_reason | TEXT | Motivo del baneo |
| ban_expires | TEXT | Fecha expiración (null = permanente) |
| email_verified | INTEGER | 0/1 — obligatorio para iniciar sesión |
| last_seen_at | TEXT | Última actividad (para contador online) |
| created_at | TEXT | Fecha de registro |
| updated_at | TEXT | Última modificación |

### `pending_registrations`
Registro temporal antes de verificar el motto. Expira en 15 minutos.
- `id`, `email`, `password` (hasheado), `code` (HB-XXXXXX), `ip`, `expires_at`

### `email_tokens`
Tokens para verificación de email. Expiran en 24 horas.
- `id`, `user_id`, `token` (UUID), `expires_at`, `used`

### `habbo_accounts`
Cuentas de Habbo verificadas por usuario y hotel.
- `id`, `user_id`, `hotel`, `habbo_name`, `verified_at`
- UNIQUE: `(user_id, hotel)` — máximo una cuenta por hotel

### `habbo_identities`
Identidad estable por `uniqueId` de Habbo (no cambia si cambia el nick).
- `id`, `user_id`, `hotel`, `habbo_uid`, `current_name`, `verified_at`

### `habbo_name_history`
Historial de nicks anteriores de una identidad.
- `id`, `identity_id`, `name`, `seen_at`

### `verify_tokens`
Códigos de verificación de motto (TTL 10 min).
- `id`, `user_id`, `hotel`, `token`, `expires_at`, `used`

### `products`
Catálogo de servicios disponibles.
- `id`, `name`, `description`, `type` (badge_respect / badge_pet / room_fill / raid / trade / custom)
- `price` (créditos), `hotel` (null = todos), `duration` (segundos), `max_quantity`, `active`, `sort_order`

**Productos por defecto:**
| ID | Nombre | Precio | Tipo |
|----|--------|--------|------|
| prod_respect_small | Pack Respetos x10 | 15 cr | badge_respect |
| prod_respect_big | Pack Respetos x50 | 60 cr | badge_respect |
| prod_pet_small | Caricias mascota x10 | 10 cr | badge_pet |
| prod_pet_big | Caricias mascota x50 | 40 cr | badge_pet |
| prod_roomfill_1h | Llenar sala 1 hora | 50 cr | room_fill |
| prod_roomfill_6h | Llenar sala 6 horas | 250 cr | room_fill |
| prod_raid | Raid a sala | 80 cr | raid |
| prod_trade | Trade automatizado | 30 cr | trade (máx 5) |

### `service_orders`
Pedidos realizados por usuarios.
- `id`, `user_id`, `product_id`, `hotel`, `habbo_name`, `status` (pending/active/completed/cancelled/failed)
- `credits_paid`, `notes`, `started_at`, `ends_at`

### `credit_transactions`
Historial completo de movimientos de créditos.
- `type`: purchase / bot_charge / service / refund / bonus / event_reward / admin_adjust

### `bots`
Bots de usuarios.
- `id`, `user_id`, `name`, `hotel`, `room`, `status` (online/offline/busy/error)
- `uptime_pct`, `actions`, `cost_per_month`, `expires_at`

### Otras tablas
- `refresh_tokens` — tokens JWT de renovación
- `chat_messages` — mensajes de chat (global / grupo / DM)
- `user_follows` — sistema de seguidores
- `reputation` — votos +rep / -rep
- `user_stats` — caché de estadísticas para leaderboards
- `groups` / `group_members` — grupos/familias/mafias
- `events` / `event_participations` — eventos con recompensas
- `ip_logs` — registro de IPs por acción (anti-spam)
- `fingerprints` — huellas de navegador (anti-multicuenta)
- `audit_logs` — log de acciones admin
- `bans` — registro de baneos

---

## 7. Variables de entorno

Archivo: `habbobots/backend/.env`

```env
# Servidor
PORT=3001
NODE_ENV=production

# JWT
JWT_SECRET=secreto_largo_y_seguro_minimo_32_chars
JWT_EXPIRES_IN=7d

# SQLite
DB_PATH=./data/habbobots.db

# Discord OAuth
DISCORD_CLIENT_ID=tu_client_id
DISCORD_CLIENT_SECRET=tu_client_secret
DISCORD_CALLBACK_URL=https://kr4n30.tech/api/auth/discord/callback

# Frontend (para redirects)
FRONTEND_URL=https://kr4n30.tech

# Email SMTP (OVH)
SMTP_HOST=ssl0.ovh.net
SMTP_PORT=587
SMTP_USER=tuemail@tudominio.com
SMTP_PASS=tu_contraseña
SMTP_FROM=HabboBots <tuemail@tudominio.com>

# Stripe (pagos)
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Bot VPS (si los bots corren en otro servidor)
BOT_VPS_URL=http://ip-bots:5000
BOT_VPS_API_KEY=clave_secreta
```

---

## 8. Despliegue en VPS

**Servidor:** Ubuntu 22.04 — `ubuntu@51.210.43.18`  
**Dominio:** `kr4n30.tech` (Cloudflare, SSL Flexible)

### Estructura en el VPS

```
/var/www/habbobots/
├── backend/          ← API Node.js (PM2: habbobots-api)
│   ├── src/
│   ├── data/         ← habbobots.db
│   ├── node_modules/
│   └── .env
└── frontend/
    └── dist/         ← Servido por Nginx
```

### Nginx (`/etc/nginx/sites-enabled/habbobots`)

```nginx
server {
    listen 80;
    server_name kr4n30.tech www.kr4n30.tech;

    # Frontend estático
    location / {
        root /var/www/habbobots/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # Proxy al backend Node
    location /api/ {
        proxy_pass http://localhost:3001/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_cache_bypass $http_upgrade;
    }
}
```

### Comandos de mantenimiento

```bash
# Ver estado del backend
pm2 status
pm2 logs habbobots-api --lines 30

# Reiniciar backend
pm2 restart habbobots-api

# Reconstruir frontend
cd /var/www/habbobots/frontend
npm run build
sudo chown -R www-data:www-data dist
sudo chmod -R 755 dist

# Reinstalar dependencias backend
cd /var/www/habbobots/backend
npm install
pm2 restart habbobots-api

# Reiniciar Nginx
sudo nginx -t && sudo systemctl reload nginx

# Verificar que la API funciona
curl https://kr4n30.tech/api/health
```

---

## 9. Scripts de deploy automático

### `deploy.py` (Python — recomendado)

Detecta cambios en tu PC y los sube al VPS automáticamente via SFTP.

**Requisitos:**
```bash
pip install paramiko watchdog
```

**Uso:**
```bash
python deploy.py
# → Elige 's' (smart: sube solo lo nuevo) o 'f' (fuerza todo)
# → Queda vigilando cambios en tiempo real
```

**Qué hace:**
- Al arrancar: compara timestamps de TODOS los archivos PC vs VPS
- Sube solo los que son más nuevos en el PC
- Vigila cambios con watchdog (eventos de fichero)
- Escaneo de respaldo cada 30 segundos (para cambios que watchdog pierda)
- Tras cambios en `frontend/src` o `frontend/public`: ejecuta `npm run build` + fix permisos
- Tras cambios en `backend/src`: ejecuta `pm2 restart habbobots-api`
- Muestra velocidad KB/s en tiempo real por archivo

**Configuración** (top del archivo):
```python
VPS_HOST = "51.210.43.18"
VPS_USER = "ubuntu"
SSH_KEY  = "~/.ssh/id_habbobots"   # clave SSH sin contraseña
LOCAL    = SCRIPT_DIR / "habbobots"
REMOTE   = "/var/www/habbobots"
```

### `deploy-watch.ps1` (PowerShell — alternativo)

Misma lógica pero en PowerShell para Windows. Menos rápido que Python.

### Configurar SSH sin contraseña (una vez)

```powershell
# 1. Generar clave
ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\id_habbobots" -N ""

# 2. Copiar al VPS
type "$env:USERPROFILE\.ssh\id_habbobots.pub" | ssh ubuntu@51.210.43.18 "mkdir -p ~/.ssh; cat >> ~/.ssh/authorized_keys; chmod 600 ~/.ssh/authorized_keys"
```

---

## 10. Infraestructura VPS

```
Internet
    │
    ▼
Cloudflare (proxy, SSL Flexible)
    │  HTTPS
    ▼
Nginx :80
    ├── / → /var/www/habbobots/frontend/dist (estático)
    └── /api/ → localhost:3001 (proxy)
                    │
                    ▼
              Node.js Express
              (PM2: habbobots-api)
                    │
                    ▼
              SQLite (habbobots.db)
```

### Hoteles de Habbo soportados

| Código | Dominio |
|--------|---------|
| es | www.habbo.es |
| com | www.habbo.com |
| br | www.habbo.com.br |
| tr | www.habbo.com.tr |
| fi | www.habbo.fi |
| de | www.habbo.de |
| fr | www.habbo.fr |
| it | www.habbo.it |
| nl | www.habbo.nl |

La verificación de motto llama a `https://{dominio}/api/public/users?name={nick}` y comprueba que `profile.motto` contiene el código de verificación.

---

*Última actualización: Junio 2026*
