"""Agente auditor de acessibilidade (TASK-004).

ÚNICO módulo que toca o agno — e SEMPRE via import lazy dentro de função, de modo
que schema/diff/knowledge/report/gate importem e rodem nos testes sem agno
instalado.

Design transversal: performance de gate de CI. O diff já chega pré-parseado no
payload (sem tools => menos round-trips e menos tokens), temperature baixa para
determinismo, e o bloco estático de conhecimento (build_knowledge_block) é
marcado para prompt caching da Anthropic quando a versão do agno suportar.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

from a11y_auditor.knowledge import build_instructions, build_knowledge_block
from a11y_auditor.schema import AuditVerdict, approved_verdict

# Modelo default. Pode ser sobrescrito por A11Y_AUDITOR_MODEL ou pelo argumento.
DEFAULT_MODEL_ID = "claude-opus-4-8"

# Temperature baixa para maximizar determinismo do veredito no gate de CI.
_TEMPERATURE = 0.0

# Nome único da env var da API key, agnóstico de provider (Anthropic, Google...).
# Passada EXPLICITAMENTE ao construtor do modelo — o SDK não a lê sozinho (ele
# só conhece ANTHROPIC_API_KEY / GOOGLE_API_KEY), por isso a injeção manual.
MODEL_API_KEY_ENV = "MODEL_API_KEY"

# Cache do agente entre chamadas repetidas (mesmo processo) — evita reconstruir
# instruções e re-instanciar o modelo a cada run_audit. Chave: (provider, model_id).
_AGENT_CACHE: dict[tuple[str, str], Any] = {}


def _resolve_model_id(model_id: Optional[str]) -> str:
    """Resolve o id do modelo: argumento > env A11Y_AUDITOR_MODEL > default."""
    return model_id or os.environ.get("A11Y_AUDITOR_MODEL") or DEFAULT_MODEL_ID


def _resolve_provider(provider: Optional[str], model_id: str) -> str:
    """Resolve o provider: argumento > env A11Y_AUDITOR_PROVIDER > inferência do id.

    Inferência pelo id do modelo: ids "gemini*" => google; o resto => anthropic.
    Retorna sempre "anthropic" ou "google".
    """
    explicit = provider or os.environ.get("A11Y_AUDITOR_PROVIDER")
    if explicit:
        normalized = explicit.strip().lower()
        if normalized in ("google", "gemini", "google-genai"):
            return "google"
        return "anthropic"
    if "gemini" in model_id.lower():
        return "google"
    return "anthropic"


def _api_key() -> Optional[str]:
    """API key unificada (MODEL_API_KEY). None se não setada (SDK tenta o fallback dele)."""
    return os.environ.get(MODEL_API_KEY_ENV)


def _build_system_message() -> str:
    """Bloco de sistema estático (catálogo + exemplos + allowlist + algoritmo de tier).

    É constante entre execuções => habilita prompt caching no provider.
    """
    return build_knowledge_block()


def _build_model(model_id: str, provider: str) -> Any:
    """Instancia o modelo do agno do provider resolvido (anthropic ou google).

    A API key vem SEMPRE de MODEL_API_KEY, passada explicitamente como `api_key`
    (o SDK não conhece esse nome de env — só ANTHROPIC_API_KEY / GOOGLE_API_KEY).

    Anthropic: habilita prompt caching do bloco estático. O bloco (catálogo +
    exemplos + allowlist, ~45KB, bem acima do mínimo de 4096 tokens do Opus) é
    constante entre execuções, então é marcado com cache_control ephemeral via
    `cache_system_prompt=True` — leituras de cache custam ~0.1x do preço de input,
    o maior ganho de custo/latência do gate em CI frequente. Se a versão do agno
    não suportar o parâmetro, faz fallback silencioso (funciona, só não economiza).

    Google/Gemini: mesmo bloco estático via system_prompt; o prompt caching do
    Gemini não usa `cache_system_prompt`, então não é marcado aqui.
    """
    system_message = _build_system_message()
    api_key = _api_key()

    if provider == "google":
        from agno.models.google import Gemini  # import lazy

        return _instantiate(Gemini, model_id, system_message, api_key, cache=False)

    from agno.models.anthropic import Claude  # import lazy

    return _instantiate(Claude, model_id, system_message, api_key, cache=True)


def _instantiate(
    model_cls: Any,
    model_id: str,
    system_message: str,
    api_key: Optional[str],
    cache: bool,
) -> Any:
    """Constrói o modelo do agno com fallback defensivo de kwargs.

    Tenta na ordem: (com cache, se pedido) -> (sem cache) -> (sem system_prompt).
    `api_key` só é passado quando setado (senão deixa o SDK usar o fallback dele).
    """
    base: dict[str, Any] = {
        "id": model_id,
        "temperature": _TEMPERATURE,
        "system_prompt": system_message,
    }
    if api_key:
        base["api_key"] = api_key

    if cache:
        try:
            return model_cls(**base, cache_system_prompt=True)
        except TypeError:
            logger.warning(
                "%s não aceitou cache_system_prompt — o bloco estático de ~45KB "
                "será reenviado SEM cache a cada run. Atualize o agno para habilitar "
                "prompt caching e reduzir custo/latência do gate.",
                getattr(model_cls, "__name__", "model"),
            )

    try:
        return model_cls(**base)
    except TypeError:
        # Provider que nomeia o system prompt de outra forma: cai pro bare model.
        base.pop("system_prompt", None)
        return model_cls(**base)


def _log_cache_usage(result: Any) -> None:
    """Best-effort: loga métricas de prompt caching do run para expor cache miss.

    Lê cache_read_input_tokens / cache_creation_input_tokens do usage do agno
    (campos canônicos da Anthropic). Se cache_read ficar 0 em execuções repetidas,
    algum invalidador silencioso está reenviando o bloco estático a preço cheio.
    Totalmente defensivo: qualquer variação de API do agno é ignorada.
    """
    try:
        metrics = getattr(result, "metrics", None) or getattr(result, "usage", None)
        if metrics is None:
            return

        def _get(obj: Any, name: str) -> Optional[int]:
            if isinstance(obj, dict):
                return obj.get(name)
            return getattr(obj, name, None)

        read = _get(metrics, "cache_read_input_tokens")
        created = _get(metrics, "cache_creation_input_tokens")
        if read is None and created is None:
            return
        if not read:
            logger.warning(
                "Prompt cache miss: cache_read_input_tokens=%s, "
                "cache_creation_input_tokens=%s. O bloco estático não foi servido "
                "do cache — verifique a versão do agno e a estabilidade do system prompt.",
                read,
                created,
            )
        else:
            logger.info(
                "Prompt cache hit: cache_read_input_tokens=%s, cache_creation_input_tokens=%s.",
                read,
                created,
            )
    except Exception:  # nunca deixar telemetria quebrar o gate
        pass


def build_agent(model_id: Optional[str] = None, provider: Optional[str] = None) -> Any:
    """Monta o Agent do agno (import lazy).

    - response_model=AuditVerdict (saída estruturada validada por pydantic).
    - instructions=build_instructions() (regras de auditoria, AA only, pt-BR...).
    - SEM tools: o diff já vem pré-parseado no prompt => menos round-trips/tokens.
    - markdown=False: o report markdown canônico é re-renderizado no gate.
    - temperature baixa + prompt caching do bloco estático para perf de CI.
    - provider anthropic (default) ou google/gemini, resolvido pelo id/env.
    """
    from agno.agent import Agent  # import lazy

    resolved = _resolve_model_id(model_id)
    resolved_provider = _resolve_provider(provider, resolved)
    model = _build_model(resolved, resolved_provider)

    return Agent(
        model=model,
        response_model=AuditVerdict,
        instructions=build_instructions(),
        tools=None,
        markdown=False,
    )


def _get_cached_agent(model_id: Optional[str], provider: Optional[str]) -> Any:
    """Reusa o agente entre chamadas repetidas no mesmo processo (chave provider+id)."""
    resolved = _resolve_model_id(model_id)
    key = (_resolve_provider(provider, resolved), resolved)
    agent = _AGENT_CACHE.get(key)
    if agent is None:
        agent = build_agent(model_id, provider)
        _AGENT_CACHE[key] = agent
    return agent


def run_audit(
    payload: str,
    model_id: Optional[str] = None,
    provider: Optional[str] = None,
) -> AuditVerdict:
    """Roda o agente sobre o payload e devolve o AuditVerdict.

    Reusa o agente em chamadas repetidas (cache por provider+model_id). Se o
    payload estiver vazio (nenhum hunk relevante), aprova sem chamar o LLM.
    """
    if not payload or not payload.strip():
        return approved_verdict(
            summary="Nenhum ponto de acessibilidade relevante no diff.",
            report_markdown="",
        )

    agent = _get_cached_agent(model_id, provider)
    result = agent.run(payload)
    _log_cache_usage(result)
    return result.content
