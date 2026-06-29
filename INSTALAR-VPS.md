# 🖥️ Guía de instalación VPS — HabboBots
# Dominio: kr4n30.tech | Base de datos: SQLite

---

## 1. Conectar al VPS

```bash
ssh root@TU_IP_VPS
```

> Si usas un usuario distinto de root, añade `sudo` en todos los comandos que lo necesitan (los marcados con ⚠️).

---

## 2. Actualizar el sistema

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl wget git ufw nano unzip build-essential
```

---

## 3. Firewall básico

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
# Cuando pregunte "proceed?" → escribe: y  y pulsa Enter
sudo ufw status
```

---

## 4. Instalar Node.js 20 (vía nvm)

> nvm se instala para el usuario actual, **no necesita sudo**.

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc

nvm install 20
nvm use 20
nvm alias default 20

node -v    # → v20.x.x
npm -v
```

---

## 5. Instalar Nginx

```bash
sudo apt install -y nginx
sudo systemctl start nginx
sudo systemctl enable nginx
sudo systemctl status nginx    # debe decir "active (running)"
```

---

## 6. Instalar PM2 (gestor de procesos Node.js)

```bash
npm install -g pm2
```

---

## 7. Instalar Certbot (SSL gratis con Let's Encrypt)

```bash
sudo apt install -y certbot python3-certbot-nginx
```

---

## 8. Preparar carpeta del proyecto

```bash
sudo mkdir -p /var/www/habbobots
sudo chown $USER:$USER /var/www/habbobots
```

---

## 9. Subir el proyecto al VPS

### Opción A — Con Git (recomendado)

```bash
cd /var/www/habbobots
git clone https://github.com/TU_USUARIO/habbobots.git .
```

### Opción B — rsync desde tu PC Windows (Git Bash o WSL)

Ejecuta esto **en tu PC**, no en el VPS:

```bash
rsync -avz --exclude node_modules \
  "/mnt/c/Users/rafar/Desktop/habbobots/Página Web HabboBOTS/" \
  root@TU_IP:/var/www/habbobots/
```

### Opción C — rsync desde PowerShell (Windows)

```powershell
# Instala primero: winget install WinSCP o usa SCP
scp -r "C:\Users\rafar\Desktop\habbobots\Página Web HabboBOTS\*" root@TU_IP:/var/www/habbobots/
```

---

## 10. Instalar dependencias y compilar

```bash
cd /var/www/habbobots

# ── Backend ──────────────────────────────
cd backend
npm install --omit=dev
cd ..

# ── Frontend (compilar a archivos estáticos) ──
cd frontend
npm install
npm run build
cd ..
```

> El build genera `frontend/dist/` — esos son los archivos HTML/CSS/JS que sirve Nginx.

---

## 11. Crear carpeta de la base de datos SQLite

```bash
mkdir -p /var/www/habbobots/backend/data
```

---

## 12. Configurar variables de entorno del backend

```bash
cp /var/www/habbobots/backend/.env.example /var/www/habbobots/backend/.env
nano /var/www/habbobots/backend/.env
```

Rellena los valores (guarda con `Ctrl+O`, sal con `Ctrl+X`):

```env
PORT=3001
NODE_ENV=production

# Genera uno seguro con el comando de abajo
JWT_SECRET=PEGA_AQUI_EL_SECRETO_GENERADO

DB_PATH=/var/www/habbobots/backend/data/habbobots.db

DISCORD_CLIENT_ID=tu_client_id
DISCORD_CLIENT_SECRET=tu_client_secret
DISCORD_CALLBACK_URL=https://kr4n30.tech/api/auth/discord/callback

FRONTEND_URL=https://kr4n30.tech

STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

BOT_VPS_URL=http://localhost:5001
BOT_VPS_API_KEY=clave_secreta_vps

BOT_GUI_URL=http://localhost:5000
```

Para generar un JWT_SECRET seguro:

```bash
node -e "console.log(require('crypto').randomBytes(48).toString('hex'))"
```

Copia la salida y pégala en `JWT_SECRET=`.

---

## 13. Instalar Python y arrancar el Bot Manager

### 13a. Instalar Python 3 y dependencias del bot

```bash
sudo apt install -y python3 python3-pip python3-venv

# Crear entorno virtual para el bot
cd /var/www/habbobots/bot
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

### 13b. Configurar la variable de entorno del API key

```bash
# La misma clave que pondrás en backend/.env → BOT_VPS_API_KEY
export BOT_VPS_API_KEY=clave_secreta_vps
```

