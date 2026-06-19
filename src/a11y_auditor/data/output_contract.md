---
job: agente-auditor-a11y
task: TASK-001
tags: [a11y, contract, output, pydantic, quality-gate, wcag, ci]
date: 2026-06-18
---

# Contrato de Saída — `AuditVerdict` (TASK-001)

> Entregável da [[Tasks/TASK-001]]. Define **o que o agente devolve** e **o que a pipeline embute no comentário do PR**. Centrado em dois produtos: (1) o **veredito de merge** (`block: true/false`) e (2) um **relatório curto** dos principais pontos de a11y do diff, com solução sugerida. Ver contexto em [[_Overview]] e arquitetura em [[Arquitetura - Agente Agno]].
>
> **Escopo de conformidade**: por ora **apenas Nível AA** (= critérios A + AA; AAA fora). **Display Orientation** está fora — o app é travado em retrato por decisão de produto.

---

## 1. Modelo de severidade (3 níveis, orientado ao diff)

A severidade **não** é fixa por regra — depende do **tipo de mudança** no diff. A mesma regra (ex.: "falta `accessibilityLabel`") vira **crítico** se uma prop foi *removida*, ou **atenção** se um componente *novo* nasceu sem ela.

| Nível | Símbolo | O que é | Origem no diff | Bloqueia merge? |
|-------|---------|---------|----------------|-----------------|
| **Crítico** | 🔴 | **Regressão de acessibilidade**: uma prop de a11y existente foi **removida** ou enfraquecida de um elemento que ainda precisa dela. "Não podemos perder acessibilidade." | Linha **removida** (`-`) que tinha a prop, sem reposição equivalente | **Sim** |
| **Atenção** | 🟠 | **Componente/elemento novo** (interativo ou visual relevante) **sem** as props de a11y obrigatórias. | Linha **adicionada** (`+`) de elemento novo não coberto | **Sim** |
| **Warning** | 🟡 | Boa prática, ou ponto que **depende de regra de negócio**, ou critério **só verificável em runtime** (contraste, magnificação, etc.). | Qualquer | **Não** |

### Nuance pai → filhos (a que você pediu)
Quando uma prop de a11y **some dos filhos mas aparece no componente pai** (ex.: o pai vira um único nó focável via `accessible={true}` e agrupa o anúncio), isso **pode ser regra de negócio legítima** — não necessariamente perda. Nesse caso o agente **rebaixa de 🔴 crítico para 🟡 warning**, sinalizando "revisar: label movido para o pai — intencional?". Só vira 🔴 se a prop sumiu e **não reapareceu** em nenhum ancestral do mesmo hunk.

### Regra do `block`
```python
def compute_block(findings: list[Finding]) -> bool:
    return any(f.tier in (Tier.critico, Tier.atencao) for f in findings)
```
- 🔴 **e** 🟠 bloqueiam (perder a11y e nascer sem a11y são ambos inaceitáveis).
- 🟡 **nunca** bloqueia — só informa.
- **O gate nunca bloqueia em critério que não consegue verificar estaticamente** (ver coluna "Auditável" no §5). Runtime-only ⇒ no máximo 🟡.

> 🎚️ **Botão de calibração**: se o rollout inicial precisar ser mais leve, mudar para `return any(f.tier == Tier.critico)` (só regressão bloqueia; componente novo sem a11y vira aviso). Decisão registrável no [[_Overview]].

---

## 2. Schema Pydantic (`response_model` do Agno)

```python
from enum import Enum
from pydantic import BaseModel, Field


class Tier(str, Enum):
    critico = "critico"   # 🔴 regressão — bloqueia
    atencao = "atencao"   # 🟠 novo sem a11y — bloqueia
    warning = "warning"   # 🟡 boa prática / regra de negócio / runtime — não bloqueia


class ChangeType(str, Enum):
    removed = "removed"     # prop/elemento saiu do diff (lado '-')
    added = "added"         # elemento novo no diff (lado '+')
    modified = "modified"   # elemento alterado


class Detectability(str, Enum):
    static = "static"       # ✅ verificável no diff (presença/ausência de prop)
    partial = "partial"     # 🟡 heurística estática; pode exigir contexto/runtime
    runtime = "runtime"     # ❌ só em device/render (BrowserStack) — nunca bloqueia


class Finding(BaseModel):
    rule_id: str = Field(..., description="ex: a11y/missing-label-on-touchable")
    criterion: str = Field(..., description="nome do critério, ex: 'Interactive Element Accessibility Label'")
    tier: Tier
    change_type: ChangeType
    detectability: Detectability
    file: str
    line: int                       # linha no arquivo pós-PR (lado '+'); para removed, a linha do hunk
    message: str                    # pt-BR, 1 frase
    fix: str                        # solução sugerida, pt-BR, curta
    wcag: list[str] = []            # ex: ["1.1.1", "4.1.2"]
    wcag_level: str = "AA"          # "A" | "AA"
    abnt: list[str] = []
    snippet: str                    # linha ofensora


class Coverage(BaseModel):
    interactive_added: int          # elementos interativos/visuais relevantes adicionados no PR
    compliant: int                  # quantos já vêm com a11y adequada
    percent: float                  # compliant / interactive_added * 100 (100.0 se denominador 0)
    regressions: int                # nº de findings 🔴 (props removidas)


class AuditVerdict(BaseModel):
    block: bool = Field(..., description="True se há finding 🔴 crítico OU 🟠 atenção")
    coverage: Coverage
    findings: list[Finding]
    summary: str                    # 1-2 frases, pt-BR
    report_markdown: str            # tabela pronta para colar no comentário do PR (ver §3)
```

