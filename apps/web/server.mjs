import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DIST_DIR = path.join(__dirname, 'dist');
const PORT = process.env.PORT || 8080;

// Estado em memória calibrado exatamente com apps/api/app/demo.py e seed.py (142 pontos, 1.284 pessoas, 11 min espera)
const INITIAL_STOPS = [
  { id: 'SP-0412', name: 'Av. Paulista, 1578', line: '875A', count: 26, x: 14, y: 20, wait_min: 17, enroute: false, status: 'critico', board_rate: 1.53, alert_active: true },
  { id: 'SP-0071', name: 'Terminal Sto. Amaro · Pl. 3', line: '6450', count: 24, x: 86, y: 55, wait_min: 15, enroute: false, status: 'critico', board_rate: 1.60, alert_active: true },
  { id: 'SP-0233', name: 'R. da Consolação, 900', line: '177H', count: 22, x: 40, y: 55, wait_min: 14, enroute: true, status: 'critico', board_rate: 1.57, alert_active: true },
  { id: 'SP-0587', name: 'Av. Rebouças, 1200', line: '7272', count: 18, x: 76, y: 36, wait_min: 12, enroute: false, status: 'atencao', board_rate: 1.50, alert_active: false },
  { id: 'SP-0104', name: 'Av. Brigadeiro Faria Lima, 1800', line: '875A', count: 17, x: 66, y: 20, wait_min: 11, enroute: false, status: 'atencao', board_rate: 1.54, alert_active: false },
  { id: 'SP-0192', name: 'Av. Ipiranga, 750', line: '177H', count: 16, x: 14, y: 80, wait_min: 12, enroute: false, status: 'atencao', board_rate: 1.33, alert_active: false },
  { id: 'SP-0310', name: 'R. Augusta, 1120', line: '6450', count: 15, x: null, y: null, wait_min: 10, enroute: false, status: 'atencao', board_rate: 1.50, alert_active: false },
  { id: 'SP-0401', name: 'Av. São João, 420', line: '7272', count: 11, x: 40, y: 20, wait_min: 9, enroute: false, status: 'normal', board_rate: 1.22, alert_active: false },
  { id: 'SP-0445', name: 'Av. Brasil, 980', line: '875A', count: 9, x: 51, y: 20, wait_min: 8, enroute: false, status: 'normal', board_rate: 1.12, alert_active: false },
  { id: 'SP-0512', name: 'Av. Santo Amaro, 2100', line: '6450', count: 10, x: 6, y: 39, wait_min: 9, enroute: false, status: 'normal', board_rate: 1.11, alert_active: false },
  { id: 'SP-0608', name: 'R. Vergueiro, 1450', line: '177H', count: 8, x: 54, y: 39, wait_min: 7, enroute: false, status: 'normal', board_rate: 1.14, alert_active: false },
  { id: 'SP-0690', name: 'Av. Angélica, 600', line: '7272', count: 7, x: 27, y: 55, wait_min: 7, enroute: false, status: 'normal', board_rate: 1.00, alert_active: false },
  { id: 'SP-0730', name: 'Av. Nove de Julho, 1300', line: '875A', count: 9, x: 31, y: 81, wait_min: 8, enroute: false, status: 'normal', board_rate: 1.12, alert_active: false },
  { id: 'SP-0815', name: 'Av. Sumaré, 890', line: '177H', count: 8, x: 66, y: 81, wait_min: 8, enroute: false, status: 'normal', board_rate: 1.00, alert_active: false },
  { id: 'SP-0902', name: 'R. Teodoro Sampaio, 1600', line: '6450', count: 6, x: 92, y: 81, wait_min: 6, enroute: false, status: 'normal', board_rate: 1.00, alert_active: false }
];

let stops = structuredClone(INITIAL_STOPS);
let extrasToday = 12;
let clockState = { sim_now: '2026-08-31T18:42:00-03:00', multiplier: 1, paused: false };
let landingStats = {
  A: { visits: 24, clicks: 5, leads: 2, ctr: 5 / 24 },
  B: { visits: 22, clicks: 4, leads: 2, ctr: 4 / 22 },
  recent: [
    { variant: 'A', company: 'Concessionária Via Sul', size: 142, email: 'operacao@viasul.com.br', created_at: new Date().toISOString() },
    { variant: 'B', company: 'Consórcio Metropolitano SP', size: 85, email: 'cco@consorciosp.com.br', created_at: new Date().toISOString() }
  ]
};

const HOURLY = [
  { hour: 5, avg_4w: 220, today: 230 }, { hour: 6, avg_4w: 510, today: 540 }, { hour: 7, avg_4w: 1020, today: 1090 },
  { hour: 8, avg_4w: 1160, today: 1210 }, { hour: 9, avg_4w: 800, today: 820 }, { hour: 10, avg_4w: 580, today: 590 },
  { hour: 11, avg_4w: 580, today: 600 }, { hour: 12, avg_4w: 650, today: 670 }, { hour: 13, avg_4w: 580, today: 595 },
  { hour: 14, avg_4w: 580, today: 610 }, { hour: 15, avg_4w: 650, today: 680 }, { hour: 16, avg_4w: 800, today: 850 },
  { hour: 17, avg_4w: 1090, today: 1190 }, { hour: 18, avg_4w: 1088, today: 1284 }, { hour: 19, avg_4w: 940, today: null },
  { hour: 20, avg_4w: 580, today: null }, { hour: 21, avg_4w: 360, today: null }, { hour: 22, avg_4w: 220, today: null }
];

