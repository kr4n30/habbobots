import 'dotenv/config';
import { createServer }   from 'http';
import express            from 'express';
import cors               from 'cors';
import helmet             from 'helmet';
import morgan             from 'morgan';
import rateLimit          from 'express-rate-limit';
import path               from 'path';
import { fileURLToPath }  from 'url';

import { initDB }          from './database/init.js';
import { initSocket }      from './services/socket.js';
import { startOrderProcessor } from './services/orderProcessor.js';
import { startCron }       from './services/cron.js';

import authRoutes       from './routes/auth.js';
import userRoutes       from './routes/users.js';
import botRoutes        from './routes/bots.js';
import creditRoutes     from './routes/credits.js';
import habboRoutes      from './routes/habbo.js';
import statsRoutes      from './routes/stats.js';
import productRoutes    from './routes/products.js';
import adminRoutes      from './routes/admin.js';
import reviewRoutes       from './routes/reviews.js';
import affiliateRoutes    from './routes/affiliates.js';
import notificationRoutes from './routes/notifications.js';
import botpanelRoutes     from './routes/botpanel.js';
import couponRoutes       from './routes/coupons.js';
import ticketRoutes       from './routes/tickets.js';
import statusRoutes       from './routes/status.js';
import pushRoutes         from './routes/push.js';
import metricsRoutes      from './routes/metrics.js';

const app        = express();
const httpServer = createServer(app);
const PORT       = process.env.PORT || 3001;

// ── Security ─────────────────────────────────────
app.use(helmet({
  contentSecurityPolicy: false, // Desactivado para el frontend Astro
}));
app.use(cors({
  origin: process.env.FRONTEND_URL || 'http://localhost:4321',
  credentials: true,
}));

// ── Rate limiting ─────────────────────────────────
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 100,
  message: { error: 'Demasiadas peticiones, intenta más tarde.' },
  standardHeaders: true,
  legacyHeaders:   false,
});
const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 10,
  message: { error: 'Demasiados intentos de autenticación.' },
  standardHeaders: true,
  legacyHeaders:   false,
});
const habboLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: 20,
  message: { error: 'Demasiadas verificaciones. Espera un minuto.' },
});

app.use(limiter);
app.use(morgan('dev'));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// ── Static uploads ────────────────────────────────
const __dirname = path.dirname(fileURLToPath(import.meta.url));
app.use('/uploads', express.static(path.resolve(__dirname, '../../public/uploads')));

// ── Routes ────────────────────────────────────────
app.use('/auth',        authLimiter, authRoutes);
app.use('/users',       userRoutes);
app.use('/bots',        botRoutes);
app.use('/credits',     creditRoutes);
app.use('/habbo',       habboLimiter, habboRoutes);
app.use('/stats',       statsRoutes);
app.use('/products',    productRoutes);
app.use('/admin',       adminRoutes);
app.use('/reviews',       reviewRoutes);
app.use('/affiliates',    affiliateRoutes);
app.use('/notifications', notificationRoutes);
app.use('/admin/botpanel', botpanelRoutes);
app.use('/coupons',   couponRoutes);
app.use('/tickets',   ticketRoutes);
app.use('/status',    statusRoutes);   // público — sin auth
app.use('/push',      pushRoutes);
app.use('/admin/metrics', metricsRoutes);

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
initSocket(httpServer);
startOrderProcessor();
startCron();

httpServer.listen(PORT, () => {
  console.log(`\n🤖 HabboBots API corriendo en http://localhost:${PORT}`);
  console.log(`   ENV: ${process.env.NODE_ENV || 'development'}\n`);
  if (process.env.DISCORD_WEBHOOK_URL) {
    console.log(`   📨 Discord webhook configurado`);
  }
});
