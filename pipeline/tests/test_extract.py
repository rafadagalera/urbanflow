import json

import pytest
import requests

from urbancare_pipeline import extract


class Resp:
    def __init__(self, status=200, texto="", conteudo=None, headers=None):
        self.status_code, self.text = status, texto
        self.content = conteudo if conteudo is not None else texto.encode()
        self.headers = headers or {}

    def raise_for_status(self):
        raise requests.HTTPError(self.status_code)

    def iter_content(self, n):
        yield self.content


class SessaoFalsa:
    """Simula o WFS: `falhas` = quantas respostas 503 antes de cada sucesso."""

    def __init__(self, registros, falhas=0, cair_na_pagina=None):
        self.registros, self.falhas, self.cair = registros, falhas, cair_na_pagina
        self.chamadas = []
        self._pendentes = falhas

    def get(self, url, params=None, **kw):
        self.chamadas.append(dict(params or {}))
        if self._pendentes:
            self._pendentes -= 1
            return Resp(503, "busy")
        self._pendentes = self.falhas
        if params.get("resultType") == "hits":
            return Resp(texto=f'<wfs:FeatureCollection numberMatched="{len(self.registros)}"/>')
        ini, n = params["startIndex"], params["count"]
        if self.cair is not None and ini // n == self.cair:
            raise requests.ConnectionError("queda")
        # FID aleatório a cada requisição, como no GeoSampa; a chave estável é "id".
        corpo = "FID,id,nome,geom\n" + "".join(
            f"p.{len(self.chamadas)}-{i},{i},{nome},POINT (1 2)\n" for i, nome in self.registros[ini:ini + n])
        return Resp(texto=corpo)

    def head(self, *a, **k):
        return Resp(headers={"content-length": "4"})


@pytest.fixture(autouse=True)
def sem_espera(monkeypatch):
    monkeypatch.setattr(extract.time, "sleep", lambda s: None)


REG = [(i, f"ponto {i}") for i in range(25)]


def test_paginacao_completa(tmp_path):
    s = SessaoFalsa(REG)
    destino = tmp_path / "pontos.csv"
    extract.baixar_wfs_csv("ponto_onibus", destino, ordenar_por="id", sessao=s, pagina=10)
    linhas = destino.read_text().splitlines()
    assert len(linhas) == 26 and linhas[0] == "FID,id,nome,geom"
    paginas = [c for c in s.chamadas if "startIndex" in c]
    assert [c["startIndex"] for c in paginas] == [0, 10, 20]
    assert all(c["sortBy"] == "id" and c["srsName"] == "EPSG:31983" for c in paginas)
    assert not (tmp_path / ".pontos.partes").exists()


def test_retenta_503(tmp_path):
    s = SessaoFalsa(REG, falhas=2)
    extract.baixar_wfs_csv("ponto_onibus", tmp_path / "p.csv", "id", sessao=s, pagina=10)
    assert len((tmp_path / "p.csv").read_text().splitlines()) == 26


def test_retoma_de_onde_parou(tmp_path):
    destino = tmp_path / "p.csv"
    with pytest.raises(extract.FonteIndisponivel):
        extract.baixar_wfs_csv("ponto_onibus", destino, "id", sessao=SessaoFalsa(REG, cair_na_pagina=2),
                               pagina=10, tentativas=2)
    assert not destino.exists()
    s = SessaoFalsa(REG)
    extract.baixar_wfs_csv("ponto_onibus", destino, "id", sessao=s, pagina=10)
    assert [c["startIndex"] for c in s.chamadas if "startIndex" in c] == [20]  # só a página que faltava
    assert len(destino.read_text().splitlines()) == 26


def test_cache_nao_baixa_de_novo(tmp_path):
    destino = tmp_path / "p.csv"
    destino.write_text("FID\n")
    s = SessaoFalsa(REG)
    extract.baixar_wfs_csv("ponto_onibus", destino, sessao=s)
    assert s.chamadas == []


def test_total_divergente_falha(tmp_path):
    class Duplicada(SessaoFalsa):
        def get(self, url, params=None, **kw):
            if params.get("startIndex") == 10:
                params = {**params, "startIndex": 0}  # servidor devolve a página 0 de novo
            return super().get(url, params, **kw)

    with pytest.raises(extract.FonteIndisponivel, match="esperado 25"):
        extract.baixar_wfs_csv("ponto_onibus", tmp_path / "p.csv", "id", sessao=Duplicada(REG), pagina=10)


def test_resposta_nao_csv_falha(tmp_path):
    class Xml(SessaoFalsa):
        def get(self, url, params=None, **kw):
            if "startIndex" in (params or {}):
                return Resp(texto="<ows:ExceptionReport>")
            return super().get(url, params, **kw)

    with pytest.raises(extract.FonteIndisponivel, match="não é CSV"):
        extract.baixar_wfs_csv("ponto_onibus", tmp_path / "p.csv", sessao=Xml(REG), pagina=10)


def test_geojson(tmp_path):
    class G(SessaoFalsa):
        def get(self, url, params=None, **kw):
            return Resp(texto=json.dumps({"type": "FeatureCollection", "features": []}))

    d = extract.baixar_wfs_geojson("distrito_municipal", tmp_path / "d.geojson", sessao=G([]))
    assert json.loads(d.read_text())["type"] == "FeatureCollection"


def test_arquivo_em_cache_com_mesmo_tamanho(tmp_path):
    d = tmp_path / "x.xlsx"
    d.write_bytes(b"1234")
    s = SessaoFalsa([])
    extract.baixar_arquivo("http://x", d, sessao=s)
    assert s.chamadas == []
