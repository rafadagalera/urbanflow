import numpy as np
import pandas as pd
import pytest

from urbancare_pipeline import gold


def oc(x, y, n=1, ano=2025, tipo_local="Via Pública", conduta="Outros", categoria="furto", transeunte=False, distrito="A"):
    return pd.DataFrame({
        "x_31983": [float(x)] * n, "y_31983": [float(y)] * n,
        "data_ocorrencia": pd.to_datetime([f"{ano}-06-01"] * n), "tipo_local": tipo_local,
        "conduta": conduta, "categoria": categoria, "transeunte": transeunte, "distrito": distrito,
    })


def test_filtro_ano_local_conduta():
    df = pd.concat([
        oc(0, 0), oc(0, 0, ano=2024), oc(0, 0, tipo_local="Outros"),
        oc(0, 0, conduta="Fios e Cabos"), oc(0, 0, conduta="Veículo"), oc(0, 0, conduta="Transeunte"),
    ], ignore_index=True)
    r = gold.filtrar_relevantes(df)
    assert list(r["conduta"]) == ["Outros", "Transeunte"]


def test_teto_por_coordenada():
    df = pd.concat([oc(0, 0, n=400), oc(50, 0, n=3)], ignore_index=True)
    xy, peso = gold.pesos_com_teto(df)
    assert sorted(peso) == [3, gold.TETO_POR_COORDENADA]


def test_contagem_no_raio_limites():
    alvo = np.array([[0.0, 0.0]])
    fontes = np.array([[29.9, 0], [30.1, 0], [0, 149.9], [0, 150.1]])
    assert gold.contar_no_raio(alvo, fontes, 30)[0] == 1
    assert gold.contar_no_raio(alvo, fontes, 150)[0] == 3
    assert gold.contar_no_raio(alvo, fontes, 150, pesos=np.array([1, 1, 10, 5.0]))[0] == 12
    assert gold.contar_no_raio(alvo, np.empty((0, 2)), 150)[0] == 0


def test_percentil_empates_no_menor_posto():
    p = gold.percentil(pd.Series([0, 0, 0, 5, 10]))
    assert list(p) == [0, 0, 0, 0.75, 1.0]


def test_faixas_pelo_ranking():
    f = gold.faixa_por_ranking(pd.Series(range(1, 101)))
    assert f.value_counts().to_dict() == {"alta": 10, "media": 30, "baixa": 60}
    assert f[9] == "alta" and f[10] == "media" and f[39] == "media" and f[40] == "baixa"


def test_escala_log_nao_satura():
    e = gold.escala_log(pd.Series([0, 65, 194]))
    assert e[0] == 0 and e[2] == 1 and 0.75 < e[1] < 0.85  # percentil daria 0,5 e 1, empatando o topo
    assert list(gold.escala_log(pd.Series([0, 0]))) == [0, 0]


def test_indicadores_ponto_ordem_e_formula():
    pontos = pd.DataFrame({"ponto_id": ["escuro_perigoso", "claro_seguro", "medio"],
                           "x_31983": [0.0, 10_000.0, 20_000.0], "y_31983": [0.0, 0.0, 0.0]})
    postes = pd.DataFrame({"x_31983": [10_000.0, 10_005.0, 20_000.0], "y_31983": [0.0, 0.0, 0.0]})
    ocs = pd.concat([oc(10, 0, n=50), oc(20_050, 0, n=2),
                     oc(0, 100, n=3, categoria="roubo", transeunte=True, conduta="Transeunte")], ignore_index=True)
    r = gold.indicadores_ponto(pontos, postes, ocs).set_index("ponto_id")
    assert r.loc["escuro_perigoso", "ocorrencias_noturnas_150m"] == gold.TETO_POR_COORDENADA + 3
    assert r.loc["escuro_perigoso", "roubos_transeunte_150m"] == 3
    assert r.loc["claro_seguro", "postes_30m"] == 2
    assert r.loc["escuro_perigoso", "dist_poste_m"] == 10_000.0 and r.loc["medio", "dist_poste_m"] == 0.0
    # escuro_perigoso: pct(oc)=1, pct(postes)=0 → 0,6 + 0,4 = 1
    assert r.loc["escuro_perigoso", "indice_vulnerabilidade"] == 1.0
    assert r.loc["escuro_perigoso", "faixa"] == "alta" and r.loc["escuro_perigoso", "ranking"] == 1
    assert r.loc["claro_seguro", "indice_vulnerabilidade"] == 0.0
    assert sorted(r["ranking"]) == [1, 2, 3]


def test_resumo_distrito():
    pontos = pd.DataFrame({"ponto_id": ["1", "2", "3"], "distrito": ["A", "A", "B"], "subprefeitura": ["S", "S", "T"]})
    ind = pd.DataFrame({"ponto_id": ["1", "2", "3"], "indice_vulnerabilidade": [0.8, 0.4, 0.1],
                        "faixa": ["alta", "baixa", "baixa"]})
    ocs = pd.concat([oc(0, 0, n=4, distrito="A"), oc(0, 0, n=2, distrito="A", ano=2024)], ignore_index=True)
    r = gold.resumo_distrito(pontos, ind, ocs).set_index("distrito")
    assert r.loc["A", "pontos"] == 2 and r.loc["A", "indice_medio"] == pytest.approx(0.6)
    assert r.loc["A", "pontos_faixa_alta"] == 1 and r.loc["A", "ocorrencias_noturnas"] == 4
    assert r.loc["B", "ocorrencias_noturnas"] == 0


def test_remove_terminais_e_corredores():
    p = pd.DataFrame({"nome": ["TERM. SANTANA , 0", "TERMINAL PQ. D. PEDRO II", " term. lapa", "R. TERMINAL , 10",
                               "AV. PAULISTA , 1754", "TERMOPILAS , 3", "M01 CARANDIRU - SANTANA , 3173",
                               "C09 SANTO AMARO , 1", "E. T. VÍTOR MANZINI , 274", "R. M01 , 5", "AV. B12-A , 3"]})
    assert list(gold.remover_fora_de_escopo(p)["nome"]) == [
        "R. TERMINAL , 10", "AV. PAULISTA , 1754", "TERMOPILAS , 3", "R. M01 , 5", "AV. B12-A , 3"]


def test_escuridao_continua_sem_degrau():
    # postes_30m salta de 1 para 0 entre 29 m e 31 m; a escuridão só segue a ordem das distâncias
    pontos = pd.DataFrame({"ponto_id": ["a", "b", "c"], "x_31983": [0.0, 1000, 2000], "y_31983": 0.0})
    postes = pd.DataFrame({"x_31983": [29.0, 1031, 2005], "y_31983": 0.0})
    r = gold.indicadores_ponto(pontos, postes, oc(9e6, 9e6).iloc[:0]).set_index("ponto_id")
    assert (r.loc["a", "postes_30m"], r.loc["b", "postes_30m"]) == (1, 0)
    assert r.loc["b", "indice_vulnerabilidade"] == 0.4 and r.loc["a", "indice_vulnerabilidade"] == 0.2
    assert r.loc["c", "indice_vulnerabilidade"] == 0.0
