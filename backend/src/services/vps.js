/**
 * Sends a command to the VPS that hosts the bots.
 * The VPS must expose a simple REST API secured by BOT_VPS_API_KEY.
 *
 * Commands: spawn | start | stop | destroy
 */
export async function sendVPSCommand(command, payload) {
  const VPS_URL = process.env.BOT_VPS_URL;
  const API_KEY = process.env.BOT_VPS_API_KEY;

  if (!VPS_URL || !API_KEY) {
    console.warn('[VPS] BOT_VPS_URL o BOT_VPS_API_KEY no configurados — comando ignorado:', command);
    return { ok: false, stub: true };
  }

  const res = await fetch(`${VPS_URL}/command`, {
    method: 'POST',
    headers: {
      'Content-Type':  'application/json',
      'X-Api-Key':     API_KEY,
    },
    body: JSON.stringify({ command, ...payload }),
    signal: AbortSignal.timeout(10_000),
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`VPS error ${res.status}: ${body}`);
  }

  return res.json();
}
