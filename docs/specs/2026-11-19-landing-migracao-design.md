# UrbanCare — migração para o repositório urbanflow, landing e chat publicado

Data: 2026-11-19. Entrega: hoje, 23h55. Complementa `2026-11-18-urbancare-genai-bigdata-design.md`.

## Decisões (com o Rafael)
1. O repositório de entrega passa a ser `rafadagalera/urbanflow`. O UrbanCare substitui o protótipo UrbanFlow num commit sobre `origin/master`, sem force push. Do Enzzo ficam o workflow `.github/workflows/azure-deploy.yml`, os endpoints `/health` e `/api/simular-alerta` (idênticos) e, no README, o badge, a Ficha Técnica (reescrita para o UrbanCare) e os integrantes.
2. O deploy continua na App Service `rg-urbanflow-prd` (Node 20, publish profile). O workflow publica a landing e o chat do UrbanCare.
3. O chat na Azure é um proxy Node sem dependências npm. A entrega de GenAI continua sendo o FastAPI, que roda localmente.
4. A chave do OpenRouter é uma App Setting `OPENROUTER_API_KEY` cadastrada pelo Enzzo. O workflow não grava segredo. Recomendação: chave dedicada com limite de crédito baixo.
5. A landing tem identidade própria e noturna.

## Componentes
| Caminho | Faz |
|---|---|
| `scripts/exportar_contexto.py` | roda localmente contra o Postgres; usa `assistente/app/contexto.py`; gera `web/contexto.json` com blocos globais, resumo e top 5 de cada distrito, lista de distritos e data do retrato |
| `web/contexto.json` | versionado (o CI não alcança o banco) |
| `web/server.mjs` | serve `public/` (ou `dist/` no pacote), `/api/perguntar`, `/api/saude`, `/health`, `/api/simular-alerta` |
| `web/public/` | landing estática + widget de chat |
| `web/test/` | `node --test` com `fetch` simulado |

### `/api/perguntar`
Reproduz o assistente Python:
- mesmo `sistema.md` e mesmas mensagens;
- mesma detecção de distrito, incluindo `SE`, `SAUDE`, `LIBERDADE` e `LIMAO`;
- `json_schema`, com recuo para `json_object`;
- extração tolerante do JSON e um reparo;
- 429 ou 5xx: uma retentativa; timeout ou falha persistente: modelo reserva; se tudo falhar, resposta segura `tipo="erro"`;
- pós-validação de `pontos_citados` e `fontes`;
- log só de metadados.

Proteções:
- pergunta vazia ou com mais de 500 caracteres: 422;
- limite em memória de 10 perguntas por minuto por IP: 429;
- arquivos estáticos sem path traversal.

### Artefato de deploy
`deploy_dist/` = `dist/` (landing) + `server.mjs` + `contexto.json` + `sistema.md` + `package.json` (`start: node server.mjs`).

## Ordem
1. Migração (feita).
2. Em paralelo: READMEs (assistente e raiz, links e PDF); chat Node + export; landing.
3. Integração local, revisão e correção.
4. Push na `master` (dispara o deploy), seguido de `curl` em `/health` e `/api/perguntar`.

## Fora de escopo
Pipeline e Postgres na nuvem, histórico de conversa, autenticação.
