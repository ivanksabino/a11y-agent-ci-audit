"""Testes do renderizador de relatorio (report.py)."""

from __future__ import annotations

import logging

from a11y_auditor.report import TIER_EMOJI, render_report
from a11y_auditor.schema import (
    ChangeType,
    Coverage,
    Detectability,
    Finding,
    Tier,
)


def _finding(tier: Tier, line: int = 1, msg: str = "msg") -> Finding:
    return Finding(
        rule_id="a11y/missing-label-on-touchable",
        criterion="Nome, função, valor",
        tier=tier,
        change_type=ChangeType.added,
        detectability=Detectability.static,
        file="src/Login.tsx",
        line=line,
        message=msg,
        fix="fix",
        wcag=["4.1.2"],
    )


def _cov(percent: float = 100.0) -> Coverage:
    return Coverage(interactive_added=2, compliant=2, percent=percent, regressions=0)


def test_emoji_map() -> None:
    assert TIER_EMOJI[Tier.critico] == "🔴"
    assert TIER_EMOJI[Tier.atencao] == "🟠"
    assert TIER_EMOJI[Tier.warning] == "🟡"


def test_cabecalho_bloqueado() -> None:
    md = render_report(
        block=True,
        coverage=_cov(),
        findings=[_finding(Tier.critico)],
        summary="resumo",
    )
    assert "## ♿ Auditoria de Acessibilidade — ⛔ Merge bloqueado" in md
    assert "> resumo" in md


def test_cabecalho_permitido_com_findings() -> None:
    md = render_report(
        block=False,
        coverage=_cov(),
        findings=[_finding(Tier.warning)],
        summary="resumo",
    )
    assert "## ♿ Auditoria de Acessibilidade — ✅ Merge permitido" in md


def test_findings_vazio_cabecalho_especial_sem_tabela() -> None:
    md = render_report(block=False, coverage=_cov(), findings=[], summary="x")
    assert "nenhum ponto de acessibilidade no diff" in md
    assert "|" not in md  # sem tabela


def test_ordenacao_critico_atencao_warning() -> None:
    findings = [
        _finding(Tier.warning, line=1, msg="w"),
        _finding(Tier.atencao, line=2, msg="a"),
        _finding(Tier.critico, line=3, msg="c"),
    ]
    md = render_report(block=True, coverage=_cov(), findings=findings, summary="s")
    pos_critico = md.index("🔴")
    pos_atencao = md.index("🟠")
    pos_warning = md.index("🟡")
    assert pos_critico < pos_atencao < pos_warning


def test_truncamento_em_max_rows_com_aviso(caplog) -> None:
    findings = [_finding(Tier.warning, line=i, msg=f"m{i}") for i in range(20)]
    with caplog.at_level(logging.WARNING):
        md = render_report(
            block=False,
            coverage=_cov(),
            findings=findings,
            summary="s",
            max_rows=15,
        )
    # 5 findings excedentes => linha de aviso na tabela.
    assert "+5 findings adicionais" in md
    # E log de warning emitido (nunca truncar em silencio).
    assert any("truncado" in r.message.lower() for r in caplog.records)


def test_sem_truncamento_quando_dentro_do_limite(caplog) -> None:
    findings = [_finding(Tier.warning, line=i) for i in range(5)]
    with caplog.at_level(logging.WARNING):
        md = render_report(
            block=False, coverage=_cov(), findings=findings, summary="s", max_rows=15
        )
    assert "findings adicionais" not in md
    assert not any("truncado" in r.message.lower() for r in caplog.records)


def test_criterion_label_inclui_wcag() -> None:
    md = render_report(
        block=True,
        coverage=_cov(),
        findings=[_finding(Tier.critico)],
        summary="s",
    )
    assert "(4.1.2)" in md
