# HabboBots — Cómo arrancar en local

## Requisitos
- [Node.js](https://nodejs.org) v18 o superior

## Instalar y arrancar

```bash
# 1. Abre una terminal en esta carpeta
cd "Página Web HabboBOTS"

# 2. Instala las dependencias (solo la primera vez)
npm install

# 3. Arranca el servidor de desarrollo
npm run dev
```

## Rutas disponibles

| URL | Página |
|-----|--------|
| `http://localhost:4321/` | Login / Registro |
| `http://localhost:4321/dashboard` | Panel principal |
| `http://localhost:4321/bots` | Gestión de bots |
| `http://localhost:4321/stats` | Estadísticas |
| `http://localhost:4321/tienda` | Tienda de créditos |
| `http://localhost:4321/perfil` | Perfil de usuario |
| `http://localhost:4321/verificar` | Verificación Habbo |

## Estructura del proyecto

```
src/
  layouts/
    AuthLayout.astro    ← Layout para login/registro
    DashLayout.astro    ← Layout con navbar + sidebar
  pages/
    index.astro         → /
    dashboard.astro     → /dashboard
    bots.astro          → /bots
    stats.astro         → /stats
    tienda.astro        → /tienda
    perfil.astro        → /perfil
    verificar.astro     → /verificar
public/
  css/style.css         ← Estilos globales (tema cyber + estilo Habbo)
  js/main.js            ← JS compartido
```

## Para producción

```bash
npm run build    # Genera la carpeta dist/
npm run preview  # Previsualiza el build
```
