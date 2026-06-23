import 'dotenv/config';
import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import morgan from 'morgan';
import rateLimit from 'express-rate-limit';

import { initDB } from './database/init.js';
import authRoutes    from './routes/auth.js';
import userRoutes    from './routes/users.js';
import botRoutes     from './routes/bots.js';
import creditRoutes  from './routes/credits.js';
import habboRoutes   from './routes/habbo.js';
import statsRoutes   from './routes/stats.js';

const app  = express();
const PORT = process.env.PORT || 3001;

// ── Security ─────────────────────────────────────
app.use(helmet());
app.use(cors({
  origin: process.env.FRONTEND_URL || 'http://localhost:4321',
  credentials: true,
}));

// ── Rate limiting ─────────────────────────────────
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 min
  max: 100,
  message: { error: 'Demasiadas peticiones, intenta más tarde.' },
});
const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 10,
  message: { error: 'Demasiados intentos de autenticación.' },
});

app.use(limiter);
app.use(morgan('dev'));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// ── Routes ────────────────────────────────────────
app.use('/auth',    authLimiter, authRoutes);
app.use('/users',   userRoutes);
app.use('/bots',    botRoutes);
app.use('/credits', creditRoutes);
app.use('/habbo',   habboRoutes);
app.use('/stats',   statsRoutes);

// ── Health check ──────────────────────────────────
app.get('/health', (_req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// ── 404 ───────────────────────────────────────────
app.use((_req, res) => {
  res.status(404).json({ error: 'Ruta no encontrada' });
});

// ── Error handler ─────────────────────────────────
app.use((err, _req, res, _next) => {
  console.error(err);
  const status = err.status || 500;
  res.status(status).json({ error: err.message || 'Error interno del servidor' });
});

// ── Start ─────────────────────────────────────────
initDB();
app.listen(PORT, () => {
  console.log(`\n🤖 HabboBots API corriendo en http://localhost:${PORT}`);
  console.log(`   ENV: ${process.env.NODE_ENV || 'development'}\n`);
});