> `response_model=AuditVerdict` faz o Agno validar e forçar o LLM a preencher o schema. `report_markdown` é renderizado pelo próprio agente (ou pós-processado a partir de `findings`) e é **o que a pipeline cola no PR**.

---

## 3. Relatório embutido no PR (curto, com solução)

Cabeçalho com o veredito + uma tabela enxuta. **Uma linha por finding**, ordenado 🔴 → 🟠 → 🟡.

### Template

```markdown
## ♿ Auditoria de Acessibilidade — {✅ Merge permitido | ⛔ Merge bloqueado}

**Cobertura do diff:** {percent}% ({compliant}/{interactive_added} elementos novos cobertos) · **Regressões:** {regressions} · **Findings:** 🔴 {n} · 🟠 {n} · 🟡 {n}

> {summary}

| | Arquivo:linha | Critério (WCAG) | O que aconteceu | Solução sugerida |
|--|---------------|-----------------|-----------------|------------------|
| 🔴 | `Header.tsx:42` | Interactive Element Accessibility Label (4.1.2) | `accessibilityLabel` removido do botão de idioma | Re-adicionar `accessibilityLabel={translate('...')}` |
| 🟠 | `SeatItem.tsx:18` | Switch Element Accessibility Label (1.3.1, 4.1.2) | `Switch` novo sem label nem `accessibilityState` | Add `accessibilityLabel` + `accessibilityState={{checked}}` |
| 🟡 | `Banner.tsx:7` | Text Element Color Contrast (1.4.3) | Não verificável no diff | Validar contraste ≥ 4.5:1 no BrowserStack |

<sub>Nível AA · 🔴 regressão e 🟠 novo-sem-a11y bloqueiam · 🟡 não bloqueia · critérios de runtime validados no BrowserStack</sub>
```

### Regras de renderização
- Se `findings` vazio: tabela some, cabeçalho vira `✅ Merge permitido — nenhum ponto de acessibilidade no diff`.
- `Solução sugerida` = campo `fix`, sempre baseado nos exemplos de [[Exemplos Antes-Depois A11Y]].
- Truncar a tabela em ~15 linhas; se houver mais, somar o restante em `+N findings adicionais` (e `log` o que foi cortado — nunca truncar em silêncio).

---

## 4. Exemplo de JSON serializado (artefato de CI)

```json
{
  "block": true,
  "coverage": { "interactive_added": 4, "compliant": 2, "percent": 50.0, "regressions": 1 },
  "summary": "1 regressão crítica (label removido) e 1 elemento novo sem rótulo. Merge bloqueado.",
  "findings": [
    {
      "rule_id": "a11y/missing-label-on-touchable",
      "criterion": "Interactive Element Accessibility Label",
      "tier": "critico", "change_type": "removed", "detectability": "static",
      "file": "modules/Home/Header.tsx", "line": 42,
      "message": "accessibilityLabel removido do TgrButtonIcon de idioma.",
      "fix": "Re-adicionar accessibilityLabel={translate('Home.A11y.Preferences')}.",
      "wcag": ["1.1.1", "4.1.2"], "wcag_level": "A", "abnt": ["7.2.1"],
      "snippet": "- accessibilityLabel={translate('Home.A11y.Preferences')}"
    }
  ],
  "report_markdown": "## ♿ Auditoria de Acessibilidade — ⛔ Merge bloqueado\n..."
}
```

---

## 5. Catálogo de critérios — BrowserStack → WCAG AA → regra → auditável

