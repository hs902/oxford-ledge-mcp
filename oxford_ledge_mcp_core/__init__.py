"""oxford_ledge_mcp_core — shared primitives for the oxford-ledge-mcp
server (tool registry, cache, structured errors, concurrency).

## Invariants

- Standalone-installable: ZERO imports from the hosted Oxford Ledge
  codebase. Ships as part of the pip-installable `oxford-ledge-mcp`
  distribution; does not assume any server-side code is available.
- Python 3.9+ (matches the pip package's `requires-python`).
- Stdlib-only core (json, hashlib, time, threading, logging).

## Public API

    from oxford_ledge_mcp_core import (
        mcp_tool,          # decorator
        MARKET, FUNDAMENTAL, STATIC, NEVER,  # TTL tier aliases
        ToolError,         # structured error class
        REGISTRY,          # tool registry dict (read-only for consumers)
        cache_key, cache_get, cache_set, clear_cache,
    )
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
    tier_sufficient,
)
from .cache import cache_key, cache_get, cache_set, clear_cache, cache_stats

__all__ = [
    "ToolError",
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
    "tier_sufficient",
]
