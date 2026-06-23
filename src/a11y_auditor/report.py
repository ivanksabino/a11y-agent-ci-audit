"""Renderizador determinístico do markdown do PR (output_contract §3)."""

from __future__ import annotations

import logging

from a11y_auditor.schema import Coverage, Finding, Tier

logger = logging.getLogger(__name__)

TIER_EMOJI: dict[Tier, str] = {
    Tier.critico: "🔴",
    Tier.atencao: "🟠",
    Tier.warning: "🟡",
}

# Ordem de exibição: 🔴 → 🟠 → 🟡
_TIER_ORDER: dict[Tier, int] = {
    Tier.critico: 0,
    Tier.atencao: 1,
    Tier.warning: 2,
}

_FOOTER = (
    "<sub>Nível AA · 🔴 regressão bloqueia · 🟠 novo-sem-a11y e 🟡 não "
    "bloqueiam (informativos) · critérios de runtime validados no BrowserStack</sub>"
)


def _escape_cell(text: str) -> str:
    """Escapa pipes para não quebrar a tabela markdown."""
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _criterion_label(finding: Finding) -> str:
    """Monta 'Critério (WCAG)' juntando o nome do critério aos códigos WCAG."""
    if finding.wcag:
        return f"{finding.criterion} ({', '.join(finding.wcag)})"
    return finding.criterion


def render_report(
    block: bool,
    coverage: Coverage,
    findings: list[Finding],
    summary: str,
    max_rows: int = 15,
) -> str:
    """Renderiza o markdown do comentário do PR conforme output_contract §3.

    Cabeçalho com veredito, linha de cobertura/contagens, citação do summary e
    tabela (1 linha/finding) ordenada 🔴 → 🟠 → 🟡. Trunca em max_rows e loga o
    excedente via logging.warning (nunca truncar em silêncio).
    """
    veredito = "⛔ Merge bloqueado" if block else "✅ Merge permitido"

    # Sem findings: cabeçalho especial, sem tabela.
    if not findings:
        return (
            "## ♿ Auditoria de Acessibilidade — "
            "✅ Merge permitido — nenhum ponto de acessibilidade no diff"
        )

    # Contagens por tier.
    n_critico = sum(1 for f in findings if f.tier is Tier.critico)
    n_atencao = sum(1 for f in findings if f.tier is Tier.atencao)
    n_warning = sum(1 for f in findings if f.tier is Tier.warning)

    cobertura_linha = (
        f"**Cobertura do diff:** {coverage.percent:.1f}% "
        f"({coverage.compliant}/{coverage.interactive_added} elementos novos cobertos) · "
        f"**Regressões:** {coverage.regressions} · "
        f"**Findings:** 🔴 {n_critico} · 🟠 {n_atencao} · 🟡 {n_warning}"
    )

    lines: list[str] = [
        f"## ♿ Auditoria de Acessibilidade — {veredito}",
        "",
        cobertura_linha,
        "",
        f"> {summary}",
        "",
        "| | Arquivo:linha | Critério (WCAG) | O que aconteceu | Solução sugerida |",
        "|--|---------------|-----------------|-----------------|------------------|",
    ]

    # Ordena por tier (🔴 → 🟠 → 🟡), mantendo estável a ordem original dentro do tier.
    ordered = sorted(findings, key=lambda f: _TIER_ORDER.get(f.tier, 99))

    visible = ordered[:max_rows]
    hidden = ordered[max_rows:]

    for f in visible:
        emoji = TIER_EMOJI.get(f.tier, "")
        local = _escape_cell(f"`{f.file}:{f.line}`")
        criterio = _escape_cell(_criterion_label(f))
        ocorrido = _escape_cell(f.message)
        solucao = _escape_cell(f.fix)
        lines.append(f"| {emoji} | {local} | {criterio} | {ocorrido} | {solucao} |")

    if hidden:
        extra = len(hidden)
        logger.warning(
            "Relatório truncado: %d findings adicionais omitidos da tabela (max_rows=%d).",
            extra,
            max_rows,
        )
        for f in hidden:
            logger.warning(
                "  finding omitido: [%s] %s:%d — %s",
                f.tier.value,
                f.file,
                f.line,
                f.message,
            )
        lines.append(f"| | | | | _+{extra} findings adicionais_ |")

    lines.append("")
    lines.append(_FOOTER)

    return "\n".join(lines)
