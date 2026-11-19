"""Carga do gold no Postgres: substitui as tabelas numa única transação."""
from __future__ import annotations

import io
import json

import pandas as pd
import psycopg2

from .config import DATABASE_URL

DDL = """
DROP TABLE IF EXISTS {s}.ft_evento_sensor, {s}.ft_indicador_ponto, {s}.ft_resumo_distrito, {s}.dim_ponto CASCADE;

CREATE TABLE {s}.dim_ponto (
  ponto_id      text PRIMARY KEY,
  nome          text NOT NULL,
  endereco      text,
  distrito      text NOT NULL,
  subprefeitura text,
  x_31983       double precision NOT NULL,
  y_31983       double precision NOT NULL,
  lat           double precision NOT NULL,
  lon           double precision NOT NULL
);
CREATE TABLE {s}.ft_indicador_ponto (
  ponto_id                  text PRIMARY KEY REFERENCES {s}.dim_ponto,
  postes_30m                integer NOT NULL,
  dist_poste_m              double precision NOT NULL,
  ocorrencias_noturnas_150m integer NOT NULL,
  roubos_transeunte_150m    integer NOT NULL,
  indice_vulnerabilidade    numeric(5,4) NOT NULL,
  faixa                     text NOT NULL CHECK (faixa IN ('alta','media','baixa')),
  ranking                   integer NOT NULL UNIQUE
);
CREATE TABLE {s}.ft_resumo_distrito (
  distrito             text PRIMARY KEY,
  subprefeitura        text,
  pontos               integer NOT NULL,
  indice_medio         numeric(5,4) NOT NULL,
  pontos_faixa_alta    integer NOT NULL,
  ocorrencias_noturnas integer NOT NULL
);
CREATE TABLE {s}.ft_evento_sensor (
  ponto_id text NOT NULL REFERENCES {s}.dim_ponto,
  ts       timestamptz NOT NULL,
  tipo     text NOT NULL CHECK (tipo IN ('lux','lotacao','pessoa_sozinha_noite')),
  valor    double precision NOT NULL,
  simulado boolean NOT NULL DEFAULT true
);
CREATE INDEX ON {s}.ft_evento_sensor (ponto_id, tipo, ts);
CREATE INDEX ON {s}.dim_ponto (distrito);

CREATE VIEW {s}.vw_pontos_escuros_agora AS
WITH lux AS (
  SELECT ponto_id, ts, valor,
         max(ts) OVER (PARTITION BY ponto_id) AS ultima,
         max(ts) FILTER (WHERE valor >= 10) OVER (PARTITION BY ponto_id) AS ultima_clara
  FROM {s}.ft_evento_sensor WHERE tipo = 'lux'
)
SELECT l.ponto_id, d.nome, d.distrito,
       (SELECT min(ts) FROM lux x WHERE x.ponto_id = l.ponto_id
          AND x.ts > coalesce(l.ultima_clara, '-infinity')) AS escuro_desde,
       l.valor AS lux_atual
FROM lux l JOIN {s}.dim_ponto d USING (ponto_id)
WHERE l.ts = l.ultima AND l.valor < 10;

CREATE TABLE IF NOT EXISTS {s}.execucao (
  run_id            text PRIMARY KEY,
  inicio            timestamptz,
  fim               timestamptz,
  linhas_por_tabela jsonb,
  status            text NOT NULL,
  detalhes          jsonb
);
"""

ORDEM = ["dim_ponto", "ft_indicador_ponto", "ft_resumo_distrito", "ft_evento_sensor"]


def _copy(cur, schema, tabela, df: pd.DataFrame):
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False, na_rep="\\N")
    buf.seek(0)
    cols = ", ".join(df.columns)
    cur.copy_expert(f"COPY {schema}.{tabela} ({cols}) FROM STDIN WITH (FORMAT csv, NULL '\\N')", buf)


def carregar(tabelas: dict[str, pd.DataFrame], dsn=None, schema="gold") -> dict[str, int]:
    """Recria as tabelas e carrega tudo em uma transação (ou nada muda)."""
    with psycopg2.connect(dsn or DATABASE_URL) as con, con.cursor() as cur:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        cur.execute(DDL.format(s=schema))
        for t in ORDEM:
            _copy(cur, schema, t, tabelas[t])
    con.close()
    return {t: len(tabelas[t]) for t in ORDEM}


def registrar_execucao(run_id, inicio, fim, linhas, status, detalhes=None, dsn=None, schema="gold"):
    with psycopg2.connect(dsn or DATABASE_URL) as con, con.cursor() as cur:
        cur.execute(
            f"""INSERT INTO {schema}.execucao (run_id, inicio, fim, linhas_por_tabela, status, detalhes)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (run_id) DO UPDATE SET inicio = EXCLUDED.inicio, fim = EXCLUDED.fim,
                  linhas_por_tabela = EXCLUDED.linhas_por_tabela, status = EXCLUDED.status,
                  detalhes = EXCLUDED.detalhes""",
            (run_id, inicio, fim, json.dumps(linhas), status, json.dumps(detalhes or {}, ensure_ascii=False)))
    con.close()
