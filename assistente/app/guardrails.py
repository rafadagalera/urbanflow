"""Guardrails de código do assistente (complementam as regras do prompt).

Todos os padrões vêm de prompts/guardrails.json, o mesmo arquivo que o chat Node
(web/server.mjs) carrega; aqui fica só a mecânica. Etapas:

- entrada: `normalizar` (NFKC, sem caracteres invisíveis/de controle, espaços colapsados)
  e `preparar_pergunta` (normaliza + mascara dados pessoais antes de ir ao modelo);
- `detectar_injecao`: pré-filtro de alta confiança; se casar, o modelo nem é chamado;
- saída: `verificar_saida` (vazamento do prompt, estigma, dados pessoais, consistência).

Nenhuma função loga texto: devolvem só contagens e nomes de regra.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .schema import Resposta

ARQUIVO = Path(__file__).resolve().parents[1] / "prompts/guardrails.json"
_FLAGS = {"i": re.I}


def _re(padrao: str, flags: str = "") -> re.Pattern:
    f = 0
    for c in flags:
        f |= _FLAGS[c]  # só 'i' é aceito: o resto não tem equivalente garantido no JS
    return re.compile(padrao, f)


@dataclass(frozen=True)
class Regras:
    bruto: dict
    passos: list
    pii: list           # [(tipo, token, regex)]
    injecao: list       # [(id, regex, sobre)]
    mapa: dict
    base64: re.Pattern
    estigma: list       # [(id, regex, sobre)]
    negacao: frozenset
    janela: int
    fim_de_frase: re.Pattern
    aspas: str
    acao_de_campo: re.Pattern
    tipos_sem_pontos: frozenset
    respostas: dict
    pergunta_max: int
    resposta_max: int
    vazamento_secao: str
    vazamento_n: int
    vazamento_permitidos: tuple


@lru_cache(maxsize=4)
def carregar(caminho: str | Path = ARQUIVO) -> Regras:
    d = json.loads(Path(caminho).read_text(encoding="utf-8"))
    passos = []
    for p in d["normalizacao"]["passos"]:
        if p["tipo"] == "regex":
            passos.append(("regex", _re(p["padrao"], p.get("flags", "")), p["por"]))
        elif p["tipo"] == "unicode":
            passos.append(("unicode", p["forma"], None))
        elif p["tipo"] == "remover_categorias":
            passos.append(("categorias", frozenset(p["categorias"]), frozenset(p.get("manter", []))))
        elif p["tipo"] == "aparar":
            passos.append(("aparar", None, None))
        else:
            raise ValueError(f"passo de normalização desconhecido: {p['tipo']}")
    inj, est = d["injecao"], d["estigma"]
    return Regras(
        bruto=d,
        passos=passos,
        pii=[(p["tipo"], p["token"], _re(p["padrao"], p.get("flags", ""))) for p in d["pii"]["padroes"]],
        injecao=[(p["id"], _re(p["padrao"], p.get("flags", "")), p.get("sobre", "dobrado"))
                 for p in inj["padroes"]],
        mapa=inj["mapa"],
        base64=_re(inj["base64"]["padrao"], inj["base64"].get("flags", "")),
        estigma=[(p["id"], _re(p["padrao"], p.get("flags", "")), p.get("sobre", "dobrado"))
                 for p in est["padroes"]],
        negacao=frozenset(est["negacao"]),
        janela=int(est["janela"]),
        fim_de_frase=_re(est["fim_de_frase"]),
        aspas=est["aspas"],
        acao_de_campo=_re(d["acao_de_campo"]["padrao"], d["acao_de_campo"].get("flags", "")),
        tipos_sem_pontos=frozenset(d["consistencia"]["tipos_sem_pontos_nem_acao"]),
        respostas=d["respostas"],
        pergunta_max=int(d["limites"]["pergunta_max"]),
        resposta_max=int(d["limites"]["resposta_max"]),
        vazamento_secao=d["vazamento"]["secao"],
        vazamento_n=int(d["vazamento"]["n_palavras"]),
        vazamento_permitidos=tuple(d["vazamento"].get("permitidos", [])),
    )


# ---------------------------------------------------------------- entrada

def normalizar(texto: str, regras: Regras | None = None) -> str:
    """Aplica os passos de normalizacao.passos, em ordem."""
    regras = regras or carregar()
    t = texto or ""
    for tipo, a, b in regras.passos:
        if tipo == "unicode":
            t = unicodedata.normalize(a, t)
        elif tipo == "regex":
            t = a.sub(b, t)
        elif tipo == "categorias":
            t = "".join(c for c in t if c in b or unicodedata.category(c) not in a)
        else:  # aparar
            t = t.strip(" \n")
    return t


def dobrar(texto: str) -> str:
    """Forma só para detecção: sem acentos (NFD sem Mn) e minúscula."""
    nfd = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").lower()


def mascarar(texto: str, regras: Regras | None = None) -> tuple[str, dict[str, int]]:
    """Troca dados pessoais por tokens ('[CPF removido]'). Devolve o texto e a contagem por tipo."""
    regras = regras or carregar()
    contagem: dict[str, int] = {}
    t = texto or ""
    for tipo, token, rx in regras.pii:
        def trocar(m, tipo=tipo, token=token):
            contagem[tipo] = contagem.get(tipo, 0) + 1
            return (m.group(1) or "") + token
        t = rx.sub(trocar, t)
    return t, contagem


@dataclass
class PerguntaPreparada:
    texto: str                                   # normalizada e mascarada: é o que vai ao modelo
    pii: dict[str, int] = field(default_factory=dict)


def preparar_pergunta(pergunta: str, regras: Regras | None = None) -> PerguntaPreparada:
    """Normaliza e mascara a pergunta antes de montar as mensagens do modelo."""
    regras = regras or carregar()
    texto, pii = mascarar(normalizar(pergunta, regras), regras)
    return PerguntaPreparada(texto, pii)


def _mapear(texto: str, mapa: dict) -> str:
    return "".join(mapa.get(c, c) for c in texto)


def _decodificados(texto: str, regras: Regras) -> list[str]:
    """Trechos em base64 da pergunta, decodificados (só os que viram UTF-8 válido)."""
    saida = []
    for m in regras.base64.finditer(texto):
        s = m.group(0)
        try:
            b = base64.b64decode(s + "=" * (-len(s) % 4), validate=True)
            saida.append(b.decode("utf-8"))
        except (binascii.Error, ValueError):
            continue
    return saida


def detectar_injecao(pergunta: str, regras: Regras | None = None) -> str | None:
    """id da primeira regra de injeção que casar, ou None. Espera a pergunta já normalizada."""
    regras = regras or carregar()
    normalizado = normalizar(pergunta, regras)
    alvos = [_mapear(dobrar(normalizado), regras.mapa)]
    alvos += [_mapear(dobrar(normalizar(d, regras)), regras.mapa) for d in _decodificados(normalizado, regras)]
    for id_, rx, sobre in regras.injecao:
        if sobre == "normalizado":
            if rx.search(normalizado):
                return id_
        elif any(rx.search(a) for a in alvos):
            return id_
    return None


def resposta_bloqueio(regras: Regras | None = None) -> Resposta:
    regras = regras or carregar()
    return Resposta(resposta=regras.respostas["injecao"], tipo="fora_de_escopo", fontes=[], pontos_citados=[],
                    acao_sugerida=None, precisa_humano=False, confianca="alta")


# ---------------------------------------------------------------- saída

def exige_humano(acao: str | None, regras: Regras | None = None) -> bool:
    regras = regras or carregar()
    return bool(regras.acao_de_campo.search(acao or ""))


def _palavras(texto: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", dobrar(texto))


def _ngramas(palavras: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(palavras[i:i + n]) for i in range(len(palavras) - n + 1)}


def secao_regras(sistema: str, regras: Regras | None = None) -> str:
    """Trecho do sistema.md da linha `## Regras` até a próxima linha `## `."""
    regras = regras or carregar()
    linhas, dentro, saida = (sistema or "").splitlines(), False, []
    for ln in linhas:
        if ln.startswith(regras.vazamento_secao):
            dentro = True
            continue
        if dentro and ln.startswith("## "):
            break
        if dentro:
            saida.append(ln)
    return "\n".join(saida)


@lru_cache(maxsize=16)
def _ngramas_secretos(sistema: str, n: int, permitidos: tuple) -> frozenset:
    """n-gramas das regras do prompt, menos as frases que o modelo deve mesmo dizer ao usuário."""
    livres = set().union(*(_ngramas(_palavras(f), n) for f in permitidos)) if permitidos else set()
    return frozenset(_ngramas(_palavras(secao_regras(sistema)), n) - livres)


def vazou_prompt(texto: str, sistema: str, publico: str = "", regras: Regras | None = None) -> bool:
    """True se `texto` repete n palavras seguidas das regras do sistema.md (fora do que é público)."""
    regras = regras or carregar()
    n = regras.vazamento_n
    segredos = _ngramas_secretos(sistema or "", n, regras.vazamento_permitidos)
    if not segredos:
        return False
    achados = _ngramas(_palavras(texto), n) & segredos
    if achados and publico:
        achados -= _ngramas(_palavras(publico), n)
    return bool(achados)


def estigma(texto: str, regras: Regras | None = None) -> str | None:
    """id da primeira afirmação estigmatizante não negada nem citada, ou None."""
    regras = regras or carregar()
    alvos = {"dobrado": dobrar(texto), "normalizado": unicodedata.normalize("NFC", texto or "")}
    for id_, rx, sobre in regras.estigma:
        t = alvos[sobre]
        for m in rx.finditer(t):
            antes = dobrar(t[:m.start()])
            if sum(antes.count(a) for a in regras.aspas) % 2 == 1:
                continue  # trecho entre aspas: citação, não afirmação
            frase = regras.fim_de_frase.split(antes)[-1]
            janela = re.findall(r"[a-z0-9]+", frase)[-regras.janela:]
            if regras.negacao & set(janela) or regras.negacao & set(re.findall(r"[a-z0-9]+", dobrar(m.group(0)))):
                continue
            return id_
    return None


def _cortar(texto: str, limite: int) -> str:
    return texto if len(texto) <= limite else texto[:limite - 1].rstrip() + "…"


def verificar_saida(r: Resposta, sistema: str = "", publico: str = "", fontes_ctx=frozenset(),
                    regras: Regras | None = None) -> tuple[Resposta, list[str]]:
    """Checagens de saída, depois da pós-validação. Devolve a resposta (talvez trocada) e eventos.

    Ordem: vazamento do prompt → estigma → máscara de dados pessoais → consistência → limite
    de tamanho. `publico` é o texto do contexto (manual + dados): repetir o manual não é vazamento.
    """
    regras = regras or carregar()
    eventos: list[str] = []
    if sistema and any(vazou_prompt(c, sistema, publico, regras) for c in (r.resposta, r.acao_sugerida or "")):
        eventos.append("vazamento_prompt")
        r = r.model_copy(update={"resposta": regras.respostas["vazamento"], "tipo": "fora_de_escopo",
                                 "fontes": [], "pontos_citados": [], "acao_sugerida": None,
                                 "precisa_humano": False, "confianca": "baixa"})
    else:
        regra = estigma(r.resposta, regras) or estigma(r.acao_sugerida or "", regras)
        if regra:
            eventos.append(f"estigma:{regra}")
            r = r.model_copy(update={"resposta": regras.respostas["estigma"], "pontos_citados": [],
                                     "acao_sugerida": None, "confianca": "baixa",
                                     "fontes": ["manual#indice"] if "manual#indice" in fontes_ctx else []})
    resposta, n1 = mascarar(r.resposta, regras)
    acao, n2 = mascarar(r.acao_sugerida, regras) if r.acao_sugerida is not None else (None, {})
    for tipo in sorted(set(n1) | set(n2)):
        eventos.append(f"pii_saida:{tipo}={n1.get(tipo, 0) + n2.get(tipo, 0)}")
    atualizar = {"resposta": _cortar(resposta, regras.resposta_max), "acao_sugerida": acao}
    if r.tipo in regras.tipos_sem_pontos and (r.pontos_citados or r.acao_sugerida is not None):
        eventos.append("consistencia_" + r.tipo)
        atualizar.update({"pontos_citados": [], "acao_sugerida": None})
    return r.model_copy(update=atualizar), eventos
