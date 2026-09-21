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
- Stored and served values are deep-copied, so a caller that mutates a
  result can never rewrite what the next caller is served. See
  `_isolate` for why the copy is on both sides and what it costs.
- TWO budgets, not one: an entry COUNT (`max_size`) and an aggregate
  BYTE budget (`_MAX_CACHE_BYTES`). The count alone was the whole
  ceiling until 2026-09-21, and it stopped being sufficient the moment
  the transport sanctioned an 8 MB body -- 500 x 8 MB is a number no
  small instance survives. See `_MAX_CACHE_BYTES`.

## Public API

    cache_key(tool_name, args) -> str
    cache_get(tool_name, args, ttl_fn) -> Any | None
    cache_set(tool_name, args, result, ttl_fn) -> None
    clear_cache() -> None  # useful for tests
"""
from __future__ import annotations

import copy
import hashlib
import json
import threading
import time as _time
from typing import Any, Callable, Optional

from .errors import ToolError

#: key -> (result, expires_at, size). Index 0 and 1 mean exactly what they
#: meant before the byte budget was added, so any reader of the pair is
#: undisturbed; `size` is this module's own accounting.
_TOOL_CACHE: dict[str, tuple[Any, float, int]] = {}
_CACHE_LOCK = threading.Lock()

#: Aggregate ceiling on STORED payload, in serialized characters.
#:
#: 2026-09-21 reseat L-3. The cache had an entry-COUNT budget
#: (`cache_set(max_size=500)`) and no byte budget at all, which was a fair
#: approximation while a tool response was ~32 KB. It stopped being one when
#: the transport sanctioned an 8 MB success body: 500 entries at that size is
#: ~4 GB of serialized payload, and Python objects cost more than their JSON.
#: Traced on a real 8,070,385-byte holdings body: parse 25.6 MB, the store
#: copy +11.6 MB, the serve copy +11.5 MB -- ~53.7 MB peak for ONE entry, i.e.
#: ~1.4x the serialized size resident for what is kept. So 32 MB here is
#: roughly 46 MB resident of held payload, on a process that also has to
#: serve. The count budget STAYS: it bounds many small entries, which the
#: byte budget alone would let grow without limit.
_MAX_CACHE_BYTES = 32 * 1024 * 1024

#: An entry whose own size exceeds this fraction of the budget is never
#: stored. Without it a single oversized payload would evict every other
#: entry and then sit there alone -- the cache would be worth less than no
#: cache, and the eviction loop would have nothing left to drop.
_MAX_ENTRY_FRACTION = 0.5


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

# The same argument, for identifiers that are NOT tickers and must not be
# routed through the ticker contract. `series` is a FRED series id, and the
# FRED handler's own validator canonicalises it as `raw.strip().upper()`
# before the id ever reaches a URL -- so `dgs10` and `DGS10` produced two
# cache entries and two upstream round-trips for a byte-identical served
# payload. Folded with the SAME plain strip+upper, deliberately not with
# normalize_ticker: that helper is today an identical strip+upper, but it
# owns the ticker contract and is documented as the place dash<->dot
# class-share rewriting would land. FRED ids legally contain '-' and '.'
# (T10Y2Y, DGS10, A191RL1Q225SBEA, and dotted vendor ids), so borrowing the
# ticker helper would make a future ticker-side rewrite silently rewrite
# series ids too -- key identity would stop equalling data identity by
# coincidence rather than by construction. One fold per normalisation
# CONTRACT, not one fold per spelling.
_UPPER_FOLDED_ARGS = ("series",)

#: Distinguishes "no live entry" from a stored `None`, so the copy step can
#: run outside the lock without conflating the two.
_MISS = object()


def _isolate(value: Any) -> Any:
    """Return a value that shares no mutable structure with `value`.

    The cache used to hand every caller the SAME dict it stored, so a
    consumer that mutated a served result -- popped a key, sorted a row
    list in place, annotated an envelope -- silently rewrote what the next
    caller got for the remainder of the TTL, with no second upstream fetch
    to correct it. A read-through cache must be invisible; sharing identity
    makes it a shared mutable global.

    The copy happens on BOTH sides, because one side alone leaves half the
    hole open: copying only on SET still lets the first reader of a hit
    poison the entry for later readers, and copying only on GET still lets
    the PRODUCER (whose returned object is the one that was stored) poison
    it for everyone. Neither ordering is a subset of the other.

    Cost, measured on this machine over JSON-shaped payloads (5 runs each):
    1.5 KB 0.05 ms, 154 KB 4.4 ms, 3.2 MB 106 ms. The wheel's own size
    policy budgets a response at ~32 KB, i.e. ~1 ms; the extreme ~2.5 MB
    payload pays ~80 ms against an upstream round-trip of hundreds of ms
    that the hit avoids entirely, so the copy never inverts the cache's
    value. A json round-trip measured ~35% faster but is refused: it
    rewrites types (tuples to lists) and raises on anything the encoder
    does not know, turning a caching detail into a serving failure.

    WHAT THE COPY COSTS IN NESTING DEPTH, and why it refuses by NAME
    (2026-09-21 reseat L-5). `copy.deepcopy` recurses, so it raises
    `RecursionError` at roughly half the depth the pre-existing recursive
    allowlist pass tolerates: measured on a default 1000-frame limit,
    `json.loads` accepts >= 1990 deep, `filter_to_allowlist` raises at 1000,
    `deepcopy` at ~500. The band [500, 1000) therefore became unservable when
    the copy landed -- a body that parsed and would have filtered now dies in
    the cache layer, AFTER the upstream call has been paid for.

    The decision, stated rather than left implicit: the band stays refused,
    and the refusal is NAMED. Raising the interpreter's recursion limit to
    make the copy reach as deep as the parser would trade a bounded refusal
    for a C-stack overflow, which is a process kill rather than an error.
    What was wrong was not the refusal but its wording: a bare
    `RecursionError` escaped as the dispatch seam's opaque `INTERNAL_ERROR`,
    which tells a reader nothing about what to do. It now says what happened
    and that nothing was cached. Reachability is low -- Oxford Ledge payloads
    are a handful of levels deep and the allowlist prunes non-admitted keys
    at every level, so 500-deep nesting under ADMITTED key names is a
    hostile-or-broken-host shape.
    """
    try:
        return copy.deepcopy(value)
    except RecursionError:
        raise ToolError(
            ToolError.DATA_UNAVAILABLE,
            "The response is nested deeper than this client will copy "
            "(roughly 500 levels), so it was neither served nor cached. "
            "That is a property of the response document, not of your "
            "arguments -- retrying with other arguments will hit the same "
            "depth.") from None


def cache_key(tool_name: str, args: dict[str, Any]) -> str:
    """Deterministic cache key from tool name + sorted-JSON-encoded args."""
    if any(isinstance(args.get(k), str) for k in _CASE_FOLDED_ARGS):
        from .ticker import normalize_ticker
        args = dict(args)
        for k in _CASE_FOLDED_ARGS:
            if isinstance(args.get(k), str):
                args[k] = normalize_ticker(args[k])
    if any(isinstance(args.get(k), str) for k in _UPPER_FOLDED_ARGS):
        args = dict(args)
        for k in _UPPER_FOLDED_ARGS:
            if isinstance(args.get(k), str):
                args[k] = args[k].strip().upper()
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
        if entry is not None and _time.time() < entry[1]:
            hit = entry[0]
        else:
            hit = _MISS
    # Copied OUTSIDE the lock: a large payload would otherwise hold every
    # other caller out of the cache for the duration of its own copy. See
    # the _isolate() note for why a copy happens at all.
    if hit is not _MISS:
        return _isolate(hit)
    return None


def _entry_size(value: Any) -> int:
    """Serialized size of a value, or -1 when it cannot be measured.

    Measured rather than estimated, because the whole point of the byte
    budget is that one entry can be three orders of magnitude bigger than
    another. `default=str` keeps a non-JSON leaf from raising; anything that
    still fails (a cycle, a `__str__` that throws) returns -1, and an entry
    whose size is UNKNOWN is not stored. Failing closed here costs a cache
    hit; failing open costs the budget its meaning.
    """
    try:
        return len(json.dumps(value, default=str))
    except Exception:
        return -1


def cache_set(
    tool_name: str,
    args: dict[str, Any],
    result: Any,
    ttl_fn: Callable[[str], int],
    max_size: int = 500,
    max_bytes: int = _MAX_CACHE_BYTES,
) -> None:
    """Store a tool result in the cache. No-op if TTL is 0.

    TWO budgets, both enforced here:

    * `max_size` -- the entry COUNT. LRU-ish: drop the entry with the
      earliest expiry. Matches the pre-extraction behavior in mcp_server.py.
    * `max_bytes` -- the aggregate SERIALIZED SIZE of everything held. Added
      2026-09-21 (reseat L-3): the count budget alone sanctioned 500 entries
      at whatever size the transport ceiling admits, and that ceiling is
      8 MB. Same earliest-expiry eviction, run until the total fits.

    An entry that would on its own consume more than `_MAX_ENTRY_FRACTION` of
    the budget is NOT stored, and nothing is evicted for it: admitting it
    would empty the cache for one payload, which is worth less than not
    caching it. The call still SERVES normally -- a cache is an optimisation,
    and a miss is not an error.
    """
    ttl = ttl_fn(tool_name)
    if ttl == 0:
        return
    size = _entry_size(result)
    if size < 0 or size > max_bytes * _MAX_ENTRY_FRACTION:
        return
    key = cache_key(tool_name, args)
    stored = _isolate(result)
    with _CACHE_LOCK:
        _TOOL_CACHE[key] = (stored, _time.time() + ttl, size)
        if len(_TOOL_CACHE) > max_size:
            oldest_key = min(_TOOL_CACHE, key=lambda k: _TOOL_CACHE[k][1])
            del _TOOL_CACHE[oldest_key]
        # Evict by earliest expiry until the aggregate fits. `len > 1` keeps
        # the entry just stored rather than evicting into an empty cache --
        # the over-large case is already refused above, so anything that
        # reaches here is worth keeping.
        while (sum(e[2] for e in _TOOL_CACHE.values()) > max_bytes
               and len(_TOOL_CACHE) > 1):
            oldest_key = min(_TOOL_CACHE, key=lambda k: _TOOL_CACHE[k][1])
            del _TOOL_CACHE[oldest_key]


def clear_cache() -> int:
    """Evict all entries. Returns the count evicted. Useful in test fixtures."""
    with _CACHE_LOCK:
        count = len(_TOOL_CACHE)
        _TOOL_CACHE.clear()
    return count


def cache_stats() -> dict[str, int]:
    """Cache statistics: total entries, valid (not-yet-expired), expired, and
    the aggregate serialized `bytes` held against `bytes_budget`.

    The two byte keys were added with the budget itself (2026-09-21): a
    budget nothing can read is a budget nobody notices being wrong.
    """
    now = _time.time()
    with _CACHE_LOCK:
        total = len(_TOOL_CACHE)
        valid = sum(1 for entry in _TOOL_CACHE.values() if entry[1] > now)
        held = sum(entry[2] for entry in _TOOL_CACHE.values())
    return {"total": total, "valid": valid, "expired": total - valid,
            "bytes": held, "bytes_budget": _MAX_CACHE_BYTES}
