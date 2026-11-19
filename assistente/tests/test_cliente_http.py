import json

import httpx

from app.llm import ClienteHTTP


def transporte(capturado, suportados):
    def handler(req: httpx.Request):
        if req.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "m/sem-temp", "supported_parameters": suportados}]})
        capturado.append(json.loads(req.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}], "usage": {}})
    return httpx.MockTransport(handler)


def test_omite_temperature_se_modelo_nao_aceita(cfg):
    cap = []
    c = ClienteHTTP(cfg, transport=transporte(cap, ["max_tokens", "response_format", "structured_outputs"]))
    c.completar("m/sem-temp", [{"role": "user", "content": "oi"}], {"type": "json_object"})
    c.completar("m/sem-temp", [{"role": "user", "content": "oi"}], {"type": "json_object"})
    assert "temperature" not in cap[0] and cap[0]["provider"] == {"require_parameters": True}
    assert len(cap) == 2  # /models consultado uma vez só (cache)


def test_envia_temperature_se_aceita_ou_lista_indisponivel(cfg):
    cap = []
    c = ClienteHTTP(cfg, transport=transporte(cap, ["temperature", "response_format"]))
    c.completar("m/sem-temp", [], {"type": "json_object"})
    c.completar("m/outro-desconhecido", [], {"type": "json_object"})
    assert cap[0]["temperature"] == cfg.temperatura and cap[1]["temperature"] == cfg.temperatura
