"""Bronze: download das fontes abertas, com cache e retomada.

O WFS do GeoSampa oscila (503/timeout). Cada página é gravada em disco assim
que chega, então uma nova execução retoma de onde parou; o arquivo final só é
montado quando todas as páginas existem e o total confere com numberMatched.
"""
from __future__ import annotations

import csv
import io
import logging
import re
import time
from pathlib import Path

import requests

from .config import BRONZE

log = logging.getLogger(__name__)

WFS_URL = "http://wms.geosampa.prefeitura.sp.gov.br/geoserver/geoportal/wfs"
SSP_URL = "https://www.ssp.sp.gov.br/assets/estatistica/transparencia/spDados/SPDadosCriminais_2025.xlsx"
PAGINA_MAX = 10_240  # teto do servidor por requisição
SRS = "EPSG:31983"
UA = {"User-Agent": "urbancare-pipeline/1.0 (projeto academico)"}

CAMADAS_CSV = {
    # camada: (arquivo bronze, chave única). A chave serve para ordenar a
    # paginação (sem chave primária o GeoServer recusa paginar) e deduplicar;
    # o FID não serve, pois é gerado de novo a cada requisição.
    "ponto_onibus": ("geosampa/ponto_onibus.csv", "cd_identificador_ponto_onibus"),
    "iluminacao_publica": ("geosampa/iluminacao_publica.csv", "cd_identificador_iluminacao_publica"),
}
CAMADAS_GEOJSON = {
    "distrito_municipal": "geosampa/distritos.geojson",
    "subprefeitura": "geosampa/subprefeituras.geojson",
}


class FonteIndisponivel(RuntimeError):
    pass


def _get(sessao, url, params=None, tentativas=6, espera=5.0, timeout=180, stream=False):
    """GET com retentativa exponencial para 429/5xx e falhas de rede."""
    ultimo = None
    for i in range(tentativas):
        try:
            r = sessao.get(url, params=params, timeout=timeout, headers=UA, stream=stream)
            if r.status_code < 400:
                return r
            if r.status_code not in (429, 500, 502, 503, 504):
                r.raise_for_status()
            ultimo = f"HTTP {r.status_code}"
        except (requests.ConnectionError, requests.Timeout) as e:
            ultimo = type(e).__name__
        pausa = espera * (2 ** i)
        log.warning("GET %s falhou (%s); tentativa %d/%d, aguardando %.0fs", url, ultimo, i + 1, tentativas, pausa)
        time.sleep(pausa)
    raise FonteIndisponivel(f"{url} indisponível após {tentativas} tentativas ({ultimo})")


def _params(camada, **extra):
    p = {"service": "WFS", "version": "2.0.0", "request": "GetFeature",
         "typeNames": f"geoportal:{camada}", "srsName": SRS}
    p.update(extra)
    return p


def total_wfs(sessao, camada) -> int:
    r = _get(sessao, WFS_URL, _params(camada, resultType="hits"))
    m = re.search(r'numberMatched="(\d+)"', r.text)
    if not m:
        raise FonteIndisponivel(f"resposta de hits sem numberMatched para {camada}")
    return int(m.group(1))


