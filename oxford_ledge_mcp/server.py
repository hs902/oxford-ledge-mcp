"""Oxford Ledge MCP Server — financial data tools for Claude Desktop.

Provides 29 tools -- 28 backed by U.S.-government public-data sources
(SEC EDGAR / FRED / U.S. Treasury / FDIC / USPTO / USAspending / CFTC) plus
`get_value_investing_fact`, which is Oxford Ledge-authored -- for querying
SEC filings & fundamentals, institutional & insider ownership,
BDC/private-credit holdings, and macro rates. As of 3.1.0 there is no
commercial-vendor feed, and third-party-copyright fields (CUSIPs, agency
ratings, third-party FRED series) are excluded.

The dispatch seam (`_execute_tool_with_limits`) owns the properties every
tool shares, so no handler has to remember them (3.4.0 publish vet, wave B3):
  * bounded arguments outside the published inputSchema `minimum` /
    `maximum` are REFUSED at the seam with the SDK's sentence (both
    transports agree; nothing is clamped);
  * a non-object result from any handler is refused (DATA_UNAVAILABLE) and
    never cached; a dict carrying an `error` is served, honestly, and never
    cached; every raised error is uncached by construction;
  * the emit allowlist is applied for every tool and a tool with no entry is
    REFUSED at runtime (INTERNAL_ERROR, a packaging defect), not served bare;
  * the four standalone tools get their `_meta` from meta_table.py; every
    dict result gets the attribution + not-advice literals last;
  * both transports (the built-in JSON-RPC loop and the mcp SDK) render one
    `_dispatch_to_content` result, so isError, the tier tag on tools/list and
    the malformed-request behaviour cannot diverge; NaN/Infinity never reach
    the wire.

Two modes:
  1. **API mode** (required for most tools): Set OXFORD_LEDGE_URL to your
     running Oxford Ledge instance. All 29 tools are available.
  2. **Standalone mode**: no server needed; 4 tools work directly against
     public APIs (2 keyless SEC EDGAR: get_fundamentals/get_sec_filings;
     2 FRED via FRED_API_KEY: get_yield_curve/get_fred_data). The other 25
     tools raise ToolError.API_REQUIRED in this mode and direct the user to
     set OXFORD_LEDGE_URL.

Y1 (2026-04-24): yfinance was removed from this package. Previous
"standalone mode" covered 18 tools via yfinance; now standalone covers
only the keyless-API tools (see above). See MIGRATING.md for upgrade
notes.

Where things live (the wheel's `oxford_ledge_mcp/` package; every module below
ships, and each handler module registers its tools by being imported HERE at
the source position its block used to occupy, so TOOL_DISPATCH insertion order
never changes):
  * server.py (this file) -- configuration (`_API_URL` / `_API_KEY`), the
    API-mode handlers, the dispatcher (`_execute_tool_with_limits`), the
    JSON-RPC loop, `main`.
  * transport.py -- the REST proxy (`_api_get`) and its status ladder, the
    hosted name-proxy bridge (`_api_tool_call`, keyed + keyless legs), the
    K-2 error translation and the disclosure literals, cut 2026-09-12; it
    reads this module's `_API_URL` / `_API_KEY` at call time.
  * server_tools.py -- the `TOOLS` advertisement (list_tools), cut 2026-09-08.
  * sec_tools.py -- get_sec_filings + the shared SEC ticker guard / archive
    URL / ticker->CIK resolver, cut 2026-09-12.
  * sec_fundamentals.py -- get_fundamentals (SEC XBRL), cut 2026-09-12; its
    own module because get_insider_trades sits between the two SEC handlers.
  * fred_tools.py -- get_yield_curve + get_fred_data and the FRED third-party
    carve-out, cut 2026-09-12.
  * meta_table.py -- the `_meta` (source / source_url / terms_url / basis)
    for the four standalone tools, attached at the dispatch seam iff the
    result carries none (2026-09-12, CV-2); the name-proxied tools get
    theirs from the host.
  * wire.py -- the one serializer (NaN/Infinity -> null) and the JSON-RPC /
    MCP result shapes both transports write, cut 2026-09-12.
  * oxford_ledge_mcp_core/ -- the registry/decorator, cache, ToolError,
    emit allowlists, and the policy modules the handlers consume.
Every name a cut moved is re-exported from this module, so
`oxford_ledge_mcp.server.<name>` keeps resolving. tools_manifest.py is the
generated monorepo catalog and is EXCLUDED from the wheel.

Run as stdio MCP server for Claude Desktop:
    oxford-ledge-mcp
"""

from __future__ import annotations

import sys
import os
import json
import traceback
import threading
import hashlib
import re
import time as _time
import urllib.request
import urllib.parse

# M1 Phase 1b: add parent dir to sys.path so the sibling
# oxford_ledge_mcp_core subpackage imports reliably.
_pkg_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _pkg_parent not in sys.path:
    sys.path.insert(0, _pkg_parent)

import logging
import math
from typing import Any

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
_logger = logging.getLogger("oxford_ledge.mcp")

# ── Configuration ─────────────────────────────────────────────────────────────

# Set OXFORD_LEDGE_URL to connect to a running Oxford Ledge instance
# e.g. OXFORD_LEDGE_URL=https://www.oxfordledge.com or http://localhost:10000
_API_URL = os.environ.get("OXFORD_LEDGE_URL", "").rstrip("/")

# MONETIZE-2 (#121): the caller's Oxford Ledge API key. Without it this client is
# ANONYMOUS against prod — every tier-gated tool 402s and no call is attributable
# to an account, so a paying customer running the published package got the free
# tier and the agent-API meter counted nothing. Optional by design: the keyless
# public-lineage tools (SEC EDGAR / Treasury) keep working with no key,
# which is the redistribution posture we shipped the clean core for.
# The key rides in the `x-api-key` header (never a query string — query strings
# land in access logs and browser history).
_API_KEY = os.environ.get("OXFORD_LEDGE_API_KEY", "").strip()

# ── Per-session concurrency limits ────────────────────────────────────────────
_MCP_MAX_CONCURRENT = 5
_MCP_HEAVY_MAX_CONCURRENT = 2
_mcp_semaphore = threading.Semaphore(_MCP_MAX_CONCURRENT)
_mcp_heavy_semaphore = threading.Semaphore(_MCP_HEAVY_MAX_CONCURRENT)

# ── M1 Phase 1b (2026-04-24): primitives moved to oxford_ledge_mcp_core ───
# Before Phase 1b, this file had its own copies of _MCP_HEAVY_TOOLS,
# _TOOL_TTL, _cache_key/_get/_set, and the ToolError class — duplicating
# the in-tree `mcp_server.py` equivalents. They drifted. Phase 1a put
# the primitives in the shared `oxford_ledge_mcp_core` subpackage; this
# phase makes the pip server consume them too.
#
# Tool registrations are now done via @mcp_tool decorators on each
# `def tool_X(args):` function, which populate the core's REGISTRY at
# module-import time. Claude Desktop sees the current 29-tool gov-public
# surface; behavior is byte-equivalent per contract.

# CHAOS-3 (2026-08-10 vet): this WAS a local empty shadow ("populated by
# @mcp_tool(heavy=True)" was false -- the decorator populates the CORE
# registry's set), so is_heavy was always False and the 2-slot heavy limit
# never enforced. Import the real set; never re-declare it here.
from oxford_ledge_mcp_core import _MCP_HEAVY_TOOLS
# Fail-closed per-tool emit boundary (2026-08-10 allowlist inversion) --
# shared with the future /api/mcp/tool bridge so both paths filter
# through ONE table.
from oxford_ledge_mcp_core.emit_allowlist import (
    EmitAllowlistMissing,
    filter_to_allowlist,
    TOOL_EMIT_ALLOWLIST,
)

# Cache lock + dict (module-level for legacy callers; the core's
# versions are canonical — these aliases point at the same objects).
from oxford_ledge_mcp import __version__
from oxford_ledge_mcp_core.fundamentals_policy import ANNUAL_FORMS, fundamentals_refusal, taxonomy_blocks
from oxford_ledge_mcp_core.split_basis import (
    apply_basis_gate, basis_gate_report, filed_values_by_year)
from oxford_ledge_mcp_core.holders_vintage import holders_disclosure, row_vintage
from oxford_ledge_mcp_core.errors import non_object_response
from oxford_ledge_mcp_core.errors import json_type_name, non_object_tool_error
from oxford_ledge_mcp_core.cache import _TOOL_CACHE, _CACHE_LOCK
from oxford_ledge_mcp.meta_table import standalone_meta
from oxford_ledge_mcp_core import (
    mcp_tool,
    MARKET,
    FUNDAMENTAL,
    STATIC,
    NEVER,
    TOOL_DISPATCH,
    _TOOL_TTL,
    ToolError,
    normalize_ticker,
    cache_key as _cache_key,
    cache_get as _cache_get_core,
    cache_set as _cache_set_core,
    clear_cache as _clear_cache_core,
)
_CACHE_TTL_MARKET = MARKET
_CACHE_TTL_FUNDAMENTAL = FUNDAMENTAL
_CACHE_TTL_STATIC = STATIC
_CACHE_TTL_NEVER = NEVER


def _cache_get(tool_name, args):
    """Return cached result if valid, else None."""
    return _cache_get_core(
        tool_name, args, lambda n: _TOOL_TTL.get(n, _CACHE_TTL_MARKET)
    )


def _cache_set(tool_name, args, result):
    """Store result in cache if tool is cacheable."""
    _cache_set_core(
        tool_name, args, result, lambda n: _TOOL_TTL.get(n, _CACHE_TTL_MARKET)
    )


# ── Y1 (2026-04-24): yfinance excision ────────────────────────────────────
# The previous `_get_yf()` lazy loader + `import yfinance` is removed. All
# tools that previously relied on it now route through `_api_get()` against
# `OXFORD_LEDGE_URL`. Standalone-mode users get `ToolError.API_REQUIRED`
# for the 11 previously-yfinance tools. See docs/plans/YFINANCE_EXCISION.md
# for rationale + MIGRATING.md for the user-facing impact.


def _log(msg):
    print(msg, file=sys.stderr, flush=True)


# Third-party-licensed identifier fields that must not be redistributed by this
# gov-public-data-only package (2026-07-21 compliance review): CUSIP is FactSet /
# CUSIP Global Services IP; agency credit ratings are the rating agencies' IP. Applied
# to raw-passthrough tools (get_13f_holdings, get_corporate_events) so a 13F/8-K row's
# `cusip` (or a blended rating) never ships even though the underlying filing is public.
_CARVEOUT_ID_KEYS = {"cusip", "moodysrating", "moodys_rating", "sprating", "sp_rating",
                     "fitchrating", "fitch_rating", "creditrating", "credit_rating"}


def _strip_carveout_ids(obj: Any) -> Any:
    """Recursively drop third-party-licensed identifier/rating keys from a payload."""
    if isinstance(obj, dict):
        return {k: _strip_carveout_ids(v) for k, v in obj.items()
                if k.lower() not in _CARVEOUT_ID_KEYS}
    if isinstance(obj, list):
        return [_strip_carveout_ids(x) for x in obj]
    return obj


