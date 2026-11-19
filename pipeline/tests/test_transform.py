import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from urbancare_pipeline import transform

# Dois "distritos" quadrados de 1 km lado a lado, numa região qualquer de SP (EPSG:31983).
X0, Y0 = 330_000, 7_390_000


@pytest.fixture
def distritos():
    return gpd.GeoDataFrame(
        {"distrito": ["A", "B"], "subprefeitura": ["SA", "SB"]},
        geometry=[box(X0, Y0, X0 + 1000, Y0 + 1000), box(X0 + 1000, Y0, X0 + 2000, Y0 + 1000)],
        crs=transform.SRS,
    )


def _pontos(linhas):
    return pd.DataFrame(linhas, columns=["cd_identificador_ponto_onibus", "nm_ponto_onibus",
                                         "tx_endereco_ponto_onibus", "ge_ponto"])


def test_pontos_distrito_tolerancia_e_descartes(distritos):
    df = _pontos([
        ["1", " AV.  PAULISTA , 100 ", "R A/ R B", f"POINT ({X0+500} {Y0+500})"],   # dentro de A
        ["2", "", "R C/ R D", f"POINT ({X0+1500} {Y0+500})"],                     # dentro de B, sem nome
        ["3", "Divisa", "", f"POINT ({X0+2100} {Y0+500})"],                       # 100 m fora → B
        ["4", "Longe", "", f"POINT ({X0+5000} {Y0+500})"],                        # 3 km fora → sai
        ["1", "Duplicado", "", f"POINT ({X0+10} {Y0+10})"],                       # id repetido → sai
    ])
    p = transform.tratar_pontos(df, distritos)
    assert list(p["ponto_id"]) == ["1", "2", "3"]
    assert list(p["distrito"]) == ["A", "B", "B"] and list(p["subprefeitura"]) == ["SA", "SB", "SB"]
    assert p.loc[0, "nome"] == "AV. PAULISTA , 100"
    assert p.loc[1, "nome"] == "R C/ R D"  # sem nome usa o endereço
    assert p["lat"].between(-24.1, -23.3).all() and p["lon"].between(-46.9, -46.3).all()


def test_postes_deduplicados_por_coordenada():
    wkt = pd.Series([
        "POINT (100.0 200.0)", "POINT (100.0 200.0)", "POINT (100.1 200.1)",  # mesmo poste
        "POINT (130 200)", None,
    ])
    p = transform.tratar_postes(wkt)
    assert len(p) == 2
    assert sorted(p["luminarias"]) == [1, 3]


def test_ocorrencias_recortadas_pelo_contorno(distritos):
    centro = gpd.GeoSeries.from_xy([X0 + 500], [Y0 + 500], crs=transform.SRS).to_crs("EPSG:4326")
    fora = gpd.GeoSeries.from_xy([X0 + 3000], [Y0 + 500], crs=transform.SRS).to_crs("EPSG:4326")
    oc = pd.DataFrame({"lat": [centro.y[0], fora.y[0]], "lon": [centro.x[0], fora.x[0]], "categoria": ["roubo", "furto"]})
    r = transform.tratar_ocorrencias(oc, distritos)
    assert len(r) == 1 and r.loc[0, "distrito"] == "A"
    assert r.loc[0, "x_31983"] == pytest.approx(X0 + 500, abs=0.05)
