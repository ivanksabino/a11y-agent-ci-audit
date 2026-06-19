"""Testes dos helpers puros de schema.py (sem LLM)."""

from __future__ import annotations

from a11y_auditor.schema import (
    AuditVerdict,
    ChangeType,
    Coverage,
    Detectability,
    Finding,
    Tier,
    approved_verdict,
    compute_block,
    compute_coverage,
)


def _finding(tier: Tier) -> Finding:
    return Finding(
        rule_id="a11y/missing-label-on-touchable",
        criterion="Nome, função, valor",
        tier=tier,
        change_type=ChangeType.added,
        detectability=Detectability.static,
        file="src/Login.tsx",
        line=42,
        message="Falta label.",
        fix="Adicione accessibilityLabel.",
    )


# --- compute_block ---------------------------------------------------------


def test_compute_block_critico_bloqueia() -> None:
    assert compute_block([_finding(Tier.critico)]) is True


def test_compute_block_atencao_bloqueia() -> None:
    assert compute_block([_finding(Tier.atencao)]) is True


def test_compute_block_warning_nao_bloqueia() -> None:
    assert compute_block([_finding(Tier.warning)]) is False


def test_compute_block_vazio_nao_bloqueia() -> None:
    assert compute_block([]) is False


def test_compute_block_mistura_com_critico_bloqueia() -> None:
    findings = [_finding(Tier.warning), _finding(Tier.critico)]
    assert compute_block(findings) is True


# --- compute_coverage ------------------------------------------------------


def test_compute_coverage_percent() -> None:
    cov = compute_coverage([], interactive_added=4, compliant=3)
    assert cov.percent == 75.0
    assert cov.interactive_added == 4
    assert cov.compliant == 3


def test_compute_coverage_denominador_zero_eh_100() -> None:
    cov = compute_coverage([], interactive_added=0, compliant=0)
    assert cov.percent == 100.0


def test_compute_coverage_regressions_conta_so_critico() -> None:
    findings = [
        _finding(Tier.critico),
        _finding(Tier.critico),
        _finding(Tier.atencao),
        _finding(Tier.warning),
    ]
    cov = compute_coverage(findings, interactive_added=2, compliant=2)
    assert cov.regressions == 2
    assert cov.percent == 100.0


# --- approved_verdict ------------------------------------------------------


def test_approved_verdict_vazio() -> None:
    v = approved_verdict("tudo ok", "## relatorio")
    assert v.block is False
    assert v.findings == []
    assert v.coverage.interactive_added == 0
    assert v.coverage.compliant == 0
    assert v.coverage.percent == 100.0
    assert v.coverage.regressions == 0
    assert v.summary == "tudo ok"
    assert v.report_markdown == "## relatorio"


# --- round-trip JSON -------------------------------------------------------


def test_round_trip_json_audit_verdict() -> None:
    findings = [_finding(Tier.critico), _finding(Tier.warning)]
    coverage = compute_coverage(findings, interactive_added=2, compliant=1)
    original = AuditVerdict(
        block=compute_block(findings),
        coverage=coverage,
        findings=findings,
        summary="resumo",
        report_markdown="## md",
    )
    dumped = original.model_dump()
    restored = AuditVerdict.model_validate(dumped)
    assert restored == original
    # Enums serializam como string.
    assert dumped["findings"][0]["tier"] == "critico"
    assert dumped["findings"][0]["change_type"] == "added"
    assert dumped["findings"][0]["detectability"] == "static"


def test_finding_defaults() -> None:
    f = _finding(Tier.warning)
    assert f.wcag == []
    assert f.wcag_level == "AA"
    assert f.abnt == []
    assert f.snippet == ""
