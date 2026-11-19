import zipfile
from datetime import date

import pandas as pd
import pytest

from urbancare_pipeline import ssp, xlsx


def linha(**kw):
    base = {
        "NOME_MUNICIPIO": "S.PAULO", "DESC_PERIODO": "A noite",
        "LATITUDE": "-23.5503", "LONGITUDE": "-46.6342",
        "DATA_OCORRENCIA_BO": "45660", "HORA_OCORRENCIA_BO": "0.875",
        "RUBRICA": "Roubo (art. 157)", "DESCR_CONDUTA": "Transeunte",
        "DESCR_TIPOLOCAL": "Via Pública", "NUM_BO": "AE1883",
        "NOME_DELEGACIA": "42º D.P.", "LOGRADOURO": "PRAÇA DA SÉ",
    }
    base.update(kw)
    return base


def test_linha_valida_e_sem_identificadores():
    r = ssp.tratar_linha(linha())
    assert r["categoria"] == "roubo" and r["transeunte"] is True
    assert r["data_ocorrencia"] == date(2025, 1, 3)
    assert r["hora_ocorrencia"] == "21:00"
    assert set(r) == set(ssp.COLUNAS_SILVER)  # NUM_BO, delegacia e logradouro ficam de fora


@pytest.mark.parametrize("campo,valor", [
    ("NOME_MUNICIPIO", "CAMPINAS"),
    ("DESC_PERIODO", "Pela manhã"),
    ("DESC_PERIODO", "Em hora incerta"),
])
def test_filtra_municipio_e_periodo(campo, valor):
    assert ssp.tratar_linha(linha(**{campo: valor})) is None


def test_madrugada_entra():
    assert ssp.tratar_linha(linha(DESC_PERIODO="De madrugada")) is not None


@pytest.mark.parametrize("lat,lon", [
    ("NULL", "NULL"), ("NUL,L", "NUL,L"), ("", ""), ("0", "0"),
    ("-22.90", "-47.06"),  # Campinas: fora do retângulo da capital
    ("VEDAÇÃO DA DIVULGAÇÃO DOS DADOS RELATIVOS", ""),
])
def test_descarta_coordenada_invalida(lat, lon):
    assert ssp.tratar_linha(linha(LATITUDE=lat, LONGITUDE=lon)) is None


def test_coordenada_com_virgula_decimal():
    r = ssp.tratar_linha(linha(LATITUDE="-23,5503", LONGITUDE="-46,6342"))
    assert r["lat"] == pytest.approx(-23.5503)


def test_linha_de_rodape_vedacao_descartada():
    rodape = {"NOME_DEPARTAMENTO": "VEDAÇÃO DA DIVULGAÇÃO DOS DADOS RELATIVOS AO NÚMERO DO BO"}
    assert ssp.tratar_linha(rodape) is None


@pytest.mark.parametrize("rubrica,esperado", [
    ("Roubo (art. 157)", "roubo"), ("Furto (art. 155)", "furto"),
    ("Furto de coisa comum (art. 156)", "furto"), ("Lesão corporal (art. 129)", "outros"), ("", "outros"),
])
def test_categoria(rubrica, esperado):
    assert ssp.categoria(rubrica) == esperado


def test_conduta_null_vira_vazio_e_nao_transeunte():
    r = ssp.tratar_linha(linha(DESCR_CONDUTA="NULL"))
    assert r["conduta"] == "" and r["transeunte"] is False


@pytest.mark.parametrize("txt,esperado", [("NULL", None), ("", None), ("23:15:00", "23:15"), ("0", "00:00")])
def test_hora(txt, esperado):
    assert ssp.hora_excel(txt) == esperado


# --- xlsx mínimo escrito à mão, para testar o leitor em streaming e o fluxo completo ---

def _xlsx(caminho, abas):
    ss, idx = [], {}

    def s(t):
        if t not in idx:
            idx[t] = len(ss)
            ss.append(t)
        return idx[t]

    def col(i):
        return chr(65 + i)

    folhas = {}
    for nome, linhas in abas.items():
        rows = []
        for r, valores in enumerate(linhas, 1):
            cells = "".join(
                f'<c r="{col(i)}{r}" t="s"><v>{s(v)}</v></c>' for i, v in enumerate(valores) if v != ""
            )
            rows.append(f'<row r="{r}">{cells}</row>')
        folhas[nome] = ('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                        f'<sheetData>{"".join(rows)}</sheetData></worksheet>')
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    nsr = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    sheets = "".join(f'<sheet name="{n}" sheetId="{i+1}" r:id="rId{i+1}"/>' for i, n in enumerate(folhas))
    rels = "".join(f'<Relationship Id="rId{i+1}" Target="worksheets/sheet{i+1}.xml" Type="x"/>'
                   for i in range(len(folhas)))
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr("xl/workbook.xml", f"<workbook {ns} {nsr}><sheets>{sheets}</sheets></workbook>")
        z.writestr("xl/_rels/workbook.xml.rels",
                   f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}</Relationships>')
        for i, xml in enumerate(folhas.values()):
            z.writestr(f"xl/worksheets/sheet{i+1}.xml", xml)
        z.writestr("xl/sharedStrings.xml",
                   f"<sst {ns}>" + "".join(f"<si><t>{t}</t></si>" for t in ss) + "</sst>")


CAB = ["NOME_MUNICIPIO", "DESC_PERIODO", "LATITUDE", "LONGITUDE", "DATA_OCORRENCIA_BO", "RUBRICA", "DESCR_CONDUTA"]


def test_tratar_ssp_le_as_duas_abas(tmp_path):
    arq = tmp_path / "ssp.xlsx"
    _xlsx(arq, {
        "JAN-JUN_2025": [CAB,
                         ["S.PAULO", "A noite", "-23.55", "-46.63", "45660", "Roubo (art. 157)", "Transeunte"],
                         ["S.PAULO", "Pela manhã", "-23.55", "-46.63", "45660", "Roubo (art. 157)", "Transeunte"]],
        "JUL-DEZ_2025": [CAB,
                         ["S.PAULO", "De madrugada", "-23.60", "-46.70", "45850", "Furto (art. 155)", ""],
                         ["CAMPINAS", "A noite", "-22.90", "-47.06", "45850", "Furto (art. 155)", ""],
                         ["VEDAÇÃO DA DIVULGAÇÃO DOS DADOS RELATIVOS"]],
    })
    assert xlsx.nomes_abas(arq) == ["JAN-JUN_2025", "JUL-DEZ_2025"]
    destino = tmp_path / "silver" / "ocorrencias_noturnas.parquet"
    cont = ssp.tratar_ssp(arq, destino)
    assert cont == {"lidas": 5, "mantidas": 2}
    df = pd.read_parquet(destino)
    assert list(df.columns) == ssp.COLUNAS_SILVER
    assert sorted(df["categoria"]) == ["furto", "roubo"]


def test_tratar_ssp_sem_linhas_validas_falha(tmp_path):
    arq = tmp_path / "vazio.xlsx"
    _xlsx(arq, {"A": [CAB, ["CAMPINAS", "A noite", "-22.9", "-47.0", "45660", "x", ""]]})
    with pytest.raises(ValueError):
        ssp.tratar_ssp(arq, tmp_path / "o.parquet")