# ── Tool definitions (18 gov-public tools) ───────────────────────────────────
#
# NOTE 2026-05-07: read-only consumers (the public /mcp catalog route, SSR
# renderer) MUST import from the manifest module, NOT from here — importing
# this server.py fires the @mcp_tool decorators below, which collide with
# the root mcp_server.py's decorators when both modules co-exist in
# sys.modules (CI run 67918257844).
#
# NOTE 2026-07-09 (#93 consolidation): tools_manifest.py is now GENERATED
# from the root mcp_tool_definitions.py via tools/gen_mcp_tools_manifest.py
# — do NOT hand-mirror edits from here into it anymore. The pip list (now in server_tools.py) is
# different in kind: it advertises the proxy handlers this pip package
# actually ships, a SUBSET of the monolith's dispatch, and several
# entries still carry pre-rename tool names (get_stock_quote vs
# batch_get_ticker_data, etc.).
#
# NOTE 2026-07-10 (#93 follow-on): this module is NO LONGER imported by the
# live web service. /api/mcp/tool + /api/mcp/tools now dispatch through the
# IN-TREE mcp_server (51 canonical tools, matching the public catalog) —
# routes/routes_admin_fastapi/mcp.py. This file serves ONLY the external
# stdio pip-package path (Claude Desktop et al. proxying REST endpoints via
# OXFORD_LEDGE_URL). Rewriting these 13 gov-public handlers as a thin
# /api/mcp/tool passthrough bridge is the OWNER-gated package-republish
# follow-on (task_queue #93); the drift gate deliberately does not equate
# this list with the manifest until that repair ships.
# (2026-09-05: the three promoted ol_bdc_* moat tools now USE that
# name-proxy bridge -- _api_tool_call below -- per the moat-promotion vet;
# the pre-existing REST-route handlers are unchanged.)

# NOTE 2026-09-08 (file-size-budget cut): the TOOLS list itself now lives
# in oxford_ledge_mcp/server_tools.py -- server.py was AT its 2150-line
# budget with zero headroom and the manifest was the natural seam. The
# list moved VERBATIM and is re-exported here, so
# `from oxford_ledge_mcp.server import TOOLS` is byte-for-byte what it was.
# The location-bearing contracts (the three AST TOOLS-assignment parsers,
# the get_corporate_events / get_yield_curve schema windows, the
# value-investing category scan) were re-pointed in the same commit.
# Do NOT confuse server_tools.py with the sibling tools_manifest.py: the
# latter is the generated monorepo catalog and is EXCLUDED from the wheel.
#
# NOTE 2026-09-12 (second file-size-budget cut, 3.4.0 publish-vet wave): the
# file was back at 1,999 of the 2,000-line threshold with six builders queued
# behind it, so the two standalone tool families left too -- the FRED family
# to fred_tools.py, get_sec_filings + the shared SEC helpers to sec_tools.py,
# and get_fundamentals to sec_fundamentals.py (its own module because
# get_insider_trades sits between the two SEC handlers and a module registers
# everything on first import). Each is imported below at the EXACT position
# its block occupied, so TOOL_DISPATCH insertion order is unchanged, and every
# moved name is re-exported here. The location-bearing pins were re-pointed in
# the same commit; the class gates that walk "every @mcp_tool handler" now
# walk all four handler modules. Contract:
# tests/test_mcp_wheel_tool_family_cut_contract.py.

from oxford_ledge_mcp.server_tools import TOOLS  # noqa: F401  (re-export)


def _with_tier_tag(name: str, description: str) -> str:
    """Prefix a tool description with the tier the dispatcher actually enforces.

    `[Tier: free]` -- callable on any authenticated key.
    `[Tier: plus]` -- 402s below that tier.

    Read from the registry rather than written into the description, so it
    tracks `@mcp_tool(min_tier=...)` automatically. A tool whose tier changes
    gets a correct tag with no edit here, and a tag can never claim a gate the
    dispatcher does not apply.

    Fails OPEN to the untagged description: a listing that raises is worse than
    one missing a hint, and the enforcement is unaffected either way.
    """
    try:
        from oxford_ledge_mcp_core.registry import REGISTRY
        tier = (REGISTRY.get(name) or {}).get("min_tier")
    except Exception:  # noqa: BLE001 -- presentation only
        return description
    return "[Tier: %s] %s" % (tier or "free", description)



# ── API proxy helper + hosted name-proxy bridge: transport.py since 2026-09-12 ─
#
# NOTE 2026-09-12 (third file-size-budget cut, 3.4.0 publish-vet wave C): the
# TRANSPORT block that stood here -- `_api_get` and its status ladder, the
# hosted name-proxy bridge `_api_tool_call` with its keyed / keyless legs, the
# K-2 error translation, `_attach_disclosure` and the two disclosure literals
# -- moved VERBATIM to oxford_ledge_mcp/transport.py after the wave-B seam
# work took this file to 2,159 lines. No @mcp_tool lives in that block, so the
# dispatch order is untouched. Every moved name is re-exported HERE, at the
# position the block occupied, so the handlers below keep calling `_api_get`
# / `_api_tool_call` through this module's globals -- which is what keeps a
# driver's `S._api_get = ...` live for them. The env-derived `_API_URL` /
# `_API_KEY` above STAY here; transport.py reads them from this module at
# call time. A hop INSIDE transport.py (`_api_tool_call` ->
# `_api_tool_call_keyed`) resolves there, not here: patch
# `oxford_ledge_mcp.transport.<name>` for those. Pinned by the family-cut
# contract in the main repo (its transport section).

from oxford_ledge_mcp.transport import (  # noqa: F401  (re-exports)
    _UPSTREAM_TEXT_CAP,
    _excerpt,
    _is_loopback_host,
    _authenticated_request,
    _parse_json_body,
    _api_get,
    _api_error_sentence,
    _OL_ATTRIBUTION,
    _OL_DISCLAIMER,
    _NO_ASK_OPERATOR,
    _HOSTED_TOOL_ERROR_CODES,
    _VERSION_SKEW_MSG,
    _BARE_CODE_TOKEN,
    _OL_PUBLIC_ORIGIN,
    _OL_KEYS_URL,
    _TIER_TOKEN_RE,
    _UPGRADE_PATH_RE,
    _tier_token,
    _tier_refusal_message,
    _hosted_error_to_tool_error,
    _read_http_error_body,
    _http_retry_after,
    _nonblank,
    _attach_disclosure,
    _api_tool_call,
    _api_tool_call_keyed,
    _api_tool_call_keyless,
)


# ── Standalone tool implementations (work without API) ────────────────────────

def _safe(v, default=None):
    if v is None:
        return default
    try:
        if isinstance(v, float) and (v != v):
            return default
        return v
    except Exception:
        return default


def _route_fault(data, ticker, key, noun, path):
    """The reshaping handlers' third error vocabulary (3.4.0 vet
    b03-ownership-1, BLOCK; CISO/COUNSEL/CHAOS co-signed).

    /api/institutional-holders answers HTTP 200 with
    `{"ticker", "holders": [], "error": "PostgreSQL not available"}`
    (data/institutional_holdings.py:1255) and with `str(e)` of a swallowed
    helper exception -- a statement timeout, measured on this very route
    (:1453); options_insiders.py:639-640 wraps both in JSONResponse(200), so
    `_api_get`'s status ladder never fires. `tool_get_holders` rebuilt its
    payload from `holders` alone, dropped the route's `error`, and served
    `holders: []` with `complete: true` -- a backend outage cached for 3600s
    as the FACT "this issuer has no institutional holders".

    Returns the sentence to ship as the payload's `error` (a plain string:
    the same RETURNED vocabulary as `non_object_response`, never raised, so
    the collection key survives for learned-key compatibility) when the
    body carries an `error` or is an EMPTY object; None for a normal body.
    The route's own text rides inside verbatim -- it is envelope vocabulary
    and the fail-closed filter keeps a string `error` -- and the sentence
    denies the false reading by name, the way the non-object envelope does.
    The dispatcher seam (B3) declines to cache a dict carrying a string
    `error`, so the outage is never served for an hour.
    """
    err = data.get("error")
    if err:
        text = err.strip() if isinstance(err, str) else json.dumps(err, sort_keys=True)
        return (
            f"{path} reported an error for '{ticker}': {text} -- the empty "
            f"{key} list is a placeholder for a FAILED read and NOT a "
            f"finding: it does not mean {ticker} has no {noun}. Retry later "
            f"rather than restating the empty list."
        )
    if not data:
        return (
            f"{path} answered with HTTP success for '{ticker}', but the body "
            f"was an empty JSON object with no '{key}' key -- the empty {key} "
            f"list is a placeholder for an unreadable response and NOT a "
            f"finding: it does not mean {ticker} has no {noun}."
        )
    return None


# b03-ownership-2 (3.4.0 vet): a legitimately empty list is a SCOPED
# statement, never a bare `[]` + `complete: true`. The scope is the route's
# (pg_get_institutional_holders_rows: position_type='COM', DISTINCT ON
# fund_cik under a 6-quarter floor, tickers in the 13F universe).
_HOLDERS_EMPTY_SCOPE_NOTE = (
    "No institutional holders returned for {ticker}. Scope of this list: "
    "13F-HR common-stock (COM) positions only, one row per filer at its "
    "latest filing, filers within the last 6 quarters, and only tickers in "
    "the 13F universe. An empty list is a statement about that scope -- "
    "not evidence that nobody holds {ticker}."
)


# ── `_meta.derived_fields` on the two RESHAPING tools (d2-wheel-prose-3) ─────
# The 9 REST proxies carry the route's `_meta` verbatim, and README.md defines
# `derived_fields` as "paths in the tool's own key names". Seven of the nine
# pass the route's payload through, so the route's paths ARE the tool's. The
# two reshaping handlers (get_holders, get_insider_trades) rebuild the payload
# under their own keys -- and passed the route's `_meta` through untouched, so
# the wheel wire named `transactions[].totalValue` over a payload whose rows
# live under `trades` with `value`, and `holders[].change_type` /
# `shares_change` / `pct_change` / `includes_sub_managers` over rows that are
# {holder, shares, value, type, quarter, filingDate} (those four are not on
# the get_holders emit allowlist and can never ship), while the wheel's OWN
# derivations the descriptions name (`vintages`, `rankingBasis`,
# `transTypeLabel`, `is_open_market`) were absent from the list. An agent
# asked which values must be attributed was pointed at keys not on its wire
# (measured 2026-09-13 with `_meta` built by the tree's own
# middleware.route_provenance.build_provenance_meta). The route's block is
# still the source of truth for `source` / `basis` / `terms_url`; only the
# PATHS are translated, at the reshape, from one small map per tool.
#
# Map value None = the route path names a key this tool never emits: DROP.
# A route path not in the map is kept iff it resolves on the wheel payload.
_INSIDER_DERIVED_PATH_MAP = {
    "transactions[].totalValue": "trades[].value",
    "transactions[].position": "trades[].position",
}
_INSIDER_ROW_KEY_MAP = {"totalValue": "value", "insiderName": "insider",
                        "transType": "type"}
#: The wheel's own derivations over the Form 4 row (server-side decode /
#: classification), listed when the payload carries them.
_INSIDER_WHEEL_DERIVED = ("trades[].value", "trades[].position",
                          "trades[].transTypeLabel", "trades[].is_open_market")
_HOLDERS_DERIVED_PATH_MAP = {
    "holders[].change_type": None,
    "holders[].shares_change": None,
    "holders[].pct_change": None,
    "holders[].includes_sub_managers": None,
}
_HOLDERS_WHEEL_DERIVED = ("vintages", "rankingBasis")


