# Notas de perfil dos dados (insumo para o PDF de Big Data)

Medido em 2026-11-18 sobre a carga real (DAG `urbancare_pipeline`, bronze + silver).

## Volumes
| Etapa | Registros |
|---|---|
| SSP 2025, linhas lidas (2 abas) | 1.161.166 |
| SSP noturnas na capital com coordenada válida (silver) | 50.999 |
| … dentro do contorno dos 96 distritos | 50.968 |
| GeoSampa pontos de ônibus (bronze) | 22.578 |
| … com distrito atribuído (silver) | 22.517 (61 fora da cidade ou duplicados) |
| GeoSampa luminárias (bronze) | 662.945 |
| … postes após deduplicar por coordenada (0,5 m) | 618.369 (média 1,07 luminária/poste, máx. 13) |

Tempos: parse do xlsx da SSP ~3 min (streaming, stdlib); silver geográfico ~6 s; DAG bronze+silver com cache ~2,5 min.

## Achados que viram limitação ou decisão
- **Hora da ocorrência ausente:** `HORA_OCORRENCIA_BO` vem NULL em 100% das linhas noturnas; só o período (`A noite`, `De madrugada`) é utilizável.
- **Datas fora de 2025:** 1.033 BOs (2%) têm data de ocorrência anterior a 2025 (mínimo 2006; 913 em 2024): BO registrado em 2025 sobre fato antigo.
- **Local:** 76% em `Via Pública`, 19,7% `Outros`, 2,3% `Terminal/Estação`.
- **Conduta:** 88% `Outros`; `Fios e Cabos` 1.739 e `Veículo` 1.327 (crimes contra patrimônio, não contra o passageiro); `Transeunte` só 1.625.
- **Coordenadas empilhadas (geocodificação/eventos):** 37.148 coordenadas distintas; 7,9% dos BOs estão em coordenadas com ≥ 20 BOs e 4,8% em coordenadas com ≥ 50.
  - Interlagos (Cidade Dutra): ~870 furtos em dois pontos, concentrados em setembro e março (festivais no autódromo), quase todos com local `Outros`.
  - Estádio do Morumbi: 291 furtos (picos em novembro e agosto, shows), 207 em `Via Pública`.
  - Largo da Batata/Pinheiros e Bela Vista: concentrações em via pública, compatíveis com risco real de rua.

## Gold (carga final de 2026-11-18: filtro + teto, escala log, faixas pelo ranking)
- Pontos no índice: 21.414 (22.517 − 920 de terminal − 183 de corredor/estação de transferência).
- Faixas pelo ranking: alta 2.142 (10%, índice 0,494–0,910), média 6.424 (30%), baixa 12.848 (60%). No corte entre alta e média há empate em 0,4939; o desempate do ranking decide.
- Top 5: R. Mourato Coelho 1022 (Pinheiros, 183 BOs a 150 m, poste a 18 m); R. Augusta 810 (Consolação, 194, 18 m); Av. Paulista 2027 (Jardim Paulista, 120, 25 m); Av. Brig. Faria Lima 447 (Pinheiros, 136, 19 m); Av. Paulista 2026 (Consolação, 113, 21 m).
- Distritos com maior índice médio: República 0,566; Bela Vista 0,558; Consolação 0,549; Sé 0,544; Barra Funda 0,527.
- Histórico das versões do índice e o porquê de cada mudança: spec §3.4 ("Como a fórmula chegou aqui"). Vale um quadro no PDF, com o top 10 de cada versão.
- Sensores simulados: 150 pontos × 1.008 leituras de lux e de lotação; 490 alertas de pessoa sozinha; 8 apagões sorteados, 4 ainda escuros na última leitura.
- DAG completo: 11 tarefas, ~2,5 min com bronze em cache (o parse da SSP é ~2 min disso).
- Limitação residual: a R. Palestra Itália 1708 (9º) fica ao lado do Allianz Parque; o teto por coordenada amortece eventos, mas não os elimina.
