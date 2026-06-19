"""Testes do nucleo de parsing/prefiltro de diff (diff.py)."""

from __future__ import annotations

import subprocess
import types

from a11y_auditor.diff import (
    DiffLine,
    Hunk,
    build_audit_payload,
    filter_relevant_hunks,
    get_pr_diff,
    is_a11y_relevant,
    parse_diff_hunks,
    resolve_refs,
)

# --- fixtures de diff unificado --------------------------------------------

# Dois hunks no MESMO arquivo, com adicoes e remocoes.
DIFF_MULTI_HUNK = """\
diff --git a/src/Login.tsx b/src/Login.tsx
index 1111111..2222222 100644
--- a/src/Login.tsx
+++ b/src/Login.tsx
@@ -10,4 +10,5 @@ function Login() {
 const a = 1;
-const old = 2;
+const novo = 2;
+<Pressable onPress={go} />
 return null;
@@ -40,3 +41,4 @@ function Footer() {
 const x = 1;
+<Image source={img} />
 const y = 2;
"""

# Arquivo novo: lado '---' e /dev/null.
DIFF_NEW_FILE = """\
diff --git a/src/New.tsx b/src/New.tsx
new file mode 100644
index 0000000..3333333
--- /dev/null
+++ b/src/New.tsx
@@ -0,0 +1,3 @@
+import React from 'react';
+<TextInput value={v} />
+export default New;
"""

# Renomeacao + edicao.
DIFF_RENAME = """\
diff --git a/src/Old.tsx b/src/Renamed.tsx
similarity index 90%
rename from src/Old.tsx
rename to src/Renamed.tsx
index 4444444..5555555 100644
--- a/src/Old.tsx
+++ b/src/Renamed.tsx
@@ -5,3 +5,3 @@
 const z = 0;
-<Text>velho</Text>
+<Text>novo</Text>
"""

# 'No newline at end of file'.
DIFF_NO_NEWLINE = """\
diff --git a/src/util.ts b/src/util.ts
index 6666666..7777777 100644
--- a/src/util.ts
+++ b/src/util.ts
@@ -1,2 +1,2 @@
 export const k = 1;
-export const j = 2;
\\ No newline at end of file
+export const j = 3;
\\ No newline at end of file
"""

# Conteudo cujo codigo comeca com '++ ' / '-- ' (diff bruto vira '+++ '/'--- ').
# NAO pode ser confundido com cabecalho de arquivo enquanto o hunk esta aberto.
DIFF_CONTENT_PLUS_MINUS = """\
diff --git a/src/Login.tsx b/src/Login.tsx
index aaaaaaa..bbbbbbb 100644
--- a/src/Login.tsx
+++ b/src/Login.tsx
@@ -10,3 +10,3 @@ function Login() {
 const a = 1;
-- legacy decrement marker
++ added marker line
+<Pressable onPress={go} />
"""

