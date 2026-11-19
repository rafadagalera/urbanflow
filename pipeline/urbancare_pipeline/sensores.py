"""Leituras de sensor SIMULADAS para os pontos do 1º ano de instalação (spec §3.5).

Determinístico: a mesma data de referência gera exatamente os mesmos eventos.
Nada aqui identifica pessoas; `pessoa_sozinha_noite` é só um contador de alerta.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

FUSO = "America/Sao_Paulo"
PONTOS_INSTALADOS = 150     # meta do 1º ano (DOCX UrbanCare)
DIAS = 7
PASSO_MIN = 10
LUX_ESCURO = 10.0           # abaixo disso o abrigo está "escuro"
FRACAO_APAGAO = 0.05
NOITE_INICIO, NOITE_FIM = 18, 6        # para luminosidade
ALERTA_INICIO, ALERTA_FIM = 21, 5      # para pessoa sozinha


def semente(fim: datetime) -> int:
    return int(fim.strftime("%Y%m%d"))


def _noite(horas: np.ndarray, ini: int, fim: int) -> np.ndarray:
    return (horas >= ini) | (horas < fim)


def simular(indicadores: pd.DataFrame, fim: datetime) -> pd.DataFrame:
    """`indicadores` precisa de ponto_id, ranking, postes_30m, indice_vulnerabilidade.

    `fim` é o instante final (exclusivo) da janela; sem fuso, é tratado como horário de SP.
    """
    fim_ts = pd.Timestamp(fim)
    fim_ts = fim_ts.tz_localize(FUSO) if fim_ts.tzinfo is None else fim_ts.tz_convert(FUSO)
    rng = np.random.default_rng(semente(fim_ts))
    alvo = indicadores.nsmallest(PONTOS_INSTALADOS, "ranking").sort_values("ranking")
    ts = pd.date_range(end=fim_ts - timedelta(minutes=PASSO_MIN), periods=DIAS * 24 * 60 // PASSO_MIN,
                       freq=f"{PASSO_MIN}min")
    horas = ts.hour.to_numpy() + ts.minute.to_numpy() / 60
    noite = _noite(ts.hour.to_numpy(), NOITE_INICIO, NOITE_FIM)
    alerta = _noite(ts.hour.to_numpy(), ALERTA_INICIO, ALERTA_FIM)
    n_ts = len(ts)

    # Apagões: ~5% dos pontos; metade continua apagada até a última leitura.
    n_ap = max(1, round(FRACAO_APAGAO * len(alvo)))
    sorteados = sorted(rng.choice(len(alvo), size=n_ap, replace=False).tolist())
    com_apagao, persistentes = set(sorteados), set(sorteados[::2])

    blocos = []
    for i, p in enumerate(alvo.itertuples(index=False)):
        # lux: dia ~ luz natural; noite ~ luminária do próprio abrigo (18 lux) + postes próximos.
        # Só um apagão leva abaixo de LUX_ESCURO; ponto sem poste não é "escuro" por si.
        lux_noite = min(18 + 9 * p.postes_30m, 60)
        lux = np.where(noite, rng.normal(lux_noite, 2.0, n_ts), rng.normal(1500, 300, n_ts))
        if i in com_apagao:
            ini = int(rng.integers(0, n_ts - 6 * 6))  # começa até 6 h antes do fim
            dur = n_ts - ini if i in persistentes else int(rng.integers(6, 6 * 24))
            janela = np.zeros(n_ts, bool)
            janela[ini:ini + dur] = True
            lux = np.where(janela & noite, rng.uniform(0.5, 6.0, n_ts), lux)
        lux = np.clip(lux, 0, None).round(1)

        # lotação: picos às 7h e 18h
        curva = 2 + 14 * np.exp(-((horas - 7) ** 2) / 2) + 12 * np.exp(-((horas - 18) ** 2) / 2.5)
        lot = rng.poisson(curva)

        # pessoa sozinha à noite: raro, mais frequente onde o índice é alto
        prob = (0.002 + 0.01 * p.indice_vulnerabilidade) * alerta
        ev = rng.random(n_ts) < prob

        blocos.append(pd.DataFrame({"ponto_id": p.ponto_id, "ts": ts, "tipo": "lux", "valor": lux}))
        blocos.append(pd.DataFrame({"ponto_id": p.ponto_id, "ts": ts, "tipo": "lotacao", "valor": lot.astype(float)}))
        if ev.any():
            blocos.append(pd.DataFrame({"ponto_id": p.ponto_id, "ts": ts[ev], "tipo": "pessoa_sozinha_noite",
                                        "valor": 1.0}))
    out = pd.concat(blocos, ignore_index=True)
    out["simulado"] = True
    return out.sort_values(["ponto_id", "ts", "tipo"], ignore_index=True)
