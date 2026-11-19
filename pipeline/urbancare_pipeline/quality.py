"""Checagens de qualidade sobre o gold já carregado. Falha a tarefa se algo violar."""
from __future__ import annotations

import psycopg2

from .config import DATABASE_URL

# nome → SQL que devolve a quantidade de violações (0 = ok)
CHECAGENS = {
    "dim_ponto_vazia": "SELECT (count(*) = 0)::int FROM {s}.dim_ponto",
    "indicador_vazio": "SELECT (count(*) = 0)::int FROM {s}.ft_indicador_ponto",
    "resumo_vazio": "SELECT (count(*) = 0)::int FROM {s}.ft_resumo_distrito",
    "eventos_vazios": "SELECT (count(*) = 0)::int FROM {s}.ft_evento_sensor",
    "coordenada_nula": "SELECT count(*) FROM {s}.dim_ponto WHERE lat IS NULL OR lon IS NULL "
                       "OR x_31983 IS NULL OR y_31983 IS NULL",
    "coordenada_fora_de_sp": "SELECT count(*) FROM {s}.dim_ponto "
                             "WHERE lat NOT BETWEEN -24.02 AND -23.35 OR lon NOT BETWEEN -46.83 AND -46.36",
    "indice_fora_de_0_1": "SELECT count(*) FROM {s}.ft_indicador_ponto "
                          "WHERE indice_vulnerabilidade NOT BETWEEN 0 AND 1",
    "ponto_id_duplicado": "SELECT count(*) - count(DISTINCT ponto_id) FROM {s}.dim_ponto",
    "indicador_sem_ponto_ou_ponto_sem_indicador":
        "SELECT count(*) FROM {s}.dim_ponto d FULL JOIN {s}.ft_indicador_ponto i USING (ponto_id) "
        "WHERE d.ponto_id IS NULL OR i.ponto_id IS NULL",
    "ranking_nao_sequencial": "SELECT (max(ranking) <> count(*) OR min(ranking) <> 1)::int FROM {s}.ft_indicador_ponto",
    "evento_fora_de_dim_ponto": "SELECT count(*) FROM {s}.ft_evento_sensor e "
                                "LEFT JOIN {s}.dim_ponto d USING (ponto_id) WHERE d.ponto_id IS NULL",
    "evento_nao_simulado": "SELECT count(*) FROM {s}.ft_evento_sensor WHERE NOT simulado",
    "pontos_distrito_divergente": "SELECT (SELECT sum(pontos) FROM {s}.ft_resumo_distrito) "
                                  "- (SELECT count(*) FROM {s}.dim_ponto)",
}


class QualidadeFalhou(RuntimeError):
    pass


def checar(dsn=None, schema="gold") -> dict[str, int]:
    with psycopg2.connect(dsn or DATABASE_URL) as con, con.cursor() as cur:
        res = {}
        for nome, sql in CHECAGENS.items():
            cur.execute(sql.format(s=schema))
            res[nome] = int(cur.fetchone()[0] or 0)
    con.close()
    return res


def violacoes(resultado: dict[str, int]) -> dict[str, int]:
    return {k: v for k, v in resultado.items() if v != 0}