def _payload_has_path(payload, path):
    """True when a `derived_fields` path resolves on *payload*: `a.b` walks
    dicts, `a[].b` walks every row of a list (an EMPTY list cannot disprove
    the key -- README: "a path may name a key only one branch emits"), and
    `a.*` needs `a` to be a dict."""
    node = payload
    for seg in path.split("."):
        if seg == "*":
            return isinstance(node, dict)
        if seg.endswith("[]"):
            node = node.get(seg[:-2]) if isinstance(node, dict) else None
            if not isinstance(node, list):
                return False
            rows = [r for r in node if isinstance(r, dict)]
            if not rows:
                return True
            node = rows[0]
            continue
        if not isinstance(node, dict) or seg not in node:
            return False
        node = node[seg]
    return True


def _remap_derived_fields(meta, payload, path_map, wheel_derived,
                          row_key_map=None, route_rows="transactions[].",
                          wheel_rows="trades[]."):
    """Return a COPY of the route's `_meta` whose `derived_fields` name THIS
    tool's keys. Untouched unless `basis` is hybrid and the list is a list;
    `source`, `basis`, `terms_url` and every other key ride through as the
    route wrote them. A translated or unmapped path survives only if it
    resolves on *payload* (the wire this block describes); the wheel's own
    derivations are appended on the same condition."""
    if not isinstance(meta, dict):
        return meta
    out = dict(meta)
    fields = out.get("derived_fields")
    if out.get("basis") != "hybrid" or not isinstance(fields, list):
        return out
    translated = []
    for p in fields:
        if not isinstance(p, str):
            continue
        if p in path_map:
            q = path_map[p]
        elif row_key_map is not None and p.startswith(route_rows):
            key = p[len(route_rows):]
            q = wheel_rows + row_key_map.get(key, key)
        else:
            q = p
        if q is None or q in translated or not _payload_has_path(payload, q):
            continue
        translated.append(q)
    for q in wheel_derived:
        if q not in translated and _payload_has_path(payload, q):
            translated.append(q)
    out["derived_fields"] = translated
    return out


@mcp_tool(name="get_holders", cache=FUNDAMENTAL)
def tool_get_holders(args):
    """Top institutional holders from SEC 13F filings.
    Y1 (2026-04-24): now requires OXFORD_LEDGE_URL (routes via
    Oxford Ledge's SEC EDGAR integration). Migration path for future
    standalone support: call SEC EDGAR 13F endpoint directly."""
    ticker = normalize_ticker(args.get("ticker"))
    # b03-ownership-3 (3.4.0 vet): an empty ticker used to ride out as
    # `?ticker=` and come back as the route's 400 dressed as DATA_UNAVAILABLE
    # ("API returned 400: No ticker provided") -- an argument error reported
    # as a data condition. Refuse BEFORE any fetch, with the code an agent
    # can act on.
    if not ticker:
        raise ToolError(ToolError.INVALID_PARAMS, "ticker is required")
    # 2026-08-10 field test #2: /api/13f-holdings never existed — the live
    # route is /api/institutional-holders (404'd on every call).
    data = _api_get("/api/institutional-holders", {"ticker": ticker})
    if not isinstance(data, dict):
        return non_object_response(ticker, "holders", "institutional holders", "/api/institutional-holders", data)
    raw = data.get("holders") or data.get("filings") or []
    holders = []
    for row in raw[:10]:
        holder = {
            # Field test #3 (2026-08-10): the live rows carry fund_name /
            # value_usd (data/institutional_holdings.get_institutional_holders)
            # -- the old chain read keys this route never emits, so holder
            # rendered "" beside correct share counts.
            "holder": str(row.get("fund_name") or row.get("holder") or row.get("name") or ""),
            "shares": _safe(row.get("shares")),
            # b03-ownership-5: `is not None`, not an or-chain -- a filed
            # value_usd of 0 is a value, and the or-chain served it as null.
            "value": _safe(row.get("value_usd") if row.get("value_usd") is not None
                           else row.get("value")),
            "type": "institutional",
        }
        holder.update(row_vintage(row))  # T7: quarter + filingDate, when the row has them
        holders.append(holder)
    fault = _route_fault(data, ticker, "holders", "institutional holders",
                         "/api/institutional-holders")
    out = {"ticker": ticker, "holders": holders,
           # 2026-09-05 field-report-#2 F5: the [:10] cut was silent -- an
           # agent could not tell "10 holders exist" from "10 of 2,400 shown".
           # Same returned/total discipline as the ol_bdc_* completeness block.
           # b03-ownership-1: on a faulted body `complete` and `totalHolders`
           # are null -- unknown, never `true` over a list the route could not
           # fill.
           "completeness": {
               "returned": len(holders),
               "totalFetched": len(raw),
               "totalHolders": None if fault else data.get("total_holders"),
               "complete": None if fault else ((len(raw) <= 10) if raw else True),
           }}
    if fault:
        out["error"] = fault
    elif not holders:
        out["note"] = _HOLDERS_EMPTY_SCOPE_NOTE.format(ticker=ticker)
    # T7 (2026-09-12): a single asOf ONLY when every returned row shares one
    # quarter, else vintages[] + rankingBasis; the route's coverage block rides
    # through. The measurement and the rule: oxford_ledge_mcp_core.holders_vintage.
    out.update(holders_disclosure(holders, data))
    # 3.4.0 vet (COUNSEL F-1 / CHAOS K-11): the reshape rebuilt the payload
    # and DROPPED the route's `_meta` -- the provenance block route_provenance
    # attaches (source / basis / terms_url). Carry it through when present so
    # the wheel inherits the route's citation with no wheel-side table --
    # with `derived_fields` translated to THIS payload's keys (d2-wheel-
    # prose-3): the route's four QoQ paths never ship here, and the wheel's
    # own `vintages` / `rankingBasis` are named when served.
    if isinstance(data.get("_meta"), dict):
        out["_meta"] = _remap_derived_fields(
            data["_meta"], out, _HOLDERS_DERIVED_PATH_MAP, _HOLDERS_WHEEL_DERIVED)
    return out


# 2026-09-12 (file-size-budget cut, 3.4.0 publish-vet wave): the standalone
# SEC family -- _SEC_TICKER_RE / _reject_bad_sec_ticker / _SEC_ARCHIVE /
# tool_get_sec_filings, plus _resolve_ticker_to_cik_via_sec (shared with
# tool_get_13f_holdings below) -- moved VERBATIM to oxford_ledge_mcp/sec_tools.py.
# The import sits at the EXACT position the block occupied: @mcp_tool registers
# at definition time, so this line IS get_sec_filings' registration and keeps
# TOOL_DISPATCH insertion order identical. Every moved name is re-exported.
from oxford_ledge_mcp.sec_tools import (  # noqa: F401  (re-exports)
    _SEC_ARCHIVE,
    _SEC_TICKER_RE,
    _reject_bad_sec_ticker,
    _resolve_ticker_to_cik_via_sec,
    tool_get_sec_filings,
)


# 2026-09-05 field-report-#2 F5-d: Form 4 transaction codes shipped as raw
# SEC letters ("P", "F") with no decode ring anywhere in the chain. Labels
# verified against the ingest writer's own code domain
# (tools/fetch_form4_transactions.py TRANSACTION_CODES -- the 18 codes it
# classifies); is_open_market mirrors that map exactly (True only for P/S).
_FORM4_CODE_LABELS = {
    "P": "Open-market purchase",
    "S": "Open-market sale",
    "A": "Award/grant",
    "D": "Disposition to issuer",
    "F": "Tax withholding",
    "M": "Option exercise/conversion",
    "G": "Gift",
    "J": "Other",
    "K": "Equity swap",
    "U": "Tender of shares",
    "W": "Acquisition/disposition by will or inheritance",
    "X": "In-the-money option exercise",
    "Z": "Deposit into/withdrawal from voting trust",
    "C": "Conversion of derivative security",
    "I": "Discretionary transaction",
    "O": "Out-of-the-money option exercise",
    "H": "Expiration of long derivative position",
    "L": "Small acquisition (Rule 16a-6)",
}


def _cents(v):
    """Round a monetary float to cents; pass non-numbers through unchanged.

    Applied to `value` (an OL-computed shares x price product whose float
    noise -- 52320.00000000001 -- motivated the 2026-09-05 F5(c) rounding)
    and NEVER to `pricePerShare`: that is the FILED figure, reported by Form 4
    filers to four decimals, and rounding it turned a $0.0045 purchase into
    "$0.0" beside a non-zero value (3.4.0 vet b03-ownership-9)."""
    return round(v, 2) if isinstance(v, float) else v


# The producing helper's window: pg_get_insider_activity(ticker, limit=20),
# `ORDER BY filing_date DESC LIMIT 20` (pg_db/queries/insiders.py); the route
# passes no limit. `totalFetched` can therefore never exceed 20 and is NOT
# the issuer's Form 4 history -- b03-ownership-11 (3.4.0 vet).
_INSIDER_ROUTE_WINDOW = 20

_INSIDER_COMPLETENESS_BASIS = (
    "totalFetched counts the route's window -- the latest 20 Form 4 rows by "
    "filing date -- not the issuer's full history; complete is null when "
    "that window came back full (20 rows), because more may exist beyond it."
)

_INSIDER_EMPTY_SCOPE_NOTE = (
    "No Form 4 rows returned for {ticker}. Scope of this list: Form 4 "
    "transactions filed for this issuer ticker and its share-class siblings, "
    "the latest 20 by filing date. An empty list means none are in that "
    "window of the store -- not that no insider has ever traded {ticker}."
)


