"""Knowledge base do agente auditor de a11y (TASK-003).

Centraliza o bloco de instrucao ESTATICO usado como system prompt do agente.
Por ser constante entre execucoes, habilita prompt caching (ver agent.py).

Nao importa agno/anthropic. Nao depende de LLM. Lê o material-fonte de
``data/*.md`` via importlib.resources para manter um unico ponto de verdade.
"""

from __future__ import annotations

from functools import lru_cache
from importlib import resources

# Nome do pacote que contem os .md de referencia (mesmo dir deste modulo).
_DATA_PACKAGE = "a11y_auditor"
_DATA_DIR = "data"


# ---------------------------------------------------------------------------
# DS_ALLOWLIST — componentes Tangerina que ja injetam role/label.
# ---------------------------------------------------------------------------
# Modelado como dado. Para cada componente: que props de a11y ele injeta
# sozinho e quais rule_ids NAO devem disparar.
# ATENCAO: TgrButtonIcon NAO injeta label (so renderiza o icone) -> exige
# accessibilityLabel explicito; por isso fica fora da supressao de label.
DS_ALLOWLIST: dict[str, dict[str, list[str]]] = {
    "TgrButtonPrimary": {
        "injects": ["accessibilityRole=button"],
        "suppresses": ["a11y/missing-role-on-button-like"],
    },
    "TgrButtonSecondary": {
        "injects": ["accessibilityRole=button"],
        "suppresses": ["a11y/missing-role-on-button-like"],
    },
    "TgrButtonMini": {
        "injects": ["accessibilityRole=button"],
        "suppresses": ["a11y/missing-role-on-button-like"],
    },
    "TgrButtonGroup": {
        "injects": ["accessibilityRole=button (nos filhos)"],
        "suppresses": ["a11y/missing-role-on-button-like"],
    },
    "TgrLanguageSelector": {
        "injects": ["accessibilityRole=button", "label dinamico"],
        "suppresses": [
            "a11y/missing-role-on-button-like",
            "a11y/missing-label-on-touchable",
        ],
    },
    # TgrButtonIcon: so icone, NAO injeta label -> NAO suprime label.
    # Ainda injeta role de botao internamente.
    "TgrButtonIcon": {
        "injects": ["accessibilityRole=button"],
        "suppresses": ["a11y/missing-role-on-button-like"],
        "requires": ["accessibilityLabel"],  # precisa de label explicito
    },
    "TgrParagraph": {
        "injects": ["accessibilityRole=text"],
        "suppresses": [],
    },
    # TgrHeading NAO injeta role de header automaticamente -> auditar manual.
    "TgrHeading": {
        "injects": [],
        "suppresses": [],
    },
    "TgrInputText": {
        "injects": ["label associado via prop label"],
        "suppresses": ["a11y/form-input-without-label"],  # se prop label existir
    },
    "TgrInputPassword": {
        "injects": ["label associado via prop label"],
        "suppresses": ["a11y/form-input-without-label"],  # se prop label existir
    },
}


# ---------------------------------------------------------------------------
# Algoritmo de atribuicao de tier (output_contract.md §6).
# ---------------------------------------------------------------------------
_TIER_ALGORITHM = """\
## Algoritmo de atribuicao de tier (AA only)

Para cada finding candidato no diff:
  1. Se detectability == runtime          -> 🟡 warning  (NUNCA bloqueia)
  2. Senao, se prop de a11y REMOVIDA (lado '-') e nao reaparece no hunk:
       - se a prop reaparece em ancestral (pai) -> 🟡 warning (revisar: regra de negocio)
       - senao                                  -> 🔴 critico
  3. Senao, se elemento NOVO (lado '+') sem prop obrigatoria:
       - se a regra e boa-pratica / depende de negocio -> 🟡 warning
       - senao                                         -> 🟠 atencao
  4. Senao                                  -> 🟡 warning

Regra do bloqueio (compute_block):
  - 🔴 critico E 🟠 atencao BLOQUEIAM o merge.
  - 🟡 warning NUNCA bloqueia (so informa).
  - O gate NUNCA bloqueia em criterio que so e verificavel em runtime
    (contraste, magnificacao, truncamento, etc.): runtime => no maximo 🟡.

Nuance pai -> filhos:
  Quando uma prop de a11y some dos filhos mas aparece no componente PAI
  (ex.: o pai vira um unico no focavel via accessible={true} e agrupa o
  anuncio), isso PODE ser regra de negocio legitima. Rebaixe de 🔴 para 🟡,
  sinalizando "revisar: label movido para o pai - intencional?". So 🔴 se a
  prop sumiu e NAO reapareceu em nenhum ancestral do mesmo hunk.
"""


# ---------------------------------------------------------------------------
# Leitura do material-fonte embutido.
# ---------------------------------------------------------------------------
def _read_data_file(filename: str) -> str:
    """Lê um arquivo de ``a11y_auditor/data`` via importlib.resources."""
    resource = resources.files(_DATA_PACKAGE).joinpath(_DATA_DIR, filename)
    return resource.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def load_rules_catalog() -> str:
    """Catalogo das 21 regras WCAG<->ABNT (data/rules_reference.md)."""
    return _read_data_file("rules_reference.md")


