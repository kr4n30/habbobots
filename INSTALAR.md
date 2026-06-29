# INSTALAR — HabboBOTS

Guía completa para instalar el proyecto desde cero en un VPS Ubuntu 22.04 (o en local Windows/Mac para desarrollo).

---

## REQUISITOS PREVIOS

| Herramienta | Versión mínima | Instalar |
|---|---|---|
| Node.js | 20+ | `curl -fsSL https://deb.nodesource.com/setup_20.x \| bash -` |
| Python | 3.11+ | `apt install python3.11 python3.11-venv python3-pip` |
| Git | cualquiera | `apt install git` |
| nginx | cualquiera | `apt install nginx` (solo producción) |

---

## 1. CLONAR EL PROYECTO

```bash
git clone https://tu-repo/habbobots.git /var/www/habbobots
cd /var/www/habbobots
```

En Windows (desarrollo):
```bash
git clone https://tu-repo/habbobots.git C:\habbobots
```

---

## 2. INSTALAR DEPENDENCIAS DEL BACKEND (Node.js)

```bash
cd backend
npm install
```

Si `web-push` da error de compilación nativa:
```bash
npm install web-push --ignore-scripts
```

---

## 3. INSTALAR DEPENDENCIAS DEL FRONTEND (Astro)

```bash
cd ../frontend
npm install
```

---

## 4. INSTALAR DEPENDENCIAS DEL BOT MANAGER (Python)

```bash
cd ../bot
python3.11 -m venv venv
source venv/bin/activate          # Linux/Mac
# venv\Scripts\activate.bat       # Windows

pip install -r requirements.txt
```

---

## 5. CONFIGURAR LAS VARIABLES DE ENTORNO DEL BACKEND

```bash
cd ../backend
cp .env.example .env
nano .env
```

Rellena las variables más importantes:

### JWT (obligatorio)
```
JWT_SECRET=pon_aqui_una_cadena_aleatoria_muy_larga_y_segura
JWT_EXPIRES_IN=7d
```
Genera una clave segura con:
```bash
node -e "console.log(require('crypto').randomBytes(64).toString('hex'))"
```

### Base de datos
```
DB_PATH=./data/habbobots.db
```
El directorio `data/` se crea automáticamente al arrancar.

### Frontend URL (para CORS y redirecciones)
```
FRONTEND_URL=https://tudominio.com      # producción
FRONTEND_URL=http://localhost:4321      # desarrollo
```

### Email SMTP (opcional pero recomendado)
Para emails de verificación, expiración de bots, etc.
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu_email@gmail.com
SMTP_PASS=tu_contrasena_de_aplicacion_gmail
SMTP_FROM=HabboBOTS <tu_email@gmail.com>
```
> Con Gmail: usa una **contraseña de aplicación** (Google → Seguridad → Verificación en dos pasos → Contraseñas de aplicación).

### Discord Webhooks (opcional)
Para recibir alertas de bots caídos, pagos, tickets:
```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/XXX/YYY
DISCORD_WEBHOOK_ORDERS=https://discord.com/api/webhooks/XXX/YYY
DISCORD_WEBHOOK_PAYMENTS=https://discord.com/api/webhooks/XXX/YYY
```
Crea los webhooks en tu servidor Discord: Canal → Integraciones → Webhooks → Nuevo Webhook.

### Bot Manager
```
BOT_VPS_URL=http://localhost:5001
BOT_GUI_URL=http://localhost:5000
```
En VPS separado: `BOT_VPS_URL=http://IP_DEL_VPS:5001`

### Push Notifications PWA (opcional)

Genera las claves VAPID:
```bash
cd backend
npx web-push generate-vapid-keys
```
Copia las claves al `.env`:
```
VAPID_PUBLIC_KEY=BExxxxxxxxxxxxxxx...
VAPID_PRIVATE_KEY=xxxxxxxxxxxxxxx...
VAPID_EMAIL=mailto:admin@tudominio.com
```

### Anti-multicuenta
```
ALLOW_MULTIPLE_ACCOUNTS_PER_IP=false     # 1 cuenta por IP (por defecto)
# ALLOW_MULTIPLE_ACCOUNTS_PER_IP=true    # desactiva el límite (desarrollo)
```

---

## 6. INICIALIZAR LA BASE DE DATOS

La base de datos SQLite se crea automáticamente al arrancar el backend.
No hay que hacer nada extra — basta con ejecutar el paso 7.

---

## 7. ARRANCAR EN DESARROLLO (local)

### Opción A: Con el script automático

**Windows:**
```
start.bat
```

**Linux/Mac:**
```bash
chmod +x start.sh
./start.sh
```

### Opción B: Manual (3 terminales)

Terminal 1 — Bot Manager:
```bash
cd bot
source venv/bin/activate
python headless_bot_manager.py
```

Terminal 2 — Backend:
```bash
cd backend
npm run dev
```

Terminal 3 — Frontend:
```bash
cd frontend
npm run dev
```

Accede en: `http://localhost:4321`

---

## 8. CREAR EL PRIMER USUARIO ADMIN

