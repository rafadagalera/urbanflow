import pytest
from fastapi.testclient import TestClient

from app.main import criar_app
from conftest import ClienteFalso, resposta_json


@pytest.fixture
def cliente_api(cfg, abrir_repo):
    def fazer(roteiro):
        return TestClient(criar_app(cfg, ClienteFalso(roteiro), abrir_repo))
    return fazer


def test_perguntar_ok(cliente_api):
    r = cliente_api([resposta_json()]).post("/perguntar", json={"pergunta": "como atendo um alerta?"})
    assert r.status_code == 200 and r.json()["tipo"] == "uso"


@pytest.mark.parametrize("corpo", [{"pergunta": ""}, {"pergunta": "   "}, {"pergunta": "x" * 501}, {}])
def test_entrada_invalida_422(cliente_api, corpo):
    assert cliente_api([]).post("/perguntar", json=corpo).status_code == 422


def test_falha_total_ainda_e_200(cliente_api):
    from app.llm import TimeoutLLM
    r = cliente_api([TimeoutLLM("x"), TimeoutLLM("y")]).post("/perguntar", json={"pergunta": "oi"})
    assert r.status_code == 200 and r.json()["tipo"] == "erro"


def test_saude_e_pagina(cliente_api):
    c = cliente_api([])
    s = c.get("/saude").json()
    assert s["chave_presente"] and s["dados_gold"] and s["modelo"] == "m/principal"
    p = c.get("/")
    assert p.status_code == 200 and 'aria-live="polite"' in p.text