### 13c. Crear servicio systemd para el headless_bot_manager

> Esto hace que el bot arranque solo al reiniciar el VPS.

```bash
sudo nano /etc/systemd/system/habbo-bot-manager.service
```

Pega esto (ajusta el usuario si no es root):

```ini
[Unit]
Description=Habbo Headless Bot Manager
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/var/www/habbobots/bot
Environment=BOT_VPS_API_KEY=clave_secreta_vps
ExecStart=/var/www/habbobots/bot/venv/bin/python headless_bot_manager.py --port 5001
Restart=always
RestartSec=5
StandardOutput=append:/var/log/habbo-bot-manager/bot.log
StandardError=append:/var/log/habbo-bot-manager/bot.log

[Install]
WantedBy=multi-user.target
```

Guarda con `Ctrl+O`, sal con `Ctrl+X`.

```bash
# Crear directorio de logs
sudo mkdir -p /var/log/habbo-bot-manager

# Activar e iniciar el servicio
sudo systemctl daemon-reload
sudo systemctl enable habbo-bot-manager
sudo systemctl start habbo-bot-manager

# Verificar que arrancó correctamente
sudo systemctl status habbo-bot-manager
sudo tail -f /var/log/habbo-bot-manager/bot.log
```

Deberías ver:
```
HeadlessBotManager v2.0 iniciado
Iniciando HeadlessBotManager en puerto 5001
```

### 13d. (Opcional) Arrancar también el web.py para el panel admin

El panel admin del dashboard (`/admin/botpanel`) conecta al `web.py` en el puerto 5000.
Puedes correrlo también con systemd:

```bash
sudo nano /etc/systemd/system/habbo-web-panel.service
```

```ini
[Unit]
Description=Habbo Bot Web Panel (Flask)
After=network.target habbo-bot-manager.service

[Service]
Type=simple
User=root
WorkingDirectory=/var/www/habbobots/bot
ExecStart=/var/www/habbobots/bot/venv/bin/python web.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable habbo-web-panel
sudo systemctl start habbo-web-panel
```

> **Nota:** El puerto 5000 y 5001 son internos (localhost). No abras estos puertos en el firewall.

---

## 14. Arrancar el backend Node.js con PM2

```bash
cd /var/www/habbobots/backend
pm2 start src/index.js --name habbobots-api

# Hacer que arranque automáticamente al reiniciar el VPS
pm2 startup
# → PM2 te dará un comando que empieza con "sudo env PATH=..."
# → Cópialo EXACTAMENTE y ejecútalo
pm2 save
```

Verificar que está corriendo:

```bash
pm2 status
pm2 logs habbobots-api --lines 30
```

Deberías ver en los logs:

```
🤖 HabboBots API corriendo en http://localhost:3001
✅ Base de datos SQLite inicializada
```

---

## 15. Configurar Nginx

```bash
sudo nano /etc/nginx/sites-available/kr4n30.tech
```

Pega esta configuración:

```nginx
server {
    listen 80;
    server_name kr4n30.tech www.kr4n30.tech;

    # ── Frontend estático (build de Astro) ──────────
    root /var/www/habbobots/frontend/dist;
    index index.html;

    # SPA routing → siempre devuelve el HTML correcto
    location / {
        try_files $uri $uri/ $uri.html /index.html;
    }

    # ── Proxy /api/* → backend Express en :3001 ─────
    location /api/ {
        proxy_pass         http://127.0.0.1:3001/;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection 'upgrade';
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 60s;
    }

    # ── Seguridad ────────────────────────────────────
    server_tokens off;
    add_header X-Frame-Options "SAMEORIGIN";
    add_header X-Content-Type-Options "nosniff";
}
```

Guarda con `Ctrl+O`, sal con `Ctrl+X`.

```bash
# Activar el sitio
sudo ln -s /etc/nginx/sites-available/kr4n30.tech /etc/nginx/sites-enabled/

# Desactivar el sitio por defecto
sudo rm -f /etc/nginx/sites-enabled/default

# Verificar que no hay errores de sintaxis
sudo nginx -t

# Recargar Nginx
sudo systemctl reload nginx
```

---

## 16. Apuntar el dominio al VPS

En el panel de tu proveedor de dominio (donde compraste **kr4n30.tech**), añade:

| Tipo | Nombre | Valor      | TTL  |
|------|--------|------------|------|
| A    | @      | TU_IP_VPS  | 3600 |
| A    | www    | TU_IP_VPS  | 3600 |

