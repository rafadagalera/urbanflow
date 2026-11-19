// Rotas HTTP: /health e /api/simular-alerta intactos, /api/perguntar, /api/saude,
// limites de uso e arquivos estáticos sem path traversal.
import assert from 'node:assert/strict';
import { after, before, describe, it } from 'node:test';

import { bruto, configTeste, fetchFalso, pastaEstatica, respostaJson, subir } from './apoio.mjs';

const json = (r) => JSON.parse(r.corpo);
const perguntar = (porta, corpo, headers = {}) => bruto(porta, '/api/perguntar', {
  metodo: 'POST', corpo: typeof corpo === 'string' ? corpo : JSON.stringify(corpo),
  headers: { 'Content-Type': 'application/json', ...headers },
});

describe('servidor', () => {
  let s;
  let f;
  let pastas;
  before(async () => {
    pastas = pastaEstatica();
    f = fetchFalso(Array(20).fill(respostaJson()));
    s = await subir({ config: configTeste({ limite_por_min: 1000 }), fetch: f, dirEstatico: pastas.pub });
  });
  after(() => s.fechar());

  it('/health e /api/health idênticos ao servidor original', async () => {
    for (const rota of ['/health', '/api/health']) {
      const r = await bruto(s.porta, rota);
      assert.equal(r.status, 200);
      assert.equal(r.headers['content-type'], 'application/json; charset=utf-8');
      assert.equal(r.headers['cache-control'], 'no-store');
      assert.deepEqual(json(r), { ok: true, service: 'urbanflow-prd',
        lgpd_mode: process.env.URBANFLOW_LGPD_MODE || 'anonymous_silhouette_300b_max' });
    }
  });

  it('/api/simular-alerta continua devolvendo 500', async () => {
    const r = await bruto(s.porta, '/api/simular-alerta');
    assert.equal(r.status, 500);
    assert.equal(r.headers['content-type'], 'application/json; charset=utf-8');
    assert.equal(r.corpo, '{"error":"Simulacao de Erro HTTP 500 para Alerta no Azure Application Insights"}');
  });

  it('rotas de demonstração do UrbanFlow removidas', async () => {
    assert.equal((await bruto(s.porta, '/api/snapshot')).status, 404);
  });

  it('POST /api/perguntar responde 200 com a Resposta', async () => {
    const r = await perguntar(s.porta, { pergunta: '  como atendo um alerta?  ' });
    assert.equal(r.status, 200);
    assert.deepEqual(json(r), JSON.parse(respostaJson()));
    // a pergunta vai limpa (strip) e delimitada
    assert.match(f.chamadas.at(-1).corpo.messages[1].content, /<pergunta_do_usuario>\ncomo atendo um alerta\?\n</);
    assert.ok(!s.logs.join('\n').includes('como atendo'));
  });

  it('entrada inválida → 422 no formato do FastAPI', async () => {
    const casos = [
      [{ pergunta: '' }, 'string_too_short'],
      [{ pergunta: '   ' }, 'value_error'],
      [{ pergunta: 'x'.repeat(501) }, 'string_too_long'],
      [{ pergunta: 5 }, 'string_type'],
      [{}, 'missing'],
      [[1], 'model_attributes_type'],
      ['{ruim', 'json_invalid'],
    ];
    for (const [corpo, tipo] of casos) {
      const r = await perguntar(s.porta, corpo);
      assert.equal(r.status, 422, JSON.stringify(corpo));
      assert.equal(json(r).detail[0].type, tipo);
    }
    const longa = json(await perguntar(s.porta, { pergunta: 'x'.repeat(501) })).detail[0];
    assert.deepEqual(longa.loc, ['body', 'pergunta']);
    assert.equal(longa.msg, 'String should have at most 500 characters');
    // 500 caracteres é o limite exato (em code points, como no Python)
    assert.equal((await perguntar(s.porta, { pergunta: 'é'.repeat(500) })).status, 200);
  });

  it('GET /api/perguntar → 405', async () => {
    const r = await bruto(s.porta, '/api/perguntar');
    assert.equal(r.status, 405);
    assert.deepEqual(json(r), { detail: 'Method Not Allowed' });
  });

  it('/api/saude sem vazar a chave', async () => {
    const r = await bruto(s.porta, '/api/saude');
    const corpo = json(r);
    assert.deepEqual(corpo, { modelo: 'm/principal', modelo_reserva: 'm/reserva', chave_presente: true,
      dados_gold: true, retrato_em: '2026-11-18T17:21:02-03:00', exportado_em: '2026-11-19T12:00:00-03:00',
      ultima_execucao: { fim: '2026-11-18T17:21:02-03:00', status: 'ok' } });
    assert.ok(!r.corpo.includes('teste"'));
  });

  it('estáticos: / → index.html, MIME correto', async () => {
    const r = await bruto(s.porta, '/');
    assert.equal(r.status, 200);
    assert.equal(r.headers['content-type'], 'text/html; charset=utf-8');
    assert.match(r.corpo, /UrbanCare/);
    assert.equal((await bruto(s.porta, '/estilo.css')).headers['content-type'], 'text/css; charset=utf-8');
    assert.equal((await bruto(s.porta, '/nao-existe.js')).status, 404);
  });

  it('path traversal e arquivos internos bloqueados', async () => {
    const caminhos = ['/../server.mjs', '/%2e%2e/contexto.json', '/..%2fsistema.md', '/%2e%2e%2fserver.mjs',
      '/..%5cserver.mjs', '/../public-x/vizinho.txt', '/%2e%2e/public-x/vizinho.txt', '/contexto.json',
      '/.env', '/%2eenv', '/server.mjs', '/sistema.md', '/%00', '/%E0%A4%A', '//etc/passwd', '/a/../../server.mjs'];
    for (const c of caminhos) {
      const r = await bruto(s.porta, c);
      assert.ok(r.status >= 400, `${c} → ${r.status}`);
      assert.ok(!r.corpo.includes('SEGREDO') && !r.corpo.includes('segredo'), c);
    }
  });
});