Primero regístrate normalmente en la web (necesitas una cuenta Habbo para verificar).

Luego promueve tu cuenta a admin:
```bash
cd scripts
node crear-admin.js tu_nick_de_habbo
```

Eso cambia tu `role` de `user` a `admin` en la base de datos.

---

## 9. DESPLIEGUE EN PRODUCCIÓN (VPS Ubuntu)

### 9.1 Construir el frontend

```bash
cd frontend
npm run build
# Los archivos estáticos quedan en frontend/dist/
```

### 9.2 Servicios systemd

Crea los archivos de servicio para que todo arranque automáticamente:

**Bot Manager:**
```bash
nano /etc/systemd/system/habbobots-manager.service
```
```ini
[Unit]
Description=HabboBOTS — Bot Manager (Python)
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/habbobots/bot
ExecStart=/var/www/habbobots/bot/venv/bin/python headless_bot_manager.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Backend Node.js:**
```bash
nano /etc/systemd/system/habbobots-backend.service
```
```ini
[Unit]
Description=HabboBOTS — Backend (Node.js)
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/habbobots/backend
ExecStart=/usr/bin/node src/index.js
Restart=always
RestartSec=5
EnvironmentFile=/var/www/habbobots/backend/.env

[Install]
WantedBy=multi-user.target
```

Activa los servicios:
```bash
systemctl daemon-reload
systemctl enable habbobots-manager habbobots-backend
systemctl start  habbobots-manager habbobots-backend
```

Comprueba que arrancan:
```bash
systemctl status habbobots-backend
systemctl status habbobots-manager
```

### 9.3 Configurar nginx

```bash
nano /etc/nginx/sites-available/habbobots
```
```nginx
server {
    listen 80;
    server_name tudominio.com www.tudominio.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name tudominio.com www.tudominio.com;

    ssl_certificate     /etc/letsencrypt/live/tudominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/tudominio.com/privkey.pem;

    # Frontend estático
    root /var/www/habbobots/frontend/dist;
    index index.html;

    # Astro SPA — manda todo lo que no sea archivo al index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy al backend Node.js
    location /api/ {
        rewrite ^/api(/.*)$ $1 break;
        proxy_pass http://localhost:3001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_cache_bypass $http_upgrade;
    }

    # Socket.io
    location /socket.io/ {
        proxy_pass http://localhost:3001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

```bash
ln -s /etc/nginx/sites-available/habbobots /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

### 9.4 SSL con Let's Encrypt

```bash
apt install certbot python3-certbot-nginx
certbot --nginx -d tudominio.com -d www.tudominio.com
```

---

## 10. ACTUALIZAR EN PRODUCCIÓN

```bash
cd /var/www/habbobots
git pull

# Instalar nuevas dependencias si las hay
cd backend && npm install
cd ../frontend && npm install && npm run build

# Reiniciar servicios
systemctl restart habbobots-backend
systemctl restart habbobots-manager
```

---

## 11. SOLUCIÓN DE PROBLEMAS FRECUENTES

### El backend no arranca
```bash
journalctl -u habbobots-backend -n 50
# Causas comunes:
# - JWT_SECRET no configurado en .env
# - Puerto 3001 ya en uso: lsof -i :3001
# - Error en package.json: cd backend && node src/index.js
```

### Los bots no se conectan
```bash
journalctl -u habbobots-manager -n 50
# Causas comunes:
# - SSO ticket de Habbo expirado (las cuentas se renuevan cada ~1h)
# - Proxy no disponible
# - Habbo cambió el protocolo WebSocket
```

### La página carga pero el login falla
```bash
# Comprueba que el proxy nginx apunta bien al backend
curl http://localhost:3001/health
# Si devuelve {"status":"ok"} el backend está corriendo
# Comprueba CORS: FRONTEND_URL en .env debe coincidir con el dominio del frontend
```

### El email de verificación no llega
```bash
# Comprueba la config SMTP en .env
# Prueba el SMTP manualmente:
node -e "
const nodemailer = require('nodemailer');
const t = nodemailer.createTransport({host:'TU_HOST',port:587,auth:{user:'USER',pass:'PASS'}});
t.verify().then(()=>console.log('OK')).catch(console.error);
"
```

### Error al instalar web-push (gyp)
```bash
npm install web-push --ignore-scripts
```

---

## 12. ESTRUCTURA DE PUERTOS (RESUMEN)

| Puerto | Servicio | Expuesto al exterior |
|---|---|---|
| `4321` | Frontend Astro (dev solamente) | Solo en desarrollo |
| `3001` | Backend Node.js | Solo via nginx `/api/` |
| `5001` | Bot Manager headless | **No** (interno solamente) |
| `5000` | Bot GUI web.py | **No** (acceso solo admin via nginx `/botcontrol/`) |
| `80/443` | nginx | **Sí** — el único expuesto públicamente |

> **Seguridad:** cierra los puertos 3001, 5000 y 5001 en el firewall del VPS. Solo el 80 y 443 deben ser públicos.
> ```bash
> ufw allow 80
> ufw allow 443
> ufw allow 22
> ufw enable
> ```
