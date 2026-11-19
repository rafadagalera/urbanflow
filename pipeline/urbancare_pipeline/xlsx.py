"""Leitura de .xlsx grande em streaming, só com a stdlib.

O openpyxl carrega a planilha inteira (~585 mil linhas por aba) e estoura a
memória/tempo; aqui o XML de cada aba é percorrido com iterparse e cada linha
é liberada logo depois de lida.
"""
from __future__ import annotations

import re
import zipfile
from collections.abc import Iterator
from xml.etree.ElementTree import iterparse

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_COL = re.compile(r"[A-Z]+")


def _indice_coluna(ref: str) -> int:
    n = 0
    for ch in _COL.match(ref).group():
        n = n * 26 + ord(ch) - 64
    return n - 1


def _strings_compartilhadas(z: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    out = []
    for _, el in iterparse(z.open("xl/sharedStrings.xml")):
        if el.tag == NS + "si":
            out.append("".join(t.text or "" for t in el.iter(NS + "t")))
            el.clear()
    return out


def _caminhos_abas(z: zipfile.ZipFile) -> dict[str, str]:
    """Nome da aba → caminho do XML dentro do zip."""
    rels = {}
    for _, el in iterparse(z.open("xl/_rels/workbook.xml.rels")):
        if el.tag.endswith("Relationship"):
            alvo = el.get("Target").lstrip("/")
            rels[el.get("Id")] = alvo if alvo.startswith("xl/") else "xl/" + alvo
    abas = {}
    for _, el in iterparse(z.open("xl/workbook.xml")):
        if el.tag == NS + "sheet":
            abas[el.get("name")] = rels[el.get(NS_REL + "id")]
    return abas


def nomes_abas(caminho) -> list[str]:
    with zipfile.ZipFile(caminho) as z:
        return list(_caminhos_abas(z))


def ler_abas(caminho, abas: list[str] | None = None) -> Iterator[tuple[str, dict[str, str]]]:
    """Gera (aba, linha) com a linha como dict cabeçalho → texto.

    Células vazias viram ''. Números saem como o texto gravado no XML.
    """
    with zipfile.ZipFile(caminho) as z:
        ss = _strings_compartilhadas(z)
        mapa = _caminhos_abas(z)
        for aba in abas or list(mapa):
            cabecalho = None
            for _, el in iterparse(z.open(mapa[aba])):
                if el.tag != NS + "row":
                    continue
                vals = {}
                for c in el.iter(NS + "c"):
                    v = c.find(NS + "v")
                    if v is not None:
                        val = ss[int(v.text)] if c.get("t") == "s" else (v.text or "")
                    else:
                        inline = c.find(NS + "is")
                        val = "".join(t.text or "" for t in inline.iter(NS + "t")) if inline is not None else ""
                    vals[_indice_coluna(c.get("r"))] = val
                el.clear()
                if cabecalho is None:
                    if vals:
                        cabecalho = [vals.get(i, "") for i in range(max(vals) + 1)]
                    continue
                yield aba, {nome: vals.get(i, "") for i, nome in enumerate(cabecalho)}
