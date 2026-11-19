"""Execução sem Airflow: python -m urbancare_pipeline [etapa ...].

Sem argumentos roda tudo na ordem do DAG.
"""
import logging
import sys
from datetime import datetime

from . import config, etapas, extract


def _tratar_ssp():
    from . import ssp
    return ssp.tratar_ssp(config.BRONZE / "ssp/SPDadosCriminais_2025.xlsx",
                          config.SILVER / "ocorrencias_noturnas.parquet")


def _tratar_geo():
    from . import transform
    return transform.tratar_geo()


ETAPAS = {
    "pontos": extract.extrair_pontos,
    "postes": extract.extrair_postes,
    "distritos": extract.extrair_distritos,
    "ssp": extract.extrair_ssp,
    "tratar_ssp": _tratar_ssp,
    "tratar_geo": _tratar_geo,
    "indicadores": etapas.indicadores_ponto,
    "resumo": etapas.resumo_distrito,
    "sensores": etapas.simular_sensores,
    "carregar": etapas.carregar_gold,
}

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    inicio = datetime.now().astimezone()
    linhas = {}
    for nome in sys.argv[1:] or [*ETAPAS, "qualidade"]:
        if nome == "qualidade":
            print("qualidade →", etapas.checar_qualidade(f"cli__{inicio:%Y-%m-%dT%H:%M:%S}", inicio, linhas))
            continue
        r = ETAPAS[nome]()
        if nome == "carregar":
            linhas = r
        print(nome, "→", r)
