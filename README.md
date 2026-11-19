# UrbanCare

[![Deploy UrbanFlow to Azure App Service](https://github.com/rafadagalera/urbanflow/actions/workflows/azure-deploy.yml/badge.svg)](https://github.com/rafadagalera/urbanflow/actions)

**Versão publicada (Azure App Service, Brazil South, HTTPS):**
- **Landing e chat do assistente:** [https://rg-urbanflow-prd-fmcjh2hkgfatbedj.brazilsouth-01.azurewebsites.net/](https://rg-urbanflow-prd-fmcjh2hkgfatbedj.brazilsouth-01.azurewebsites.net/)
- **Healthcheck:** [https://rg-urbanflow-prd-fmcjh2hkgfatbedj.brazilsouth-01.azurewebsites.net/health](https://rg-urbanflow-prd-fmcjh2hkgfatbedj.brazilsouth-01.azurewebsites.net/health)

UrbanCare é um abrigo de ônibus inteligente para quem espera o ônibus à noite, com foco em mulheres desacompanhadas, mães com crianças e idosos. O abrigo monitora a lotação, detecta queda de luminosidade e sinaliza pessoa vulnerável sozinha à noite, usando silhuetas anônimas (Edge AI, conceito do produto). Este repositório traz duas entregas da Global Solution CitizenTech (FIAP, 4ESPS) ligadas pelo banco de dados: um **pipeline de dados** (Airflow + PostgreSQL) que calcula um índice de vulnerabilidade noturna para os pontos de ônibus de São Paulo a partir de dados abertos, e um **assistente de IA generativa** (FastAPI + OpenRouter) que responde, com base no manual do produto e nas tabelas gold, perguntas de operadores e gestores. O UrbanCare evolui o protótipo UrbanFlow; o histórico dele está preservado no git.

---

## Ficha Técnica do MVP (Global Solution 2026.2, FIAP 4ESPS)

| Campo | Detalhamento |
| :--- | :--- |
| **Nome do Produto** | **UrbanCare** (solução alinhada à convocação da parceira **CitizenTech**; evolução do UrbanFlow) |
| **Cidadão e Território** | Passageiros que esperam ônibus à noite em São Paulo, com foco em mulheres desacompanhadas, mães com crianças e idosos. Quem paga: Secretarias de Mobilidade e concessionárias de iluminação (PPP). Quem opera: central de monitoramento. |
| **Problema, em uma frase** | Faltam dados para decidir onde um abrigo inteligente protege mais: pontos de ônibus escuros e com muitas ocorrências noturnas ao redor ficam sem prioridade, e a espera à noite segue insegura para quem é mais vulnerável. |
| **Proposta de Valor** | Priorizar com dados onde instalar e atender abrigos (índice de vulnerabilidade noturna por ponto), avisar lotação, escuridão e pessoa sozinha à noite, e responder dúvidas de operação em linguagem natural. Privacidade por projeto: silhuetas anônimas e nenhum quadro de imagem guardado. |
| **Arquitetura: Componentes** | Pipeline Airflow (bronze, silver e gold) → PostgreSQL, schema `gold` → assistente FastAPI com OpenRouter (modelo principal e reserva, saída validada). Landing e chat publicados na **Azure App Service** (`rg-urbanflow-prd`) por **GitHub Actions** (`azure-deploy.yml`). |
| **Fontes de Dados** | **GeoSampa** (pontos de ônibus, postes de iluminação pública, distritos e subprefeituras, via WFS) e **SSP-SP** (ocorrências criminais de 2025, planilha pública), mais leituras de sensores **simuladas** com semente fixa e marcadas `simulado = true`. |
| **Modelos de IA Utilizados** | **Edge AI** de detecção de silhuetas anônimas no abrigo: conceito do produto, **não implementado** nesta entrega. **LLM via OpenRouter** com saída estruturada (principal `anthropic/claude-haiku-5.5`, reserva `openai/gpt-6-luna`) para o assistente. |
| **URL do MVP e Repositório** | **MVP:** https://rg-urbanflow-prd-fmcjh2hkgfatbedj.brazilsouth-01.azurewebsites.net/ · **GitHub:** https://github.com/rafadagalera/urbanflow |
| **Indicadores de Impacto** | (1) Pontos de ônibus priorizados por vulnerabilidade noturna (ranking de todos os pontos de rua, faixas alta, média e baixa); (2) pontos com abrigo escuro identificados (lux abaixo de 10) e tempo desde que escureceram; (3) alertas de lotação, de escuridão e de pessoa sozinha à noite, sempre com decisão humana em campo. |
| **ODS Conectados (ONU)** | **ODS 11** (Cidades e Comunidades Sustentáveis, meta 11.2: transporte seguro com atenção a mulheres, crianças e idosos) e **ODS 5** (Igualdade de Gênero). |

---

## As duas entregas

| Disciplina | Documentação | Evidências |
| :--- | :--- | :--- |
| **Big Data Architecture & Data Integration** | [`pipeline/README.md`](pipeline/README.md) e [PDF da entrega](docs/bigdata/UrbanCare-BigData.pdf) | [prints do Airflow, consultas ao gold e notas dos dados](docs/bigdata/) |
| **Generative AI for Engineering** | [`assistente/README.md`](assistente/README.md) | [saídas reais de 3 modelos, pytest](docs/evidencias/README.md) |

O pipeline alimenta o assistente: a cada pergunta, o assistente lê o resumo do schema `gold` no Postgres.

## Estrutura do repositório

```
.
├── docker-compose.yml          postgres, airflow (webserver, scheduler, init) e assistente
├── .env.example                variáveis sem valores; o .env fica fora do git
├── pipeline/                   entrega Big Data
│   ├── dags/                   DAG urbancare_pipeline
│   ├── urbancare_pipeline/     extração, tratamento, gold, sensores simulados, carga, qualidade
│   ├── tests/                  pytest
│   └── README.md
├── assistente/                 entrega GenAI
│   ├── app/                    FastAPI: main, config, llm, contexto, schema, static/ (chat)
│   ├── prompts/sistema.md      prompt de sistema versionado
│   ├── tests/                  pytest com cliente LLM simulado
│   └── README.md
├── web/                        versão publicada: landing, chat e servidor Node (Azure)
├── .github/workflows/          azure-deploy.yml (CI/CD para a Azure App Service)
├── docs/
│   ├── manual.md               manual do produto (contexto do assistente)
│   ├── specs/                  especificações de projeto
│   ├── bigdata/                diagrama, prints, notas dos dados, consultas e PDF
│   └── evidencias/             saídas do assistente em 3 modelos e saídas do pytest
├── scripts/                    gerar_evidencias.py, gerar_pdf_bigdata.py, exportar_contexto.py
└── data/                       bronze e silver gerados pelo pipeline (fora do git)
```

## Como rodar localmente

Requer Docker com Compose.

1. Configure o ambiente e crie as pastas montadas pelo compose:
   ```bash
   cp .env.example .env     # preencha senhas, chaves do Airflow e, para o assistente, OPENROUTER_API_KEY, LLM_MODEL e LLM_FALLBACK_MODEL
   mkdir -p data logs
   docker compose up -d --build
   ```
2. Dispare a DAG (a primeira execução baixa as fontes e leva mais tempo; as seguintes usam o cache):
   ```bash
   docker compose exec airflow-scheduler airflow dags unpause urbancare_pipeline
   docker compose exec airflow-scheduler airflow dags trigger urbancare_pipeline
   ```
   O Airflow fica em <http://localhost:8080> (usuário e senha: `AIRFLOW_ADMIN_USER` e `AIRFLOW_ADMIN_PASSWORD` do `.env`); detalhes no [README do pipeline](pipeline/README.md).
3. Abra o assistente em <http://localhost:8000> (chat) e confira `/saude`. Para rodar os testes e regenerar as evidências, veja o [README do assistente](assistente/README.md#7-como-rodar).

---

## Integrantes do Grupo (4ESPS)
- **Beatriz Silva Pinheiro Rocha** — RM: 553455
- **Enzzo Monteiro Barros Silva** — RM: 552616
- **Iago Diniz Fontes** — RM: 553776
- **Larissa Estella Gonçalves dos Santos** — RM: 552695
- **Rafael Alves do Nascimento** — RM: 553117
