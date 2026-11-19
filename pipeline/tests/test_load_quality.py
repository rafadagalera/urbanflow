"""Integração com o Postgres real, num schema descartável. Pulado sem DATABASE_URL."""
import os
from datetime import datetime

import pandas as pd
import psycopg2
import pytest

from urbancare_pipeline import gold, load, quality, sensores

DSN = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="sem DATABASE_URL")
S = "gold_teste"


@pytest.fixture
def tabelas():
    dim = pd.DataFrame({
        "ponto_id": [f"p{i}" for i in range(5)], "nome": "R X", "endereco": "", "distrito": ["A", "A", "B", "B", "B"],
        "subprefeitura": "S", "x_31983": [0.0, 500, 1000, 1500, 2000], "y_31983": 0.0,
        "lat": -23.5, "lon": -46.6,
    })
    postes = pd.DataFrame({"x_31983": [500.0], "y_31983": [0.0]})
    oc = pd.DataFrame({"x_31983": [0.0, 10], "y_31983": [0.0, 0], "data_ocorrencia": pd.to_datetime(["2025-01-01"] * 2),
                       "tipo_local": "Via Pública", "conduta": "Outros", "categoria": "roubo", "transeunte": False,
                       "distrito": "A"})
    ind = gold.indicadores_ponto(dim, postes, oc)
    return {
        "dim_ponto": dim, "ft_indicador_ponto": ind,
        "ft_resumo_distrito": gold.resumo_distrito(dim, ind, oc),
        "ft_evento_sensor": sensores.simular(ind, datetime(2026, 11, 18)),
    }


@pytest.fixture(autouse=True)
def limpa():
    yield
    with psycopg2.connect(DSN) as c, c.cursor() as cur:
        cur.execute(f"DROP SCHEMA IF EXISTS {S} CASCADE")


def test_carga_qualidade_e_view(tabelas):
    linhas = load.carregar(tabelas, DSN, S)
    assert linhas["dim_ponto"] == 5
    assert quality.violacoes(quality.checar(DSN, S)) == {}
    with psycopg2.connect(DSN) as c, c.cursor() as cur:
        cur.execute(f"SELECT count(*), min(escuro_desde) IS NOT NULL FROM {S}.vw_pontos_escuros_agora")
        n, tem_desde = cur.fetchone()
    assert n >= 1 and tem_desde  # 5 pontos → 1 apagão sorteado, e ele persiste até o fim
    load.registrar_execucao("teste", None, None, linhas, "ok", dsn=DSN, schema=S)
    load.carregar(tabelas, DSN, S)  # recarga substitui sem erro e preserva execucao
    with psycopg2.connect(DSN) as c, c.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {S}.execucao")
        assert cur.fetchone()[0] == 1


def test_qualidade_detecta_violacao(tabelas):
    load.carregar(tabelas, DSN, S)
    with psycopg2.connect(DSN) as c, c.cursor() as cur:
        cur.execute(f"UPDATE {S}.dim_ponto SET lat = -10 WHERE ponto_id = 'p0'")
        cur.execute(f"DELETE FROM {S}.ft_resumo_distrito WHERE distrito = 'B'")
    ruins = quality.violacoes(quality.checar(DSN, S))
    assert set(ruins) == {"coordenada_fora_de_sp", "pontos_distrito_divergente"}


def test_carga_atomica(tabelas):
    load.carregar(tabelas, DSN, S)
    ruim = dict(tabelas)
    ruim["ft_indicador_ponto"] = tabelas["ft_indicador_ponto"].assign(faixa="invalida")
    with pytest.raises(psycopg2.Error):
        load.carregar(ruim, DSN, S)
    with psycopg2.connect(DSN) as c, c.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {S}.ft_indicador_ponto")
        assert cur.fetchone()[0] == 5  # a carga anterior continua intacta
