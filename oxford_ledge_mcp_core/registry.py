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


# Tier RANKS for min_tier comparisons. This is a deliberate DUPLICATE of
# `middleware.auth._TIER_ORDER`: this package is published to PyPI and may
# not import in-tree Oxford Ledge code (MCP_FOLLOWUPS M1-R1 import
# boundary), so the two maps are kept in lock-step by a contract instead --
# tests/test_mcp_tier_ladder_parity_contract.py, the MCP sibling of the
# FE/BE pin in tests/test_tier_rank_fe_be_drift_contract.py.
#
# CORRECTED 2026-08-28. The previous value was
#     ("learner", "analyst", "plus", "pro", "investor_plus")
# under a comment claiming it aligned with the HTTP acceptance set. It did
# not: it shared only `plus` and `pro` with that ladder, three of its five
# entries are not tiers at all (they are old DISPLAY names -- Learner,
# Analyst, Investor+AI), and four purchasable tiers were absent. Absent
# means ValueError means denied, so every min_tier tool rejected
# professional ($29 Power User), institutional_plus (the top SKU) and team
# ($99 Advisor) — the three most expensive individual/seat SKUs we sell.
# That is EXT-AUDIT #46 (2026-07-05) repeating in the one copy of the
# ladder its contract does not cover.
#
# Ties are real and must be preserved, which is why this is a dict and not
# a tuple: team ranks WITH pro (advisor seat = Investor-equivalent) and
# team-member ranks WITH free (client seat = Learner-equivalent).
TIER_RANK = {
    "free": 0,
    "team-member": 0,
    "plus": 1,
    "pro": 2,
    "team": 2,
    "professional": 3,
    "institutional_plus": 4,
}

# Deprecated spellings from the 2026-04-24 M2 ladder, kept so an existing
# claude_desktop_config.json keeps working. The rule for what earns an
# alias is ONE-DIRECTIONAL: a spelling that PASSED a gate under the old
# tuple must keep passing (removing it silently revokes access from a
# working config), but a spelling that was DENIED stays denied -- granting
# new access is a product decision, not a bug fix.
#
# So `investor_plus` is aliased (it passed min_tier="plus" at old index 4)
# and `learner` is aliased to free (it was denied, and free is denied too,
# so the alias is behaviour-preserving and merely names it correctly).
# `analyst` is deliberately NOT aliased: tests/test_mcp_tier_gates.py pins
# it as insufficient for plus, and although `Analyst` was once the display
# name for the plus tier, honouring that reading here would hand access to
# every config carrying the old string. It falls through to unknown, which
# denies -- exactly what it did before.
_LEGACY_TIER_ALIASES = {
    "learner": "free",
    "investor_plus": "institutional_plus",
}

# Retained for backward compatibility with anything importing the old name
# (it is in this package's __all__). Cheapest-first, ties broken
# arbitrarily; TIER_RANK is authoritative.
TIER_ORDER = tuple(sorted(TIER_RANK, key=lambda t: TIER_RANK[t]))


def _normalize_tier(value: str | None) -> str | None:
    """Fold a hand-typed tier string to a canonical key, or None.

    Unlike the HTTP side -- where the tier comes from the database -- this
    value is typed by a human into the `env` dict of
    claude_desktop_config.json. `"Plus"` and `" plus "` are the same
    intent as `"plus"`, and denying them produced an error message telling
    the user to set the very variable they had just set.
    """
    if value is None:
        return None
    key = value.strip().lower()
    if not key:
        return None
    key = _LEGACY_TIER_ALIASES.get(key, key)
    return key if key in TIER_RANK else None


def tier_sufficient(user_tier: str | None, min_tier: str | None) -> bool:
    """Return True if `user_tier` meets the `min_tier` bar.

    If `min_tier is None`, always True (tool is unrestricted).
    If `user_tier` is None, empty or unrecognised, False -- deny by
    default. An unrecognised REQUIRED tier is also False: a typo in a
    decorator must fail closed rather than open a tool to everyone.
    """
    if min_tier is None:
        return True
    required = _normalize_tier(min_tier)
    if required is None:
        return False
    held = _normalize_tier(user_tier)
    if held is None:
        return False
    return TIER_RANK[held] >= TIER_RANK[required]
