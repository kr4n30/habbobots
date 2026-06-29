@echo off
title HabboBots - Dev Server
color 0B

echo.
echo  =============================================
echo    HabboBots - Arrancando servidores...
echo  =============================================
echo.

:: Verifica que Node.js está instalado
where node >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Node.js no encontrado. Instala desde https://nodejs.org
  pause
  exit /b 1
)

:: Instala dependencias del backend si no existen
if not exist "backend\node_modules" (
  echo [INFO] Instalando dependencias del backend...
  cd backend
  call npm install
  cd ..
)

:: Instala dependencias del frontend si no existen
if not exist "frontend\node_modules" (
  echo [INFO] Instalando dependencias del frontend...
  cd frontend
  call npm install
  cd ..
)

:: Copia .env si no existe
if not exist "backend\.env" (
  copy "backend\.env.example" "backend\.env" >nul
  echo [!] Creado backend\.env desde .env.example
  echo [!] Edita backend\.env con tus claves antes de continuar.
  echo.
)

:: ── Python Bot Manager (puerto 5001) ─────────────────────────────────────────
echo [1/3] Iniciando headless_bot_manager.py (puerto 5001)...
if exist "bot\venv\Scripts\activate.bat" (
  start "HabboBots BOT-MANAGER :5001" cmd /k "cd bot && call venv\Scripts\activate.bat && python headless_bot_manager.py"
) else (
  start "HabboBots BOT-MANAGER :5001" cmd /k "cd bot && python headless_bot_manager.py"
)
timeout /t 2 /nobreak >nul

:: ── Python Web GUI (puerto 5000) ─────────────────────────────────────────────
echo [2/3] Iniciando web.py panel admin (puerto 5000)...
if exist "bot\venv\Scripts\activate.bat" (
  start "HabboBots WEB-GUI :5000" cmd /k "cd bot && call venv\Scripts\activate.bat && python web.py"
) else (
  start "HabboBots WEB-GUI :5000" cmd /k "cd bot && python web.py"
)
timeout /t 2 /nobreak >nul

:: ── Node.js Backend (puerto 3001) ────────────────────────────────────────────
echo [3/3] Iniciando Node.js backend (puerto 3001)...
start "HabboBots BACKEND :3001" cmd /k "cd backend && npm run dev"
timeout /t 3 /nobreak >nul

:: ── Astro Frontend (puerto 4321) ─────────────────────────────────────────────
echo [4/4] Iniciando Astro frontend (puerto 4321)...
start "HabboBots FRONTEND :4321" cmd /k "cd frontend && npm run dev"

:: Espera y abre el navegador
timeout /t 5 /nobreak >nul
start http://localhost:4321

echo.
echo  ✅  Todos los servicios iniciados:
echo    • Bot Manager  → http://localhost:5001
echo    • Web GUI      → http://localhost:5000
echo    • Backend API  → http://localhost:3001
echo    • Frontend     → http://localhost:4321
echo.
echo  Para crear un admin (primera vez):
echo    node scripts/crear-admin.js
echo.
echo  Los servidores corren en sus propias ventanas.
pause >nul