Todos os critérios que você listou, mapeados para nível **AA**, com `rule_id` (reusando o catálogo de 21 regras do `REFERENCE.md` quando há equivalência) e **se dá para auditar no diff estático**. `Tier típico` indica o nível **quando o elemento é novo / a prop foi removida**; runtime-only é sempre 🟡.

> Legenda auditável: ✅ estático (presença/ausência de prop) · 🟡 parcial (heurística, pode pedir contexto) · ❌ runtime (só em device — vira 🟡, **não bloqueia**).

### Accessibility Labels
| Critério | rule_id | WCAG (nível) | Auditável | Tier típico |
|----------|---------|--------------|-----------|-------------|
| Interactive Element Accessibility Label | `a11y/missing-label-on-touchable` | 1.1.1, 4.1.2 (A) | ✅ | 🔴/🟠 |
| Missing View Type in Spoken Output | `a11y/missing-role-on-button-like` | 4.1.2 (A) | ✅ | 🔴/🟠 |
| Editable Element Accessibility Label | `a11y/form-input-without-label` | 1.3.1, 3.3.2 (A) | ✅ | 🔴/🟠 |
| Content Description in Editable Elements | `a11y/form-input-without-label` | 1.3.1, 3.3.2 (A) | ✅ | 🔴/🟠 |
| Accessible Input Field Labels (Exp.) | `a11y/form-input-without-label` | 1.3.1, 3.3.2 (A) | ✅ | 🟠 |
| Switch Element Accessibility Label | `a11y/switch-without-label` | 1.3.1, 4.1.2 (A) | ✅ | 🔴/🟠 |
| Checkbox Element Accessibility Label | `a11y/checkbox-without-label` | 1.3.1, 4.1.2 (A) | ✅ | 🔴/🟠 |
| Meaningful accessibility label for images | `a11y/image-without-alt` | 1.1.1 (A) | ✅ | 🔴/🟠 |
| Label in Name | `a11y/label-in-name` | 2.5.3 (A) | 🟡 | 🟡 |
| Accessibility Label at front (BP) | `a11y/label-text-at-front` | boa prática | 🟡 | 🟡 |
| Link Text Purpose | `a11y/link-text-purpose` | 2.4.4 (A) | 🟡 | 🟡 |
| Duplicate State Info in Spoken Output | `a11y/duplicate-state-in-label` | 4.1.2 / BP | ✅ | 🟡 |
| Duplicate Type Info in Spoken Output | `a11y/duplicate-role-in-label` | 4.1.2 / BP | ✅ | 🟡 |
| Duplicate Accessibility Label on Screen | `a11y/duplicate-label-on-screen` | 4.1.2 / BP | 🟡 | 🟡 |
| Special-Character Element Accessibility Label (BP) | `a11y/special-char-label` | boa prática | ✅ | 🟡 |

### Accessible Images
| Critério | rule_id | WCAG (nível) | Auditável | Tier típico |
|----------|---------|--------------|-----------|-------------|
| Images with Text | `a11y/image-of-text` | 1.4.5 (AA) | ❌ runtime | 🟡 |

### Content Structure
| Critério | rule_id | WCAG (nível) | Auditável | Tier típico |
|----------|---------|--------------|-----------|-------------|
| Missing Heading (Exp.) | `a11y/heading-without-role` | 1.3.1 (A), 2.4.6 (AA) | ✅ | 🟠 |
| Incorrect Heading (Exp.) | `a11y/heading-hierarchy-skipped` | 1.3.1, 2.4.6 (AA) | 🟡 | 🟡 |

### Text resize
| Critério | rule_id | WCAG (nível) | Auditável | Tier típico |
|----------|---------|--------------|-----------|-------------|
| Font Magnification Support | `a11y/missing-dynamic-type-support` | 1.4.4 (AA) | ✅ (detecta `allowFontScaling={false}` / `maxFontSizeMultiplier=1`) | 🔴 se removeu escala / 🟠 se add bloqueio |
| Text Truncation | `a11y/text-truncation` | 1.4.4, 1.4.10 (AA) | ❌ runtime | 🟡 |
| Readable Font Size (BP) | `a11y/readable-font-size` | boa prática | 🟡 (fontSize literal pequeno) | 🟡 |

### Color Contrast
| Critério | rule_id | WCAG (nível) | Auditável | Tier típico |
|----------|---------|--------------|-----------|-------------|
| Text Element Color Contrast (Minimum) | `a11y/text-contrast` | 1.4.3 (AA) | ❌ runtime | 🟡 |
| Non-Text Element Color Contrast | `a11y/non-text-contrast` | 1.4.11 (AA) | ❌ runtime | 🟡 |