@mcp_tool(name="get_insider_trades", cache=FUNDAMENTAL)
def tool_get_insider_trades(args):
    """Recent insider transactions (Form 4).
    Y1 (2026-04-24): now requires OXFORD_LEDGE_URL. Backed by OL's
    form4_transactions table (176K rows) which sources directly from
    SEC EDGAR — more authoritative than yfinance's scraped view."""
    ticker = normalize_ticker(args.get("ticker"))
    # b03-ownership-10 (3.4.0 vet): with no ticker the route silently switches
    # to its MARKET-WIDE branch (market_passthrough.py: pg_get_recent_insider_
    # buys) and this reshape dropped each row's issuer ticker, so the wheel
    # served open-market buys from arbitrary issuers under `ticker: ""`.
    # Refuse BEFORE any fetch.
    if not ticker:
        raise ToolError(ToolError.INVALID_PARAMS, "ticker is required")
    data = _api_get("/api/insider-activity", {"ticker": ticker})
    if not isinstance(data, dict):
        return non_object_response(ticker, "trades", "insider transactions", "/api/insider-activity", data)
    raw = data.get("transactions") or data.get("trades") or []
    trades = []
    # d2-wheel-prose-2 (2026-09-13 deep audit, FIX-BEFORE-PUBLISH): this was
    # `raw[:15]` under a description and a README that both say "the latest
    # 20 rows by filing date (the route's window)" -- rows 16-20 of the
    # window were unreachable through the tool (it has no limit argument)
    # and only the completeness block admitted it. The cut is the route's
    # own window now, so the sentence is true and `complete` keeps its
    # b03-ownership-11 meaning (null when the window came back full).
    for row in raw[:_INSIDER_ROUTE_WINDOW]:
        # 2026-08-10 field test #2: the wire contract is camelCase
        # (schemas/responses.py InsiderActivityTxn: insiderName /
        # transactionType) — the old chains read keys the API never emits,
        # so every row rendered an empty insider + type beside real shares.
        # 2026-09-05 field-report-#2 F5-b: the old date chain preferred
        # filingDate SILENTLY (transactionDate was last in the chain and,
        # until the same-day pg helper fix, never on the wire at all). Both
        # dates ship explicitly, with dateBasis saying which one "date"
        # carries. "date" keeps the SAME value it emitted before this change
        # (filingDate-preferred) -- learned-key compatibility.
        #
        # b03-ownership-7 (3.4.0 vet, BLOCK): dateBasis used to say
        # "transaction" whenever a transactionDate EXISTED while `date` was
        # filingDate-first -- so on every live row (the helper SELECTs both
        # dates) the label named a basis the value did not have. The label
        # now names the date actually served: the two are assigned TOGETHER
        # from one branch, so they cannot disagree.
        code = (row.get("transType") or row.get("transactionType")
                or row.get("type") or row.get("transactionCode") or "")
        txn_date = row.get("transactionDate") or ""
        filing_date = row.get("filingDate") or ""
        if filing_date:
            date_val, date_basis = filing_date, "filing"
        elif txn_date:
            date_val, date_basis = txn_date, "transaction"
        else:
            # the legacy `date` key (no live route emits it): no basis claimed
            date_val, date_basis = (row.get("date") or ""), None
        trades.append({
            # Field test #3: /api/insider-activity rows come from
            # pg_get_insider_activity, whose SQL aliases are the wire SOT:
            # transType / filingDate / totalValue (insiderName was right).
            # The InsiderActivityTxn schema keys belong to a different route
            # family -- pin to the helper's aliases, not the lookalike model.
            "insider": str(row.get("insiderName") or row.get("insider") or row.get("name") or row.get("reportingOwner") or ""),
            "position": row.get("position"),
            "shares": _safe(row.get("shares") or row.get("transactionShares")),
            # b03-ownership-9: the FILED price, unrounded (see _cents).
            "pricePerShare": _safe(row.get("pricePerShare")),
            "value": _cents(_safe(row.get("totalValue") or row.get("value") or row.get("transactionValue"))),
            "sharesOwned": _safe(row.get("sharesOwned")),
            "type": code,
            "transTypeLabel": _FORM4_CODE_LABELS.get(str(code).strip().upper()),
            "is_open_market": str(code).strip().upper() in ("P", "S"),
            "transactionDate": txn_date,
            "filingDate": filing_date,
            "dateBasis": date_basis,
            "date": date_val,
            # b03-ownership-8: the route labels derivative-table rows
            # (insiders.py `securityTitle` / `isDerivative`, on EVERY row);
            # the reshape dropped both, so an RSU award or an option leg read
            # as "50,000 shares" of common stock. Passed through as the
            # helper emits them -- NULL means "the filing did not say", never
            # a claimed "not a derivative".
            "securityTitle": row.get("securityTitle"),
            "isDerivative": row.get("isDerivative"),
            "url": row.get("url"),
            # G2 F10 (2026-09-13): the read-side fold's labels -- see
            # pg_db/queries/form4_dedupe.py. NULL isAmendment means the store
            # holds no form type, never "not amended".
            "isAmendment": row.get("isAmendment"),
            "accessionNumber": row.get("accessionNumber"),
            "supersedesAccession": row.get("supersedesAccession"),
            "formType": row.get("formType"),
        })
    fault = _route_fault(data, ticker, "trades", "insider transactions",
                         "/api/insider-activity")
    window_full = len(raw) >= _INSIDER_ROUTE_WINDOW
    out = {"ticker": ticker, "trades": trades,
           # F5 (2026-09-05): the (then [:15]) cut was silent -- same
           # returned/total discipline as the ol_bdc_* completeness block.
           # b03-ownership-11: `complete` is null when the route's 20-row
           # window came back full -- the store may hold more; and
           # b03-ownership-1 (sibling): null on a faulted body. With the
           # cut at the window (d2-wheel-prose-2) a partial window is
           # served whole, so it is complete by construction.
           "completeness": {
               "returned": len(trades),
               "totalFetched": len(raw),
               "complete": None if (fault or window_full) else True,
               "completeness_basis": _INSIDER_COMPLETENESS_BASIS,
           }}
    if fault:
        out["error"] = fault
    elif not trades:
        out["note"] = _INSIDER_EMPTY_SCOPE_NOTE.format(ticker=ticker)
    # `_meta` passthrough: same reason as tool_get_holders -- with the
    # derived paths renamed to THIS payload's keys (d2-wheel-prose-3).
    if isinstance(data.get("_meta"), dict):
        out["_meta"] = _remap_derived_fields(
            data["_meta"], out, _INSIDER_DERIVED_PATH_MAP,
            _INSIDER_WHEEL_DERIVED, row_key_map=_INSIDER_ROW_KEY_MAP)
    return out


# 2026-09-12 (same cut): tool_get_fundamentals moved VERBATIM to
# oxford_ledge_mcp/sec_fundamentals.py -- a SEPARATE module from sec_tools.py
# because get_insider_trades (above) sits between the two SEC handlers and a
# module registers everything on first import; importing it HERE keeps
# get_fundamentals at its old slot in TOOL_DISPATCH.
from oxford_ledge_mcp.sec_fundamentals import tool_get_fundamentals  # noqa: F401  (re-export)


# 2026-09-12 (same cut): the FRED family -- _YC_HISTORY_LIMIT /
# _YC_LOOKBACK_TOLERANCE_DAYS / _yc_pick_year_ago / tool_get_yield_curve /
# _FRED_THIRDPARTY_NOTE / _FRED_GOV_PREFIXES / _fred_thirdparty_cache /
# _scrub_fred_key / _fred_series_is_thirdparty / tool_get_fred_data -- moved
# VERBATIM to oxford_ledge_mcp/fred_tools.py. Imported at the EXACT position the
# block occupied so get_yield_curve + get_fred_data keep their TOOL_DISPATCH
# slots. Every moved name is re-exported.
from oxford_ledge_mcp.fred_tools import (  # noqa: F401  (re-exports)
    _FRED_GOV_PREFIXES,
    _FRED_THIRDPARTY_NOTE,
    _YC_HISTORY_LIMIT,
    _YC_LOOKBACK_TOLERANCE_DAYS,
    _fred_series_is_thirdparty,
    _fred_thirdparty_cache,
    _scrub_fred_key,
    _yc_pick_year_ago,
    tool_get_fred_data,
    tool_get_yield_curve,
)


# ── API-mode tool implementations ────────────────────────────────────────────
# These tools proxy to a running Oxford Ledge instance.

@mcp_tool(name="get_corporate_events", cache=FUNDAMENTAL)
def tool_get_corporate_events(args):
    ticker = normalize_ticker(args.get("ticker"))
    params = {"ticker": ticker}
    # 2026-08-10 field test #2: /api/corporate-events never existed (the
    # live route is /api/company/events, param name `type`) — 404'd always.
    if args.get("event_type"):
        params["type"] = args["event_type"]
    # Emit boundary (2026-08-10 allowlist inversion, oxford_ledge_mcp_core.
    # emit_allowlist): fail-CLOSED per-tool allowlist is the primary filter --
    # an unrecognized field is dropped, never shipped. The carve-out strip
    # stays as defense-in-depth (its key set also validates the allowlists
    # at import time, so the two can never drift apart).
    return _strip_carveout_ids(filter_to_allowlist(
        "get_corporate_events", _api_get("/api/company/events", params)))


#: search_bdc_borrower's page bound = the host store's LIMIT backstop (the
#: hosted twin's data.bdc_borrower_pg.BORROWER_ROWS_BACKSTOP; the schema
#: `maximum` on both catalogs is pinned equal to it by contract).
_BORROWER_ROWS_BACKSTOP = 5000


def _page_holder_rows(envelope, limit, offset):
    """Wave K / K4 (2026-09-13, OWNER B5a): one declared page of the resolved
    borrower's `holders` rows, sliced IN the wheel over the full REST
    envelope -- /api/bdc/borrower takes only `q`, so a forwarded limit would
    be dropped silently (the get_13f_holdings max_holdings shape), and
    slicing here means `page.total` is exact. Twin of the hosted
    `data.bdc_borrower_pg.page_holder_rows`, pinned output-identical over one
    fixture by tests/test_mcp_search_bdc_borrower_paging_contract.py:
    aggregates stay whole-borrower, `matches` is never paged, an offset past
    the end is an honest empty page, and the tool supplies its own
    `completeness` (total known) so no dispatch default can guess."""
    if (not isinstance(envelope, dict) or envelope.get("error")
            or not isinstance(envelope.get("holders"), list)):
        return envelope  # an error envelope is served as-is, never paged
    rows = envelope["holders"]
    limit = max(1, min(int(limit), _BORROWER_ROWS_BACKSTOP))
    offset = max(0, int(offset))
    window = rows[offset:offset + limit]
    out = dict(envelope)
    out["holders"] = window
    out["page"] = {"limit": limit, "offset": offset, "returned": len(window),
                   "total": len(rows), "hasMore": (offset + len(window)) < len(rows)}
    out["completeness"] = {"returned": len(window), "limit": limit,
                           "total_available": len(rows),
                           "complete": len(window) >= len(rows),
                           "completeness_basis": "total_known", "rows_key": "holders"}
    return out


@mcp_tool(name="search_bdc_borrower", cache=FUNDAMENTAL)
def tool_search_bdc_borrower(args):
    # 2026-08-10 field test #2: /api/bdc/search never existed — the live
    # route is /api/bdc/borrower (same `q` param).
    # 2026-09-09 (OWNER 2a): was a bare _api_get, so this tool
    # emitted unfiltered while its twin get_bdc_list was routed
    # through after COUNSEL F-2. Same boundary, same fix.
    data = _api_get("/api/bdc/borrower", {"q": args["query"]})
    # K4: page ONLY when the caller declared one -- an undeclared call is
    # byte-for-byte the pre-paging wire. Bounds were refused at the seam.
    if args.get("limit") is not None or args.get("offset") is not None:
        data = _page_holder_rows(
            data,
            _BORROWER_ROWS_BACKSTOP if args.get("limit") is None else args["limit"],
            0 if args.get("offset") is None else args["offset"])
    return filter_to_allowlist("search_bdc_borrower", data)


@mcp_tool(name="get_bdc_list", cache=FUNDAMENTAL)
def tool_get_bdc_list(args):
    # 2026-09-08 (COUNSEL F-2): this rode NO emit filter while serving
    # the same reconciliation keys as get_bdc_holdings, which made the
    # allowlist a partial boundary rather than the one its header
    # describes. NB the payload is {"bdcs": [...]}, not a bare list --
    # `bdcs` is admitted explicitly in the allowlist because it is not
    # an _ENVELOPE_KEY, and without it the filter fails closed on the
    # whole response.
    return filter_to_allowlist("get_bdc_list", _api_get("/api/bdc/list"))


@mcp_tool(name="get_bdc_borrower_mark_history", cache=FUNDAMENTAL)
def tool_get_bdc_borrower_mark_history(args):
    # 2026-09-05 external field-test F4: the borrower panel's priceHistory
    # was 8 tranches of ONE quarter. This proxies the purpose-built
    # multi-quarter route. New tools register an emit allowlist rather
    # than ship bare (fail-closed redistribution boundary).
    # b06-bdc-marks-3 (3.4.0 vet): `args["borrower_norm"]` escaped the
    # dispatcher as a bare KeyError and reached the wire as INTERNAL_ERROR
    # "'borrower_norm'" -- an error that will not say what it is -- while
    # the sibling name-proxies return INVALID_PARAMS naming the argument.
    borrower_norm = str(args.get("borrower_norm") or "").strip()
    if not borrower_norm:
        raise ToolError(
            ToolError.INVALID_PARAMS,
            "`borrower_norm` is required -- take borrowerNorm from a "
            "search_bdc_borrower result")
    params = {"q": borrower_norm}
    if args.get("quarters") is not None:
        params["quarters"] = int(args["quarters"])
    return filter_to_allowlist(
        "get_bdc_borrower_mark_history",
        _api_get("/api/bdc/borrower-mark-history", params))


