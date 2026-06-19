"""Testes do gate de CI (gate.py). NAO exigem agno instalado."""

from __future__ import annotations

import json
import sys

import a11y_auditor.diff as diff_mod
import a11y_auditor.gate as gate_mod
from a11y_auditor.gate import main, run_gate
from a11y_auditor.schema import (
    AuditVerdict,
    ChangeType,
    Coverage,
    Detectability,
    Finding,
    Tier,
)

# Diff de logica pura (sem relevancia de a11y).
DIFF_PURE = """\
diff --git a/src/math.ts b/src/math.ts
index 8888888..9999999 100644
--- a/src/math.ts
+++ b/src/math.ts
@@ -1,3 +1,3 @@
 export function sum(a, b) {
-  return a - b;
+  return a + b;
 }
"""

# Diff com relevancia de a11y.
DIFF_A11Y = """\
diff --git a/src/Login.tsx b/src/Login.tsx
index 1111111..2222222 100644
--- a/src/Login.tsx
+++ b/src/Login.tsx
@@ -10,2 +10,3 @@
 const a = 1;
+<Pressable onPress={go} />
 return null;
"""


def _agno_importado() -> bool:
    return any(m == "agno" or m.startswith("agno.") for m in sys.modules)


def _blocking_verdict() -> AuditVerdict:
    finding = Finding(
        rule_id="a11y/missing-label-on-touchable",
        criterion="Nome, função, valor",
        tier=Tier.critico,
        change_type=ChangeType.added,
        detectability=Detectability.static,
        file="src/Login.tsx",
        line=11,
        message="Pressable sem label.",
        fix="Adicione accessibilityLabel.",
        wcag=["4.1.2"],
    )
    return AuditVerdict(
        block=True,
        coverage=Coverage(
            interactive_added=1, compliant=0, percent=0.0, regressions=1
        ),
        findings=[finding],
        summary="1 regressao critica.",
        report_markdown="(sera re-renderizado pelo gate)",
    )


# --- curto-circuito: diff vazio --------------------------------------------


def test_diff_vazio_aprova_sem_agno(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(gate_mod, "get_pr_diff", lambda **kw: "")
    out = tmp_path / "verdict.json"
    verdict = run_gate(
        base_ref="origin/main",
        head_ref="HEAD",
        out_path=str(out),
    )
    assert verdict.block is False
    assert verdict.findings == []
    assert not _agno_importado()
    # Artefato gravado.
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["block"] is False


# --- curto-circuito: sem hunk relevante ------------------------------------


def test_diff_sem_a11y_aprova_sem_agno(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(gate_mod, "get_pr_diff", lambda **kw: DIFF_PURE)
    out = tmp_path / "verdict.json"
    verdict = run_gate(
        base_ref="origin/main",
        head_ref="HEAD",
        out_path=str(out),
    )
    assert verdict.block is False
    assert verdict.findings == []
    assert not _agno_importado()


# --- caminho com bloqueio (run_audit mockado) ------------------------------


def test_caminho_block_grava_json_e_recompoe(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(gate_mod, "get_pr_diff", lambda **kw: DIFF_A11Y)

    # Injeta run_audit no modulo agent SEM importar agno (modulo agent importa
    # agno apenas dentro de build_agent, nunca no topo).
    import a11y_auditor.agent as agent_mod

    monkeypatch.setattr(
        agent_mod,
        "run_audit",
        lambda payload, model_id=None, provider=None: _blocking_verdict(),
    )

    out = tmp_path / "verdict.json"
    verdict = run_gate(
        base_ref="origin/main",
        head_ref="HEAD",
        out_path=str(out),
    )
    assert verdict.block is True
    assert len(verdict.findings) == 1
    # Re-render canonico: markdown deve ter cabecalho de bloqueio.
    assert "⛔ Merge bloqueado" in verdict.report_markdown
    # JSON gravado com nao-ASCII preservado.
    raw = out.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert data["block"] is True
    assert data["findings"][0]["rule_id"] == "a11y/missing-label-on-touchable"


# --- main retorna 1 quando bloqueia ----------------------------------------


def test_main_retorna_1_quando_block(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(gate_mod, "get_pr_diff", lambda **kw: DIFF_A11Y)
    import a11y_auditor.agent as agent_mod

    monkeypatch.setattr(
        agent_mod,
        "run_audit",
        lambda payload, model_id=None, provider=None: _blocking_verdict(),
    )

    out = tmp_path / "verdict.json"
    rc = main(
        [
            "--base",
            "origin/main",
            "--head",
            "HEAD",
            "--out",
            str(out),
        ]
    )
    assert rc == 1


# --- main retorna 0 quando aprovado ----------------------------------------


def test_main_retorna_0_quando_aprovado(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(gate_mod, "get_pr_diff", lambda **kw: "")
    out = tmp_path / "verdict.json"
    rc = main(["--base", "origin/main", "--head", "HEAD", "--out", str(out)])
    assert rc == 0
    assert not _agno_importado()
