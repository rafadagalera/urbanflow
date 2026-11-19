"""Silver da SSP-SP: ocorrências noturnas na cidade de São Paulo.

Regras (spec §3.3, tarefa tratar_ssp):
- município = S.PAULO;
- período "A noite" ou "De madrugada";
- coordenada numérica e dentro do retângulo da cidade (o recorte fino pelo
  contorno dos distritos é feito em tratar_geo, que já tem os polígonos);
- descarta identificadores e endereço (NUM_BO, delegacia, logradouro...).
"""
from __future__ import annotations

from datetime import date, timedelta

MUNICIPIO = "S.PAULO"
PERIODOS_NOTURNOS = frozenset({"A noite", "De madrugada"})
# Retângulo que contém o município de São Paulo (WGS84), com folga.
LAT_MIN, LAT_MAX = -24.02, -23.35
LON_MIN, LON_MAX = -46.83, -46.36
_EXCEL_EPOCH = date(1899, 12, 30)

COLUNAS_SILVER = [
    "data_ocorrencia", "hora_ocorrencia", "periodo", "categoria", "transeunte",
    "rubrica", "conduta", "tipo_local", "lat", "lon",
]


def numero(txt: str) -> float | None:
    """Converte '−23.55', '-23,55' etc.; devolve None para NULL, vazio, lixo."""
    t = (txt or "").strip().replace(",", ".")
    try:
        v = float(t)
    except ValueError:
        return None
    return v if v == v else None  # descarta NaN


def data_excel(txt: str) -> date | None:
    v = numero(txt)
    if v is None or v <= 0:
        return None
    return _EXCEL_EPOCH + timedelta(days=int(v))


def hora_excel(txt: str) -> str | None:
    """A hora vem como fração do dia (0.75 = 18:00) ou como 'HH:MM:SS'."""
    t = (txt or "").strip()
    if not t or t.upper() == "NULL":
        return None
    if ":" in t:
        return t[:5]
    v = numero(t)
    if v is None:
        return None
    minutos = round((v % 1) * 24 * 60) % (24 * 60)
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


def categoria(rubrica: str) -> str:
    r = (rubrica or "").strip().lower()
    if r.startswith("roubo"):
        return "roubo"
    if r.startswith("furto"):
        return "furto"
    return "outros"


def tratar_linha(linha: dict[str, str]) -> dict | None:
    """Devolve a linha silver ou None se ela não entra."""
    if linha.get("NOME_MUNICIPIO", "").strip() != MUNICIPIO:
        return None
    if linha.get("DESC_PERIODO", "").strip() not in PERIODOS_NOTURNOS:
        return None
    lat, lon = numero(linha.get("LATITUDE", "")), numero(linha.get("LONGITUDE", ""))
    if lat is None or lon is None or not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
        return None
    conduta = (linha.get("DESCR_CONDUTA") or "").strip()
    conduta = "" if conduta.upper() == "NULL" else conduta
    return {
        "data_ocorrencia": data_excel(linha.get("DATA_OCORRENCIA_BO", "")),
        "hora_ocorrencia": hora_excel(linha.get("HORA_OCORRENCIA_BO", "")),
        "periodo": linha["DESC_PERIODO"].strip(),
        "categoria": categoria(linha.get("RUBRICA", "")),
        "transeunte": conduta == "Transeunte",
        "rubrica": (linha.get("RUBRICA") or "").strip(),
        "conduta": conduta,
        "tipo_local": (linha.get("DESCR_TIPOLOCAL") or "").strip(),
        "lat": lat,
        "lon": lon,
    }


def tratar_ssp(xlsx, destino) -> dict:
    """Lê todas as abas do xlsx, grava o parquet silver e devolve contagens."""
    import pandas as pd

    from . import xlsx as lx

    total, mantidas, linhas = 0, 0, []
    for _, linha in lx.ler_abas(xlsx):
        total += 1
        r = tratar_linha(linha)
        if r is not None:
            linhas.append(r)
    mantidas = len(linhas)
    if not mantidas:
        raise ValueError(f"nenhuma ocorrência noturna válida em {xlsx}")
    df = pd.DataFrame(linhas, columns=COLUNAS_SILVER)
    df["data_ocorrencia"] = pd.to_datetime(df["data_ocorrencia"])
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(destino)
    return {"lidas": total, "mantidas": mantidas}
