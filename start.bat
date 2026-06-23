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
  echo [1/2] Instalando dependencias del backend...
  cd backend
  call npm install
  cd ..
)

:: Instala dependencias del frontend si no existen
if not exist "frontend\node_modules" (
  echo [2/2] Instalando dependencias del frontend...
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

echo.
echo  Arrancando...
echo   Backend  ^>  http://localhost:3001
echo   Frontend ^>  http://localhost:4321
echo.
echo  Cierra esta ventana para detener ambos servidores.
echo.

:: Arranca el backend en una nueva ventana
start "HabboBots BACKEND :3001" cmd /k "cd backend && npm run dev"

:: Espera 2 segundos y arranca el frontend
timeout /t 2 /nobreak >nul
start "HabboBots FRONTEND :4321" cmd /k "cd frontend && npm run dev"

:: Espera 4 segundos y abre el navegador
timeout /t 4 /nobreak >nul
start http://localhost:4321

echo  Servidores corriendo. Pulsa cualquier tecla para cerrar este asistente.
echo  (Los servidores seguiran activos en sus ventanas)
pause >nul
