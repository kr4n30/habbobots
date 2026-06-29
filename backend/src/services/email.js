import nodemailer from 'nodemailer';

const transporter = nodemailer.createTransport({
  host:   process.env.SMTP_HOST,
  port:   parseInt(process.env.SMTP_PORT || '587'),
  secure: process.env.SMTP_PORT === '465',
  auth: {
    user: process.env.SMTP_USER,
    pass: process.env.SMTP_PASS,
  },
});

const FROM = `"HabboBots" <${process.env.SMTP_FROM || process.env.SMTP_USER}>`;
const BASE = process.env.FRONTEND_URL || 'https://kr4n30.tech';

export async function sendVerificationEmail(toEmail, username, token) {
  const url = `${BASE}/verificar-email?token=${token}`;

  await transporter.sendMail({
    from:    FROM,
    to:      toEmail,
    subject: '✉️ Verifica tu cuenta en HabboBots',
    html: `
<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#09091f;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#09091f;padding:40px 16px;">
    <tr><td align="center">
      <table width="480" cellpadding="0" cellspacing="0" style="background:#0d1428;border:1px solid rgba(0,195,255,.18);border-radius:12px;overflow:hidden;">

        <!-- Header -->
        <tr><td style="background:linear-gradient(90deg,#0a3a6e,#1a1650);padding:14px 24px;border-bottom:2px solid #000;">
          <span style="font-family:'Orbitron',Arial,sans-serif;font-size:18px;font-weight:700;color:#00c3ff;letter-spacing:2px;">HABBOBOTS</span>
        </td></tr>

        <!-- Body -->
        <tr><td style="padding:32px 28px;color:#c8d4f0;">
          <p style="margin:0 0 8px;font-size:18px;font-weight:700;color:#fff;">Hola, <span style="color:#9b30ff;">${username}</span></p>
          <p style="margin:0 0 24px;font-size:14px;color:#8899bb;line-height:1.6;">Estás a un clic de activar tu cuenta. Haz clic en el botón para verificar tu dirección de email:</p>

          <table cellpadding="0" cellspacing="0"><tr><td>
            <a href="${url}" style="display:inline-block;padding:13px 32px;background:linear-gradient(135deg,#9b30ff,#6010cc);color:#fff;text-decoration:none;border-radius:8px;font-size:15px;font-weight:700;letter-spacing:.5px;border:2px solid #000;">
              Verificar email →
            </a>
          </td></tr></table>

          <p style="margin:24px 0 0;font-size:12px;color:#556080;line-height:1.7;">
            O copia este enlace en tu navegador:<br>
            <a href="${url}" style="color:#00c3ff;word-break:break-all;">${url}</a>
          </p>

          <hr style="border:none;border-top:1px solid rgba(0,195,255,.1);margin:24px 0;">
          <p style="margin:0;font-size:12px;color:#445066;">
            Este enlace expira en <strong>24 horas</strong>. Si no creaste esta cuenta, ignora este mensaje.
          </p>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>`,
  });
}

// ── Email: bot próximo a expirar ─────────────────────────────────────────────
export async function sendBotExpiryEmail(toEmail, username, botName, expiresAt) {
  if (!process.env.SMTP_HOST) return; // SMTP no configurado, silencioso
  const url      = `${BASE}/bots`;
  const expLabel = new Date(expiresAt).toLocaleString('es-ES', {
    day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });

  await transporter.sendMail({
    from:    FROM,
    to:      toEmail,
    subject: `⚠️ Tu bot "${botName}" expira en 24 horas`,
    html: `
<!DOCTYPE html><html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#09091f;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#09091f;padding:40px 16px;">
    <tr><td align="center">
      <table width="480" cellpadding="0" cellspacing="0" style="background:#0d1428;border:1px solid rgba(255,190,0,.25);border-radius:12px;overflow:hidden;">
        <tr><td style="background:linear-gradient(90deg,#3a2a00,#1a1650);padding:14px 24px;border-bottom:2px solid #000;">
          <span style="font-family:'Orbitron',Arial,sans-serif;font-size:18px;font-weight:700;color:#ffbe00;letter-spacing:2px;">HABBOBOTS</span>
        </td></tr>
        <tr><td style="padding:32px 28px;color:#c8d4f0;">
          <p style="margin:0 0 8px;font-size:18px;font-weight:700;color:#fff;">Hola, <span style="color:#ffbe00;">${username}</span> ⚠️</p>
          <p style="margin:0 0 6px;font-size:14px;color:#8899bb;line-height:1.6;">Tu bot <strong style="color:#fff;">${botName}</strong> expirará en menos de 24 horas.</p>
          <p style="margin:0 0 24px;font-size:13px;color:#556080;">Fecha de expiración: <strong style="color:#ffbe00;">${expLabel}</strong></p>

          <table cellpadding="0" cellspacing="0"><tr><td>
            <a href="${url}" style="display:inline-block;padding:13px 32px;background:linear-gradient(135deg,#ffbe00,#cc8800);color:#000;text-decoration:none;border-radius:8px;font-size:15px;font-weight:700;letter-spacing:.5px;">
              Renovar bot →
            </a>
          </td></tr></table>

          <hr style="border:none;border-top:1px solid rgba(255,190,0,.1);margin:24px 0;">
          <p style="margin:0;font-size:12px;color:#445066;">
            Si no renuevas, el bot dejará de funcionar automáticamente cuando expire.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>`,
  });
}

// ── Email: servicio completado ────────────────────────────────────────────────
export async function sendServiceCompletedEmail(toEmail, username, serviceName, hotel) {
  if (!process.env.SMTP_HOST) return;
  const url = `${BASE}/servicios`;

  await transporter.sendMail({
    from:    FROM,
    to:      toEmail,
    subject: `✅ Tu servicio "${serviceName}" ha terminado`,
    html: `
<!DOCTYPE html><html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#09091f;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#09091f;padding:40px 16px;">
    <tr><td align="center">
      <table width="480" cellpadding="0" cellspacing="0" style="background:#0d1428;border:1px solid rgba(0,255,163,.18);border-radius:12px;overflow:hidden;">
        <tr><td style="background:linear-gradient(90deg,#003a20,#1a1650);padding:14px 24px;border-bottom:2px solid #000;">
          <span style="font-family:'Orbitron',Arial,sans-serif;font-size:18px;font-weight:700;color:#00ffa3;letter-spacing:2px;">HABBOBOTS</span>
        </td></tr>
        <tr><td style="padding:32px 28px;color:#c8d4f0;">
          <p style="margin:0 0 8px;font-size:18px;font-weight:700;color:#fff;">¡Listo, <span style="color:#00ffa3;">${username}</span>! ✅</p>
          <p style="margin:0 0 24px;font-size:14px;color:#8899bb;line-height:1.6;">
            Tu servicio <strong style="color:#fff;">${serviceName}</strong> en <strong>habbo.${hotel}</strong> ha finalizado correctamente.
          </p>
          <table cellpadding="0" cellspacing="0"><tr><td>
            <a href="${url}" style="display:inline-block;padding:13px 32px;background:linear-gradient(135deg,#00ffa3,#00cc80);color:#000;text-decoration:none;border-radius:8px;font-size:15px;font-weight:700;">
              Ver mis servicios →
            </a>
          </td></tr></table>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>`,
  });
}
