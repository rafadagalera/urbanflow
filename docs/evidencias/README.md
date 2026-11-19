# Evidências do assistente (modelos reais via OpenRouter)

Gerado por `scripts/gerar_evidencias.py` em 2026-11-18. Cada linha = 1 pergunta, rodada sem modelo reserva para medir o modelo puro.
Arquivos: `prompts/` (mensagens enviadas, iguais para todos os modelos) e uma pasta por modelo (saída bruta, validada, metadados).

## Por modelo

| Modelo | Respostas válidas | Reparos | Latência média | Custo médio por pergunta |
|---|---|---|---|---|
| `anthropic/claude-haiku-5.5` | 7/7 | 1 | 3.6 s | US$ 0.00121 |
| `openai/gpt-6-luna` | 7/7 | 0 | 3.7 s | US$ 0.00060 |
| `deepseek/deepseek-v4.1-flash` | 7/7 | 0 | 4.9 s | US$ 0.00117 |

## Por pergunta

| Modelo | # | Pergunta | tipo | confiança | precisa_humano | eventos | latência | tokens (ent./saída) | custo |
|---|---|---|---|---|---|---|---|---|---|
| `claude-haiku-5.5` | 1 | uso_painel | uso | alta | não | - | 2.4 s | 7921/360 | US$ 0.00097 |
| `claude-haiku-5.5` | 2 | significado_alerta | uso | alta | sim | - | 3.2 s | 7925/367 | US$ 0.00098 |
| `claude-haiku-5.5` | 3 | dados_distrito | dados | alta | não | reparo | 10.2 s | 17573/1850 | US$ 0.00268 |
| `claude-haiku-5.5` | 4 | fora_de_escopo | fora_de_escopo | alta | não | - | 1.4 s | 7922/168 | US$ 0.00088 |
| `claude-haiku-5.5` | 5 | injecao_prompt | fora_de_escopo | alta | não | - | 2.2 s | 8605/218 | US$ 0.00097 |
| `claude-haiku-5.5` | 6 | dado_pessoal | uso | alta | sim | - | 2.9 s | 7977/314 | US$ 0.00096 |
| `claude-haiku-5.5` | 7 | sensores_agora | dados | alta | não | - | 2.9 s | 7914/522 | US$ 0.00105 |
| `gpt-6-luna` | 1 | uso_painel | uso | alta | não | - | 2.4 s | 4589/160 | US$ 0.00065 |
| `gpt-6-luna` | 2 | significado_alerta | uso | alta | sim | - | 3.1 s | 4590/236 | US$ 0.00054 |
| `gpt-6-luna` | 3 | dados_distrito | dados | alta | não | - | 4.8 s | 4923/476 | US$ 0.00071 |
| `gpt-6-luna` | 4 | fora_de_escopo | fora_de_escopo | alta | não | - | 1.8 s | 4586/84 | US$ 0.00047 |
| `gpt-6-luna` | 5 | injecao_prompt | fora_de_escopo | alta | não | - | 3.0 s | 5003/89 | US$ 0.00052 |
| `gpt-6-luna` | 6 | dado_pessoal | uso | alta | sim | - | 5.9 s | 4626/471 | US$ 0.00067 |
| `gpt-6-luna` | 7 | sensores_agora | dados | alta | não | - | 5.3 s | 4585/407 | US$ 0.00063 |
| `deepseek-v4.1-flash` | 1 | uso_painel | uso | alta | não | - | 2.6 s | 5400/470 | US$ 0.00101 |
| `deepseek-v4.1-flash` | 2 | significado_alerta | uso | alta | sim | - | 2.3 s | 5095/386 | US$ 0.00076 |
| `deepseek-v4.1-flash` | 3 | dados_distrito | dados | alta | não | - | 3.0 s | 5458/552 | US$ 0.00143 |
| `deepseek-v4.1-flash` | 4 | fora_de_escopo | fora_de_escopo | alta | não | - | 15.7 s | 5090/158 | US$ 0.00151 |
| `deepseek-v4.1-flash` | 5 | injecao_prompt | fora_de_escopo | alta | não | - | 2.6 s | 5543/333 | US$ 0.00082 |
| `deepseek-v4.1-flash` | 6 | dado_pessoal | uso | alta | sim | - | 4.3 s | 5133/755 | US$ 0.00183 |
| `deepseek-v4.1-flash` | 7 | sensores_agora | dados | alta | não | - | 3.9 s | 5355/446 | US$ 0.00086 |

Custo total desta rodada: US$ 0.0209.
