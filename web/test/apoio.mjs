// Apoio aos testes: contexto de exemplo, fetch simulado e servidor em porta livre.
// Sem efeitos colaterais na importação (o node --test do Node 20 executa tudo em test/).
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';

import { criarServidor, lerConfig } from '../server.mjs';

const linha = (id, nome, d, pos) => `- ponto_id ${id} | ${nome} | distrito ${d} | posição ${pos} | índice 0.900 | `
  + 'faixa alta | ocorrências noturnas a 150 m: 100 | poste mais próximo: 20 m';

export const CONTEXTO = {
  versao: 1,
  gerado_em: '2026-11-19T12:00:00-03:00',
  tem_dados: true,
  manual: { 'manual#alertas': 'Alertas\nComo atender.', 'manual#indice': 'Índice\nComo é calculado.' },
  blocos_globais: [
    ['gold.execucao', 'Última atualização dos dados: 18/11/2026 17:20 (status ok)'],
    ['gold.ft_indicador_ponto', 'Top 10 do ranking de vulnerabilidade (cidade toda):\n'
      + `${linha('111', 'R. MOURATO COELHO , 1022', 'PINHEIROS', 1)}\n${linha('222', 'R. AUGUSTA , 810', 'CONSOLACAO', 2)}`],
  ],
  pontos_globais: ['111', '222'],
  distritos: ['PINHEIROS', 'SE', 'SAUDE', 'LIBERDADE', 'CIDADE DUTRA', 'JARDIM PAULISTA', 'CONSOLACAO'],
  por_distrito: Object.fromEntries(['PINHEIROS', 'SE', 'SAUDE', 'LIBERDADE', 'CIDADE DUTRA', 'JARDIM PAULISTA',
    'CONSOLACAO'].map((d, i) => [d, { fonte: `gold.ft_resumo_distrito#${d}`,
    bloco: `Distrito ${d}: sem resumo.\nOs 5 pontos mais vulneráveis do distrito:\n${linha(`9${i}`, `R. DE ${d}`, d, 7)}`,
    pontos: [`9${i}`] }])),
  saude: { dados_gold: true, ultima_execucao: { fim: '2026-11-18T17:21:02-03:00', status: 'ok' } },
};

export const SISTEMA = 'SISTEMA DE TESTE';

export function respostaJson(extra = {}) {
  return JSON.stringify({ resposta: 'ok', tipo: 'uso', fontes: ['manual#alertas'], pontos_citados: [],
    acao_sugerida: null, precisa_humano: false, confianca: 'alta', ...extra });
}

const corpoOk = (conteudo) => ({ choices: [{ message: { content: conteudo } }],
  usage: { prompt_tokens: 100, completion_tokens: 20, cost: 0.0001 } });

/**
 * fetch simulado. Roteiro consumido em ordem a cada POST /chat/completions:
 * string = conteúdo do modelo; { status, corpo } = resposta HTTP; 'TIMEOUT' = espera o sinal abortar.
 * GET /models devolve `modelos` (ou 500 se null).
 */
export function fetchFalso(roteiro, { modelos = null } = {}) {
  const fila = [...roteiro];
  const chamadas = [];
  const f = async (url, init = {}) => {
    if (String(url).endsWith('/models')) {
      if (!modelos) return new Response('fora', { status: 500 });
      return new Response(JSON.stringify({ data: modelos }), { status: 200 });
    }
    const corpo = JSON.parse(init.body);
    chamadas.push({ url: String(url), modelo: corpo.model, formato: corpo.response_format.type,
      nMsgs: corpo.messages.length, corpo, headers: init.headers });
    const item = fila.shift();
    if (item === undefined) throw new Error('roteiro esgotado');
    if (item === 'TIMEOUT') {
      // o timer do AbortSignal.timeout é unref: sem este, o loop de eventos do teste esvazia antes do abort
      const segura = setTimeout(() => {}, 60_000);
      return new Promise((_, rejeitar) => init.signal.addEventListener('abort', () => {
        clearTimeout(segura);
        rejeitar(init.signal.reason);
      }));
    }
    if (typeof item === 'string') return new Response(JSON.stringify(corpoOk(item)), { status: 200 });
    return new Response(typeof item.corpo === 'string' ? item.corpo : JSON.stringify(item.corpo ?? {}),
      { status: item.status });
  };
  f.chamadas = chamadas;
  f.restantes = fila;
  return f;
}

export function configTeste(extra = {}) {
  return { ...lerConfig({}), api_key: 'teste', modelo: 'm/principal', modelo_reserva: 'm/reserva',
    modelos: ['m/principal', 'm/reserva'], ...extra };
}

/** Pasta temporária: raiz/{server.mjs, contexto.json, sistema.md, public/index.html, public/contexto.json}. */
export function pastaEstatica() {
  const raiz = fs.mkdtempSync(path.join(os.tmpdir(), 'urbancare-teste-'));
  const pub = path.join(raiz, 'public');
  fs.mkdirSync(pub);
  fs.writeFileSync(path.join(pub, 'index.html'), '<!doctype html><title>UrbanCare</title>');
  fs.writeFileSync(path.join(pub, 'estilo.css'), 'body{}');
  fs.writeFileSync(path.join(pub, '.env'), 'SEGREDO=1');
  fs.writeFileSync(path.join(pub, 'contexto.json'), '{"segredo": true}');
  for (const nome of ['server.mjs', 'contexto.json', 'sistema.md']) fs.writeFileSync(path.join(raiz, nome), 'SEGREDO');
  fs.mkdirSync(path.join(raiz, 'public-x'));
  fs.writeFileSync(path.join(raiz, 'public-x', 'vizinho.txt'), 'SEGREDO');
  return { raiz, pub };
}

/** Sobe o servidor numa porta livre; devolve { base, porta, fechar, logs }. */
export async function subir(opcoes = {}) {
  const logs = [];
  const servidor = criarServidor({ contexto: CONTEXTO, sistema: SISTEMA, dormir: async () => {},
    log: (l) => logs.push(l), ...opcoes });
  await new Promise((ok) => servidor.listen(0, '127.0.0.1', ok));
  const porta = servidor.address().port;
  return { base: `http://127.0.0.1:${porta}`, porta, logs,
    fechar: () => new Promise((ok) => servidor.close(ok)) };
}

/** Requisição crua: o caminho vai exatamente como escrito (fetch normalizaria "..", "%2e%2e"). */
export function bruto(porta, caminho, { metodo = 'GET', headers = {}, corpo } = {}) {
  return new Promise((ok, erro) => {
    const req = http.request({ host: '127.0.0.1', port: porta, path: caminho, method: metodo, headers }, (res) => {
      let dados = '';
      res.setEncoding('utf8');
      res.on('data', (c) => { dados += c; });
      res.on('end', () => ok({ status: res.statusCode, headers: res.headers, corpo: dados }));
    });
    req.on('error', erro);
    if (corpo !== undefined) req.write(corpo);
    req.end();
  });
}