describe('limites de uso', () => {
  it('10 por minuto por IP; primeiro salto forjado do X-Forwarded-For não zera a contagem', async () => {
    let t = 1_000_000;
    const s = await subir({ config: configTeste(), fetch: fetchFalso(Array(20).fill(respostaJson())),
      agora: () => t });
    try {
      const status = [];
      for (let i = 0; i < 11; i++) {
        // o cliente forja o primeiro item; a Azure acrescenta o IP real (com porta) no fim
        const r = await perguntar(s.porta, { pergunta: 'oi' }, { 'X-Forwarded-For': `10.0.0.${i}, 200.1.2.3:5${i}123` });
        status.push(r.status);
        if (r.status === 429) {
          assert.match(json(r).detail, /Espere um minuto/);
          assert.ok(Number(r.headers['retry-after']) > 0);
        }
      }
      assert.deepEqual(status, [...Array(10).fill(200), 429]);
      // outro IP real segue livre
      assert.equal((await perguntar(s.porta, { pergunta: 'oi' }, { 'X-Forwarded-For': '200.9.9.9' })).status, 200);
      // passado um minuto, libera de novo
      t += 60_000;
      assert.equal((await perguntar(s.porta, { pergunta: 'oi' }, { 'X-Forwarded-For': '200.1.2.3:4' })).status, 200);
    } finally {
      await s.fechar();
    }
  });

  it('sem X-Forwarded-For usa o IP do socket', async () => {
    const s = await subir({ config: configTeste({ limite_por_min: 2 }), fetch: fetchFalso(Array(5).fill(respostaJson())) });
    try {
      const st = [];
      for (let i = 0; i < 3; i++) st.push((await perguntar(s.porta, { pergunta: 'oi' })).status);
      assert.deepEqual(st, [200, 200, 429]);
    } finally {
      await s.fechar();
    }
  });

  it('teto global por hora somando todos os clientes', async () => {
    let t = 7_200_000; // início de uma hora cheia
    const s = await subir({ config: configTeste({ limite_global_hora: 3 }), fetch: fetchFalso(Array(10).fill(respostaJson())),
      agora: () => t });
    try {
      const st = [];
      for (let i = 0; i < 4; i++) {
        const r = await perguntar(s.porta, { pergunta: 'oi' }, { 'X-Forwarded-For': `200.0.0.${i}` });
        st.push(r.status);
        if (r.status === 429) assert.match(json(r).detail, /limite de uso desta hora; tente mais tarde/);
      }
      assert.deepEqual(st, [200, 200, 200, 429]);
      t += 3_600_000; // hora seguinte: janela nova
      assert.equal((await perguntar(s.porta, { pergunta: 'oi' }, { 'X-Forwarded-For': '200.0.0.9' })).status, 200);
    } finally {
      await s.fechar();
    }
  });
});