@mcp_tool(name="get_bdc_holdings", cache=FUNDAMENTAL)
def tool_get_bdc_holdings(args):
    # 2026-09-05 external field test: the package could find a borrower
    # (search_bdc_borrower) and list BDCs (get_bdc_list) but had no
    # entity->portfolio read. Proxies the existing /api/bdc/holdings
    # route (its only parameter is `ticker`).
    ticker = normalize_ticker(args.get("ticker"))
    return filter_to_allowlist(
        "get_bdc_holdings", _api_get("/api/bdc/holdings", {"ticker": ticker}))


# ── 2026-09-05 moat promotion: three BDC name-proxies ────────────────────────
# Promoted IN_TREE_ONLY -> SHARED per the CISO+COUNSEL+CHAOS vet
# (docs/board/audit/2026-09-05_CISO_COUNSEL_CHAOS_moat_promotion_vet.md)
# + OWNER ratification. Each handler passes its tool name as a HARDCODED
# STRING LITERAL (K-1: tool-identity integrity — no caller-influenced value
# may reach the dispatched "tool" field; a caller-supplied "tool" key inside
# `arguments` lands harmlessly inside arguments, the hosted route reads only
# the top-level field), and every result rides the fail-closed emit
# allowlist (L-2: "the bridge must ride this filter, or bridging widens
# leakage" — the module's own design note). heavy=True mirrors the in-tree
# registrations for dispersion/top_borrowers (#75 abuse control); all three
# are FREE (deliberately-not-tiered, OWNER-reverted plus-gate precedent at
# moat_reads.py:295-299).

@mcp_tool(name="ol_bdc_top_borrowers", cache=FUNDAMENTAL, heavy=True)
def tool_ol_bdc_top_borrowers(args):
    """Name-proxy to the hosted ol_bdc_top_borrowers (FREE, SEC-EDGAR SOI)."""
    return filter_to_allowlist(
        "ol_bdc_top_borrowers",
        _api_tool_call("ol_bdc_top_borrowers", args))


@mcp_tool(name="ol_bdc_borrower_dispersion", cache=FUNDAMENTAL, heavy=True)
def tool_ol_bdc_borrower_dispersion(args):
    """Name-proxy to the hosted ol_bdc_borrower_dispersion (FREE, SEC-EDGAR SOI)."""
    return filter_to_allowlist(
        "ol_bdc_borrower_dispersion",
        _api_tool_call("ol_bdc_borrower_dispersion", args))


@mcp_tool(name="ol_bdc_common_borrowers", cache=FUNDAMENTAL)
def tool_ol_bdc_common_borrowers(args):
    """Name-proxy to the hosted ol_bdc_common_borrowers (FREE, SEC-EDGAR SOI)."""
    return filter_to_allowlist(
        "ol_bdc_common_borrowers",
        _api_tool_call("ol_bdc_common_borrowers", args))


# ── The eleven, promoted from IN_TREE_ONLY 2026-09-09 ────────────────────────
# COUNSEL COMPLIANCE_REVIEW_v1: ADMIT-WITH-CONDITIONS on all eleven, zero
# refusals, lineage traced handler -> helper SELECT -> ingest per tool. That
# clears the LICENSING leg; `feedback_public_repo_persona_vet` still needs
# CISO + CHAOS + OWNER for the publish itself.
#
# All eleven are NAME-PROXIES, identical in shape to the three moat tools above:
# the hosted dispatch owns the data access and every result rides the
# fail-closed `filter_to_allowlist` (L-2: "the bridge must ride this filter, or
# bridging widens leakage"). Their allowlists were seeded from LIVE payloads,
# never from a SELECT list.
#
# C5, and the reason none of these is a direct client: `get_activist_stakes` is
# a WRITE-ON-READ -- it fires a live EDGAR fetch when its cache is >24h stale.
# Proxied, that call is made by OUR host under OUR rate control and OUR
# identity. A direct EDGAR client in the wheel would put third-party traffic on
# a federal endpoint wearing our contact string, which is the shape to avoid.

@mcp_tool(name="ol_form_d_raises", cache=FUNDAMENTAL)
def tool_ol_form_d_raises(args):
    """Name-proxy to the hosted ol_form_d_raises (SEC EDGAR Form D private placements)."""
    return filter_to_allowlist(
        "ol_form_d_raises",
        _api_tool_call("ol_form_d_raises", args))


@mcp_tool(name="ol_insider_recent_buys", cache=FUNDAMENTAL)
def tool_ol_insider_recent_buys(args):
    """Name-proxy to the hosted ol_insider_recent_buys (SEC Form 4 open-market purchases)."""
    return filter_to_allowlist(
        "ol_insider_recent_buys",
        _api_tool_call("ol_insider_recent_buys", args))


@mcp_tool(name="get_fails_to_deliver", cache=FUNDAMENTAL)
def tool_get_fails_to_deliver(args):
    """Name-proxy to the hosted get_fails_to_deliver (SEC fails-to-deliver, biweekly)."""
    return filter_to_allowlist(
        "get_fails_to_deliver",
        _api_tool_call("get_fails_to_deliver", args))


@mcp_tool(name="get_activist_stakes", cache=FUNDAMENTAL)
def tool_get_activist_stakes(args):
    """Name-proxy to the hosted get_activist_stakes (SEC EDGAR 13D/G beneficial-owner filings)."""
    return filter_to_allowlist(
        "get_activist_stakes",
        _api_tool_call("get_activist_stakes", args))


@mcp_tool(name="ol_treasury_debt", cache=FUNDAMENTAL)
def tool_ol_treasury_debt(args):
    """Name-proxy to the hosted ol_treasury_debt (Treasury MSPD, verbatim)."""
    return filter_to_allowlist(
        "ol_treasury_debt",
        _api_tool_call("ol_treasury_debt", args))


@mcp_tool(name="ol_cftc_cot", cache=FUNDAMENTAL)
def tool_ol_cftc_cot(args):
    """Name-proxy to the hosted ol_cftc_cot (CFTC Commitments of Traders)."""
    return filter_to_allowlist(
        "ol_cftc_cot",
        _api_tool_call("ol_cftc_cot", args))


@mcp_tool(name="ol_fdic_bank", cache=FUNDAMENTAL)
def tool_ol_fdic_bank(args):
    """Name-proxy to the hosted ol_fdic_bank (FDIC BankFind; `ticker` is OUR CERT map)."""
    return filter_to_allowlist(
        "ol_fdic_bank",
        _api_tool_call("ol_fdic_bank", args))


@mcp_tool(name="ol_federal_contracts", cache=FUNDAMENTAL)
def tool_ol_federal_contracts(args):
    """Name-proxy to the hosted ol_federal_contracts (USAspending; ticker attribution is OUR crosswalk)."""
    return filter_to_allowlist(
        "ol_federal_contracts",
        _api_tool_call("ol_federal_contracts", args))


@mcp_tool(name="ol_patents", cache=FUNDAMENTAL)
def tool_ol_patents(args):
    """Name-proxy to the hosted ol_patents (USPTO ODP public filings)."""
    return filter_to_allowlist(
        "ol_patents",
        _api_tool_call("ol_patents", args))


@mcp_tool(name="ol_bdc_mark_changes", cache=FUNDAMENTAL, heavy=True)
def tool_ol_bdc_mark_changes(args):
    """Name-proxy to the hosted ol_bdc_mark_changes (OL parse of SEC-EDGAR BDC SOIs (ol-derived))."""
    return filter_to_allowlist(
        "ol_bdc_mark_changes",
        _api_tool_call("ol_bdc_mark_changes", args))


@mcp_tool(name="ol_bdc_credit_quality", cache=FUNDAMENTAL)
def tool_ol_bdc_credit_quality(args):
    """Name-proxy to the hosted ol_bdc_credit_quality (OL parse of SEC-EDGAR BDC SOIs (ol-derived))."""
    return filter_to_allowlist(
        "ol_bdc_credit_quality",
        _api_tool_call("ol_bdc_credit_quality", args))


# ── The two plus-gated tools: NAME-PROXIES since the 3.4.0 vet ───────────────
# min_tier="plus": canonical premium analytics. Mirrors mcp_server.py;
# sf_monetization_v3-compliant. The wheel does not enforce the tier itself:
# `_api_tool_call`'s keyed leg (/api/mcp/tool) is metered and tier-gated by
# the hosted dispatcher, and the keyless leg (/mcp) refuses a plus-gated
# tool for an anonymous caller with `authentication_required`, which
# `_hosted_error_to_tool_error` maps to AUTH_REQUIRED.
#
# WHY NAME-PROXIES (3.4.0 vet b04-events-capital-1 / -2 / -8, three BLOCKs,
# and -7). Until 2026-09-12 these two were bare `_api_get` relays of the
# SPA's REST routes -- /api/debt-maturities and /api/capital-structure --
# while their descriptions, their allowlists and the hosted catalog were all
# written for the IN-TREE tools of the same name. Measured on the wire:
#   * /api/debt-maturities served schedule[].amount in WHOLE DOLLARS
#     (services/credit_data.py: `amt * 1e6`) under a description that says
#     "in millions" -- a six-orders-of-magnitude lie on a paid tool; and off
#     the SPA's warm data_store it FABRICATED a ladder from Finnhub totalDebt
#     with hard-coded 15/15/12/12/46 buckets (`source: finnhub-estimate`),
#     vendor lineage through a tool classed GOV_PUBLIC/CLEANCORE.
#   * /api/capital-structure served a Finnhub-fed capital STRUCTURE snapshot
#     (layers[]{layer, amount, percentage}) under a description promising the
#     10-year capital ALLOCATION scorecard -- and with the provider's real key
#     shape its hit branch is unreachable, so the description was false on
#     100% of calls.
# The hosted tools are the EDGAR parse (data/edgar_debt_maturities.py, no
# vendor leg; amounts in millions; the validation block) and the XBRL
# scorecard (data/edgar_xbrl._fetch_capital_allocation). Proxying them by
# NAME serves the shape, the units and the provenance (`_meta`) the
# descriptions were written for -- the ol_bdc_* / eleven pattern, hardcoded
# literal tool name (K-1), result through the fail-closed allowlist (L-2),
# whose entries were re-seeded from an EXECUTED capture of the hosted
# dispatcher (tests/test_mcp_debt_capital_name_proxy_contract.py). The REST
# routes' provenance reclassification is a hosted-side change (B5a).

@mcp_tool(name="get_debt_maturities", cache=FUNDAMENTAL, heavy=True, min_tier="plus")
def tool_get_debt_maturities(args):
    """Name-proxy to the hosted get_debt_maturities (SEC EDGAR 10-K/20-F footnote parse; Plus tier -- keyed leg)."""
    return filter_to_allowlist(
        "get_debt_maturities",
        _api_tool_call("get_debt_maturities", args))


