import json
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Config  # noqa: E402
from app.llm import ErroLLM, TimeoutLLM  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]


def ponto(pid, nome, distrito, ranking, indice=0.9, faixa="alta"):
    return {"ponto_id": pid, "nome": nome, "distrito": distrito, "ranking": ranking,
            "indice_vulnerabilidade": indice, "faixa": faixa, "ocorrencias_noturnas_150m": 100, "dist_poste_m": 20.0}


class RepoFalso:
    def __init__(self, vazio=False, quebrado=False):
        self.vazio, self.quebrado = vazio, quebrado

    def distritos(self):
        return ["PINHEIROS", "SE", "SAUDE", "LIBERDADE", "CIDADE DUTRA", "JARDIM PAULISTA", "CONSOLACAO"]

    def top_ranking(self, n):
        if self.quebrado:
            raise ConnectionError("banco fora")
        return [] if self.vazio else [ponto("111", "R. MOURATO COELHO , 1022", "PINHEIROS", 1),
                                      ponto("222", "R. AUGUSTA , 810", "CONSOLACAO", 2)][:n]

    def escuros_agora(self):
        return [{"ponto_id": "333", "nome": "AV. TIRADENTES , 614", "distrito": "BOM RETIRO",
                 "escuro_desde": datetime(2026, 11, 17, 21, 0, tzinfo=timezone.utc), "lux_atual": 2.5}]

    def top_distritos(self, n):
        return [{"distrito": "REPUBLICA", "subprefeitura": "SE", "pontos": 122, "indice_medio": 0.5655,
                 "pontos_faixa_alta": 83, "ocorrencias_noturnas": 1833}]

    def resumo_distrito(self, d):
        return {"distrito": d, "subprefeitura": "X", "pontos": 10, "indice_medio": 0.4,
                "pontos_faixa_alta": 2, "ocorrencias_noturnas": 50}

    def pontos_distrito(self, d, n):
        return [ponto("444" if d == "PINHEIROS" else "555", f"R. DE {d}", d, 7)]

    def ultima_execucao(self):
        return {"run_id": "r1", "fim": datetime(2026, 11, 18, 20, 20, tzinfo=timezone.utc), "status": "ok"}


@pytest.fixture
def repo():
    return RepoFalso()


@pytest.fixture
def abrir_repo(repo):
    @contextmanager
    def abrir():
        yield repo
    return abrir


def resposta_json(**kw):
    base = {"resposta": "ok", "tipo": "uso", "fontes": ["manual#alertas"], "pontos_citados": [],
            "acao_sugerida": None, "precisa_humano": False, "confianca": "alta"}
    base.update(kw)
    return json.dumps(base, ensure_ascii=False)


class ClienteFalso:
    """Roteiro: lista de itens consumidos em ordem; str = conteúdo, Exception = levanta."""

    def __init__(self, roteiro):
        self.roteiro = list(roteiro)
        self.chamadas = []

    def completar(self, modelo, mensagens, response_format):
        self.chamadas.append({"modelo": modelo, "formato": response_format["type"], "n_msgs": len(mensagens)})
        item = self.roteiro.pop(0)
        if isinstance(item, Exception):
            raise item
        return {"choices": [{"message": {"content": item}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20, "cost": 0.0001}}


@pytest.fixture
def cfg():
    return Config(api_key="teste", modelo="m/principal", modelo_reserva="m/reserva",
                  manual_path=RAIZ / "docs/manual.md", database_url="")


__all__ = ["ErroLLM", "TimeoutLLM"]
