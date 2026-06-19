"""Gate de CI de acessibilidade.

Orquestra o fluxo: resolve refs -> diff -> hunks -> prefiltro de relevancia ->
auditoria via LLM -> re-render canonico do relatorio -> artefato JSON.

Curto-circuitos de performance: se o diff vier vazio ou nenhum hunk for
relevante para a11y, devolve veredito aprovado SEM importar/agendar o agente
(agno nao e importado nesses caminhos).

NUNCA importa agno no topo: o import e lazy, feito dentro de run_audit
(em agent.py). Aqui so importamos run_audit de forma diferida no caminho que
realmente precisa do LLM.
"""

from __future__ import annotations

import argparse
import json
import logging

from a11y_auditor.diff import (
    build_audit_payload,
    filter_relevant_hunks,
    get_pr_diff,
    parse_diff_hunks,
    resolve_refs,
)
from a11y_auditor.report import render_report
from a11y_auditor.schema import (
    AuditVerdict,
    approved_verdict,
    compute_block,
    compute_coverage,
)

logger = logging.getLogger(__name__)


def run_gate(
    base_ref: str | None = None,
    head_ref: str | None = None,
    repo_path: str = ".",
    out_path: str = "a11y-verdict.json",
    model_id: str | None = None,
    provider: str | None = None,
) -> AuditVerdict:
    """Executa o gate de a11y e grava o veredito em ``out_path``.

    Passos:
      1) Resolve as refs (parametros explicitos ou deteccao de CI).
      2) Coleta o diff. Vazio => veredito aprovado, sem tocar no LLM.
      3) Parseia hunks e aplica o prefiltro de relevancia de a11y.
         Sem hunks relevantes => veredito aprovado, sem tocar no LLM.
      4) Monta o payload compacto e roda a auditoria via LLM.
      5) Recomputa block/coverage e RE-RENDERIZA o markdown de forma canonica.
      6) Grava o artefato JSON.
    """
    # 1) Resolucao de refs.
    if base_ref is None or head_ref is None:
        resolved_base, resolved_head = resolve_refs()
        base_ref = base_ref or resolved_base
        head_ref = head_ref or resolved_head

    # 2) Diff. Vazio => aprovado (curto-circuito, sem LLM).
    diff = get_pr_diff(base_ref=base_ref, head_ref=head_ref, repo_path=repo_path)
    if not diff.strip():
        summary = "Nenhuma alteracao em arquivos relevantes no diff."
        report_md = render_report(
            block=False,
            coverage=compute_coverage([], 0, 0),
            findings=[],
            summary=summary,
        )
        verdict = approved_verdict(summary, report_md)
        _write_artifact(verdict, out_path)
        return verdict

    # 3) Hunks + prefiltro de relevancia. Sem hunks relevantes => aprovado.
    hunks = parse_diff_hunks(diff)
    relevant = filter_relevant_hunks(hunks)
    if not relevant:
        summary = "Nenhum ponto de acessibilidade relevante no diff."
        report_md = render_report(
            block=False,
            coverage=compute_coverage([], 0, 0),
            findings=[],
            summary=summary,
        )
        verdict = approved_verdict(summary, report_md)
        _write_artifact(verdict, out_path)
        return verdict

    # 4) Payload compacto + auditoria via LLM (import lazy de agno em agent.py).
    payload = build_audit_payload(relevant)
    from a11y_auditor.agent import run_audit  # lazy: so aqui agno e necessario

    verdict = run_audit(payload, model_id=model_id, provider=provider)

    # 5) Recomputo defensivo de block/coverage e re-render canonico do markdown.
    block = compute_block(verdict.findings)
    coverage = compute_coverage(
        verdict.findings,
        verdict.coverage.interactive_added,
        verdict.coverage.compliant,
    )
    report_md = render_report(
        block=block,
        coverage=coverage,
        findings=verdict.findings,
        summary=verdict.summary,
    )
    verdict = AuditVerdict(
        block=block,
        coverage=coverage,
        findings=verdict.findings,
        summary=verdict.summary,
        report_markdown=report_md,
    )

    # 6) Artefato JSON.
    _write_artifact(verdict, out_path)
    return verdict


def _write_artifact(verdict: AuditVerdict, out_path: str) -> None:
    """Grava o veredito como JSON (UTF-8, sem escapar nao-ASCII)."""
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(verdict.model_dump(), fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def main(argv: list[str] | None = None) -> int:
    """CLI do gate. Retorna 1 se o merge for bloqueado, senao 0."""
    parser = argparse.ArgumentParser(
        prog="a11y-auditor",
        description="Gate de CI de auditoria de acessibilidade (WCAG AA).",
    )
    parser.add_argument(
        "--base",
        dest="base",
        default=None,
        help="Ref base do diff (ex.: origin/main). Default: deteccao automatica.",
    )
    parser.add_argument(
        "--head",
        dest="head",
        default=None,
        help="Ref head do diff (ex.: HEAD). Default: deteccao automatica.",
    )
    parser.add_argument(
        "--repo",
        dest="repo",
        default=".",
        help="Caminho do repositorio git. Default: diretorio atual.",
    )
    parser.add_argument(
        "--out",
        dest="out",
        default="a11y-verdict.json",
        help="Caminho do artefato JSON de saida. Default: a11y-verdict.json.",
    )
    parser.add_argument(
        "--model",
        dest="model",
        default=None,
        help="ID do modelo do agente (ex.: claude-opus-4-8, gemini-2.5-pro). "
        "Default: env A11Y_AUDITOR_MODEL.",
    )
    parser.add_argument(
        "--provider",
        dest="provider",
        default=None,
        choices=["anthropic", "google"],
        help="Provider do LLM. Default: env A11Y_AUDITOR_PROVIDER ou inferido do "
        "id do modelo (ids 'gemini*' => google, senão anthropic).",
    )
    args = parser.parse_args(argv)

    verdict = run_gate(
        base_ref=args.base,
        head_ref=args.head,
        repo_path=args.repo,
        out_path=args.out,
        model_id=args.model,
        provider=args.provider,
    )

    status = "BLOQUEADO" if verdict.block else "APROVADO"
    cov = verdict.coverage
    print(f"Auditoria de acessibilidade: {status}")
    print(
        f"Cobertura: {cov.compliant}/{cov.interactive_added} "
        f"({cov.percent:.1f}%) | regressoes: {cov.regressions} | "
        f"findings: {len(verdict.findings)}"
    )
    print(verdict.summary)

    return 1 if verdict.block else 0


def cli() -> int:
    """Entrypoint do console_script."""
    return main()
