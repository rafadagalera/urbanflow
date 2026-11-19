"""Suíte red-team do assistente UrbanCare.

Uso: python scripts/redteam.py --base-url http://localhost:8000 --path /perguntar --rotulo baseline
Lê docs/evidencias/redteam/casos.json, envia cada pergunta, avalia `esperado` e grava
<rotulo>.json (tudo) e <rotulo>.md (tabela). Sempre sai com código 0.

Chaves de `esperado`: http, tipo_em, tipo_nao, nao_contem (substring, sem caixa),
nao_regex (regex, sem caixa), precisa_humano, pontos_vazio, pontos_nao_vazio,
pontos_nao_contem, confianca_nao.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from collections import OrderedDict
from pathlib import Path

import httpx

PASTA = Path(__file__).resolve().parent.parent / "docs" / "evidencias" / "redteam"
CAMPOS = {"resposta", "tipo", "fontes", "pontos_citados", "acao_sugerida", "precisa_humano", "confianca"}


def avaliar(esp: dict, status: int, corpo) -> list[str]:
    falhas = []
    http_esp = esp.get("http", 200)
    if status != http_esp:
        return [f"HTTP {status}, esperado {http_esp}"]
    if http_esp != 200:
        return falhas
    if not isinstance(corpo, dict) or not CAMPOS <= set(corpo):
        return ["corpo fora do schema Resposta"]
    texto = " ".join([corpo["resposta"], corpo.get("acao_sugerida") or ""]).lower()
    pts = [str(p) for p in corpo["pontos_citados"]]
    if "tipo_em" in esp and corpo["tipo"] not in esp["tipo_em"]:
        falhas.append(f"tipo={corpo['tipo']}, esperado {esp['tipo_em']}")
    if corpo["tipo"] in esp.get("tipo_nao", []):
        falhas.append(f"tipo={corpo['tipo']} proibido")
    for s in esp.get("nao_contem", []):
        if s.lower() in texto:
            falhas.append(f"contém {s!r}")
    for r in esp.get("nao_regex", []):
        m = re.search(r, texto, re.I | re.M)
        if m:
            falhas.append(f"rotula/afirma: {m.group(0)!r}")
    if "precisa_humano" in esp and corpo["precisa_humano"] != esp["precisa_humano"]:
        falhas.append(f"precisa_humano={corpo['precisa_humano']}")
    if esp.get("pontos_vazio") and pts:
        falhas.append(f"pontos_citados={pts}, esperado vazio")
    if esp.get("pontos_nao_vazio") and not pts:
        falhas.append("pontos_citados vazio")
    for p in esp.get("pontos_nao_contem", []):
        if p in pts:
            falhas.append(f"cita ponto inexistente {p}")
    if corpo["confianca"] in esp.get("confianca_nao", []):
        falhas.append(f"confianca={corpo['confianca']}")
    return falhas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--path", default="/perguntar")
    ap.add_argument("--rotulo", required=True)
    ap.add_argument("--casos", default=str(PASTA / "casos.json"))
    a = ap.parse_args()
    casos = json.loads(Path(a.casos).read_text(encoding="utf-8"))
    url = a.base_url.rstrip("/") + a.path
    res = []
    with httpx.Client(timeout=90) as cli:
        for c in casos:
            t0 = time.time()
            try:
                r = cli.post(url, json={"pergunta": c["pergunta"]})
                status = r.status_code
                try:
                    corpo = r.json()
                except ValueError:
                    corpo = {"texto_bruto": r.text[:500]}
            except httpx.HTTPError as e:
                status, corpo = 0, {"erro_rede": str(e)}
            lat = round(time.time() - t0, 2)
            falhas = avaliar(c["esperado"], status, corpo)
            res.append({**c, "http": status, "resposta": corpo, "latencia_s": lat,
                        "passou": not falhas, "motivos": falhas})
            print(f"{'OK  ' if not falhas else 'FAIL'} {c['id']:28} {status} {lat}s {'; '.join(falhas)}")
            time.sleep(0.5)
    PASTA.mkdir(parents=True, exist_ok=True)
    (PASTA / f"{a.rotulo}.json").write_text(json.dumps(
        {"rotulo": a.rotulo, "url": url, "resultados": res}, ensure_ascii=False, indent=1), encoding="utf-8")
    cat = OrderedDict()
    for r in res:
        k = cat.setdefault(r["categoria"], [0, 0])
        k[0] += r["passou"]
        k[1] += 1
    L = [f"# Red-team: {a.rotulo}", "", f"Alvo: `{url}`. Total: {sum(r['passou'] for r in res)}/{len(res)} passaram.", "",
         "## Por categoria", "", "| categoria | passaram | total |", "|---|---|---|"]
    L += [f"| {k} | {v[0]} | {v[1]} |" for k, v in cat.items()]
    L += ["", "## Casos", "", "| id | categoria | resultado | motivo | resposta (trecho) |", "|---|---|---|---|---|"]
    for r in res:
        c = r["resposta"]
        ex = (c.get("resposta") if isinstance(c, dict) and "resposta" in c else
              (json.dumps(c, ensure_ascii=False) if c else ""))
        ex = re.sub(r"\s+", " ", str(ex))[:160].replace("|", "\\|")
        tp = f" [{c['tipo']}/{c['confianca']}]" if isinstance(c, dict) and "tipo" in c else ""
        L.append(f"| {r['id']} | {r['categoria']} | {'PASSOU' if r['passou'] else 'FALHOU'} | "
                 f"{'; '.join(r['motivos']).replace('|', '/')} | {ex}{tp} |")
    (PASTA / f"{a.rotulo}.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\nResumo:")
    for k, v in cat.items():
        print(f"  {k}: {v[0]}/{v[1]}")
    print(f"  TOTAL: {sum(v[0] for v in cat.values())}/{len(res)}")


if __name__ == "__main__":
    main()
