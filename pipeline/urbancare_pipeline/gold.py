"""Gold: indicadores por ponto de ônibus e resumo por distrito (spec §3.4)."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

# Parâmetros do índice (justificativa na spec §3.4 e no PDF).
RAIO_POSTE_M = 30.0
RAIO_OCORRENCIA_M = 150.0
PESO_OCORRENCIAS = 0.6
PESO_ESCURIDAO = 0.4
# Faixas pelo ranking: alta = 10% mais vulneráveis; média = os 30% seguintes.
FRACAO_ALTA = 0.10
FRACAO_MEDIA = 0.30
ANO_REFERENCIA = 2025
TIPO_LOCAL_RELEVANTE = "Via Pública"
CONDUTAS_PATRIMONIO = frozenset({"Fios e Cabos", "Veículo", "Interior de Veículo", "Carga"})
TETO_POR_COORDENADA = 10
# Paradas de terminal ("TERM.") e de corredor/estação de transferência ("M01 ...",
# "C09 ...", "E. T. ..."): fora do escopo do abrigo de rua. Têm luz própria da
# SPTrans, ausente do cadastro de postes, e várias plataformas por local.
PADRAO_FORA_DE_ESCOPO = r"^\s*(?:TERM\.|TERMINAL\b|[A-Z]\d{2}\s|E\.\s?T\.)"

COLUNAS_INDICADOR = ["ponto_id", "postes_30m", "dist_poste_m", "ocorrencias_noturnas_150m", "roubos_transeunte_150m",
                     "indice_vulnerabilidade", "faixa", "ranking"]


def remover_fora_de_escopo(pontos: pd.DataFrame) -> pd.DataFrame:
    fora = pontos["nome"].str.upper().str.contains(PADRAO_FORA_DE_ESCOPO, regex=True)
    return pontos[~fora].reset_index(drop=True)


def escala_log(s: pd.Series) -> pd.Series:
    """log(1+x)/log(1+max): em [0, 1] e, ao contrário do percentil, não satura no topo."""
    m = s.max()
    if not m or m <= 0:
        return pd.Series(np.zeros(len(s)), index=s.index)
    return np.log1p(s) / np.log1p(m)


def distancia_mais_proximo(alvos_xy: np.ndarray, fontes_xy: np.ndarray) -> np.ndarray:
    if len(fontes_xy) == 0:
        return np.full(len(alvos_xy), np.inf)
    d, _ = cKDTree(fontes_xy).query(alvos_xy)
    return d


def filtrar_relevantes(oc: pd.DataFrame) -> pd.DataFrame:
    """BOs que contam no índice: 2025, via pública, sem crimes contra patrimônio."""
    m = (
        (pd.to_datetime(oc["data_ocorrencia"]).dt.year == ANO_REFERENCIA)
        & (oc["tipo_local"] == TIPO_LOCAL_RELEVANTE)
        & ~oc["conduta"].isin(CONDUTAS_PATRIMONIO)
    )
    return oc[m]


def pesos_com_teto(oc: pd.DataFrame, teto=TETO_POR_COORDENADA) -> tuple[np.ndarray, np.ndarray]:
    """Agrupa por coordenada exata; cada coordenada pesa min(n, teto). Devolve (xy, peso)."""
    if oc.empty:
        return np.empty((0, 2)), np.empty(0)
    g = oc.groupby(["x_31983", "y_31983"]).size()
    xy = np.array(g.index.tolist(), dtype=float)
    return xy, np.minimum(g.to_numpy(), teto).astype(float)


def contar_no_raio(alvos_xy: np.ndarray, fontes_xy: np.ndarray, raio: float,
                   pesos: np.ndarray | None = None) -> np.ndarray:
    """Para cada alvo, soma dos pesos (ou contagem) das fontes a até `raio` metros."""
    if len(fontes_xy) == 0:
        return np.zeros(len(alvos_xy))
    arvore = cKDTree(fontes_xy)
    if pesos is None:
        return arvore.query_ball_point(alvos_xy, r=raio, return_length=True).astype(float)
    vizinhos = arvore.query_ball_point(alvos_xy, r=raio)
    return np.array([pesos[v].sum() if v else 0.0 for v in vizinhos])


def percentil(s: pd.Series) -> pd.Series:
    """Rank normalizado em [0, 1]; empates recebem o menor posto (zeros ficam em 0)."""
    n = len(s)
    if n <= 1:
        return pd.Series(np.zeros(n), index=s.index)
    return (s.rank(method="min") - 1) / (n - 1)


def faixa_por_ranking(ranking: pd.Series) -> pd.Series:
    n = len(ranking)
    corte_alta = int(np.ceil(FRACAO_ALTA * n))
    corte_media = int(np.ceil((FRACAO_ALTA + FRACAO_MEDIA) * n))
    return pd.Series(np.select([ranking <= corte_alta, ranking <= corte_media], ["alta", "media"], "baixa"),
                     index=ranking.index)


def indicadores_ponto(pontos: pd.DataFrame, postes: pd.DataFrame, ocorrencias: pd.DataFrame) -> pd.DataFrame:
    alvos = pontos[["x_31983", "y_31983"]].to_numpy(float)
    rel = filtrar_relevantes(ocorrencias)
    xy, peso = pesos_com_teto(rel)
    xy_rt, peso_rt = pesos_com_teto(rel[(rel["categoria"] == "roubo") & rel["transeunte"]])
    postes_xy = postes[["x_31983", "y_31983"]].to_numpy(float)
    df = pd.DataFrame({
        "ponto_id": pontos["ponto_id"].to_numpy(),
        "postes_30m": contar_no_raio(alvos, postes_xy, RAIO_POSTE_M).astype(int),
        "dist_poste_m": distancia_mais_proximo(alvos, postes_xy).round(1),
        "ocorrencias_noturnas_150m": contar_no_raio(alvos, xy, RAIO_OCORRENCIA_M, peso).astype(int),
        "roubos_transeunte_150m": contar_no_raio(alvos, xy_rt, RAIO_OCORRENCIA_M, peso_rt).astype(int),
    })
    # Ocorrências em escala log (não satura no topo); escuridão = percentil da
    # distância ao poste mais próximo (sem o degrau de "0 ou 1 poste a 30 m").
    df["indice_vulnerabilidade"] = (
        PESO_OCORRENCIAS * escala_log(df["ocorrencias_noturnas_150m"])
        + PESO_ESCURIDAO * percentil(df["dist_poste_m"])
    ).round(4)
    # Ranking único: índice, depois mais ocorrências, depois poste mais distante, depois id (estável).
    ordem = df.sort_values(
        ["indice_vulnerabilidade", "ocorrencias_noturnas_150m", "dist_poste_m", "ponto_id"],
        ascending=[False, False, False, True], kind="mergesort").index
    df.loc[ordem, "ranking"] = np.arange(1, len(df) + 1)
    df["ranking"] = df["ranking"].astype(int)
    df["faixa"] = faixa_por_ranking(df["ranking"])
    return df[COLUNAS_INDICADOR].sort_values("ranking", ignore_index=True)


def resumo_distrito(pontos: pd.DataFrame, indicadores: pd.DataFrame, ocorrencias: pd.DataFrame) -> pd.DataFrame:
    j = pontos[["ponto_id", "distrito", "subprefeitura"]].merge(indicadores, on="ponto_id")
    r = j.groupby(["distrito", "subprefeitura"], as_index=False).agg(
        pontos=("ponto_id", "size"),
        indice_medio=("indice_vulnerabilidade", "mean"),
        pontos_faixa_alta=("faixa", lambda f: int((f == "alta").sum())),
    )
    oc = filtrar_relevantes(ocorrencias).groupby("distrito").size().rename("ocorrencias_noturnas")
    r = r.merge(oc, left_on="distrito", right_index=True, how="left")
    r["ocorrencias_noturnas"] = r["ocorrencias_noturnas"].fillna(0).astype(int)
    r["indice_medio"] = r["indice_medio"].round(4)
    return r.sort_values("indice_medio", ascending=False, ignore_index=True)
