#!/usr/bin/env bash
# Para todos los servicios de HabboBOTS

GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'

echo -e "${RED}[HabboBOTS] Deteniendo servicios...${NC}"

# Leer PIDs guardados
if [ -f /tmp/habbobots-pids.txt ]; then
  source /tmp/habbobots-pids.txt
  for pid in $BOT_MANAGER_PID $WEB_GUI_PID $BACKEND_PID $FRONTEND_PID; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null && echo "  Detenido PID $pid"
  done
  rm /tmp/habbobots-pids.txt /tmp/habbobots-*.pid 2>/dev/null || true
else
  # Fallback: matar por puerto
  for port in 5001 5000 3001 4321; do
    pid=$(lsof -ti tcp:$port 2>/dev/null || true)
    [ -n "$pid" ] && kill -9 "$pid" 2>/dev/null && echo "  Puerto $port (PID $pid) liberado"
  done
fi

echo -e "${GREEN}✅  Todos los servicios detenidos.${NC}"
