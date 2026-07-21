"""Declarative tool registry — the @mcp_tool decorator + cache TTL
tiers + the legacy-compat views that existing dispatcher code reads.

Extracted 2026-04-24 from `mcp_server.py` as part of the M1 twin-
dedup sprint. F2 MCP Dedup Phase 4 (2026-04-24) introduced this
pattern; M1 makes it the shared primitive both servers use.

## Usage

    from oxford_ledge_mcp_core import mcp_tool, MARKET, FUNDAMENTAL, NEVER

    @mcp_tool(name="get_company_data", cache=MARKET)
    def tool_get_company_data(args):
        ...

    @mcp_tool(name="run_screener", cache=NEVER, heavy=True)
    def tool_run_screener(args):
        ...

## How the legacy views are populated

`TOOL_DISPATCH`, `_TOOL_TTL`, and `_MCP_HEAVY_TOOLS` are denormalized
views of `REGISTRY`. The decorator populates them at function-
definition time. Existing dispatcher code iterates them directly;
keeping them in sync with `REGISTRY` avoids a disruptive API break
during the migration.

## Invariants

- `REGISTRY` is the single source of truth. Never mutate the three
  views directly — only via `mcp_tool(...)`.
- Tool names must be unique across the process. Duplicate
  registration raises `ValueError`.
- `cache` default is `MARKET` (60s). Override with FUNDAMENTAL
  (3600s), STATIC (86400s), NEVER (0), or an explicit integer.
- `heavy=True` marks a tool as acquiring the heavy-concurrency
  semaphore (max 2 in-flight) in addition to the general semaphore.
"""
from __future__ import annotations

from typing import Any, Callable

# ── TTL tier aliases ───────────────────────────────────────────────
# Seconds. Exposed as constants so callers can write:
#   @mcp_tool(name="X", cache=MARKET)
# instead of
#   @mcp_tool(name="X", cache=60)
MARKET = 60           # Market data: prices change fast
FUNDAMENTAL = 3600    # Fundamentals: change infrequently
STATIC = 86400        # Static reference: glossary, facts, etc.
NEVER = 0             # Never cache: portfolio mutations, user-specific


# Handler signature seen by dispatcher. Each tool is
# `(args: dict[str, Any]) -> Any` — arg validation is per-tool.
ToolHandler = Callable[[dict[str, Any]], Any]


# ── Primary registry ───────────────────────────────────────────────
# tool_name -> {"handler": callable, "cache_ttl": int, "heavy": bool,
#               "min_tier": str | None}
REGISTRY: dict[str, dict[str, Any]] = {}


# ── Denormalized legacy views ──────────────────────────────────────
# Populated by the decorator at function-definition time. Existing
# dispatcher code in mcp_server.py iterates these directly (via
# `name in TOOL_DISPATCH`, `_TOOL_TTL.get(name, 60)`, etc.) — keeping
# them in sync avoids a disruptive API break during migration.
TOOL_DISPATCH: dict[str, ToolHandler] = {}  # name -> handler
_TOOL_TTL: dict[str, int] = {}       # name -> int (seconds)
_MCP_HEAVY_TOOLS: set[str] = set()  # names of heavy-concurrency tools


def mcp_tool(*, name: str, cache: int = MARKET, heavy: bool = False,
             min_tier: str | None = None,
             is_write: bool = False,
             args_schema: dict[str, Any] | None = None,
             ) -> Callable[[ToolHandler], ToolHandler]:
    """Decorator: register an MCP tool handler with its cache TTL,
    concurrency class, and optional tier-gate requirement.

    Args:
        name: The tool name as Claude Desktop sees it. Must be unique.
        cache: TTL in seconds. Use MARKET / FUNDAMENTAL / STATIC / NEVER
               tier constants or a literal int.
        heavy: If True, the tool acquires the heavy semaphore in
               addition to the general one. Default False.
        min_tier: Required subscription tier for this tool, if any.
                  One of "learner" / "plus" / "pro" / "investor_plus"
                  (matches the HTTP route `require_min_tier` values) or
                  None for unrestricted. M2 (2026-04-24): enforced via
                  `OXFORD_LEDGE_USER_TIER` env var in the in-tree
                  stdio dispatcher. The pip server's HTTP path
                  (`POST /api/mcp/tool`) enforces this `min_tier` as a
                  PRIMARY pre-dispatch gate in
                  `routes/routes_admin_fastapi/mcp.py`
                  (`_mcp_tool_min_tier` -> `TierGateException` 402),
                  resolving the caller's tier from the authenticated
                  session (anon = free, deny-by-default), in addition
                  to the tier-gated `_api_get` backstop. CYCLE
                  2026-05-18 (CISO P1) replaced the prior
                  "enforces via session cookies unchanged" claim,
                  which was fiction — the HTTP route had NO tier gate
                  of its own before that.

    Raises:
        ValueError if `name` is already registered.
    """

    def decorator(fn: ToolHandler) -> ToolHandler:
        if name in REGISTRY:
            raise ValueError(f"Duplicate MCP tool registration: {name}")
        REGISTRY[name] = {
            "handler": fn,
            "cache_ttl": cache,
            "heavy": heavy,
            "min_tier": min_tier,
            # SF-MCP-WRITE Phase 1 (2026-06-12, OWNER-ratified §7.1):
            # METADATA ONLY in this shared core. Enforcement (kill-switch,
            # dry-run-by-default, idempotency, audit append) lives in the
            # in-tree dispatcher (mcp_server.py _execute_write_tool) — the
            # OSS twin gains no write capability from these fields, and the
            # OSS write extension stays separately gated per plan §9 +
            # feedback_public_repo_persona_vet. args_schema is the
            # source-of-truth arg contract (§3.4); the dispatcher enforces
            # additionalProperties:false against it.
            "is_write": is_write,
            "args_schema": args_schema,
        }
        # Keep the legacy views in sync. See the module docstring for
        # why they exist.
        TOOL_DISPATCH[name] = fn
        _TOOL_TTL[name] = cache
        if heavy:
            _MCP_HEAVY_TOOLS.add(name)
        return fn

    return decorator


# Tier ordering for min_tier comparisons. Lower index = cheaper tier.
# Values align with the HTTP-side `middleware.auth.require_min_tier`
# acceptance set. Unknown tier strings compare as "insufficient for anything".
TIER_ORDER = ("learner", "analyst", "plus", "pro", "investor_plus")


def tier_sufficient(user_tier: str | None, min_tier: str | None) -> bool:
    """Return True if `user_tier` meets the `min_tier` bar.

    If `min_tier is None`, always True (tool is unrestricted).
    If `user_tier is None` or unknown, False (deny by default).
    """
    if min_tier is None:
        return True
    try:
        min_idx = TIER_ORDER.index(min_tier)
    except ValueError:
        # Unknown required tier — treat as "never sufficient" (fails closed)
        return False
    if user_tier is None:
        return False
    try:
        user_idx = TIER_ORDER.index(user_tier)
    except ValueError:
        return False
    return user_idx >= min_idx
