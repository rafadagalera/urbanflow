"""Configuração por variáveis de ambiente (spec §4.2). Valor vazio = padrão."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _env(nome, padrao=""):
    v = os.environ.get(nome, "").strip()
    return v or padrao


@dataclass(frozen=True)
class Config:
    api_key: str = field(default_factory=lambda: _env("OPENROUTER_API_KEY"))
    base_url: str = field(default_factory=lambda: _env("LLM_BASE_URL", "https://openrouter.ai/api/v1"))
    modelo: str = field(default_factory=lambda: _env("LLM_MODEL", "anthropic/claude-haiku-5.5"))
    modelo_reserva: str = field(default_factory=lambda: _env("LLM_FALLBACK_MODEL", "openai/gpt-6-luna"))
    timeout_s: float = field(default_factory=lambda: float(_env("LLM_TIMEOUT_S", "30")))
    temperatura: float = field(default_factory=lambda: float(_env("LLM_TEMPERATURE", "0.2")))
    max_tokens: int = field(default_factory=lambda: int(_env("LLM_MAX_TOKENS", "2000")))
    database_url: str = field(default_factory=lambda: _env("DATABASE_URL"))
    manual_path: Path = field(default_factory=lambda: Path(_env("MANUAL_PATH", str(RAIZ.parent / "docs/manual.md"))))
    prompt_path: Path = field(default_factory=lambda: Path(_env("PROMPT_PATH", str(RAIZ / "prompts/sistema.md"))))

    @property
    def modelos(self) -> list[str]:
        return [m for m in dict.fromkeys([self.modelo, self.modelo_reserva]) if m]
