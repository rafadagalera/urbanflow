"""Etapas gold/carga/qualidade com caminhos padrão: usadas pelo DAG e pela CLI."""
from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd

from . import gold, load, quality, sensores
from .config import DATA_DIR, SILVER

log = logging.getLogger(__name__)
GOLD = DATA_DIR / "gold"


def _grava(df, nome):
    GOLD.mkdir(parents=True, exist_ok=True)
    destino = GOLD / f"{nome}.parquet"
    tmp = destino.with_suffix(".tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(destino)
    return len(df)


def _le(nome):
    return pd.read_parquet(GOLD / f"{nome}.parquet")


def indicadores_ponto() -> dict:
    todos = pd.read_parquet(SILVER / "pontos.parquet")
    pontos = gold.remover_fora_de_escopo(todos)
    ind = gold.indicadores_ponto(pontos, pd.read_parquet(SILVER / "postes.parquet"),
                                 pd.read_parquet(SILVER / "ocorrencias_geo.parquet"))
    out = {"dim_ponto": _grava(pontos, "dim_ponto"), "ft_indicador_ponto": _grava(ind, "ft_indicador_ponto")}
    out["fora_de_escopo"] = len(todos) - len(pontos)
    out["faixas"] = ind["faixa"].value_counts().to_dict()
    log.info("indicadores: %s", out)
    return out


def resumo_distrito() -> dict:
    r = gold.resumo_distrito(_le("dim_ponto"), _le("ft_indicador_ponto"),
                             pd.read_parquet(SILVER / "ocorrencias_geo.parquet"))
    return {"ft_resumo_distrito": _grava(r, "ft_resumo_distrito")}


def simular_sensores(fim: datetime | None = None) -> dict:
    """`fim` = fim da janela; padrão é a meia-noite de hoje (SP), para a última leitura cair à noite."""
    if fim is None:
        fim = pd.Timestamp.now(tz=sensores.FUSO).normalize().to_pydatetime()
    ev = sensores.simular(_le("ft_indicador_ponto"), fim)
    out = {"ft_evento_sensor": _grava(ev, "ft_evento_sensor")}
    out["por_tipo"] = ev["tipo"].value_counts().to_dict()
    return out


def carregar_gold() -> dict:
    return load.carregar({t: _le(t) for t in load.ORDEM})


def checar_qualidade(run_id: str, inicio=None, linhas: dict | None = None) -> dict:
    res = quality.checar()
    ruins = quality.violacoes(res)
    status = "falha" if ruins else "ok"
    load.registrar_execucao(run_id, inicio, datetime.now().astimezone(), linhas or {}, status,
                            {"checagens": res})
    if ruins:
        raise quality.QualidadeFalhou(f"checagens violadas: {ruins}")
    return res
