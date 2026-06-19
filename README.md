# a11y-auditor-agent

Agente auditor de **acessibilidade** (WCAG 2.2 AA + ABNT NBR 17060) para React Native, orientado ao **diff de um PR** e desenhado como **quality gate de CI**. Sucessor da skill `a11y-static-audit` — agora um processo Python autônomo (Agno) que emite um veredito estruturado (`AuditVerdict`) e um exit code.

## Por que diff + quality gate

- **Escopo = linhas alteradas** (`git diff`), não o grafo de telas inteiro: rápido o bastante para rodar por PR e justo (o autor só responde pelo que mudou).
- **Saída = decisão binária + métrica**: `block: true/false` vira exit code; `coverage` vira métrica; `findings[]` viram comentário no PR.
- **Few-shot embutido**: o catálogo de regras e os pares antes→depois validados do GOL viajam como knowledge do agente (`src/a11y_auditor/data/`).

## Modelo de severidade (3 níveis)

| Tier | O que é | Bloqueia? |
|------|---------|-----------|
| 🔴 `critico` | Regressão: prop de a11y removida de elemento que ainda precisa | **Sim** |
| 🟠 `atencao` | Elemento novo (interativo/visual) sem props obrigatórias | **Sim** |
| 🟡 `warning` | Boa prática / regra de negócio / só verificável em runtime | Não |

`block = any(tier in {critico, atencao})`. O gate **nunca** bloqueia critério não-verificável estaticamente (contraste, truncamento…) — esses viram 🟡 apontando para validação no BrowserStack.

## Performance (é um gate de CI)

- **Curto-circuito sem LLM**: diff vazio ou sem hunk relevante a a11y → aprova sem chamar o modelo.
- **Prefiltro estático** (`is_a11y_relevant`) corta hunks de lógica pura antes do LLM.
- **Diff pré-parseado** em Python → **uma única chamada** ao LLM, sem tools/round-trips.
- **`agno` lazy** → cold-start baixo no caminho de curto-circuito (os módulos determinísticos e os testes rodam sem agno).
- **Prompt caching** do bloco estático de knowledge (constante entre runs) via `cache_system_prompt`; métricas de cache logadas para expor cache miss.

## Estrutura

```
src/a11y_auditor/
  schema.py      # Pydantic: Tier/ChangeType/Detectability, Finding, Coverage, AuditVerdict + compute_block/compute_coverage
  diff.py        # get_pr_diff, resolve_refs (Azure/GitHub), parse_diff_hunks, is_a11y_relevant, build_audit_payload
  knowledge.py   # DS_ALLOWLIST (Tangerina) + build_knowledge_block (cacheável) + build_instructions
  report.py      # render_report determinístico (markdown do comentário de PR)
  agent.py       # build_agent/run_audit — ÚNICO módulo que toca agno (lazy)
  gate.py        # run_gate + main/cli (exit code) + artefato a11y-verdict.json
  __main__.py    # python -m a11y_auditor
  data/          # rules_reference.md, examples_before_after.md, output_contract.md
tests/           # 49 testes (schema, diff, knowledge, report, gate com agno mockado)
```

## Uso

```bash
# Anthropic (default): pip install -e ".[agent]"
# Google Gemini:       pip install -e ".[gemini]"
pip install -e ".[agent]"
export MODEL_API_KEY=...                              # key do provider escolhido
opcional: export A11Y_AUDITOR_MODEL=claude-opus-4-8   (default)

# Rodar o gate (refs autodetectados do CI, ou explícitos)
python -m a11y_auditor --base origin/main --head HEAD
echo "exit code = $?"   # 1 = bloqueado, 0 = aprovado

# Usar Gemini (provider inferido do id, ou via --provider/A11Y_AUDITOR_PROVIDER)
export MODEL_API_KEY=...                              # sua Google API key
python -m a11y_auditor --model gemini-2.5-pro --base origin/main --head HEAD
```

A API key é sempre lida de `MODEL_API_KEY` (nome único, agnóstico de provider) e
passada explicitamente ao modelo. O provider é resolvido por: `--provider` >
env `A11Y_AUDITOR_PROVIDER` > inferência do id (`gemini*` → google, senão anthropic).

Sem `[agent]` (só pydantic), os módulos determinísticos e os testes rodam normalmente; o gate aprova nos caminhos de curto-circuito sem precisar de agno.

## Desenvolvimento

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
```
