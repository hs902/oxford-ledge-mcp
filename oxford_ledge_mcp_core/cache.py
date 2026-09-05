"""In-process response cache for MCP tool handlers.

Extracted 2026-04-24 from `mcp_server.py` as part of the M1 twin-
dedup sprint. Both the in-tree and pip MCP servers now share the
same cache primitives.

## Design

- Key = `tool_name + MD5(sorted_args_json)[:16]`. Deterministic
  across dict-iteration-order changes.
- Storage = module-level dict (`_TOOL_CACHE`). Thread-safe via
  `_CACHE_LOCK`. In-process only; no cross-subprocess sharing.
- TTL tiers are enforced by the caller (via the @mcp_tool
  `cache=...` flag). This module just stores + retrieves.

## Public API

    cache_key(tool_name, args) -> str
    cache_get(tool_name, args, ttl_fn) -> Any | None
    cache_set(tool_name, args, result, ttl_fn) -> None
    clear_cache() -> None  # useful for tests
"""
from __future__ import annotations

import hashlib
import json
import threading
import time as _time
from typing import Any, Callable, Optional

_TOOL_CACHE: dict[str, tuple[Any, float]] = {}  # key -> (result, expires_at)
_CACHE_LOCK = threading.Lock()


# Args folded to canonical form before keying. EXACTLY the fields every
# handler already normalizes via normalize_ticker (the repo-wide ticker
# contract, ratchet-enforced) -- so key identity equals data identity by
# construction. Deliberately NARROW: folding any case-significant arg
# (a query string, a note) would serve one casing's cached result for
# another's, which is a correctness bug traded for a cache hit. The
# 2026-08-31 MCP audit measured the cost of NOT folding these two as
# duplicate entries only (handlers normalize internally), so this is
# efficiency -- but it also means a lowercase retry after an uppercase
# miss now HITS instead of refetching.
_CASE_FOLDED_ARGS = ("ticker", "symbol")


def cache_key(tool_name: str, args: dict[str, Any]) -> str:
    """Deterministic cache key from tool name + sorted-JSON-encoded args."""
    if any(isinstance(args.get(k), str) for k in _CASE_FOLDED_ARGS):
        from .ticker import normalize_ticker
        args = dict(args)
        for k in _CASE_FOLDED_ARGS:
            if isinstance(args.get(k), str):
                args[k] = normalize_ticker(args[k])
    args_str = json.dumps(args, sort_keys=True, default=str)
    h = hashlib.md5((tool_name + args_str).encode()).hexdigest()[:16]
    return f"{tool_name}:{h}"


def cache_get(
    tool_name: str,
    args: dict[str, Any],
    ttl_fn: Callable[[str], int],
) -> Optional[Any]:
    """Return cached result if valid, else None.

    Args:
        tool_name: The tool name.
        args: The tool call's args dict.
        ttl_fn: Callable that takes a tool name and returns its TTL in
                seconds. The dispatcher passes a lookup into the
                registry here. Returning 0 means "never cache" —
                `cache_get` returns None immediately.
    """
    ttl = ttl_fn(tool_name)
    if ttl == 0:
        return None
    key = cache_key(tool_name, args)
    with _CACHE_LOCK:
        entry = _TOOL_CACHE.get(key)
        if entry and _time.time() < entry[1]:
            return entry[0]
    return None


def cache_set(
    tool_name: str,
    args: dict[str, Any],
    result: Any,
    ttl_fn: Callable[[str], int],
    max_size: int = 500,
) -> None:
    """Store a tool result in the cache. No-op if TTL is 0.

    LRU-ish eviction: if the cache exceeds `max_size`, drop the entry
    with the earliest expiry timestamp. Matches the pre-extraction
    behavior in mcp_server.py.
    """
    ttl = ttl_fn(tool_name)
    if ttl == 0:
        return
    key = cache_key(tool_name, args)
    with _CACHE_LOCK:
        _TOOL_CACHE[key] = (result, _time.time() + ttl)
        if len(_TOOL_CACHE) > max_size:
            oldest_key = min(_TOOL_CACHE, key=lambda k: _TOOL_CACHE[k][1])
            del _TOOL_CACHE[oldest_key]


def clear_cache() -> int:
    """Evict all entries. Returns the count evicted. Useful in test fixtures."""
    with _CACHE_LOCK:
        count = len(_TOOL_CACHE)
        _TOOL_CACHE.clear()
    return count


def cache_stats() -> dict[str, int]:
    """Return cache statistics: total entries, valid (not-yet-expired), expired."""
    now = _time.time()
    with _CACHE_LOCK:
        total = len(_TOOL_CACHE)
        valid = sum(1 for _, (_, exp) in _TOOL_CACHE.items() if exp > now)
    return {"total": total, "valid": valid, "expired": total - valid}
