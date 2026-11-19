"""Silver geográfico: pontos de ônibus, postes e ocorrências em EPSG:31983.

- pontos: chave, nome, endereço, distrito/subprefeitura por junção espacial,
  coordenadas métricas (31983) e geográficas (WGS84);
- postes: um registro por coordenada (o cadastro tem uma linha por luminária,
  várias no mesmo poste);
- ocorrências: reprojetadas e recortadas pelo contorno real dos distritos.
"""
from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from .config import BRONZE, SILVER

log = logging.getLogger(__name__)

SRS = "EPSG:31983"
TOLERANCIA_DISTRITO_M = 200  # ponto a até 200 m de um distrito (ex.: na divisa) recebe o mais próximo
PRECISAO_POSTE_M = 0.5       # luminárias a menos de 0,5 m são o mesmo poste


def carregar_distritos(distritos_geojson, subpref_geojson) -> gpd.GeoDataFrame:
    d = gpd.read_file(distritos_geojson).to_crs(SRS)
    s = gpd.read_file(subpref_geojson)[["cd_identificador_subprefeitura", "nm_subprefeitura"]]
    d = d.merge(s, on="cd_identificador_subprefeitura", how="left")
    return d.rename(columns={"nm_distrito_municipal": "distrito", "nm_subprefeitura": "subprefeitura"})[
        ["distrito", "subprefeitura", "geometry"]]


def atribuir_distrito(g: gpd.GeoDataFrame, distritos: gpd.GeoDataFrame,
                      tolerancia=TOLERANCIA_DISTRITO_M) -> gpd.GeoDataFrame:
    """Junta distrito/subprefeitura; quem cai fora de todos e além da tolerância é descartado."""
    base = g.reset_index(drop=True)
    j = gpd.sjoin(base, distritos, how="left", predicate="within").drop(columns="index_right")
    j = j[~j.index.duplicated(keep="first")]  # ponto exatamente na divisa entra em um só
    fora = j["distrito"].isna()
    if fora.any() and tolerancia:
        perto = gpd.sjoin_nearest(base.loc[fora[fora].index], distritos, how="left", max_distance=tolerancia)
        perto = perto[~perto.index.duplicated(keep="first")]
        j.loc[perto.index, ["distrito", "subprefeitura"]] = perto[["distrito", "subprefeitura"]].values
    return j[j["distrito"].notna()].reset_index(drop=True)


def _limpa(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.strip().str.replace(r"\s+", " ", regex=True)


def tratar_pontos(df: pd.DataFrame, distritos: gpd.GeoDataFrame) -> pd.DataFrame:
    g = gpd.GeoDataFrame(
        {
            "ponto_id": df["cd_identificador_ponto_onibus"].astype(str).str.strip(),
            "nome": _limpa(df["nm_ponto_onibus"]),
            "endereco": _limpa(df["tx_endereco_ponto_onibus"]),
        },
        geometry=shapely.from_wkt(df["ge_ponto"].values), crs=SRS,
    )
    g = g[~g.geometry.is_empty & g.geometry.notna()].drop_duplicates("ponto_id")
    g["nome"] = g["nome"].where(g["nome"] != "", g["endereco"])
    g = atribuir_distrito(g, distritos)
    wgs = g.geometry.to_crs("EPSG:4326")
    return pd.DataFrame({
        "ponto_id": g["ponto_id"], "nome": g["nome"], "endereco": g["endereco"],
        "distrito": g["distrito"], "subprefeitura": g["subprefeitura"],
        "x_31983": g.geometry.x.round(2), "y_31983": g.geometry.y.round(2),
        "lat": wgs.y.round(7), "lon": wgs.x.round(7),
    }).sort_values("ponto_id", ignore_index=True)


def tratar_postes(geometria_wkt: pd.Series) -> pd.DataFrame:
    pts = shapely.from_wkt(geometria_wkt.dropna().values)
    xy = shapely.get_coordinates(pts)
    chave = np.round(xy / PRECISAO_POSTE_M).astype(np.int64)
    df = pd.DataFrame({"kx": chave[:, 0], "ky": chave[:, 1], "x_31983": xy[:, 0], "y_31983": xy[:, 1]})
    out = df.groupby(["kx", "ky"], sort=True).agg(
        x_31983=("x_31983", "first"), y_31983=("y_31983", "first"), luminarias=("x_31983", "size"))
    return out.reset_index(drop=True).round({"x_31983": 2, "y_31983": 2})


def tratar_ocorrencias(oc: pd.DataFrame, distritos: gpd.GeoDataFrame) -> pd.DataFrame:
    g = gpd.GeoDataFrame(oc, geometry=gpd.points_from_xy(oc["lon"], oc["lat"]), crs="EPSG:4326").to_crs(SRS)
    g = atribuir_distrito(g, distritos, tolerancia=0)  # BO fora do contorno da cidade sai
    g["x_31983"], g["y_31983"] = g.geometry.x.round(2), g.geometry.y.round(2)
    return pd.DataFrame(g.drop(columns="geometry"))


def _grava(df: pd.DataFrame, destino: Path):
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(destino)


def tratar_geo(bronze=BRONZE, silver=SILVER) -> dict:
    distritos = carregar_distritos(bronze / "geosampa/distritos.geojson", bronze / "geosampa/subprefeituras.geojson")
    bruto_pontos = pd.read_csv(bronze / "geosampa/ponto_onibus.csv", dtype=str)
    pontos = tratar_pontos(bruto_pontos, distritos)
    bruto_postes = pd.read_csv(bronze / "geosampa/iluminacao_publica.csv", dtype=str, usecols=["ge_ponto"])
    postes = tratar_postes(bruto_postes["ge_ponto"])
    oc_bruto = pd.read_parquet(silver / "ocorrencias_noturnas.parquet")
    oc = tratar_ocorrencias(oc_bruto, distritos)
    _grava(pontos, silver / "pontos.parquet")
    _grava(postes, silver / "postes.parquet")
    _grava(oc, silver / "ocorrencias_geo.parquet")
    cont = {
        "pontos_bronze": len(bruto_pontos), "pontos": len(pontos),
        "luminarias": len(bruto_postes), "postes": len(postes),
        "ocorrencias_silver": len(oc_bruto), "ocorrencias_na_cidade": len(oc),
        "distritos": len(distritos),
    }
    log.info("tratar_geo: %s", cont)
    return cont
