"""Ingestao e parsing de diff de PR (TASK-002).

Sem dependencia de LLM. Responsavel por:
- resolver refs de base/head conforme o CI (Azure DevOps / GitHub Actions);
- obter o diff via `git diff` filtrado para arquivos de codigo;
- parsear hunks unificados mantendo os DOIS contadores (new/old) corretos;
- prefiltrar hunks por relevancia de a11y (peca central de PERFORMANCE);
- renderizar um payload compacto (minimo de tokens) para o agente.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field


@dataclass
class DiffLine:
    """Uma linha do diff com seu numero (no lado relevante)."""

    line: int
    code: str


@dataclass
class Hunk:
    """Um hunk de um arquivo: linhas adicionadas, removidas e o contexto bruto."""

    file: str
    added: list[DiffLine] = field(default_factory=list)
    removed: list[DiffLine] = field(default_factory=list)
    context: str = ""


# ---------------------------------------------------------------------------
# Resolucao de refs (CI-aware)
# ---------------------------------------------------------------------------


def _normalize_azure_branch(ref: str) -> str:
    """Normaliza branch do Azure ('refs/heads/x') para 'origin/x'."""
    ref = ref.strip()
    if ref.startswith("refs/heads/"):
        return "origin/" + ref[len("refs/heads/") :]
    return ref


def resolve_refs() -> tuple[str, str]:
    """Detecta o ambiente de CI e devolve (base_ref, head_ref).

    Ordem de deteccao:
      1. Azure DevOps: SYSTEM_PULLREQUEST_TARGETBRANCH / SYSTEM_PULLREQUEST_SOURCEBRANCH
      2. GitHub Actions: GITHUB_BASE_REF / GITHUB_HEAD_REF
      3. Fallback local: ('origin/main', 'HEAD')
    """
    azure_base = os.environ.get("SYSTEM_PULLREQUEST_TARGETBRANCH")
    azure_head = os.environ.get("SYSTEM_PULLREQUEST_SOURCEBRANCH")
    if azure_base:
        base = _normalize_azure_branch(azure_base)
        head = _normalize_azure_branch(azure_head) if azure_head else "HEAD"
        return base, head

    gh_base = os.environ.get("GITHUB_BASE_REF")
    gh_head = os.environ.get("GITHUB_HEAD_REF")
    if gh_base:
        base = "origin/" + gh_base.strip()
        head = ("origin/" + gh_head.strip()) if gh_head else "HEAD"
        return base, head

    return "origin/main", "HEAD"


# ---------------------------------------------------------------------------
# Obtencao do diff
# ---------------------------------------------------------------------------


def get_pr_diff(
    base_ref: str = "origin/main",
    head_ref: str = "HEAD",
    repo_path: str = ".",
) -> str:
    """Executa `git diff base...head` filtrando arquivos de codigo.

    check=False; em qualquer erro devolve "" (gate aprova por seguranca).
    """
    cmd = [
        "git",
        "-C",
        repo_path,
        "diff",
        f"{base_ref}...{head_ref}",
        "--unified=3",
        "--",
        "*.ts",
        "*.tsx",
        "*.js",
        "*.jsx",
    ]
    try:
        result = subprocess.run(
            cmd,
            check=False,
            text=True,
            capture_output=True,
        )
    except (OSError, ValueError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout or ""


# ---------------------------------------------------------------------------
# Parsing de diff unificado
# ---------------------------------------------------------------------------

# @@ -old_start[,old_count] +new_start[,new_count] @@ ...
_HUNK_HEADER_RE = re.compile(
    r"^@@ -(?P<old>\d+)(?:,\d+)? \+(?P<new>\d+)(?:,\d+)? @@"
)
# Caminho do arquivo a partir de '+++ b/<path>'
_PLUS_FILE_RE = re.compile(r"^\+\+\+ (?:b/)?(?P<path>.+?)\s*$")
_MINUS_FILE_RE = re.compile(r"^--- (?:a/)?(?P<path>.+?)\s*$")


def parse_diff_hunks(diff: str) -> list[Hunk]:
    """Parser de diff unificado com DOIS contadores de linha.

    Mantem `new_line` (lado +/contexto) e `old_line` (lado -/contexto),
    inicializados pelo header @@ -a,b +c,d @@.
      - '+' (nao '+++')  -> added com new_line; new_line++
      - '-' (nao '---')  -> removed com old_line; old_line++
      - contexto (' ')   -> entra em context; new_line++ e old_line++
    Trata novo arquivo ('+++ b/<path>'), /dev/null, renomeacoes e
    'No newline at end of file'. context acumula o hunk inteiro (com prefixos).
    """
    hunks: list[Hunk] = []
    if not diff:
        return hunks

    current_file = ""
    pending_minus_file = ""  # caminho do '--- a/...', fallback p/ novo arquivo
    current: Hunk | None = None
    new_line = 0
    old_line = 0

    lines = diff.split("\n")
    for raw in lines:
        # Cabecalho de arquivo novo (diff --git) — reseta contexto de arquivo.
        if raw.startswith("diff --git"):
            current = None
            current_file = ""
            pending_minus_file = ""
            continue

        # Linha '--- a/...' ou '--- /dev/null'.
        # So e' cabecalho de arquivo FORA de um hunk (current is None): dentro de
        # um hunk, '--- texto' e' conteudo de uma linha removida cujo codigo
        # comeca com '-- ' e deve cair no branch de '-'.
        if current is None and raw.startswith("--- "):
            m = _MINUS_FILE_RE.match(raw)
            if m:
                path = m.group("path")
                pending_minus_file = "" if path == "/dev/null" else path
            continue

        # Linha '+++ b/...' define o arquivo do hunk (lado pos-PR).
        # Mesmo raciocinio: so e' cabecalho fora de um hunk; dentro, '+++ texto'
        # e' uma linha adicionada cujo codigo comeca com '++ '.
        if current is None and raw.startswith("+++ "):
            m = _PLUS_FILE_RE.match(raw)
            if m:
                path = m.group("path")
                if path == "/dev/null":
                    # Arquivo deletado: usa o lado '---'.
                    current_file = pending_minus_file
                else:
                    current_file = path
            current = None  # proximo @@ abre o hunk
            continue

        # Cabecalho de hunk @@ ... @@
        header = _HUNK_HEADER_RE.match(raw)
        if header:
            old_line = int(header.group("old"))
            new_line = int(header.group("new"))
            current = Hunk(file=current_file)
            current.context = raw + "\n"
            hunks.append(current)
            continue

        if current is None:
            # Linhas fora de hunk (ex.: 'index ...', 'rename ...') sao ignoradas.
            continue

        # 'No newline at end of file' — metadado, nao avanca contadores.
        if raw.startswith("\\"):
            current.context += raw + "\n"
            continue

        if raw.startswith("+"):
            code = raw[1:]
            current.added.append(DiffLine(line=new_line, code=code))
            current.context += raw + "\n"
            new_line += 1
        elif raw.startswith("-"):
            code = raw[1:]
            current.removed.append(DiffLine(line=old_line, code=code))
            current.context += raw + "\n"
            old_line += 1
        else:
            # Contexto: linha comecando com ' ' (ou linha vazia entre hunks).
            current.context += raw + "\n"
            new_line += 1
            old_line += 1

    return hunks


# ---------------------------------------------------------------------------
# Prefiltro de relevancia de a11y (PERFORMANCE)
# ---------------------------------------------------------------------------

# Padroes que indicam relevancia de acessibilidade em JSX/React Native.
# Centro de performance: so chama o LLM se algo aqui casar.
A11Y_PATTERNS: list[str] = [
    "<",
    "accessib",  # cobre accessible, accessibility*, accessibilityLabel, etc.
    "aria-",
    "accessible",
    "importantForAccessibility",
    "Touchable",
    "Pressable",
    "onPress",
    "<Image",
    "<Text",
    "<TextInput",
    "Switch",
    "Checkbox",
    "role",
    "allowFontScaling",
    "maxFontSizeMultiplier",
    "hitSlop",
    "Modal",
    "accessibilityViewIsModal",
    "LiveRegion",
    "Tgr",
]

# Padroes que precisam de ancora (evitar falso-positivo de performance):
#   '<'    -> tag JSX de abertura/fechamento ('<Foo', '</Foo'), NAO 'a < b'.
#   'role' -> atributo JSX ('role=') ou 'accessibilityRole', NAO 'controller'/'enrollment'.
# Os demais tokens da lista entram como substring literal (escapados).
_ANCHORED: dict[str, str] = {
    "<": r"</?[A-Za-z]",
    "role": r"role=|accessibilityRole",
}
_A11Y_REGEX = re.compile(
    "|".join(_ANCHORED.get(p, re.escape(p)) for p in A11Y_PATTERNS)
)


def is_a11y_relevant(hunk: Hunk) -> bool:
    """True se alguma linha added/removed casar com A11Y_PATTERNS.

    Prefiltro de performance: contexto NAO conta — apenas as mudancas reais.
    """
    for dl in hunk.added:
        if _A11Y_REGEX.search(dl.code):
            return True
    for dl in hunk.removed:
        if _A11Y_REGEX.search(dl.code):
            return True
    return False


def filter_relevant_hunks(hunks: list[Hunk]) -> list[Hunk]:
    """Mantem apenas os hunks com relevancia de a11y."""
    return [h for h in hunks if is_a11y_relevant(h)]


# ---------------------------------------------------------------------------
# Payload compacto para o LLM (minimo de tokens)
# ---------------------------------------------------------------------------


def _context_only(context: str) -> str:
    """Filtra o contexto bruto do hunk para nao duplicar linhas '+'/'-'.

    Mantem o header '@@', as linhas de contexto (' ') e os metadados
    ('\\ No newline...'); descarta as linhas '+'/'-' (ja emitidas como
    '+N:'/'-:' antes do bloco ctx) para minimizar tokens no payload do LLM.
    """
    kept: list[str] = []
    for line in context.split("\n"):
        if line.startswith("+") or line.startswith("-"):
            continue
        kept.append(line)
    return "\n".join(kept).rstrip("\n")


def build_audit_payload(hunks: list[Hunk]) -> str:
    """Renderiza os hunks relevantes de forma COMPACTA para o LLM.

    Agrupa por arquivo. Para cada hunk emite:
      - linhas '+' com o numero pos-PR (lado novo),
      - linhas '-' marcadas como removidas,
      - o contexto bruto do hunk (arvore minima).
    Devolve "" se nao houver hunk (gate nem chama o agente).
    """
    if not hunks:
        return ""

    # Preserva a ordem de aparicao dos arquivos.
    files_order: list[str] = []
    by_file: dict[str, list[Hunk]] = {}
    for h in hunks:
        if h.file not in by_file:
            by_file[h.file] = []
            files_order.append(h.file)
        by_file[h.file].append(h)

    parts: list[str] = []
    for file in files_order:
        parts.append(f"### {file}")
        for h in by_file[file]:
            for dl in h.added:
                parts.append(f"+{dl.line}: {dl.code}")
            for dl in h.removed:
                parts.append(f"-: {dl.code}")
            # Contexto do hunk para a arvore minima. As linhas '+'/'-' ja foram
            # emitidas acima; aqui mantemos APENAS o header '@@' e as linhas de
            # contexto (' ') para nao duplicar tokens (hot path: minimizar tokens).
            ctx = _context_only(h.context)
            if ctx:
                parts.append("ctx:")
                parts.append(ctx)
        parts.append("")  # separador entre arquivos

    return "\n".join(parts).rstrip("\n")
