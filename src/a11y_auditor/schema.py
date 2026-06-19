"""Schema do a11y-auditor-agent: enums, modelos Pydantic e helpers puros.

Sem dependencia de LLM. Importavel sem agno instalado.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Tier(str, Enum):
    """Severidade do achado de acessibilidade."""

    critico = "critico"
    atencao = "atencao"
    warning = "warning"


class ChangeType(str, Enum):
    """Tipo de mudanca no diff que originou o achado."""

    removed = "removed"
    added = "added"
    modified = "modified"


class Detectability(str, Enum):
    """Quao detectavel o problema e (estatico, parcial, so em runtime)."""

    static = "static"
    partial = "partial"
    runtime = "runtime"


class Finding(BaseModel):
    """Um achado de acessibilidade pontual."""

    rule_id: str
    criterion: str
    tier: Tier
    change_type: ChangeType
    detectability: Detectability
    file: str
    line: int
    message: str
    fix: str
    wcag: list[str] = Field(default_factory=list)
    wcag_level: str = "AA"
    abnt: list[str] = Field(default_factory=list)
    snippet: str = ""


class Coverage(BaseModel):
    """Cobertura de acessibilidade do delta auditado."""

    interactive_added: int
    compliant: int
    percent: float
    regressions: int


class AuditVerdict(BaseModel):
    """Veredito final da auditoria."""

    block: bool
    coverage: Coverage
    findings: list[Finding]
    summary: str
    report_markdown: str


# --- Helpers puros (sem LLM) ---


def compute_block(findings: list[Finding]) -> bool:
    """True se algum finding tem tier critico ou atencao."""
    return any(f.tier in {Tier.critico, Tier.atencao} for f in findings)


def compute_coverage(
    findings: list[Finding], interactive_added: int, compliant: int
) -> Coverage:
    """Calcula a cobertura do delta.

    percent = compliant / interactive_added * 100 (100.0 se interactive_added == 0).
    regressions = numero de findings com tier critico.
    """
    if interactive_added == 0:
        percent = 100.0
    else:
        percent = compliant / interactive_added * 100
    regressions = sum(1 for f in findings if f.tier == Tier.critico)
    return Coverage(
        interactive_added=interactive_added,
        compliant=compliant,
        percent=percent,
        regressions=regressions,
    )


def approved_verdict(summary: str, report_markdown: str) -> AuditVerdict:
    """Veredito aprovado vazio: nao bloqueia, sem findings, cobertura 100%."""
    return AuditVerdict(
        block=False,
        coverage=Coverage(
            interactive_added=0, compliant=0, percent=100.0, regressions=0
        ),
        findings=[],
        summary=summary,
        report_markdown=report_markdown,
    )