Espera entre 5 min y 2 horas. Para verificar la propagación:

```bash
nslookup kr4n30.tech
# debe devolver tu IP del VPS
```

O desde el navegador: `http://kr4n30.tech` debe cargar la web.

---

## 16. Activar SSL con Let's Encrypt

```bash
sudo certbot --nginx -d kr4n30.tech -d www.kr4n30.tech
```

- Introduce tu email cuando te lo pida
- Selecciona **2: Redirect** → fuerza HTTPS automáticamente

Certbot modifica el Nginx y renueva el certificado cada 90 días solo.

Verificar renovación automática:

```bash
sudo certbot renew --dry-run
```

---

## ✅ Resultado final

| Qué                    | Dónde                                              |
|------------------------|----------------------------------------------------|
| Web pública            | `https://kr4n30.tech`                             |
| API backend            | `https://kr4n30.tech/api/`                        |
| Base de datos web      | `/var/www/habbobots/backend/data/habbobots.db`    |
| Base de datos bot      | `/var/www/habbobots/bot/bots.db`                  |
| Bot (servicios auto)   | `http://localhost:5001` (headless_bot_manager.py) |
| Bot (panel admin)      | `http://localhost:5000` (web.py)                  |
| Logs backend           | `pm2 logs habbobots-api`                          |
| Logs bot manager       | `/var/log/habbo-bot-manager/bot.log`               |
| Logs Nginx             | `/var/log/nginx/`                                  |

---

## Comandos del día a día

```bash
# ── Backend Node.js ──────────────────────
pm2 status
pm2 logs habbobots-api

# Reiniciar tras cambios de código
pm2 restart habbobots-api

# Actualizar código desde Git
cd /var/www/habbobots
git pull
cd frontend && npm run build && cd ..
pm2 restart habbobots-api

# Recargar Nginx (tras cambiar su config)
sudo nginx -t && sudo systemctl reload nginx

# Logs de Nginx en tiempo real
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log

# ── Bot Manager ──────────────────────────
# Estado
sudo systemctl status habbo-bot-manager
sudo systemctl status habbo-web-panel

# Logs en tiempo real
sudo tail -f /var/log/habbo-bot-manager/bot.log

# Reiniciar tras cambios en el bot
sudo systemctl restart habbo-bot-manager
sudo systemctl restart habbo-web-panel

# ── Nginx / Sistema ───────────────────────
# Recargar Nginx (tras cambiar su config)
sudo nginx -t && sudo systemctl reload nginx

sudo systemctl status nginx
sudo systemctl status pm2-root    # o pm2-$USER

# Espacio en disco (SQLite puede crecer)
df -h
du -sh /var/www/habbobots/backend/data/
du -sh /var/www/habbobots/bot/bots.db
```

---

## Solución de problemas

### El bot manager no arranca

```bash
sudo journalctl -u habbo-bot-manager -n 50
sudo tail -f /var/log/habbo-bot-manager/bot.log
```

Causas comunes:
- Error de importación → verifica que el venv tenga todos los paquetes: `cd /var/www/habbobots/bot && source venv/bin/activate && pip install -r requirements.txt`
- Puerto 5001 ocupado → `sudo lsof -i :5001`
- API key no configurada → revisa la línea `Environment=BOT_VPS_API_KEY=...` en el servicio

### El backend no arranca

```bash
pm2 logs habbobots-api --lines 50
```

Causas comunes:
- `JWT_SECRET` no configurado → edita `.env`
- Puerto 3001 ocupado → `sudo lsof -i :3001`
- Permisos de la carpeta data → `sudo chown -R $USER:$USER /var/www/habbobots/backend/data`

### La web muestra 502 Bad Gateway

```bash
pm2 status                    # el proceso debe estar "online"
pm2 restart habbobots-api
sudo systemctl reload nginx
```

### Certbot falla

El dominio debe apuntar ya a tu IP antes de ejecutar certbot:

```bash
curl -I http://kr4n30.tech    # debe responder desde tu VPS
```

Si todavía no propaga, espera y repite el comando.

### Backup de la base de datos SQLite

```bash
# Copia de seguridad manual
cp /var/www/habbobots/backend/data/habbobots.db \
   /var/www/habbobots/backend/data/habbobots.db.bak.$(date +%Y%m%d)

# Automatizar con cron (backup diario a las 3:00)
crontab -e
# Añade esta línea:
# 0 3 * * * cp /var/www/habbobots/backend/data/habbobots.db /var/backups/habbobots-$(date +\%Y\%m\%d).db
```