@mcp_tool(name="get_capital_allocation", cache=FUNDAMENTAL, heavy=True, min_tier="plus")
def tool_get_capital_allocation(args):
    """Name-proxy to the hosted get_capital_allocation (SEC EDGAR XBRL scorecard: up to 30 fiscal-year labels, 10-year summary window; Plus tier -- keyed leg)."""
    return filter_to_allowlist(
        "get_capital_allocation",
        _api_tool_call("get_capital_allocation", args))


# _resolve_ticker_to_cik_via_sec (the stdlib-only ticker->CIK resolver that
# tool_get_13f_holdings below shares with get_sec_filings) lived here until the
# 2026-09-12 cut; it is now defined in oxford_ledge_mcp/sec_tools.py and bound
# in this module by the re-export import beside get_sec_filings above.


# The route's published bounds for `max_holdings` (server_asgi.py
# fund_holdings: Query(50, ge=1, le=500)); the wheel clamps to them BEFORE
# the request so an out-of-range value never becomes a 422 (b03-ownership-18).
_13F_MAX_HOLDINGS_MIN = 1
_13F_MAX_HOLDINGS_CAP = 500

#: The ticker arm of the get_13f_holdings identifier fork (f2-ownership-6):
#: ASCII letters with at most one `.` or `-` class suffix -- the shapes SEC's
#: company map spells (BRK-B) and callers write (BRK.B); the resolver tries
#: the other separator itself. `str.isalpha()` admitted any Unicode letter
#: and refused every class share.
_13F_TICKER_RE = re.compile(r"[A-Z]{1,10}(?:[.-][A-Z]{1,4})?")
_13F_CIK_RE = re.compile(r"[0-9]{1,10}")


# NO min_tier (OWNER ruling 2026-09-05, external field-test F9): the whole
# 13F product surface is free -- /api/fund-holdings and its timeseries
# sibling carry no require_min_tier, and the SSR/SPA 13F views are public.
# The prior min_tier="plus" here was a FALSE PAYWALL: the package refused
# calls the server would happily serve. Parity is now pinned by
# tests/test_mcp_package_tier_parity_contract.py in the main repo.
@mcp_tool(name="get_13f_holdings", cache=FUNDAMENTAL, heavy=True)
def tool_get_13f_holdings(args):
    # b03-ownership-18 (3.4.0 vet): `args["fund"]` was a KeyError that
    # reached the wire as INTERNAL_ERROR "'fund'" on the base install's
    # built-in transport (which validates nothing). An absent argument is
    # an argument error.
    fund = str(args.get("fund") or "").strip()
    if not fund:
        raise ToolError(
            ToolError.INVALID_PARAMS,
            "fund is required: a numeric CIK (e.g. 1067983 for Berkshire "
            "Hathaway) or a ticker (e.g. BLK, BRK-B).")
    # 2026-09-05 field-report-#2 F6-validation: port of the in-tree SEC-F1
    # guard (mcp_server.py _tool_get_13f_holdings) -- the pip twin took the
    # value unvalidated, so "BRK.B" rode to the API and came back as an
    # SEC-availability-shaped error instead of an argument error. The
    # ticker->CIK resolve uses SEC's public company_tickers.json (stdlib-only
    # -- this package cannot import the in-tree cik_map). Severity note: the
    # value lands as a urlencoded query param on OL's own API (not an EDGAR
    # URL path), so this is error-quality parity, not SSRF.
    #
    # f2-ownership-6 (2026-09-13 deep audit, FIX-BEFORE-PUBLISH): the fork
    # was `fund.isalpha()`, which refused BRK-B / BRK.B BEFORE the dot/dash-
    # aware resolver it hands off to (sec_tools._resolve_ticker_to_cik_via_
    # sec, written for exactly those forms) -- and SEC's map has no bare
    # "BRK" (BRK-A / BRK-B only), so the schema's own example could not
    # resolve on either server. The ticker arm is now the class-share shape
    # (ASCII letters, one optional `.`/`-` class suffix); the CIK arm is
    # 1-10 ASCII digits (DELTA re-vet CISO-4 / CHAOS-8: `isdigit()` admitted
    # Arabic-Indic digits and a 30-digit "CIK", each a guaranteed-404 EDGAR
    # request); anything else is the argument error. The in-tree twin runs
    # the byte-alike _13F_TICKER_RE fork (mcp_server.py, 2026-09-13);
    # tests/test_mcp_behavioral_parity_contract.py pins both twins' ALLOW
    # arm for BRK-B / BRK.B and the deny arm for a value neither shape
    # admits.
    fund_up = fund.upper()
    if _13F_TICKER_RE.fullmatch(fund_up):
        resolved = _resolve_ticker_to_cik_via_sec(fund_up)
        if not resolved:
            raise ToolError(
                ToolError.INVALID_PARAMS,
                f"Could not resolve ticker '{fund}' to a CIK number via SEC's "
                f"company map (class shares are listed there as BRK-B, not "
                f"BRK). Try providing the CIK directly (e.g. 1067983 for "
                f"Berkshire Hathaway).")
        fund = resolved
    elif not _13F_CIK_RE.fullmatch(fund):
        raise ToolError(
            ToolError.INVALID_PARAMS,
            f"Invalid fund identifier '{fund}': provide a numeric CIK "
            f"(e.g. 1067983) or a ticker -- letters with at most one "
            f"class suffix (BLK, BRK-B or BRK.B).")
    # 2026-08-10 field test #2: the route signature is cik-only
    # (server_asgi fund_holdings(cik=Query(""))); sending fund= fell through
    # to 400 "No CIK provided" on every call. The input schema now says CIK.
    params = {"cik": fund}
    # b03-ownership-18: the route bounds are Query(50, ge=1, le=500)
    # (server_asgi.py fund_holdings); the in-tree twin clamps with
    # _wave1_cap(value, 50, 500). The wheel forwarded the raw value, so 1000
    # came back as a pydantic 422 dressed as DATA_UNAVAILABLE and 0 was
    # silently dropped. Clamp to [1, 500] here, explicitly -- the handler
    # guard; a non-numeric value still raises (ValueError -> INVALID_PARAMS
    # at the dispatcher), because "abc" is an argument error, not 50.
    if args.get("max_holdings") is not None and args.get("max_holdings") != "":
        params["max_holdings"] = str(
            max(_13F_MAX_HOLDINGS_MIN, min(_13F_MAX_HOLDINGS_CAP, int(args["max_holdings"]))))
    data = _api_get("/api/fund-holdings", params)
    # b03-ownership-17: both upstream empty branches (data/edgar_13f.py --
    # "no 13F-HR found" and "the infotable parse returned nothing") ship
    # `holdings: [], totalValue: 0` with no note, so a parse failure read as
    # "this fund reports $0 of holdings" and was cached for an hour. The two
    # are told apart by `filingDate`: the not-a-filer branch has none. A
    # string `error` beside the empty list is the package's RETURNED error
    # vocabulary (errors.non_object_response), and the seam never caches a
    # dict that carries one.
    if (isinstance(data, dict) and not data.get("holdings")
            and not data.get("error")):
        filed = str(data.get("filingDate") or "").strip()
        if not filed:
            data["error"] = (
                f"no 13F-HR filed by CIK {fund}: the SEC submissions index "
                f"lists no 13F-HR for this filer -- holdings is empty and "
                f"totalValue 0 is a placeholder, not a reported portfolio "
                f"value.")
        else:
            data["error"] = (
                f"the latest 13F-HR (filed {filed}) could not be parsed: the "
                f"information table returned no rows -- holdings is empty "
                f"and totalValue 0 is a placeholder, not a reported "
                f"portfolio value.")
    # Emit boundary (2026-08-10 allowlist inversion): fail-CLOSED per-tool
    # allowlist first (`cusip` is deliberately absent from it -- the FactSet/
    # CGS carve-out that removed the bond tools in 3.1.0), carve-out strip
    # retained as defense-in-depth.
    return _strip_carveout_ids(filter_to_allowlist("get_13f_holdings", data))


@mcp_tool(name="get_value_investing_fact", cache=STATIC)
def tool_get_value_investing_fact(args):
    # Repointed 3.1.0 (compliance review): was mis-wired to a random-ticker profile
    # endpoint that returned {ticker, company, marketCap, sector} (vendor-lineage fields),
    # not a value-investing fact. /api/value-investing/random serves the OL-original
    # curated lore corpus (value_investing_db) — clean OL IP.
    params = {}
    if args.get("category"):
        params["category"] = args["category"]
    return _api_get("/api/value-investing/random", params)


# TOOL_MAP was formerly a 36-entry dict literal here. As of M1
# Phase 1b (2026-04-24), registrations are via @mcp_tool decorators
# on each tool function above; the dispatcher reads the core's
# TOOL_DISPATCH view (imported above).
# ── Removed-tool guidance ────────────────────────────────────────────────────
# Vendor-data-lineage tools removed across 2.1.0 (FMP-removal) + 3.0.0 (keyless-
# public cut). A client that calls a removed name gets a structured migration
# pointer instead of a bare "Unknown tool", so an agent can self-correct to the
# SEC-XBRL / FRED / hosted replacement. Pointers name ONLY tools that survive in
# this package (the 16 gov-public tools) or "the hosted Oxford Ledge MCP server".
# See CHANGELOG.md + MIGRATING.md. (2.0.4 / 2.1.0 stay installable on PyPI for
# anyone pinning the old tools.)
_REMOVED_TOOLS = {
    # 2.1.0 FMP-removal
    "calculate_intrinsic_value": "removed in 2.1.0 (vendor-fed). Use `get_fundamentals` for SEC-XBRL statements; the DCF/EPV/Graham signal `ol_intrinsic_value` is available via the hosted Oxford Ledge MCP server.",
    "get_company_data": "removed in 2.1.0 (vendor-fed). Use `get_fundamentals` (SEC XBRL).",
    "get_company_profile": "removed in 2.1.0 (vendor-fed). Use `get_fundamentals` (SEC XBRL); company identity is available via the hosted Oxford Ledge MCP server.",
    "get_market_indicators": "removed in 2.1.0 (vendor-fed). Use `get_yield_curve` or `get_fred_data` (FRED).",
    "get_peer_comparison": "removed in 2.1.0 (vendor-fed). Fetch `get_fundamentals` per ticker; `ol_peer_fundamentals` is available via the hosted Oxford Ledge MCP server.",
    "get_price_history": "removed in 2.1.0 (vendor-fed price data has no distributable source).",
    "get_valuation_history": "removed in 2.1.0 (vendor-fed).",
    # 3.0.0 keyless-public cut (gov-public-data-only pip surface)
    "get_stock_quote": "removed in 3.0.0 (keyless-public cut — vendor quote). SEC financials: `get_fundamentals`.",
    "get_financials": "removed in 3.0.0 (keyless-public cut — FMP-primary). Use `get_fundamentals` (SEC XBRL).",
    "get_balance_sheet": "removed in 3.0.0 (keyless-public cut — FMP-primary). Use `get_fundamentals` (SEC XBRL).",
    "get_cash_flow": "removed in 3.0.0 (keyless-public cut — FMP-primary). Use `get_fundamentals` (SEC XBRL).",
    "get_analyst_recommendations": "removed in 3.0.0 (keyless-public cut — vendor analyst estimates; no gov-public source). Available via the hosted Oxford Ledge MCP server.",
    "get_company_info": "removed in 3.0.0 (keyless-public cut — vendor profile). Company identity via the hosted Oxford Ledge MCP server.",
    "compare_stocks": "removed in 3.0.0 (keyless-public cut — vendor data). Fetch `get_fundamentals` per ticker.",
    "screen_stocks": "removed in 3.0.0 (keyless-public cut — vendor screener). Available via the hosted Oxford Ledge MCP server.",
    "get_anomaly_flags": "removed in 3.0.0 (keyless-public cut — vendor composite). Available via the hosted Oxford Ledge MCP server.",
    "get_options_chain": "removed in 3.0.0 (keyless-public cut — options vendor). Available via the hosted Oxford Ledge MCP server.",
    "get_economic_calendar": "removed in 3.0.0 (keyless-public cut). Use `get_fred_data` / `get_yield_curve` (FRED) for macro data.",
    "get_news": "removed in 3.0.0 (keyless-public cut — aggregated third-party headlines). Available via the hosted Oxford Ledge MCP server.",
    "search_company": "removed in 3.0.0 (keyless-public cut — blended profile source). SEC identity via `get_fundamentals` / `get_sec_filings`, or the hosted Oxford Ledge MCP server.",
    # 3.1.0 CUSIP carve-out (bond identifiers are FactSet / CUSIP Global Services IP)
    # 2026-09-14 (W1): both said "Available via the hosted Oxford Ledge MCP
    # server" after the hosted twins were RETIRED (2026-09-13: FINRA
    # auth-walled the public TRACE hosts in 2026-07 and Oxford Ledge holds no
    # licence to redistribute TRACE data). The hosted names still answer, as
    # {status: 'retired', use_instead: 'ol_bond_directory_screen', ...} with
    # empty lists / null prices -- a retired shape, never data -- so the
    # pointer names the working hosted sibling instead.
    "search_bonds": "removed in 3.1.0 (CUSIP carve-out — bond CUSIPs are FactSet IP, licensed separately from FINRA data) and RETIRED on the hosted Oxford Ledge MCP server too (2026-09-13: FINRA auth-walled its public TRACE issuer search; the hosted name now answers status 'retired' with empty lists, never a search result). For corporate-bond discovery use the hosted server's ol_bond_directory_screen (LQD/HYG directory: issuer, grade, coupon, maturity -- reference data, no prices); for one issuer's own maturity schedule use get_debt_maturities.",
    "get_bond_data": "removed in 3.1.0 (CUSIP carve-out — bond CUSIPs are FactSet IP, licensed separately from FINRA data) and RETIRED on the hosted Oxford Ledge MCP server too (2026-09-13: FINRA auth-walled its public TRACE bond page; the hosted name now answers status 'retired' with every price field null, never a quote). For corporate-bond discovery use the hosted server's ol_bond_directory_screen (reference data, no prices); for one issuer's own maturity schedule use get_debt_maturities.",
    "get_short_interest": "removed in 3.1.0 (advertised stub with unresolved float-lineage + FINRA-attribution; returns until it's real). Available via the hosted Oxford Ledge MCP server.",
}


