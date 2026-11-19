from datetime import datetime

import pandas as pd

from urbancare_pipeline import sensores

IND = pd.DataFrame({
    "ponto_id": [f"p{i:03d}" for i in range(200)],
    "ranking": range(1, 201),
    "postes_30m": [i % 4 for i in range(200)],
    "indice_vulnerabilidade": [1 - i / 200 for i in range(200)],
})
FIM = datetime(2026, 11, 18)


def test_deterministico_pela_data():
    a, b = sensores.simular(IND, FIM), sensores.simular(IND, FIM)
    pd.testing.assert_frame_equal(a, b)
    c = sensores.simular(IND, datetime(2026, 11, 19))
    assert not a["valor"].equals(c["valor"])


def test_alcance_janela_e_marcacao():
    ev = sensores.simular(IND, FIM)
    assert ev["ponto_id"].nunique() == sensores.PONTOS_INSTALADOS
    assert set(ev["ponto_id"]) == {f"p{i:03d}" for i in range(150)}  # os 150 primeiros do ranking
    assert ev["simulado"].all()
    lux = ev[ev["tipo"] == "lux"]
    assert lux.groupby("ponto_id").size().eq(7 * 24 * 6).all()
    fim_local = pd.Timestamp(FIM, tz=sensores.FUSO)
    assert lux["ts"].max() == fim_local - pd.Timedelta(minutes=10)
    assert lux["ts"].min() == fim_local - pd.Timedelta(days=7)


def test_apagao_alguns_terminam_escuros():
    ev = sensores.simular(IND, FIM)
    ultima = ev[ev["tipo"] == "lux"].sort_values("ts").groupby("ponto_id").tail(1)
    escuros = ultima[ultima["valor"] < sensores.LUX_ESCURO]
    assert 1 <= len(escuros) <= round(sensores.FRACAO_APAGAO * 150)


def test_pessoa_sozinha_so_de_madrugada_e_mais_no_indice_alto():
    ev = sensores.simular(IND, FIM)
    alerta = ev[ev["tipo"] == "pessoa_sozinha_noite"]
    h = alerta["ts"].dt.hour
    assert ((h >= 21) | (h < 5)).all()
    topo = alerta["ponto_id"].isin([f"p{i:03d}" for i in range(50)]).sum()
    base = alerta["ponto_id"].isin([f"p{i:03d}" for i in range(100, 150)]).sum()
    assert topo > base


def test_lotacao_pico_maior_que_madrugada():
    ev = sensores.simular(IND, FIM)
    lot = ev[ev["tipo"] == "lotacao"]
    media = lot.groupby(lot["ts"].dt.hour)["valor"].mean()
    assert media[7] > 3 * media[3] and media[18] > 3 * media[3]