# Hunk de logica pura (util .ts, sem JSX/a11y).
DIFF_PURE_LOGIC = """\
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


# --- parse_diff_hunks ------------------------------------------------------


def test_parse_multi_hunk_mesmo_arquivo() -> None:
    hunks = parse_diff_hunks(DIFF_MULTI_HUNK)
    assert len(hunks) == 2
    assert all(h.file == "src/Login.tsx" for h in hunks)


def test_parse_numeracao_lado_novo_e_velho() -> None:
    hunks = parse_diff_hunks(DIFF_MULTI_HUNK)
    h1 = hunks[0]
    # Header @@ -10,4 +10,5 @@ ; primeira linha de contexto na 10.
    # Removed 'const old = 2;' fica no lado old, linha 11.
    assert [r.line for r in h1.removed] == [11]
    assert h1.removed[0].code == "const old = 2;"
    # Added: 'const novo = 2;' lado new linha 11; '<Pressable.../>' linha 12.
    assert [a.line for a in h1.added] == [11, 12]
    assert h1.added[0].code == "const novo = 2;"
    assert h1.added[1].code == "<Pressable onPress={go} />"

    h2 = hunks[1]
    # Header @@ -40,3 +41,4 @@ ; contexto 'const x = 1;' na new=41.
    # '<Image .../>' added na new=42.
    assert [a.line for a in h2.added] == [42]
    assert h2.added[0].code == "<Image source={img} />"
    assert h2.removed == []


def test_parse_arquivo_novo_dev_null() -> None:
    hunks = parse_diff_hunks(DIFF_NEW_FILE)
    assert len(hunks) == 1
    h = hunks[0]
    assert h.file == "src/New.tsx"
    # Header @@ -0,0 +1,3 @@ ; tres adicoes em 1,2,3.
    assert [a.line for a in h.added] == [1, 2, 3]
    assert h.removed == []


def test_parse_renomeacao_usa_novo_caminho() -> None:
    hunks = parse_diff_hunks(DIFF_RENAME)
    assert len(hunks) == 1
    h = hunks[0]
    assert h.file == "src/Renamed.tsx"
    assert [r.code for r in h.removed] == ["<Text>velho</Text>"]
    assert [a.code for a in h.added] == ["<Text>novo</Text>"]
    # Linha do contexto 'const z = 0;' em 5 => removed/added em 6.
    assert h.removed[0].line == 6
    assert h.added[0].line == 6


def test_parse_no_newline_nao_avanca_contador() -> None:
    hunks = parse_diff_hunks(DIFF_NO_NEWLINE)
    assert len(hunks) == 1
    h = hunks[0]
    # Contexto 'export const k = 1;' em 1; removed em old=2; added em new=2.
    assert [r.line for r in h.removed] == [2]
    assert [a.line for a in h.added] == [2]
    assert h.removed[0].code == "export const j = 2;"
    assert h.added[0].code == "export const j = 3;"
    # A linha '\\ No newline...' deve aparecer no contexto bruto.
    assert "No newline at end of file" in h.context


def test_parse_vazio_retorna_lista_vazia() -> None:
    assert parse_diff_hunks("") == []


def test_parse_conteudo_iniciado_por_plus_minus_nao_e_cabecalho() -> None:
    # Regressao: linhas de conteudo '-- ...'/'++ ...' (raw '--- '/'+++ ') dentro
    # de um hunk aberto NAO podem ser tratadas como cabecalho de arquivo, senao
    # added/removed somem e a numeracao quebra (gate aprovaria por fail-open).
    hunks = parse_diff_hunks(DIFF_CONTENT_PLUS_MINUS)
    assert len(hunks) == 1
    h = hunks[0]
    assert h.file == "src/Login.tsx"
    # Removida: '- legacy decrement marker' (codigo '- legacy decrement marker').
    assert [r.code for r in h.removed] == ["- legacy decrement marker"]
    # Adicionadas: '++ added marker line' -> codigo '+ added marker line';
    # depois o '<Pressable .../>'. O componente interativo nao pode sumir.
    assert [a.code for a in h.added] == [
        "+ added marker line",
        "<Pressable onPress={go} />",
    ]
    # Numeracao: contexto 'const a = 1;' em new=10; added em new=11 e 12.
    assert [a.line for a in h.added] == [11, 12]


# --- is_a11y_relevant ------------------------------------------------------


def test_is_a11y_relevant_jsx_true() -> None:
    hunks = parse_diff_hunks(DIFF_MULTI_HUNK)
    # Ambos os hunks tem JSX (Pressable, Image).
    assert is_a11y_relevant(hunks[0]) is True
    assert is_a11y_relevant(hunks[1]) is True


def test_is_a11y_relevant_logica_pura_false() -> None:
    hunks = parse_diff_hunks(DIFF_PURE_LOGIC)
    assert len(hunks) == 1
    assert is_a11y_relevant(hunks[0]) is False


def test_is_a11y_relevant_so_olha_changes_nao_contexto() -> None:
    # Contexto contem '<' mas added/removed sao logica pura.
    h = Hunk(
        file="x.ts",
        added=[DiffLine(line=2, code="  return a + b;")],
        removed=[DiffLine(line=2, code="  return a - b;")],
        context="@@ -1,3 +1,3 @@\n <Foo />\n  return a - b;\n",
    )
    assert is_a11y_relevant(h) is False


# --- filter_relevant_hunks -------------------------------------------------


def test_filter_relevant_hunks_remove_logica_pura() -> None:
    hunks = parse_diff_hunks(DIFF_MULTI_HUNK + DIFF_PURE_LOGIC)
    rel = filter_relevant_hunks(hunks)
    assert len(rel) == 2
    assert all(h.file == "src/Login.tsx" for h in rel)


def test_filter_relevant_hunks_vazio() -> None:
    assert filter_relevant_hunks([]) == []


# --- build_audit_payload ---------------------------------------------------


def test_build_audit_payload_vazio() -> None:
    assert build_audit_payload([]) == ""


def test_build_audit_payload_compacto_com_arquivo_e_linhas() -> None:
    hunks = parse_diff_hunks(DIFF_MULTI_HUNK)
    payload = build_audit_payload(hunks)
    assert "### src/Login.tsx" in payload
    # Linhas adicionadas com numero pos-PR.
    assert "+11: const novo = 2;" in payload
    assert "+12: <Pressable onPress={go} />" in payload
    assert "+42: <Image source={img} />" in payload
    # Removidas marcadas.
    assert "-: const old = 2;" in payload


def test_build_audit_payload_agrupa_por_arquivo() -> None:
    hunks = parse_diff_hunks(DIFF_NEW_FILE + DIFF_RENAME)
    payload = build_audit_payload(hunks)
    assert payload.count("### src/New.tsx") == 1
    assert payload.count("### src/Renamed.tsx") == 1


# --- resolve_refs ----------------------------------------------------------


def test_resolve_refs_fallback_local(monkeypatch) -> None:
    for var in (
        "SYSTEM_PULLREQUEST_TARGETBRANCH",
        "SYSTEM_PULLREQUEST_SOURCEBRANCH",
        "GITHUB_BASE_REF",
        "GITHUB_HEAD_REF",
    ):
        monkeypatch.delenv(var, raising=False)
    assert resolve_refs() == ("origin/main", "HEAD")


def test_resolve_refs_azure_normaliza_refs_heads(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
    monkeypatch.delenv("GITHUB_HEAD_REF", raising=False)
    monkeypatch.setenv("SYSTEM_PULLREQUEST_TARGETBRANCH", "refs/heads/main")
    monkeypatch.setenv("SYSTEM_PULLREQUEST_SOURCEBRANCH", "refs/heads/feature/x")
    base, head = resolve_refs()
    assert base == "origin/main"
    assert head == "origin/feature/x"


def test_resolve_refs_github_actions(monkeypatch) -> None:
    monkeypatch.delenv("SYSTEM_PULLREQUEST_TARGETBRANCH", raising=False)
    monkeypatch.delenv("SYSTEM_PULLREQUEST_SOURCEBRANCH", raising=False)
    monkeypatch.setenv("GITHUB_BASE_REF", "main")
    monkeypatch.setenv("GITHUB_HEAD_REF", "feature-x")
    base, head = resolve_refs()
    assert base == "origin/main"
    assert head == "origin/feature-x"


# --- get_pr_diff: decode robusto de bytes nao-UTF-8 ------------------------


def test_get_pr_diff_decodifica_bytes_nao_utf8(monkeypatch) -> None:
    """Diff com byte nao-UTF-8 (ex.: Latin-1) NAO pode virar diff vazio.

    Regressao: antes, text=True estourava UnicodeDecodeError (subclasse de
    ValueError), que era engolido e devolvia "" -> gate aprovava sem olhar o
    diff. Agora usa errors="replace": o byte invalido vira U+FFFD e o diff
    sobrevive.
    """
    captured = {}

    def fake_run(cmd, **kwargs):
        captured.update(kwargs)
        # Simula o que subprocess faz com encoding utf-8 + errors=replace:
        # o byte 0xe7 (ç em Latin-1) vira o caractere de substituicao.
        raw = b"diff --git a/f.tsx b/f.tsx\n+const x = 'a\xe7\xe3o';\n"
        decoded = raw.decode(kwargs.get("encoding", "utf-8"), errors=kwargs.get("errors", "strict"))
        return types.SimpleNamespace(returncode=0, stdout=decoded, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    out = get_pr_diff("main", "HEAD", repo_path="/qualquer")
    assert out != ""  # nao virou vazio
    assert "diff --git" in out
    # garante o decode tolerante (utf-8 + replace), nao text=True cru
    assert captured.get("errors") == "replace"
    assert captured.get("encoding") == "utf-8"
