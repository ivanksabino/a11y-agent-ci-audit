"""Testes da knowledge base estatica (knowledge.py)."""

from __future__ import annotations

from a11y_auditor.knowledge import (
    DS_ALLOWLIST,
    build_instructions,
    build_knowledge_block,
    load_examples,
    load_rules_catalog,
)


def test_load_rules_catalog_nao_quebra() -> None:
    catalog = load_rules_catalog()
    assert isinstance(catalog, str)
    assert len(catalog) > 0


def test_load_examples_nao_quebra() -> None:
    examples = load_examples()
    assert isinstance(examples, str)
    assert len(examples) > 0


def test_knowledge_block_contem_rule_ids() -> None:
    block = build_knowledge_block()
    # Amostra de rule_ids do catalogo precisa estar embutida.
    for rule_id in (
        "a11y/missing-label-on-touchable",
        "a11y/image-without-alt",
        "a11y/missing-role-on-button-like",
    ):
        assert rule_id in block


def test_knowledge_block_contem_allowlist() -> None:
    block = build_knowledge_block()
    for nome in DS_ALLOWLIST:
        assert nome in block
    # TgrButtonIcon precisa ser mencionado como exigindo label.
    assert "TgrButtonIcon" in block


def test_knowledge_block_constante_entre_chamadas() -> None:
    a = build_knowledge_block()
    b = build_knowledge_block()
    assert a == b  # cacheavel / determinístico


def test_build_instructions_lista_pt_br() -> None:
    instr = build_instructions()
    assert isinstance(instr, list)
    assert len(instr) > 0
    assert all(isinstance(s, str) for s in instr)
    joined = "\n".join(instr)
    # Deve falar de AA e de pt-BR / coverage do delta.
    assert "AA" in joined


def test_ds_allowlist_button_icon_exige_label() -> None:
    info = DS_ALLOWLIST["TgrButtonIcon"]
    assert "accessibilityLabel" in info.get("requires", [])
    # NAO deve suprimir a regra de label.
    assert "a11y/missing-label-on-touchable" not in info.get("suppresses", [])
