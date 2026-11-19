"""UrbanCare: GeoSampa + SSP-SP → bronze → silver → gold (Postgres).

A lógica fica no pacote urbancare_pipeline; as tarefas só chamam funções,
então o mesmo fluxo roda sem Airflow (python -m urbancare_pipeline).
"""
from datetime import datetime, timedelta

from airflow.decorators import dag, task

PADRAO = {
    "owner": "urbancare",
    "retries": 2,
    "retry_delay": timedelta(minutes=3),
}


@dag(
    dag_id="urbancare_pipeline",
    schedule="@daily",
    start_date=datetime(2026, 11, 1),
    catchup=False,
    max_active_runs=1,
    default_args=PADRAO,
    tags=["urbancare", "bigdata"],
    doc_md=__doc__,
)
def urbancare_pipeline():
    # ---------- Bronze: fontes abertas, com cache e retomada ----------
    @task(retries=4, retry_delay=timedelta(minutes=5))
    def extrair_pontos():
        from urbancare_pipeline import extract
        return extract.extrair_pontos()

    @task(retries=4, retry_delay=timedelta(minutes=5))
    def extrair_postes():
        from urbancare_pipeline import extract
        return extract.extrair_postes()

    @task(retries=4, retry_delay=timedelta(minutes=5))
    def extrair_distritos():
        from urbancare_pipeline import extract
        return extract.extrair_distritos()

    @task(retries=4, retry_delay=timedelta(minutes=5))
    def extrair_ssp():
        from urbancare_pipeline import extract
        return extract.extrair_ssp()

    # ---------- Silver ----------
    @task
    def tratar_ssp():
        from urbancare_pipeline import config, ssp
        return ssp.tratar_ssp(config.BRONZE / "ssp/SPDadosCriminais_2025.xlsx",
                              config.SILVER / "ocorrencias_noturnas.parquet")

    @task
    def tratar_geo():
        from urbancare_pipeline import transform
        return transform.tratar_geo()

    # ---------- Gold ----------
    @task
    def indicadores_ponto():
        from urbancare_pipeline import etapas
        return etapas.indicadores_ponto()

    @task
    def resumo_distrito():
        from urbancare_pipeline import etapas
        return etapas.resumo_distrito()

    @task
    def simular_sensores(data_interval_end=None):
        # Janela de 7 dias terminando no fim do intervalo (meia-noite em SP):
        # a mesma data gera sempre os mesmos eventos.
        from urbancare_pipeline import etapas
        return etapas.simular_sensores(data_interval_end)

    # ---------- Carga e qualidade ----------
    @task
    def carregar_gold():
        from urbancare_pipeline import etapas
        return etapas.carregar_gold()

    @task(retries=0)
    def checar_qualidade(linhas: dict, run_id=None, dag_run=None):
        from urbancare_pipeline import etapas
        return etapas.checar_qualidade(run_id, dag_run.start_date if dag_run else None, linhas)

    bronze_geo = [extrair_pontos(), extrair_postes(), extrair_distritos()]
    silver_ssp = tratar_ssp()
    extrair_ssp() >> silver_ssp
    silver_geo = tratar_geo()
    bronze_geo >> silver_geo
    silver_ssp >> silver_geo

    ind = indicadores_ponto()
    silver_geo >> ind
    carga = carregar_gold()
    ind >> [resumo_distrito(), simular_sensores()] >> carga
    checar_qualidade(carga)


urbancare_pipeline()
