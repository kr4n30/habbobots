#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  HabboBOTS — Inicio de los 3 servicios (Linux / VPS)
#  Uso: chmod +x start.sh && ./start.sh
# ═══════════════════════════════════════════════════════════════

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

# ── Colores ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

echo ""
echo "  ██╗  ██╗ █████╗ ██████╗ ██████╗  ██████╗ ██████╗  ██████╗ ████████╗███████╗"
echo "  ██║  ██║██╔══██╗██╔══██╗██╔══██╗██╔═══██╗██╔══██╗██╔═══██╗╚══██╔══╝██╔════╝"
echo "  ███████║███████║██████╔╝██████╔╝██║   ██║██████╔╝██║   ██║   ██║   ███████╗"
echo "  ██╔══██║██╔══██║██╔══██╗██╔══██╗██║   ██║██╔══██╗██║   ██║   ██║   ╚════██║"
echo "  ██║  ██║██║  ██║██████╔╝██████╔╝╚██████╔╝██████╔╝╚██████╔╝   ██║   ███████║"
echo "  ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚═════╝  ╚═════╝ ╚═════╝  ╚═════╝   ╚═╝   ╚══════╝"
echo ""

# ── Verificar dependencias ───────────────────────────────────────────────────
command -v node  >/dev/null 2>&1 || error "Node.js no encontrado. Instálalo con: nvm install 20"
command -v npm   >/dev/null 2>&1 || error "npm no encontrado."
command -v python3 >/dev/null 2>&1 || error "Python3 no encontrado."

# ── Instalar dependencias si faltan ─────────────────────────────────────────
if [ ! -d "$ROOT/backend/node_modules" ]; then
  info "Instalando dependencias del backend..."
  cd "$ROOT/backend" && npm install
fi

if [ ! -d "$ROOT/frontend/node_modules" ]; then
  info "Instalando dependencias del frontend..."
  cd "$ROOT/frontend" && npm install
fi

# .env del backend
if [ ! -f "$ROOT/backend/.env" ]; then
  warn "No existe backend/.env, copiando desde .env.example..."
  cp "$ROOT/backend/.env.example" "$ROOT/backend/.env"
  warn "Edita backend/.env con tus claves antes de continuar."
fi

# ── Función para matar un puerto si ya está en uso ──────────────────────────
kill_port() {
  local port=$1
  local pid
  pid=$(lsof -ti tcp:"$port" 2>/dev/null || true)
  if [ -n "$pid" ]; then
    warn "Puerto $port ocupado (PID $pid), liberando..."
    kill -9 "$pid" 2>/dev/null || true
    sleep 1
  fi
}

# ── Función para verificar que un puerto levantó ────────────────────────────
wait_for_port() {
  local port=$1
  local name=$2
  local tries=0
  while ! curl -s "http://localhost:$port" >/dev/null 2>&1; do
    sleep 1
    tries=$((tries+1))
    if [ $tries -ge 15 ]; then
      warn "$name (puerto $port) tardó más de lo esperado."
      return
    fi
  done
  info "$name listo en http://localhost:$port"
}

# ── Activar venv Python ─────────────────────────────────────────────────────
PYTHON_CMD="python3"
if [ -f "$ROOT/bot/venv/bin/activate" ]; then
  source "$ROOT/bot/venv/bin/activate"
  PYTHON_CMD="python"
  info "Venv Python activado"
fi

# Matar puertos previos si estaban en uso
kill_port 5001
kill_port 5000
kill_port 3001
kill_port 4321

# ── 1. headless_bot_manager.py (5001) ───────────────────────────────────────
info "[1/4] Iniciando headless_bot_manager.py (puerto 5001)..."
cd "$ROOT/bot"
$PYTHON_CMD headless_bot_manager.py > /tmp/habbobots-botmanager.log 2>&1 &
BOT_MANAGER_PID=$!
echo $BOT_MANAGER_PID > /tmp/habbobots-botmanager.pid
info "Bot Manager PID: $BOT_MANAGER_PID | Log: /tmp/habbobots-botmanager.log"
sleep 2

# ── 2. web.py GUI panel (5000) ──────────────────────────────────────────────
info "[2/4] Iniciando web.py panel admin (puerto 5000)..."
cd "$ROOT/bot"
$PYTHON_CMD web.py > /tmp/habbobots-webgui.log 2>&1 &
WEB_GUI_PID=$!
echo $WEB_GUI_PID > /tmp/habbobots-webgui.pid
info "Web GUI PID: $WEB_GUI_PID | Log: /tmp/habbobots-webgui.log"
sleep 2

# ── 3. Node.js Backend (3001) ────────────────────────────────────────────────
info "[3/4] Iniciando Node.js backend (puerto 3001)..."
cd "$ROOT/backend"
npm run dev > /tmp/habbobots-backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > /tmp/habbobots-backend.pid
info "Backend PID: $BACKEND_PID | Log: /tmp/habbobots-backend.log"
sleep 3

# ── 4. Astro Frontend (4321) ────────────────────────────────────────────────
info "[4/4] Iniciando Astro frontend (puerto 4321)..."
cd "$ROOT/frontend"
npm run dev > /tmp/habbobots-frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > /tmp/habbobots-frontend.pid
info "Frontend PID: $FRONTEND_PID | Log: /tmp/habbobots-frontend.log"

# ── Resumen ──────────────────────────────────────────────────────────────────
sleep 3
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║       ✅  HabboBOTS corriendo                    ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║${NC}  Bot Manager   →  http://localhost:5001          ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  Web GUI       →  http://localhost:5000          ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  Backend API   →  http://localhost:3001          ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  Frontend      →  http://localhost:4321          ${GREEN}║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║${NC}  Logs en /tmp/habbobots-*.log                    ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  Para parar todo: ./stop.sh                      ${GREEN}║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Para crear un admin:"
echo "    node $ROOT/scripts/crear-admin.js"
echo ""

# ── Guardar PIDs juntos ──────────────────────────────────────────────────────
cat > /tmp/habbobots-pids.txt <<EOF
BOT_MANAGER_PID=$BOT_MANAGER_PID
WEB_GUI_PID=$WEB_GUI_PID
BACKEND_PID=$BACKEND_PID
FRONTEND_PID=$FRONTEND_PID
EOF

# ── Esperar (Ctrl+C para parar todo) ────────────────────────────────────────
trap 'echo ""; info "Deteniendo todos los servicios..."; kill $BOT_MANAGER_PID $WEB_GUI_PID $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0' INT TERM

wait