def _unknown_tool_text(name: str) -> str:
    """Message for an unrecognized tool name. A known-removed tool gets a 2.1.0
    migration pointer; anything else gets the generic form."""
    hint = _REMOVED_TOOLS.get(name)
    if hint:
        return f"Tool '{name}' was {hint}"
    return f"Unknown tool: {name}"


# ── Concurrency-limited tool execution ───────────────────────────────────────

_JSON_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: (isinstance(v, int) and not isinstance(v, bool))
    or (isinstance(v, float) and v.is_integer()),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
    "null": lambda v: v is None,
}


def _validate_args_against_schema(tool_name, args):
    """critic-1 (3.4.0 vet), the input-validation half: the mcp SDK runs
    jsonschema over the advertised inputSchema BEFORE `call_tool` and answers
    "Input validation error: 'series' is a required property" (isError), so
    a missing required key could never reach a handler on that transport --
    while the built-in loop, the transport a bare install runs, validated
    nothing and a missing key surfaced as a raw KeyError rendered
    INTERNAL_ERROR "'series'" (b03-18, b05-9, b06-3). The four keywords these
    schemas use -- `required`, `type`, `enum`, `maxItems` -- are checked here
    with the SDK's own sentences, from the SAME `TOOLS` list, so the two
    transports refuse the same call the same way. Raises INVALID_PARAMS."""
    schema = next((t.get("inputSchema") or {} for t in TOOLS if t.get("name") == tool_name), None)
    if not isinstance(schema, dict):
        return
    for key in schema.get("required") or ():
        if key not in args:
            raise ToolError(ToolError.INVALID_PARAMS,
                            f"Input validation error: '{key}' is a required property")
    for pname, spec in (schema.get("properties") or {}).items():
        if pname not in args or not isinstance(spec, dict):
            continue
        v = args[pname]
        types = spec.get("type")
        types = [types] if isinstance(types, str) else (types or [])
        # The property NAME leads each sentence (merge of the 3.4.0 fix wave,
        # 2026-09-12): the SDK's jsonschema text ("None is not of type
        # 'string'") keeps the failing path in `json_path`, not in the message,
        # and four handler-level refusals (b03-3, b03-18, b06-3) were written
        # to say WHICH argument -- so the seam says it too. The SDK sentence
        # stays a substring, which is what the transports-agree contract pins.
        if types and not any(_JSON_TYPE_CHECKS.get(t, lambda _v: True)(v) for t in types):
            shown = "', '".join(types)
            raise ToolError(ToolError.INVALID_PARAMS,
                            f"Input validation error: `{pname}`: {v!r} is not of type '{shown}'")
        # Bounds (re-vet 2026-09-12, CISO-D1 / CHAOS NEW-1 / COUNSEL W-2): the
        # SDK transport's jsonschema REFUSES an out-of-range number before
        # call_tool ("5000 is greater than the maximum of 100") while this
        # loop used to CLAMP it and serve -- the same call answered two ways
        # depending on which extra was installed, and the hosted seam refuses
        # too (mcp_param_contract: "does not silently clamp"). One semantic on
        # every path: refuse, with the SDK's sentence and the property named.
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v:
            mx, mn = spec.get("maximum"), spec.get("minimum")
            if isinstance(mx, (int, float)) and not isinstance(mx, bool) and v > mx:
                raise ToolError(ToolError.INVALID_PARAMS,
                                f"Input validation error: `{pname}`: {v!r} is greater than the maximum of {mx!r}")
            if isinstance(mn, (int, float)) and not isinstance(mn, bool) and v < mn:
                raise ToolError(ToolError.INVALID_PARAMS,
                                f"Input validation error: `{pname}`: {v!r} is less than the minimum of {mn!r}")
        if isinstance(spec.get("enum"), list) and v not in spec["enum"]:
            raise ToolError(ToolError.INVALID_PARAMS,
                            f"Input validation error: `{pname}`: {v!r} is not one of {spec['enum']!r}")
        if isinstance(spec.get("maxItems"), int) and isinstance(v, list) \
                and len(v) > spec["maxItems"]:
            raise ToolError(ToolError.INVALID_PARAMS,
                            f"Input validation error: `{pname}`: {v!r} is too long")


def _carries_error(result):
    """K-3 (ii): a dict result whose `error` says something is an HONEST
    answer to serve and a WRONG thing to cache -- 26 of 29 tools replayed a
    200-with-`error` envelope (PostgreSQL unavailable, SEC unreachable, "No
    data for ZZZZ") for 3600s, so one transient failure became an hour of
    the same refusal. Same predicate `mcp_provenance.attach_provenance` uses."""
    return isinstance(result, dict) and bool(result.get("error"))


def _execute_tool_with_limits(tool_name, args):
    """Execute a tool call with caching, concurrency limits, and structured errors.

    The seam properties (3.4.0 publish vet, in dispatch order): arguments are
    a JSON object (K-4), validated against the advertised inputSchema the way
    the mcp SDK does (critic-1) -- required, type, enum, maxItems AND the
    minimum / maximum bounds, refused with the SDK's own sentences so the
    two transports answer an out-of-range number the same way (re-vet
    CISO-D1 / NEW-1; the clamp-and-note the wave first shipped is gone);
    the handler runs; a non-object result is refused (K-3 i); the emit allowlist
    is applied for EVERY tool and a tool with no entry is refused (critic-6,
    the 3.2.0 K-2 runtime fail-closed property, restored); the four
    standalone tools get their `_meta` (CV-2); the disclosure literals append
    last (L-5); a result carrying
    `error` is served but never cached (K-3 ii). Every RAISED error bypasses
    the cache write by construction.
    """
    handler = TOOL_DISPATCH.get(tool_name)
    if not handler:
        return None
    if not isinstance(args, dict):
        # K-4: a non-object `arguments` reached cache_key and came back as
        # INTERNAL_ERROR with raw Python text ("'list' object has no
        # attribute 'get'"). It is the caller's request that is malformed.
        raise ToolError(
            ToolError.INVALID_PARAMS,
            "tools/call `arguments` must be a JSON object, got a JSON "
            f"{json_type_name(args)}.")
    _validate_args_against_schema(tool_name, args)

    cached = _cache_get(tool_name, args)
    if cached is not None:
        return cached

    is_heavy = tool_name in _MCP_HEAVY_TOOLS

    if not _mcp_semaphore.acquire(timeout=30):
        raise ToolError(
            ToolError.RATE_LIMITED,
            f"Too many concurrent requests ({_MCP_MAX_CONCURRENT} max). Try again shortly.",
            retry_after=30,
        )

    heavy_acquired = False
    try:
        if is_heavy:
            if not _mcp_heavy_semaphore.acquire(timeout=30):
                raise ToolError(
                    ToolError.RATE_LIMITED,
                    f"Too many concurrent heavy requests ({_MCP_HEAVY_MAX_CONCURRENT} max). Try again shortly.",
                    retry_after=30,
                )
            heavy_acquired = True

        result = handler(args)
        # K-3 (i): a passthrough handler hands back whatever the upstream
        # decoded; a bare `[]` walked the key filter unchanged, took no
        # disclosure, was cached and served as isError:false on 23 tools.
        # The two reshaping tools return a DICT envelope for that body and
        # never reach this raise.
        if not isinstance(result, dict):
            raise non_object_tool_error(tool_name, result)
        # CISO F5 (2026-09-12): the emit allowlist is applied HERE, for every
        # tool, rather than by each handler remembering to (9 of 29 did not).
        # Idempotent over the handlers that call it themselves. UNCONDITIONAL
        # (critic-6, 3.4.0 vet): a tool with NO entry raises
        # EmitAllowlistMissing and is refused as a packaging defect -- the
        # runtime fail-closed property the 3.2.0 vet proved by probe and the
        # allowlist module promises, restored. The CI gate
        # (tests/test_mcp_wheel_emit_boundary_contract.py) reds a missing
        # entry first; this is for the day CI is not in the loop. Before
        # _cache_set, so the cache holds the projection that ships.
        result = filter_to_allowlist(tool_name, result)
        # CV-2 (2026-09-12): the four standalone tools cross no hosted seam
        # and carried no `_meta`. Attached iff the result has none, after the
        # filter (envelope vocabulary either way), before the disclosure.
        if "_meta" not in result:
            meta = standalone_meta(tool_name, args)
            if meta:
                result["_meta"] = meta
        # L-5 Layer 3 (2026-09-12): attribution + not-advice attach at the ONE
        # seam (15/29 tools shipped bare); a blank counts as absent (K-8),
        # and BEFORE _cache_set.
        result = _attach_disclosure(result)
        # K-3 (ii): served, honestly; never replayed from the cache.
        if not _carries_error(result):
            _cache_set(tool_name, args, result)
        return result
    except ToolError:
        raise
    except EmitAllowlistMissing as e:
        # 3.2.0 vet K-2b: fail-closed stays fail-closed, but with a
        # structured code instead of a bare INTERNAL_ERROR re-raise. The
        # code is INTERNAL_ERROR deliberately (not DATA_UNAVAILABLE: the
        # data exists -- the PACKAGE is misconfigured, same honesty rule
        # that keeps a routing 404 out of DATA_UNAVAILABLE).
        raise ToolError(
            ToolError.INTERNAL_ERROR,
            f"{tool_name} reached the redistribution boundary without an "
            "emit allowlist -- a packaging defect, not missing data. "
            "Report it to the package maintainer; retrying or changing "
            "arguments will not help.")
    except TimeoutError as e:
        raise ToolError(ToolError.TIMEOUT, str(e))
    except ValueError as e:
        raise ToolError(ToolError.INVALID_PARAMS, str(e))
    except Exception as e:
        err_str = str(e).lower()
        if "rate limit" in err_str or "429" in err_str:
            raise ToolError(ToolError.RATE_LIMITED, str(e), retry_after=60)
        if "not found" in err_str or "no data" in err_str or "empty" in err_str:
            raise ToolError(ToolError.DATA_UNAVAILABLE, str(e))
        raise
    finally:
        if heavy_acquired:
            _mcp_heavy_semaphore.release()
        _mcp_semaphore.release()