def baixar_wfs_csv(camada, destino: Path, ordenar_por=None, sessao=None,
                   pagina=PAGINA_MAX, forcar=False, **kw_get) -> Path:
    """Baixa a camada inteira em CSV, página a página, com retomada."""
    if destino.exists() and not forcar:
        log.info("%s já em cache: %s", camada, destino)
        return destino
    sessao = sessao or requests.Session()
    total = total_wfs(sessao, camada)
    partes = destino.parent / f".{destino.stem}.partes"
    partes.mkdir(parents=True, exist_ok=True)
    n_pag = -(-total // pagina)
    for k in range(n_pag):
        arq = partes / f"{k:04d}.csv"
        if arq.exists():
            continue
        extra = {"outputFormat": "csv", "count": pagina, "startIndex": k * pagina}
        if ordenar_por:
            extra["sortBy"] = ordenar_por
        r = _get(sessao, WFS_URL, _params(camada, **extra), **kw_get)
        texto = r.content.decode("utf-8")
        if not texto.startswith("FID"):
            raise FonteIndisponivel(f"{camada} pág. {k}: resposta não é CSV ({texto[:120]!r})")
        tmp = arq.with_suffix(".tmp")
        tmp.write_text(texto, encoding="utf-8")
        tmp.replace(arq)
        log.info("%s página %d/%d", camada, k + 1, n_pag)
    # Junta as páginas, deduplicando pela chave (proteção contra páginas sobrepostas).
    vistos, linhas, cabecalho = set(), [], None
    for arq in sorted(partes.glob("*.csv")):
        leitor = csv.reader(io.StringIO(arq.read_text(encoding="utf-8")))
        cab = next(leitor)
        cabecalho = cabecalho or cab
        i_chave = cab.index(ordenar_por) if ordenar_por else 0
        for linha in leitor:
            if linha and linha[i_chave] not in vistos:
                vistos.add(linha[i_chave])
                linhas.append(linha)
    if len(linhas) != total:
        raise FonteIndisponivel(f"{camada}: {len(linhas)} registros únicos, esperado {total}; "
                                f"apague {partes} e rode de novo")
    tmp = destino.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cabecalho)
        w.writerows(linhas)
    tmp.replace(destino)
    for arq in partes.glob("*"):
        arq.unlink()
    partes.rmdir()
    return destino


def baixar_wfs_geojson(camada, destino: Path, sessao=None, forcar=False, **kw_get) -> Path:
    if destino.exists() and not forcar:
        return destino
    sessao = sessao or requests.Session()
    r = _get(sessao, WFS_URL, _params(camada, outputFormat="application/json"), **kw_get)
    if '"FeatureCollection"' not in r.text[:200]:
        raise FonteIndisponivel(f"{camada}: resposta não é GeoJSON ({r.text[:120]!r})")
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".tmp")
    tmp.write_text(r.text, encoding="utf-8")
    tmp.replace(destino)
    return destino


def baixar_arquivo(url, destino: Path, sessao=None, **kw_get) -> Path:
    """Baixa só se o arquivo local não existir ou tiver tamanho diferente do remoto."""
    sessao = sessao or requests.Session()
    remoto = None
    try:
        h = sessao.head(url, timeout=60, headers=UA, allow_redirects=True)
        remoto = int(h.headers.get("content-length", 0)) or None
    except requests.RequestException as e:
        log.warning("HEAD %s falhou (%s)", url, e)
    if destino.exists() and (remoto is None or destino.stat().st_size == remoto):
        log.info("cache válido: %s (%d bytes)", destino, destino.stat().st_size)
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    r = _get(sessao, url, stream=True, **kw_get)
    tmp = destino.with_suffix(".tmp")
    with tmp.open("wb") as f:
        for bloco in r.iter_content(1 << 20):
            f.write(bloco)
    if remoto and tmp.stat().st_size != remoto:
        raise FonteIndisponivel(f"download incompleto de {url}")
    tmp.replace(destino)
    return destino


# Funções chamadas pelas tarefas do DAG (e pelo modo sem Airflow).
def extrair_pontos(base=BRONZE):
    arq, ordem = CAMADAS_CSV["ponto_onibus"]
    return str(baixar_wfs_csv("ponto_onibus", base / arq, ordem))


def extrair_postes(base=BRONZE):
    arq, ordem = CAMADAS_CSV["iluminacao_publica"]
    return str(baixar_wfs_csv("iluminacao_publica", base / arq, ordem))


def extrair_distritos(base=BRONZE):
    return [str(baixar_wfs_geojson(c, base / a)) for c, a in CAMADAS_GEOJSON.items()]


def extrair_ssp(base=BRONZE):
    return str(baixar_arquivo(SSP_URL, base / "ssp/SPDadosCriminais_2025.xlsx"))
