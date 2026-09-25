"""The wheel's response-size measurement for the tools no dispatcher ever
measured. IT REPORTS; IT NEVER TRIMS.

## Why this exists

An external live review of the published 3.6.0 wheel (2026-09-21) found
`get_bdc_holdings` for a mid-sized BDC returning ~118,000 characters, past
the reviewing MCP client's tool-result ceiling; the client wrote the answer
to disk instead of handing it to the model. The hosted server has measured
its own payloads since #105 -- a `_meta.response_size` block {chars,
approx_tokens, budget_chars, over_budget[, hint]} attached at its dispatch
seam -- but `get_bdc_holdings` never passes through that seam on either
side: the wheel's handler calls the REST route `/api/bdc/holdings` directly
(`_api_get`), and a REST route runs no dispatcher. The same is true of every
`_api_get`-backed wheel tool. The name-proxied tools (`_api_tool_call`) go
through the hosted dispatcher and already carry the host's block, which the
wheel's envelope frame keeps -- so they are NOT measured again here.

## Why a port, not an import

The hosted measurement (`mcp_response_size.py`, repo root) reads the hosted
registry and parameter catalog. The wheel imports nothing from the monorepo
-- the standalone-installable rule the package `__init__` states, re-affirmed
at the 3.4.0 vet as CISO-11 -- so the pure function is re-stated here:
`len(json.dumps(result, default=str))`, the same serialization the wire uses,
and the same block shape, so a consumer reads ONE shape on both channels.

## Why it does not trim

"IT REPORTS, IT NEVER TRIMS" is the recorded design on both surfaces: dropping
rows to fit a budget would make a tool's own `completeness` block lie -- fewer
rows than found, still claiming complete -- which is strictly worse than a
large answer. Reversing that is an OWNER decision, not a builder's. So this
attaches a measurement and, when over budget, the actionable lever; the caller
decides. The lever is read off the LIVE schema (`_declares_param`) rather than
a hand-kept roster, so it cannot go stale. Until 2026-09-22
`get_bdc_holdings` declared no `limit`, and the hint said so rather than
naming a parameter the tool did not have; the OWNER ruling of that date gave
it `limit` / `offset` -- the review's own measurement, ~118,000 chars for
HRZN, is what made the case -- and the hint began naming them the moment the
schema did. Tools that still declare no `limit` keep the other sentence.

(A line of this docstring may not begin at column 0 with the word `from` or
`import`: the CISO-11 standalone-import contract reads this module's lines by
prefix, and a wrapped sentence starting that way is read as a monorepo import.)

## The budget

32,000 serialized characters -- the hosted policy number (~8K tokens at the
4-chars-per-token rule of thumb, ~4% of a 200K window, ~100 rows of a
BDC-holding shape). It is BELOW every client ceiling this package knows of:
the reviewing client refused an answer of ~53,600 characters, and Claude Code
documents a 10,000-token warning on MCP tool output (~40,000 characters) with
a 25,000-token hard limit. Matching the host's number means a consumer sees
one budget everywhere; because size is reported on every response, the
number can be re-derived from real traffic instead of argued.

The approximate-token figure is the host's rule of thumb, for a human reading
the envelope; this module never re-implements a tokenizer to sharpen it.
"""
from __future__ import annotations

import json
from typing import Any

#: ~4 chars per token, the usual English rule of thumb (same as the host).
CHARS_PER_TOKEN = 4

#: Serialized-character budget, in the dispatcher's own serialization. The
#: hosted policy number; see the module header for why it is also the right
#: one for the wheel.
RESPONSE_BUDGET_CHARS = 32_000


def measure(result: Any) -> int:
    """Serialized size in characters, or 0 when it cannot be measured.

    The SAME `json.dumps(..., default=str)` the wire serializer applies, so the
    number describes what the caller receives rather than an approximation of
    it. (The wire additionally maps NaN/Infinity to null and indents by two;
    the indent is whitespace a tokenizer largely ignores and the budget is a
    policy number, so the compact measurement is the one reported -- exactly
    as on the host.)
    """
    try:
        return len(json.dumps(result, default=str))
    except (TypeError, ValueError):
        return 0


def _size_block(tool_name: str, chars: int, budget_chars: int, has_limit: bool) -> dict[str, Any]:
    block: dict[str, Any] = {
        "chars": chars,
        "approx_tokens": chars // CHARS_PER_TOKEN,
        "budget_chars": budget_chars,
        "over_budget": chars > budget_chars,
    }
    if block["over_budget"]:
        # Name the lever. A warning a caller cannot act on is noise. The
        # hosted text names `limit`; a REST tool with no `limit` gets the
        # honest sentence instead of a parameter it cannot pass.
        lever = (f"re-request `{tool_name}` with a smaller `limit`" if has_limit else
                 f"`{tool_name}` takes no `limit`, so the size is the hosted route's whole "
                 f"answer; read the totals and the first rows, or ask a narrower question")
        block["hint"] = (
            f"This response is {chars:,} chars (~{chars // CHARS_PER_TOKEN:,} tokens), over "
            f"the {budget_chars:,}-char budget. Nothing was dropped -- {lever} if it is "
            f"crowding out your analysis.")
    return block


def attach_response_size(
    tool_name: str,
    result: Any,
    *,
    budget_chars: int = RESPONSE_BUDGET_CHARS,
    has_limit: bool = False,
) -> Any:
    """Additively attach `_meta.response_size`. Never trims, never reorders.

    No-op for a non-dict result and for an error envelope -- an error is
    already small and already tells the caller what to do. The tool's own
    block wins (`setdefault`, as on the host): a payload that arrives with a
    `_meta.response_size` -- the host's, on a name-proxied tool -- keeps it,
    which is what makes this safe to call on every dict result even though
    the seam calls it for the REST path only. A payload with no `_meta` gets
    one, inserted BEFORE the two disclosure literals (the dispatch seam pins
    them as the last two keys). Returns the (possibly new) dict.
    """
    if not isinstance(result, dict) or result.get("error"):
        return result
    chars = measure(result)
    if not chars:
        return result
    block = _size_block(tool_name, chars, budget_chars, has_limit)
    meta = result.get("_meta")
    if isinstance(meta, dict):
        meta.setdefault("response_size", block)
        return result
    out: dict[str, Any] = {}
    tail: dict[str, Any] = {}
    for k, v in result.items():
        if k in ("attribution", "disclaimer"):
            tail[k] = v
        else:
            out[k] = v
    out["_meta"] = {"response_size": block}
    out.update(tail)
    return out
