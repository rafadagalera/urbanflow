-- Consultas de conferência do schema gold (usadas nos prints da entrega de Big Data).
-- Rodar: docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d urbancare' < docs/bigdata/consultas_gold.sql

\pset footer off
\echo '== 1. Linhas por tabela gold =='
SELECT 'dim_ponto' AS tabela, count(*) AS linhas FROM gold.dim_ponto
UNION ALL SELECT 'ft_indicador_ponto', count(*) FROM gold.ft_indicador_ponto
UNION ALL SELECT 'ft_resumo_distrito', count(*) FROM gold.ft_resumo_distrito
UNION ALL SELECT 'ft_evento_sensor', count(*) FROM gold.ft_evento_sensor
UNION ALL SELECT 'vw_pontos_escuros_agora', count(*) FROM gold.vw_pontos_escuros_agora
UNION ALL SELECT 'execucao', count(*) FROM gold.execucao;

\echo '== 2. Pontos por faixa de vulnerabilidade =='
SELECT faixa, count(*) AS pontos,
       round(min(indice_vulnerabilidade)::numeric, 3) AS indice_min,
       round(max(indice_vulnerabilidade)::numeric, 3) AS indice_max
FROM gold.ft_indicador_ponto
GROUP BY faixa
ORDER BY indice_max DESC;

\echo '== 3. Os 10 pontos mais vulneráveis =='
SELECT i.ranking, p.nome, p.distrito,
       round(i.indice_vulnerabilidade::numeric, 3) AS indice,
       i.ocorrencias_noturnas_150m AS ocorr_150m,
       round(i.dist_poste_m::numeric, 1) AS dist_poste_m,
       i.faixa
FROM gold.ft_indicador_ponto i
JOIN gold.dim_ponto p USING (ponto_id)
ORDER BY i.ranking
LIMIT 10;

\echo '== 4. Os 10 distritos com maior índice médio =='
SELECT distrito, subprefeitura, pontos,
       round(indice_medio::numeric, 3) AS indice_medio,
       pontos_faixa_alta, ocorrencias_noturnas
FROM gold.ft_resumo_distrito
ORDER BY indice_medio DESC
LIMIT 10;

\echo '== 5. Pontos escuros agora (sensores simulados) =='
SELECT ponto_id, nome, distrito, escuro_desde, round(lux_atual::numeric, 1) AS lux_atual
FROM gold.vw_pontos_escuros_agora
ORDER BY escuro_desde
LIMIT 8;

\echo '== 6. Últimas execuções do pipeline =='
SELECT run_id, inicio, fim, status,
       linhas_por_tabela->>'ft_indicador_ponto' AS linhas_indicador
FROM gold.execucao
ORDER BY inicio DESC
LIMIT 5;
