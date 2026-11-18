# UrbanFlow — Plataforma Inteligente de Mobilidade Urbana, Mídia OOH e Impacto Social (Parceira CitizenTech)

[![Deploy UrbanFlow to Azure App Service](https://github.com/rafadagalera/urbanflow/actions/workflows/azure-deploy.yml/badge.svg)](https://github.com/rafadagalera/urbanflow/actions)

**URL Pública Oficial em Produção (Azure App Service — Brazil South com HTTPS):**
- **Painel Operacional Ao Vivo:** [https://rg-urbanflow-prd-fmcjh2hkgfatbedj.brazilsouth-01.azurewebsites.net/](https://rg-urbanflow-prd-fmcjh2hkgfatbedj.brazilsouth-01.azurewebsites.net/)
- **Landing Page Executiva do Produto (Variante A):** [https://rg-urbanflow-prd-fmcjh2hkgfatbedj.brazilsouth-01.azurewebsites.net/landing?v=A](https://rg-urbanflow-prd-fmcjh2hkgfatbedj.brazilsouth-01.azurewebsites.net/landing?v=A)
- **Landing Page Executiva do Produto (Variante B):** [https://rg-urbanflow-prd-fmcjh2hkgfatbedj.brazilsouth-01.azurewebsites.net/landing?v=B](https://rg-urbanflow-prd-fmcjh2hkgfatbedj.brazilsouth-01.azurewebsites.net/landing?v=B)
- **Métricas de Conversão da Landing Page:** [https://rg-urbanflow-prd-fmcjh2hkgfatbedj.brazilsouth-01.azurewebsites.net/landing/metricas](https://rg-urbanflow-prd-fmcjh2hkgfatbedj.brazilsouth-01.azurewebsites.net/landing/metricas)
- **Healthcheck da API (LGPD Mode):** [https://rg-urbanflow-prd-fmcjh2hkgfatbedj.brazilsouth-01.azurewebsites.net/health](https://rg-urbanflow-prd-fmcjh2hkgfatbedj.brazilsouth-01.azurewebsites.net/health)

---

## Ficha Técnica do MVP (Global Solution 2026.2 — FIAP 4ESPS)

| Campo | Detalhamento Oficial |
| :--- | :--- |
| **Nome do Produto** | **UrbanFlow** (Solução tecnológica alinhada à convocação da parceira **CitizenTech**) |
| **Cidadão e Território** | Passageiros do transporte público urbano em grandes metrópoles (foco em mulheres, crianças, idosos e pessoas com deficiência/mobilidade reduzida que sofrem com espera cega e insegurança noturna) e 3 stakeholders B2B/B2G: Concessionárias de Ônibus (142 pontos), Empresas de Mídia OOH (38 painéis) e Prefeituras. |
| **Problema, em uma frase** | A assimetria de dados nos pontos de ônibus gera espera cega em abrigos superlotados, escuros e inacessíveis para o cidadão, além de ineficiência de frota para viações, falta de auditoria para mídia OOH e cegueira de fiscalização (SLA) para prefeituras. |
| **Proposta de Valor** | Transformar pontos de ônibus em abrigos inteligentes, seguros e humanizados que monitoram lotação e iluminação em tempo real para despachar ônibus extras, identificar pontos de escuridão e proteger vulneráveis à noite — com **100% de privacidade (LGPD)** usando apenas silhuetas anônimas (`<= 300 bytes`) e destruindo as imagens instantaneamente em RAM, enquanto se autofinancia via eficiência de frota e auditoria de mídia OOH. |
| **Arquitetura: Componentes** | Sensores Edge IoT nos Abrigos -> **Microsoft Azure Brazil South** (`Resource Group rg-urbanflow-prd`, `Azure App Service Linux HTTPS`, `Azure Application Insights + Log Analytics + Action Groups`) <- **CI/CD GitHub Actions** (`rafadagalera/urbanflow`). |
| **Fontes de Dados** | Telemetria JSON anônima de borda (`<= 300B`: `stop_id`, `ts`, `count`, tempo de espera, luminância/escuridão e Dwell Time OOH) e simulação determinística calibrada de 142 pontos urbanos. |
| **Modelos de IA Utilizados** | Visão Computacional na Borda (detecção anônima de silhuetas, fluxo óptico anti-fraude, medição de luminância e OCR para validação de comprovantes) + IA Generativa para relatórios e alertas operacionais. |
| **URL do MVP e Repositório** | **MVP:** https://rg-urbanflow-prd-fmcjh2hkgfatbedj.brazilsouth-01.azurewebsites.net/ · **GitHub:** https://github.com/rafadagalera/urbanflow |
| **Indicadores de Impacto** | (1) Redução do tempo médio de espera nos pontos de pico (meta SLA <= 11 min); (2) Resolução de pontos às escuras; (3) Proteção noturna a cidadãos vulneráveis; (4) Redução de até 9% em custos de frota ociosa. |
| **ODS Conectados (ONU)** | **ODS 11** (Cidades e Comunidades Sustentáveis — Meta 11.2), **ODS 9** (Indústria, Inovação e Infraestrutura), **ODS 10** (Redução das Desigualdades) e **ODS 13** (Ação Contra a Mudança Global do Clima). |

---

## Integrantes do Grupo (4ESPS)
- **Beatriz Silva Pinheiro Rocha** — RM: 553455
- **Enzzo Monteiro Barros Silva** — RM: 552616
- **Iago Diniz Fontes** — RM: 553776
- **Larissa Estella Gonçalves dos Santos** — RM: 552695
- **Rafael Alves do Nascimento** — RM: 553117
