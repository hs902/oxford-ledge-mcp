"""oxford_ledge_mcp_core — shared primitives for the Oxford Ledge
MCP servers (in-tree `mcp_server.py` + pip `mcp_package/oxford_ledge_mcp/server.py`).

Introduced 2026-04-24 as part of the M1 twin-dedup sprint
(docs/plans/MCP_FOLLOWUPS.md §7 + §15.1). Before this package, both
servers implemented the same primitives (tool registry, cache,
error class, concurrency) independently, and drifted against each
other. Now both import from here; per-server code is the data-access
adapter layer only.

## Invariants

- **Standalone-installable:** this package has ZERO imports from
  `routes.*`, `middleware.*`, `server_asgi`, `pg_db`, `oxford_ledge_db`,
  `data_providers`, or any other in-tree Oxford Ledge module. It
  ships as part of the pip-installable `oxford-ledge-mcp` distribution
  and must not assume the full OL codebase is available.
- **Python 3.9+:** matches the pip package's `requires-python`.
- **No optional deps** — the core pulls in only `stdlib` modules
  (json, hashlib, time, threading, logging). Data-access modules
  (yfinance, requests, etc.) stay with the consuming server.

## Public API

    from oxford_ledge_mcp_core import (
        mcp_tool,          # decorator
        MARKET, FUNDAMENTAL, STATIC, NEVER,  # TTL tier aliases
        ToolError,         # structured error class
        REGISTRY,          # tool registry dict (read-only for consumers)
        # cache:
        cache_key, cache_get, cache_set, clear_cache,
    )

## Migration status (per sprint plan)

- Phase 1a (THIS COMMIT, 2026-04-24): errors + registry + cache
  extracted; in-tree `mcp_server.py` consumes. Pip server untouched.
- Phase 1b: pip server (`mcp_package/oxford_ledge_mcp/server.py`)
  migrated to consume the same primitives. Drops its 0-decorator
  3-dict pattern.
- Phase 2+: dispatcher + concurrency + stdio protocol + shared tool
  schemas extracted. See MCP_FOLLOWUPS §7.3.
"""
from .errors import ToolError
from .registry import (
    mcp_tool,
    MARKET,
    FUNDAMENTAL,
    STATIC,
    NEVER,
    REGISTRY,
    TOOL_DISPATCH,
    _TOOL_TTL,
    _MCP_HEAVY_TOOLS,
    TIER_ORDER,
    TIER_RANK,
    tier_sufficient,
)
from .cache import cache_key, cache_get, cache_set, clear_cache, cache_stats
from .ticker import normalize_ticker

__all__ = [
    "ToolError",
    "normalize_ticker",
    "mcp_tool",
    "MARKET",
    "FUNDAMENTAL",
    "STATIC",
    "NEVER",
    "REGISTRY",
    "TOOL_DISPATCH",
    "_TOOL_TTL",
    "_MCP_HEAVY_TOOLS",
    "cache_key",
    "cache_get",
    "cache_set",
    "clear_cache",
    "cache_stats",
    "TIER_ORDER",
    "TIER_RANK",
    "tier_sufficient",
]