### Readable Text and Layout
| Critério | rule_id | WCAG (nível) | Auditável | Tier típico |
|----------|---------|--------------|-----------|-------------|
| Readable Text Spacing (BP) | `a11y/text-spacing` | 1.4.12 (AA) | ❌ runtime | 🟡 |
| Responsive Containers (Exp.) | `a11y/responsive-containers` | 1.4.10 (AA) | 🟡 (width/height fixos) | 🟡 |
| Two-Dimensional Scrolling (Exp.) | `a11y/two-dimensional-scrolling` | 1.4.10 (AA) | 🟡 | 🟡 |

### Focus and Navigation
| Critério | rule_id | WCAG (nível) | Auditável | Tier típico |
|----------|---------|--------------|-----------|-------------|
| Screen Reader Focus for Interactive Elements (Exp.) | `a11y/sr-focus-interactive` | 2.4.3 (A), 4.1.2 | 🟡 | 🟡 |
| Spoken Description not Meaningful | `a11y/non-meaningful-description` | 1.1.1, 4.1.2 | 🟡 (labels genéricos: "image", "icon", "untitled") | 🟡 |
| Overlapping Interactive Elements | `a11y/overlapping-targets` | 2.5.8 (AA) | ❌ runtime | 🟡 |
| Traversal Order Cycle (Exp.) | `a11y/traversal-order-cycle` | 2.4.3 (A) | 🟡 | 🟡 |
| Meaningful Visual Order (Exp.) | `a11y/visual-order` | 1.3.2 (A) | ❌ runtime | 🟡 |
| Meaningful Reading Order (Exp.) | `a11y/reading-order` | 1.3.2 (A) | 🟡 | 🟡 |
| Keyboard Focus for Interactive Elements (Exp.) | `a11y/keyboard-focus` | 2.1.1 (A), 2.4.7 (AA) | 🟡 | 🟡 |

### Input Purpose
| Critério | rule_id | WCAG (nível) | Auditável | Tier típico |
|----------|---------|--------------|-----------|-------------|
| Input type for Input Fields (Exp.) | `a11y/input-type` | 1.3.5 (AA) | ✅ (`keyboardType`, `textContentType`, `autoComplete`) | 🟠 |

### Touch Target Size
| Critério | rule_id | WCAG (nível) | Auditável | Tier típico |
|----------|---------|--------------|-----------|-------------|
| Touch Target Size & Spacing | `a11y/touch-target-too-small` | 2.5.8 (AA) | 🟡 (literal ✅; tema dinâmico → 🟡) | 🟠 / 🟡 |

### Accessible Elements
| Critério | rule_id | WCAG (nível) | Auditável | Tier típico |
|----------|---------|--------------|-----------|-------------|
| Interactive Elements with Unsupported Type | `a11y/unsupported-interactive-type` | 4.1.2 (A) | 🟡 | 🟡/🟠 |

### Excluído por decisão de produto
| Critério | Motivo |
|----------|--------|
| App Orientation Lock (Display Orientation, 1.3.4 AA) | App travado em **retrato** — fora de escopo. |

---

## 6. Como o agente atribui o `tier` (algoritmo)

```
para cada finding candidato no diff:
  se detectability == runtime:                         → 🟡 warning  (nunca bloqueia)
  senão se prop de a11y REMOVIDA (lado '-') e não reaparece no hunk:
      se reaparece em ancestral (pai)?                 → 🟡 warning  (revisar: regra de negócio)
      senão                                            → 🔴 critico
  senão se elemento NOVO (lado '+') sem prop obrigatória:
      se regra é boa-prática / depende de negócio       → 🟡 warning
      senão                                            → 🟠 atencao
  senão                                                → 🟡 warning
```

> Componentes na **allowlist do Tangerina** (ver [[Arquitetura - Agente Agno]] §5 e `REFERENCE.md`) já injetam `role`/`label` → **suprimidos** (não geram finding).

---

## 7. Checklist de aceite (TASK-001)

- [x] `Finding`, `Coverage`, `AuditVerdict` modelados (§2)
- [x] Regra do `block` definida — 🔴 **e** 🟠 bloqueiam; refina o "só error em linha adicionada" original para incluir **regressão** (prop removida) (§1)
- [x] `coverage` para diff = elementos novos cobertos / total novos, + contador de regressões (§2)
- [x] Serialização JSON validada como artefato de CI (§4)
- [x] Relatório curto para comentário de PR, com solução (§3)
- [x] Todos os critérios solicitados incluídos, **AA only**, Display Orientation excluída (§5)