# ── The wire: one serializer, one dispatch, two transports ───────────────────
# The serializer (K-5: NaN/Infinity -> null, allow_nan=False), the two
# JSON-RPC result shapes and the SDK-transport error live in wire.py (cut in
# the same wave, for the file-size budget); re-exported here by name.
from oxford_ledge_mcp.wire import (  # noqa: E402,F401  (re-exports)
    _TransportToolError,
    _coerce_for_wire,
    _rpc_error,
    _tool_content,
    _wire_dumps,
    _wire_fallback,
)


def _dispatch_to_content(tool_name, tool_args):
    """Run one tools/call and return (content_text, is_error).

    critic-1 (3.4.0 vet): the built-in loop said isError:true for every
    ToolError / INTERNAL_ERROR / unknown tool while the mcp-SDK `call_tool`
    returned the same text as a plain content list, which the SDK marks
    isError:false -- so on the `[mcp]` install every wheel error read as a
    success. Both transports now render THIS pair.
    """
    fn = TOOL_DISPATCH.get(tool_name)
    if not fn:
        return _unknown_tool_text(tool_name), True
    try:
        result = _execute_tool_with_limits(tool_name, tool_args)
        return _wire_dumps(result, indent=2), False
    except ToolError as e:
        _log(f"Tool error ({tool_name}): [{e.code}] {e.message}")
        return _wire_dumps(e.to_dict()), True
    except Exception as e:
        _log(f"Tool error ({tool_name}): {traceback.format_exc()}")
        error_payload = {"error": {"code": "INTERNAL_ERROR", "message": str(e)}}
        return _wire_dumps(error_payload), True


# ── JSON-RPC MCP Protocol ────────────────────────────────────────────────────

# Server-level disclosure, sent ONCE at initialize (L-5 CYCLE, OWNER-
# ratified 2026-08-24, option e-prime Layer 2). Property register, never
# imperative -- an instruction-shaped sentence in the system prompt reads
# as a script and gets parroted (CHAOS K-D). Per-payload short form is
# the queued Layer 3, not this.
SERVER_INSTRUCTIONS = (
    "Oxford Ledge MCP provides public U.S. financial data -- SEC EDGAR "
    "filings and XBRL fundamentals, institutional and insider ownership, "
    "BDC private-credit holdings, and FRED/Treasury macro series. All "
    "figures are as-filed or as-published and may be lagged, revised, or "
    "incomplete; SEC ownership filings are periodic and can be up to 45 "
    "days behind. This data is informational only and is not investment, "
    "financial, legal, or tax advice. Terms: "
    "https://www.oxfordledge.com/terms")

def handle_request(req):
    """One JSON-RPC request -> one response dict (None for a notification).

    K-4 (3.4.0 publish vet): a non-object request, `params: null` / a
    non-object `params`, or non-object `arguments` used to raise
    AttributeError OUT of this function; the stdio loop logged it and wrote
    NO response, so a conformant client waited forever. They are JSON-RPC
    errors now (-32600 Invalid Request / -32602 Invalid params), which is
    what the mcp SDK's pydantic parsing answers for the same shapes.
    """
    if not isinstance(req, dict):
        return _rpc_error(None, -32600,
                          "Invalid Request: expected a JSON-RPC request object, "
                          f"got a JSON {json_type_name(req)}")
    method = req.get("method", "")
    req_id = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                # 2026-08-10: was a hardcoded "2.0.2" under 3.x — the wheel
                # introduced itself as a version two majors old, which cost a
                # full field-test audit to a stale-build ambiguity. Contract-
                # pinned to __version__ so it can never drift again.
                "serverInfo": {"name": "oxford-ledge-mcp", "version": __version__},
                "instructions": SERVER_INSTRUCTIONS,
            },
        }

    if method == "notifications/initialized":
        return None

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    if method == "tools/list":
        # K-2 (3.4.0 publish vet): the derived `[Tier: ...]` prefix was
        # applied on the SDK `list_tools` path only, and a bare
        # `pip install oxford-ledge-mcp` (`dependencies = []`) runs THIS
        # loop -- so the transport the base install uses listed untagged
        # descriptions. Same helper, same derivation, both transports;
        # tests/test_mcp_transports_agree_contract.py drives both listings.
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": [
            dict(t, description=_with_tier_tag(t["name"], t["description"]))
            for t in TOOLS]}}

    if method == "tools/call":
        params = req.get("params")
        if not isinstance(params, dict):
            return _rpc_error(req_id, -32602,
                              "Invalid params: tools/call `params` must be an object "
                              f"with `name` and `arguments`, got a JSON {json_type_name(params)}")
        tool_name = params.get("name")
        tool_args = params.get("arguments")
        if tool_args is None:
            tool_args = {}
        if not isinstance(tool_name, str) or not isinstance(tool_args, dict):
            return _rpc_error(req_id, -32602,
                              "Invalid params: `name` must be a string and `arguments` "
                              f"an object, got name={json_type_name(tool_name)} "
                              f"arguments={json_type_name(tool_args)}")
        text, is_error = _dispatch_to_content(tool_name, tool_args)
        return {"jsonrpc": "2.0", "id": req_id, "result": _tool_content(text, is_error)}

    return _rpc_error(req_id, -32601, f"Unknown method: {method}")


def main():
    """Run the MCP server on stdin/stdout."""
    mode = "API" if _API_URL else "standalone"
    tool_count = len(TOOLS)
    _log(f"Oxford Ledge MCP Server v{__version__} starting ({tool_count} tools, {mode} mode)...")
    if _API_URL:
        _log(f"  API endpoint: {_API_URL}")
    else:
        _log("  Tip: Set OXFORD_LEDGE_URL for all 29 tools. Standalone mode serves only the keyless public-API tools (2 SEC EDGAR; FRED with FRED_API_KEY).")

    # Try to use the mcp package if available
    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        from mcp.types import Tool, TextContent
        import asyncio

        _log("Using mcp package for protocol handling")

        # 2026-09-05 (field-test F2): a stale install (3.1.1 vs PyPI 3.2.0)
        # tested silently for a full session. The handshake now carries the
        # version so client UIs display it; older mcp libs without the kwarg
        # fall back to the name-only form.
        try:
            server = Server("oxford-ledge-mcp", version=__version__)
        except TypeError:
            server = Server("oxford-ledge-mcp")

        @server.list_tools()
        async def list_tools():
            # TIER, DERIVED. External field test 2026-09-08: "16 of 18
            # descriptions say [Requires API mode]; only 2 actually 402. A
            # model can't predict which call will fail, so it either avoids
            # all 16 or burns calls discovering the boundary."
            #
            # The tag is read from REGISTRY[name]["min_tier"] -- the value the
            # @mcp_tool decorator recorded and the same one the API-mode
            # dispatcher enforces -- so the description cannot drift from the
            # behaviour. Hand-writing the tier into 18 descriptions would have
            # rebuilt the prose-vs-enforcement split this exists to close.
            return [
                Tool(name=t["name"],
                     description=_with_tier_tag(t["name"], t["description"]),
                     inputSchema=t["inputSchema"])
                for t in TOOLS
            ]

        @server.call_tool()
        async def call_tool(name: str, arguments: dict):
            # critic-1 (3.4.0 publish vet): this returned the error JSON as
            # a plain content list for the ToolError / INTERNAL_ERROR /
            # unknown-tool arms, and the SDK marks a returned list as
            # SUCCESS -- every wheel error rode this transport with
            # isError:false while the built-in loop said true. One dispatch
            # for both transports; an error arm RAISES so the SDK flags it.
            text, is_error = _dispatch_to_content(name, arguments)
            if is_error:
                raise _TransportToolError(text)
            return [TextContent(type="text", text=text)]

        async def run():
            async with stdio_server() as (read_stream, write_stream):
                # CHAOS-1 (2026-08-10 vet): create_initialization_options()
                # defaults server_version to the mcp LIBRARY's own version, so
                # SDK-path sessions introduced themselves as e.g. 1.26.0 — the
                # exact version-ambiguity class that cost the field-test
                # audit. Pass the package version explicitly.
                init_opts = server.create_initialization_options()
                init_opts.server_name = "oxford-ledge-mcp"
                init_opts.server_version = __version__
                # Guarded: `instructions` presence on mcp 1.0.0 is
                # NOT-VERIFIED; a crash at startup is strictly worse
                # than a session without the disclosure (L-5 Layer 2).
                if hasattr(init_opts, "instructions"):
                    init_opts.instructions = SERVER_INSTRUCTIONS
                await server.run(read_stream, write_stream, init_opts)

        asyncio.run(run())

    except ImportError:
        _log("mcp package not installed -- using built-in JSON-RPC over stdio")

        while True:
            request = None
            try:
                line = sys.stdin.readline()
                if not line:
                    break

                line = line.strip()
                if not line:
                    continue

                # Handle Content-Length header framing
                if line.lower().startswith("content-length:"):
                    content_length = int(line.split(":", 1)[1].strip())
                    sys.stdin.readline()  # blank separator
                    body = sys.stdin.read(content_length)
                    request = json.loads(body)
                else:
                    request = json.loads(line)

                response = handle_request(request)
                if response is not None:
                    out = _wire_dumps(response)
                    sys.stdout.write(out + "\n")
                    sys.stdout.flush()

            except json.JSONDecodeError as e:
                _log(f"JSON parse error: {e}")
                err = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse error: {e}"}}
                sys.stdout.write(json.dumps(err) + "\n")
                sys.stdout.flush()
            except KeyboardInterrupt:
                break
            except Exception as e:
                # K-4: never leave a request unanswered. handle_request no
                # longer raises on a malformed request, so this arm is the
                # last resort -- and it still writes a JSON-RPC error rather
                # than logging and going quiet on the client.
                _log(f"Unexpected error: {e}")
                traceback.print_exc(file=sys.stderr)
                rid = request.get("id") if isinstance(request, dict) else None
                sys.stdout.write(json.dumps(
                    _rpc_error(rid, -32603, f"Internal error: {type(e).__name__}")) + "\n")
                sys.stdout.flush()

    _log("Oxford Ledge MCP server stopped.")


if __name__ == "__main__":
    main()