@lru_cache(maxsize=1)
def load_examples() -> str:
    """Pares antes->depois para few-shot (data/examples_before_after.md)."""
    return _read_data_file("examples_before_after.md")


def _render_allowlist() -> str:
    """Renderiza a DS_ALLOWLIST de forma compacta para o prompt."""
    linhas: list[str] = [
        "## Allowlist do Design System Tangerina",
        "",
        "Componentes que ja injetam props de a11y internamente. Quando o "
        "elemento vem de um destes, NAO gere finding para a regra suprimida.",
        "",
    ]
    for nome, info in DS_ALLOWLIST.items():
        injeta = ", ".join(info.get("injects", [])) or "(nada automatico)"
        suprime = ", ".join(info.get("suppresses", [])) or "(nenhuma)"
        linha = f"- `{nome}` injeta: {injeta} | suprime: {suprime}"
        requer = info.get("requires")
        if requer:
            linha += f" | AINDA EXIGE: {', '.join(requer)}"
        linhas.append(linha)
    linhas.append("")
    linhas.append(
        "ATENCAO: `TgrButtonIcon` NAO injeta accessibilityLabel (so o icone) "
        "-> ainda exige accessibilityLabel explicito."
    )
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# Bloco de conhecimento CONSTANTE (cacheavel).
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def build_knowledge_block() -> str:
    """Bloco de instrucao constante usado como base do system prompt.

    Identico em toda execucao => habilita prompt caching da Anthropic.
    Reune: catalogo de regras + exemplos antes->depois + DS_ALLOWLIST +
    algoritmo de atribuicao de tier (output_contract §6).
    """
    partes = [
        "# Base de conhecimento — Auditor de Acessibilidade (WCAG 2.2 AA / "
        "ABNT NBR 17060)",
        "",
        "Escopo: APENAS Nivel AA (criterios A + AA; AAA fora). Display "
        "Orientation fora (app travado em retrato).",
        "",
        "---",
        "",
        "# Catalogo de regras (WCAG <-> ABNT)",
        "",
        load_rules_catalog(),
        "",
        "---",
        "",
        "# Exemplos antes -> depois (few-shot; base para o campo `fix`)",
        "",
        load_examples(),
        "",
        "---",
        "",
        _render_allowlist(),
        "",
        "---",
        "",
        _TIER_ALGORITHM,
    ]
    return "\n".join(partes)


# ---------------------------------------------------------------------------
# Instrucoes do agente (lista para o Agno).
# ---------------------------------------------------------------------------
def build_instructions() -> list[str]:
    """Instrucoes operacionais do agente Agno (pt-BR, AA only)."""
    return [
        "Voce e um auditor de acessibilidade de codigo React Native, "
        "especializado em WCAG 2.2 Nivel AA e ABNT NBR 17060.",
        "Audite SOMENTE as linhas marcadas como adicionadas ('+') ou "
        "removidas ('-') no payload do diff. Use o contexto apenas para "
        "entender a estrutura; nao gere finding em linha de contexto.",
        "Escopo de conformidade: APENAS Nivel AA (criterios A + AA). Ignore "
        "AAA e Display Orientation (app travado em retrato).",
        "Suprima componentes da allowlist do Tangerina que ja injetam a prop "
        "em questao (ver DS_ALLOWLIST). ATENCAO: TgrButtonIcon NAO injeta "
        "accessibilityLabel -> ainda exige label explicito.",
        "Atribua o tier conforme o algoritmo: regressao (prop removida sem "
        "reposicao) = 🔴 critico; elemento novo sem prop obrigatoria = "
        "🟠 atencao; boa-pratica / regra de negocio = 🟡 warning.",
        "Criterios so verificaveis em runtime (contraste, magnificacao, "
        "truncamento, espacamento) sao SEMPRE 🟡 warning (detectability="
        "runtime) e NUNCA bloqueiam o merge.",
        "Se uma prop sumiu dos filhos mas reaparece no componente pai do "
        "mesmo hunk, rebaixe de 🔴 para 🟡 e sinalize para revisao humana.",
        "Calcule coverage sobre o DELTA do PR: interactive_added = elementos "
        "interativos/visuais relevantes adicionados; compliant = quantos ja "
        "vem com a11y adequada; regressions = numero de findings 🔴.",
        "block = True se houver qualquer finding 🔴 critico OU 🟠 atencao.",
        "Para cada finding preencha: rule_id, criterion, tier, change_type, "
        "detectability, file, line (linha pos-PR; para removed, a linha do "
        "hunk), message (1 frase pt-BR), fix (solucao curta pt-BR baseada "
        "nos exemplos), wcag, wcag_level, abnt e snippet (linha ofensora).",
        "Todas as mensagens voltadas ao usuario devem estar em pt-BR.",
        "Seja conservador: na duvida entre estatico e runtime, prefira "
        "detectability=partial ou runtime e tier 🟡 (o gate nunca bloqueia "
        "em criterio que nao consegue verificar estaticamente).",
    ]
