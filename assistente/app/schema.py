"""Entrada e saída do assistente (spec §4.4).

O Pydantic valida; o JSON Schema enviado ao provedor é escrito à mão, plano e
estrito (sem $defs/anyOf/title, que quebram o modo strict em alguns provedores).
O limite de 1200 caracteres fica só no Pydantic.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_PERGUNTA = 500
MAX_RESPOSTA = 1200


class Pergunta(BaseModel):
    pergunta: str = Field(min_length=1, max_length=MAX_PERGUNTA)

    @field_validator("pergunta")
    @classmethod
    def nao_vazia(cls, v: str) -> str:
        # normaliza antes de checar: só caracteres invisíveis/espaços = vazia (422);
        # o limite vale de novo depois, porque o NFKC pode expandir o texto.
        from .guardrails import normalizar  # import tardio: guardrails importa este módulo
        v = normalizar(v)
        if not v:
            raise ValueError("pergunta vazia")
        if len(v) > MAX_PERGUNTA:
            raise ValueError(f"pergunta com mais de {MAX_PERGUNTA} caracteres após normalização")
        return v


class Resposta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resposta: str = Field(max_length=MAX_RESPOSTA)
    tipo: Literal["uso", "dados", "fora_de_escopo", "erro"]
    fontes: list[str]
    pontos_citados: list[str]
    acao_sugerida: str | None
    precisa_humano: bool
    confianca: Literal["alta", "media", "baixa"]


JSON_SCHEMA = {
    "name": "resposta_urbancare",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "resposta": {"type": "string", "description": "Texto ao usuário, em pt-BR, até 1200 caracteres."},
            "tipo": {"type": "string", "enum": ["uso", "dados", "fora_de_escopo", "erro"]},
            "fontes": {"type": "array", "items": {"type": "string"},
                       "description": "Rótulos [fonte: ...] do contexto usados na resposta."},
            "pontos_citados": {"type": "array", "items": {"type": "string"},
                               "description": "ponto_id citados, exatamente como no contexto."},
            "acao_sugerida": {"type": ["string", "null"]},
            "precisa_humano": {"type": "boolean"},
            "confianca": {"type": "string", "enum": ["alta", "media", "baixa"]},
        },
        "required": ["resposta", "tipo", "fontes", "pontos_citados", "acao_sugerida", "precisa_humano",
                     "confianca"],
    },
}


def resposta_erro(msg="Não consegui responder agora. Tente de novo em instantes; se persistir, "
                      "procure a equipe técnica.") -> Resposta:
    return Resposta(resposta=msg, tipo="erro", fontes=[], pontos_citados=[], acao_sugerida=None,
                    precisa_humano=False, confianca="baixa")