function buildSnapshot() {
  const alerts = stops.filter(s => s.status === 'critico' || s.status === 'atencao').slice(0, 4);
  const critical = stops.filter(s => s.status === 'critico').length;
  const attention = stops.filter(s => s.status === 'atencao').length;
  return {
    clock: clockState,
    overview: {
      people: 1284,
      avg_wait_min: 11,
      wait_over_goal_min: 3,
      goal_wait_min: 8,
      stops_total: 142,
      stops_in_alert: critical + attention,
      critical,
      attention,
      extras_today: extrasToday,
      vs_avg_pct: 18
    },
    alerts,
    map: stops.filter(s => s.x !== null),
    hourly: HOURLY
  };
}

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.mp4': 'video/mp4',
  '.json': 'application/json; charset=utf-8',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2'
};

function sendJson(res, status, data) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
  res.end(JSON.stringify(data));
}

function readBody(req) {
  return new Promise((resolve) => {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      try { resolve(JSON.parse(body || '{}')); } catch { resolve({}); }
    });
  });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url || '/', `http://${req.headers.host || 'localhost'}`);
  const p = url.pathname;

  // Healthcheck e Rota de Teste de Alerta 500 para o Azure Application Insights
  if (p === '/health' || p === '/api/health') {
    return sendJson(res, 200, { ok: true, service: 'urbanflow-prd', lgpd_mode: process.env.URBANFLOW_LGPD_MODE || 'anonymous_silhouette_300b_max' });
  }
  if (p === '/api/simular-alerta') {
    res.writeHead(500, { 'Content-Type': 'application/json; charset=utf-8' });
    return res.end(JSON.stringify({ error: 'Simulacao de Erro HTTP 500 para Alerta no Azure Application Insights' }));
  }

  // Rotas de API consumidas pelo Frontend React
  if (p === '/api/snapshot') {
    return sendJson(res, 200, buildSnapshot());
  }
  if (p === '/api/stream') {
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no'
    });
    res.write(`event: snapshot\ndata: ${JSON.stringify(buildSnapshot())}\n\n`);
    const timer = setInterval(() => {
      res.write(`event: snapshot\ndata: ${JSON.stringify(buildSnapshot())}\n\n`);
    }, 2000);
    req.on('close', () => clearInterval(timer));
    return;
  }
  if (p === '/api/stops') {
    return sendJson(res, 200, stops.map(s => ({ ...s, svg_x: s.x, svg_y: s.y })));
  }
  if (p === '/api/dispatches' && req.method === 'POST') {
    const body = await readBody(req);
    const target = stops.find(s => s.id === body.stop_id);
    if (target) target.enroute = true;
    extrasToday += 1;
    return sendJson(res, 201, { id: Date.now(), stop_id: body.stop_id || 'SP-0412', garage_id: 'GAR-VM', status: 'a_caminho', boards: 14 });
  }
  if (p === '/api/dispatches') {
    return sendJson(res, 200, []);
  }
  if (p === '/api/sim/scenario/demo' && req.method === 'POST') {
    stops = structuredClone(INITIAL_STOPS);
    extrasToday = 12;
    return sendJson(res, 200, { clock: clockState, overview: buildSnapshot().overview });
  }
  if (p === '/api/sim/clock') {
    if (req.method === 'POST') {
      const body = await readBody(req);
      if (typeof body.paused === 'boolean') clockState.paused = body.paused;
      if (typeof body.multiplier === 'number') clockState.multiplier = body.multiplier;
    }
    return sendJson(res, 200, clockState);
  }
  if (p === '/api/landing/events' && req.method === 'POST') {
    const body = await readBody(req);
    const v = body.variant === 'B' ? 'B' : 'A';
    if (body.kind === 'visit') landingStats[v].visits += 1;
    if (body.kind === 'click') landingStats[v].clicks += 1;
    landingStats[v].ctr = landingStats[v].clicks / Math.max(1, landingStats[v].visits);
    return sendJson(res, 202, { accepted: true });
  }
  if (p === '/api/leads' && req.method === 'POST') {
    const body = await readBody(req);
    const v = body.variant === 'B' ? 'B' : 'A';
    landingStats[v].leads += 1;
    landingStats.recent.unshift({
      variant: v,
      company: body.company || 'Empresa Piloto',
      size: Number(body.size) || 20,
      email: body.email || 'contato@empresa.com.br',
      created_at: new Date().toISOString()
    });
    return sendJson(res, 201, { accepted: true });
  }
  if (p === '/api/landing/metrics') {
    const totalVisits = landingStats.A.visits + landingStats.B.visits;
    const totalClicks = landingStats.A.clicks + landingStats.B.clicks;
    const totalLeads = landingStats.A.leads + landingStats.B.leads;
    return sendJson(res, 200, {
      A: landingStats.A,
      B: landingStats.B,
      total: { visits: totalVisits, clicks: totalClicks, leads: totalLeads, ctr: totalClicks / Math.max(1, totalVisits) },
      goal_ctr: 0.15,
      goal_leads: 3,
      recent: landingStats.recent.slice(0, 20)
    });
  }
  if (p === '/api/landing/data' && req.method === 'DELETE') {
    return sendJson(res, 200, { ok: true });
  }

  // Servir arquivos estáticos do build Vite (dist) ou fallback SPA para index.html
  let filePath = path.join(DIST_DIR, p === '/' ? 'index.html' : p);
  if (!filePath.startsWith(DIST_DIR)) {
    res.writeHead(403);
    return res.end('Forbidden');
  }
  if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
    const ext = path.extname(filePath).toLowerCase();
    res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' });
    return fs.createReadStream(filePath).pipe(res);
  }

  const indexHtml = path.join(DIST_DIR, 'index.html');
  if (fs.existsSync(indexHtml)) {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    return fs.createReadStream(indexHtml).pipe(res);
  }

  res.writeHead(404);
  res.end('Not found');
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`UrbanFlow Production Server listening on http://0.0.0.0:${PORT}`);
});
