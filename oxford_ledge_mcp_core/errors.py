"""Structured error vocabulary for MCP tool handlers.

`ToolError` was extracted 2026-04-24 from `mcp_server.py` as part of the
M1 twin-dedup sprint. Both the in-tree and pip MCP servers raise this
same class; consumers (Claude Desktop) see consistent error codes
regardless of which server they're talking to.

A tool has TWO ways to say "something is wrong": it RAISES `ToolError`
(isError true, `{"error": {"code", "message", ...}}`), or it RETURNS an
envelope carrying a plain-string `error` beside the collection it could
not fill. `non_object_response` below builds the second kind, so the two
tools that need it cannot drift into two different sentences.

The RAISED twin for the same input class lives here too (`non_object_tool_error`,
2026-09-12 3.4.0 publish vet K-3 / b04-4 / b04-14 / b03-15 / b07-8): the wheel's
dispatch seam refuses a non-object result from ANY handler with it, so the
23 passthrough tools that used to serve a bare `[]` / `"oops"` / `null` as
isError:false (and cache it for an hour) now raise. Both sentences read the
one `_JSON_TYPE_NAMES` map, so they report the same type the same way.
"""
from __future__ import annotations

from typing import Any


class ToolError(Exception):
    """Structured MCP tool error with code, message, and optional retry_after."""

    RATE_LIMITED = "RATE_LIMITED"
    INVALID_PARAMS = "INVALID_PARAMS"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    CACHE_MISS = "CACHE_MISS"
    API_REQUIRED = "API_REQUIRED"  # pip standalone mode: tool needs OXFORD_LEDGE_URL
    # 2026-08-10 field test #2: a 404 on a nonexistent PATH is a developer
    # bug (client/server version skew), not missing data. Laundering it as
    # DATA_UNAVAILABLE told the agent "the filing doesn't exist" and kept
    # three dead endpoint strings invisible for months.
    NOT_FOUND = "NOT_FOUND"

    #: Keys the envelope owns. `details` may not shadow them -- a refusal
    #: that overwrote `code` would change what the client dispatches on.
    _RESERVED = frozenset({"code", "message", "retry_after"})

    def __init__(self, code: str, message: str,
                 retry_after: int | None = None,
                 details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.message = message
        self.retry_after = retry_after
        # 2026-09-07 (pip get_fundamentals IFRS refusal): a structured
        # refusal has to carry WHAT the filer does have (taxonomy, cik, a
        # hint) beside the human sentence, in the ONE error shape the
        # package already emits. Merged into the `error` object by
        # to_dict(); None/empty leaves the wire shape byte-identical.
        self.details: dict[str, Any] = {
            k: v for k, v in (details or {}).items() if k not in self._RESERVED}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"error": {"code": self.code, "message": self.message}}
        if self.retry_after:
            d["error"]["retry_after"] = self.retry_after
        if self.details:
            d["error"].update(self.details)
        return d


#: JSON type names for the message below. Keyed on the EXACT type, so
#: `bool` (a subclass of `int`) is not reported as a number.
_JSON_TYPE_NAMES: dict[type, str] = {
    list: "array", str: "string", bool: "boolean",
    int: "number", float: "number", type(None): "null",
}


def json_type_name(payload: Any) -> str:
    """The JSON type name of a decoded value (`True` -> "boolean", never
    "number"), for the two non-object sentences below."""
    return _JSON_TYPE_NAMES.get(type(payload), type(payload).__name__)


def non_object_tool_error(tool_name: str, payload: Any) -> ToolError:
    """RAISED refusal for "the upstream answered successfully with a body
    that is not a JSON object" -- the dispatch-seam twin of
    `non_object_response` (which RETURNS an envelope for the two reshaping
    tools that keep their collection key).

    2026-09-12 (3.4.0 publish vet, CHAOS K-3). Every passthrough handler in
    the wheel returns whatever `_api_get` / `_api_tool_call` decoded; the
    seam then filtered it (a list walks through the key filter unchanged),
    attached nothing (`_attach_disclosure` is dict-only), CACHED it for the
    tool's TTL and served it as isError:false. Measured on 23 of 29 tools
    with a 200 body of `[]`, `"oops"` and `null`, all three legs. An agent
    reads a bare `[]` as "there are none". The refusal is DATA_UNAVAILABLE
    (the data may well exist; the CONTRACT between this client and that
    server does not), never INVALID_PARAMS (the caller's arguments are not
    what is wrong) and never cached (a raised ToolError bypasses the
    cache write by construction).
    """
    return ToolError(
        ToolError.DATA_UNAVAILABLE,
        f"{tool_name}: the endpoint answered with a non-object body (a JSON "
        f"{json_type_name(payload)}) -- a client/server contract mismatch, "
        f"not a statement about the data. Nothing was cached. Retrying with "
        f"other arguments will hit the same mismatch; upgrade oxford-ledge-mcp "
        f"or report the response shape.",
    )


def non_object_response(ticker: str, key: str, noun: str, path: str,
                        payload: Any) -> dict[str, Any]:
    """RETURNED (not raised) envelope for "the API answered successfully
    with valid JSON that is not an object".

    2026-09-07. `get_holders` (`server.py:1064`) and `get_insider_trades`
    (`:1199`) returned a bare `{"ticker", "<key>": []}` on that branch. An
    agent reads an empty list as a FACT — "this issuer has no
    institutional holders", "no insider bought or sold" — so a bare empty
    list publishes a false negative about a financial surface. The shape
    here mirrors `tool_get_sec_filings`' empty path: the collection stays
    (learned-key compatibility) and a plain-string `error` says why it is
    empty. FOUNDATIONAL `feedback_label_renames_leave_hidden_siblings` —
    the sweep that fixed `get_fundamentals` NAMED these two and moved on.

    The WORDING is load-bearing, and the obvious wording is wrong. Every
    HTTP-status failure inside `_api_get` raises `ToolError` from the
    `urllib.error.HTTPError` handler and every transport failure raises it
    from the `urllib.error.URLError` handler; a body that is not UTF-8 or
    not JSON raises `UnicodeDecodeError` / `JSONDecodeError` out of
    `json.loads`. None of those reach this branch (executed, not reasoned:
    docs/board/audit/2026-09-07_CHAOS_mcp_empty_list_envelopes.md §1). It
    is reachable ONLY on a successful response whose body parsed to a JSON
    array/string/number/boolean/null. "Could not reach the API" would ship
    a new confident lie of exactly the class this envelope closes.
    """
    jt = json_type_name(payload)
    return {
        "ticker": ticker,
        key: [],
        "error": (
            f"{path} answered with HTTP success for '{ticker}', but the body "
            f"was a JSON {jt}, not an object -- an oxford-ledge-mcp "
            f"client/server contract mismatch. No {noun} could be read from "
            f"it, so the empty {key} list is a placeholder for an unreadable "
            f"response and NOT a finding: it does not mean {ticker} has no "
            f"{noun}. Transport failures, HTTP error statuses and malformed "
            f"JSON all raise instead of reaching this path, so retrying "
            f"another ticker will hit the same mismatch -- upgrade "
            f"oxford-ledge-mcp or report the response shape."
        ),
    }
