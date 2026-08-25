"""Oxford Ledge MCP Server — financial data tools for Claude Desktop.

Provides 13 gov-public-data tools for querying SEC filings & fundamentals,
institutional & insider ownership, BDC/private-credit holdings, and macro
rates. As of 3.1.0 this is a gov-public-data-only surface (SEC EDGAR / FRED /
U.S. Treasury) — no commercial-vendor feed, and third-party-copyright fields
(CUSIPs, agency ratings, third-party FRED series) are excluded.

Two modes:
  1. **API mode** (required for most tools): Set OXFORD_LEDGE_URL to your
     running Oxford Ledge instance. All 13 tools are available.
  2. **Standalone mode**: no server needed; 4 tools work directly against
     public APIs (2 keyless SEC EDGAR: get_fundamentals/get_sec_filings;
     2 FRED via FRED_API_KEY: get_yield_curve/get_fred_data). The other 9
     tools raise ToolError.API_REQUIRED in this mode and direct the user to
     set OXFORD_LEDGE_URL.

Y1 (2026-04-24): yfinance was removed from this package. Previous
"standalone mode" covered 18 tools via yfinance; now standalone covers
only the keyless-API tools (see above). See MIGRATING.md for upgrade
notes.

Run as stdio MCP server for Claude Desktop:
    oxford-ledge-mcp
"""

import sys
import os
import json
import traceback
import threading
import hashlib
import time as _time
import datetime as _dt
import urllib.request
import urllib.parse

# M1 Phase 1b: add parent dir to sys.path so the sibling
# oxford_ledge_mcp_core subpackage imports reliably.
_pkg_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _pkg_parent not in sys.path:
    sys.path.insert(0, _pkg_parent)

import logging
import math
import re
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
# module-import time. Claude Desktop sees the current 13-tool gov-public
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
)

# Cache lock + dict (module-level for legacy callers; the core's
# versions are canonical — these aliases point at the same objects).
from oxford_ledge_mcp import __version__
from oxford_ledge_mcp_core.cache import _TOOL_CACHE, _CACHE_LOCK
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


# ── Tool definitions (13 gov-public tools) ───────────────────────────────────
#
# NOTE 2026-05-07: read-only consumers (the public /mcp catalog route, SSR
# renderer) MUST import from the manifest module, NOT from here — importing
# this server.py fires the @mcp_tool decorators below, which collide with
# the root mcp_server.py's decorators when both modules co-exist in
# sys.modules (CI run 67918257844).
#
# NOTE 2026-07-09 (#93 consolidation): tools_manifest.py is now GENERATED
# from the root mcp_tool_definitions.py via tools/gen_mcp_tools_manifest.py
# — do NOT hand-mirror edits from here into it anymore. THIS list is
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

TOOLS = [
    # ── Core company data (API-mode via OXFORD_LEDGE_URL; Y1 2026-04-24) ──
    {
        "name": "get_holders",
        "description": "Get top 10 institutional shareholders for a stock with share counts and values.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol"}
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_sec_filings",
        "description": (
            "Get recent SEC EDGAR filings (10-K, 10-Q, 8-K, DEF 14A) for a "
            "company with filing dates and direct links."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol"},
                "filing_type": {"type": "string", "description": "Filing type filter (10-K, 10-Q, 8-K, etc). Optional."},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_insider_trades",
        "description": "Get recent insider buy/sell transactions for a company from Form 4 filings.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol"}
            },
            "required": ["ticker"],
        },
    },
    # ── SEC EDGAR tools (standalone via direct API) ──
    {
        "name": "get_fundamentals",
        "description": (
            "Get XBRL-parsed financial statements from SEC EDGAR for a ticker. "
            "Returns up to 10 years of revenue, net income, EPS, operating cash "
            "flow, total assets, total debt, and other key line items."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol (e.g. AAPL)"}
            },
            "required": ["ticker"],
        },
    },
    # ── Bond / credit tools (standalone via FINRA TRACE) ──
    # ── Macro / economic tools (standalone via FRED) ──
    {
        "name": "get_yield_curve",
        "description": (
            "Get the current Treasury yield curve (1M through 30Y) from FRED "
            "with optional historical comparison."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "include_history": {"type": "boolean", "description": "Include yield curve from 1 year ago for comparison (default false)"}
            },
        },
    },
    {
        "name": "get_fred_data",
        "description": (
            "Get economic data from FRED (Federal Reserve Economic Data). "
            "Supports any FRED series ID (e.g. GDP, UNRATE, CPIAUCSL, DFF, "
            "T10Y2Y, FEDFUNDS)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "series": {"type": "string", "description": "FRED series ID (e.g. GDP, UNRATE, CPIAUCSL, DFF)"},
                "days": {"type": "integer", "description": "Number of days of history (default 365)"},
            },
            "required": ["series"],
        },
    },
    # ── Short interest (API-mode via OXFORD_LEDGE_URL; Y1 2026-04-24) ──
    # ── API-mode tools (require OXFORD_LEDGE_URL) ──
    {
        "name": "get_corporate_events",
        "description": (
            "Get corporate events for a ticker: M&A activity, executive changes, "
            "restructurings, dividend changes, and other material events. [Requires API mode]"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol (e.g. AAPL)"},
                "event_type": {"type": "string", "description": "Optional filter: acquisition, divestiture, executive_change, restructuring, dividend, or ALL"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "search_bdc_borrower",
        "description": (
            "Search BDC (Business Development Company) portfolio holdings by "
            "borrower name. Returns which BDCs hold the company, fair values, "
            "par amounts, and investment types. [Requires API mode]"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Borrower/company name to search (e.g. Finastra, Medline)"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_bdc_list",
        "description": (
            "List all BDC tickers tracked by Oxford Ledge with their names, AUM "
            "(total fair value), holding counts, and latest filing dates. [Requires API mode]"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_debt_maturities",
        "description": (
            "Get the debt maturity schedule from SEC EDGAR 10-K footnotes. "
            "Returns year-by-year maturity amounts in millions and a confidence "
            "level (high/medium/low/none). [Requires API mode]"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol (e.g. AAPL)"}
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_capital_allocation",
        "description": (
            "Get 10-year capital allocation scorecard from SEC EDGAR XBRL: "
            "buybacks, dividends, debt issuance/repayment, acquisitions, "
            "stock compensation, and shares outstanding history. [Requires API mode]"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol (e.g. AAPL)"}
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_13f_holdings",
        "description": (
            "Get top institutional holdings from a fund's latest SEC 13F filing. "
            "Accepts a fund CIK number ONLY (not a ticker). Returns fund name, "
            "filing date, top holdings with share counts and market values. "
            "[Requires API mode]"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "fund": {"type": "string", "description": "Fund CIK number (e.g. 1067983 for Berkshire Hathaway). CIK only — the API does not resolve fund tickers."},
                "max_holdings": {"type": "number", "description": "Maximum number of holdings to return (default 50)"},
            },
            "required": ["fund"],
        },
    },
    {
        "name": "get_value_investing_fact",
        "description": (
            "Get a value investing quote, principle, or historical fact. Includes "
            "quotes from Buffett, Graham, Munger, Klarman, and other value "
            "investing legends with full citations. [Requires API mode]"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Optional category, matched case-insensitively. The vocabulary is EXACTLY: principle, historical_fact, psychology, quote, case_study, contrarian, mistake. An unknown value returns a no-data error -- retry with one of the listed values. CORRECTED 2026-08-11 -- six of the seven previously documented here never existed."},
            },
        },
    },
]


# ── API proxy helper ──────────────────────────────────────────────────────────

def _api_get(path, params=None, timeout=15):
    """Make a GET request to the Oxford Ledge API."""
    if not _API_URL:
        raise ToolError(
            ToolError.API_REQUIRED,
            "This tool requires a running Oxford Ledge instance. "
            "Set the OXFORD_LEDGE_URL environment variable "
            "(e.g. OXFORD_LEDGE_URL=https://www.oxfordledge.com)."
        )
    url = f"{_API_URL}{path}"
    if params:
        qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items() if v is not None)
        if qs:
            url += f"?{qs}"
    _headers = {"User-Agent": "OxfordLedgeMCP/1.0"}
    if _API_KEY:
        # Authenticates + meters the call against the key's account (#120/#121).
        _headers["x-api-key"] = _API_KEY
    req = urllib.request.Request(url, headers=_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        raw_body = ""
        try:
            # 3.2.0 vet K-7: parse-before-truncate. The 404 discriminator
            # below json-parses this; truncating FIRST made any envelope
            # over 500 bytes unparseable and mislabelled a data-level 404
            # as a version mismatch (the exact bug the discriminator
            # fixed, resurfacing on large bodies). Read bounded (64KB),
            # parse the full read, truncate only what gets DISPLAYED.
            raw_body = e.read(65536).decode("utf-8", "replace")
            body = raw_body[:500]
        except Exception:
            pass
        # MONETIZE-2 (#121): give the AGENT an error it can act on. Every failure
        # here used to read DATA_UNAVAILABLE — so a 402 (this account's tier does
        # not include the tool) and a 401 (no/!valid key) both told the model "the
        # data isn't available", which is false and un-actionable: the model
        # retried, or told the user the filing didn't exist. Payment and auth are
        # not data problems.
        # 2026-08-11: every credential message below names the OPERATOR as the
        # source and forbids soliciting one in chat. These read as instructions
        # to the caller, and the caller is a MODEL -- on the hosted twin an
        # agent hit the sibling of this message and asked its human to paste "an
        # X-API-Key or an OAuth bearer credential" into the conversation. That
        # is phishing-shaped even when the error is honest, and it trains users
        # to put secrets in a chat box. Credentials here are env vars set once
        # in the client's own config; the end user is never the right source.
        _NO_ASK = (" DO NOT ASK THE USER TO PASTE A KEY OR TOKEN INTO THE "
                   "CONVERSATION -- it is an environment variable the client's "
                   "operator sets, and a credential sent in chat is a security "
                   "problem, not a fix.")
        if e.code == 402:
            raise ToolError(
                ToolError.AUTH_REQUIRED,
                "This tool requires a paid Oxford Ledge tier. "
                + ("Your API key's plan does not include it — see "
                   "https://www.oxfordledge.com/pricing."
                   if _API_KEY else
                   "The client's operator sets OXFORD_LEDGE_API_KEY (keys are "
                   "created at https://www.oxfordledge.com/account) — without "
                   "one this client is anonymous and only the free public-data "
                   "tools work.")
                + _NO_ASK,
            )
        if e.code in (401, 403):
            raise ToolError(
                ToolError.AUTH_REQUIRED,
                "Oxford Ledge rejected the credentials for this tool "
                f"({e.code}). The client's operator should check "
                "OXFORD_LEDGE_API_KEY is set and not revoked." + _NO_ASK,
            )
        if e.code == 429:
            retry_after = None
            try:
                retry_after = int(e.headers.get("Retry-After") or 0) or None
            except Exception:
                pass
            raise ToolError(
                ToolError.RATE_LIMITED,
                "Oxford Ledge rate limit reached for this key.",
                retry_after=retry_after,
            )
        if e.code == 404:
            # Same reasoning that earned 402 its own code: a 404 on a path is
            # a client/server version mismatch (developer bug), not "the data
            # doesn't exist" — never launder it as DATA_UNAVAILABLE.
            #
            # 2026-08-11: but the server uses 404 for BOTH. A route answers
            # 404 through the unified error envelope when a FILTER matched
            # nothing (the envelope helper REWRITES unmatched messages to a
            # status-code default, so the agent sees generic no-data text,
            # not the route's literal -- 3.2.0 vet K-7 corrected the account
            # here that claimed otherwise), so a
            # perfectly-routed call with an unknown `category` was reported to
            # the agent as "this endpoint does not exist" — and the directive
            # below ("report it rather than retrying") steered it AWAY from the
            # one correct recovery, which was to try another category. Two
            # individually-defensible decisions producing a confident lie.
            #
            # Discriminate on the BODY, which is unambiguous: our own handlers
            # emit the unified envelope {error, message, status, request_id}
            # (the server's shared error-envelope helper), whereas an unrouted path
            # gets FastAPI's default {"detail": "Not Found"}. A data-level 404
            # therefore carries `error` + `status`; a routing 404 does not.
            _envelope = None
            try:
                _parsed = json.loads(raw_body)
                if isinstance(_parsed, dict) and "error" in _parsed \
                        and "status" in _parsed:
                    _envelope = _parsed
            except Exception:
                _envelope = None
            if _envelope is not None:
                # Routed fine; the FILTER matched nothing. Actionable by
                # changing arguments, so it must not read as a broken build.
                raise ToolError(
                    ToolError.DATA_UNAVAILABLE,
                    f"No data matched this request: "
                    f"{_envelope.get('message') or _envelope.get('error')} "
                    f"(the endpoint exists and responded — adjust the "
                    f"arguments, e.g. a different category/filter value, "
                    f"rather than reporting a version mismatch).",
                )
            raise ToolError(
                ToolError.NOT_FOUND,
                f"HTTP 404 for {path} — this endpoint does not exist on the "
                "server. Likely a package/API version mismatch, not missing "
                "data; report it rather than retrying other tickers.",
            )
        raise ToolError(ToolError.DATA_UNAVAILABLE, f"API returned {e.code}: {body}")
    except urllib.error.URLError as e:
        raise ToolError(ToolError.DATA_UNAVAILABLE, f"Cannot reach Oxford Ledge API at {_API_URL}: {e.reason}")


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


@mcp_tool(name="get_holders", cache=FUNDAMENTAL)
def tool_get_holders(args):
    """Top institutional holders from SEC 13F filings.
    Y1 (2026-04-24): now requires OXFORD_LEDGE_URL (routes via
    Oxford Ledge's SEC EDGAR integration). Migration path for future
    standalone support: call SEC EDGAR 13F endpoint directly."""
    ticker = normalize_ticker(args.get("ticker"))
    # 2026-08-10 field test #2: /api/13f-holdings never existed — the live
    # route is /api/institutional-holders (404'd on every call).
    data = _api_get("/api/institutional-holders", {"ticker": ticker})
    if not isinstance(data, dict):
        return {"ticker": ticker, "holders": []}
    raw = data.get("holders") or data.get("filings") or []
    holders = []
    for row in raw[:10]:
        holders.append({
            # Field test #3 (2026-08-10): the live rows carry fund_name /
            # value_usd (data/institutional_holdings.get_institutional_holders)
            # -- the old chain read keys this route never emits, so holder
            # rendered "" beside correct share counts.
            "holder": str(row.get("fund_name") or row.get("holder") or row.get("name") or ""),
            "shares": _safe(row.get("shares")),
            "value": _safe(row.get("value_usd") or row.get("value")),
            "type": "institutional",
        })
    return {"ticker": ticker, "holders": holders}


@mcp_tool(name="get_sec_filings", cache=FUNDAMENTAL)
def tool_get_sec_filings(args):
    ticker = normalize_ticker(args.get("ticker"))
    filing_type = args.get("filing_type", "").strip()
    try:
        # 2026-08-10 field test #2: no filing_type used to silently default
        # to 10-K while the manifest advertised 10-K/10-Q/8-K/DEF 14A — a
        # no-arg call returned ten 10-Ks. Absent type now means ALL forms.
        # (Also dropped the duplicated action=getcompany query param.)
        _type_q = f"&type={filing_type}" if filing_type else ""
        cik_url = (
            f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=&CIK={ticker}"
            f"{_type_q}&dateb=&owner=include&count=10&search_text=&output=atom"
        )
        req = urllib.request.Request(cik_url, headers={"User-Agent": "OxfordLedge contact@oxfordledge.com"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read().decode("utf-8")
        import xml.etree.ElementTree as ET
        root = ET.fromstring(data)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall(".//atom:entry", ns)
        filings = []
        for entry in entries[:10]:
            title = entry.findtext("atom:title", "", ns)
            link = entry.find("atom:link", ns)
            href = link.get("href", "") if link is not None else ""
            updated = entry.findtext("atom:updated", "", ns)
            filings.append({"title": title, "url": href, "date": updated[:10] if updated else ""})
        return {"ticker": ticker, "filings": filings}
    except Exception as e:
        return {"ticker": ticker, "filings": [], "error": str(e)}


@mcp_tool(name="get_insider_trades", cache=FUNDAMENTAL)
def tool_get_insider_trades(args):
    """Recent insider transactions (Form 4).
    Y1 (2026-04-24): now requires OXFORD_LEDGE_URL. Backed by OL's
    form4_transactions table (176K rows) which sources directly from
    SEC EDGAR — more authoritative than yfinance's scraped view."""
    ticker = normalize_ticker(args.get("ticker"))
    data = _api_get("/api/insider-activity", {"ticker": ticker})
    if not isinstance(data, dict):
        return {"ticker": ticker, "trades": []}
    raw = data.get("transactions") or data.get("trades") or []
    trades = []
    for row in raw[:15]:
        # 2026-08-10 field test #2: the wire contract is camelCase
        # (schemas/responses.py InsiderActivityTxn: insiderName /
        # transactionType) — the old chains read keys the API never emits,
        # so every row rendered an empty insider + type beside real shares.
        trades.append({
            # Field test #3: /api/insider-activity rows come from
            # pg_get_insider_activity, whose SQL aliases are the wire SOT:
            # transType / filingDate / totalValue (insiderName was right).
            # The InsiderActivityTxn schema keys belong to a different route
            # family -- pin to the helper's aliases, not the lookalike model.
            "insider": str(row.get("insiderName") or row.get("insider") or row.get("name") or row.get("reportingOwner") or ""),
            "shares": _safe(row.get("shares") or row.get("transactionShares")),
            "value": _safe(row.get("totalValue") or row.get("value") or row.get("transactionValue")),
            "type": row.get("transType") or row.get("transactionType") or row.get("type") or row.get("transactionCode") or "",
            "date": row.get("filingDate") or row.get("date") or row.get("transactionDate") or "",
        })
    return {"ticker": ticker, "trades": trades}


@mcp_tool(name="get_fundamentals", cache=FUNDAMENTAL, heavy=True)
def tool_get_fundamentals(args):
    """Get XBRL fundamentals from SEC EDGAR directly."""
    ticker = normalize_ticker(args.get("ticker"))
    try:
        # Step 1: Resolve ticker to CIK
        tickers_url = "https://www.sec.gov/files/company_tickers.json"
        req = urllib.request.Request(tickers_url, headers={"User-Agent": "OxfordLedge contact@oxfordledge.com"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            tickers_data = json.loads(resp.read().decode("utf-8"))
        cik = None
        for entry in tickers_data.values():
            if normalize_ticker(entry.get("ticker")) == ticker:
                cik = str(entry["cik_str"]).zfill(10)
                break
        if not cik:
            raise ToolError(ToolError.DATA_UNAVAILABLE, f"Could not find CIK for ticker '{ticker}'")

        # Step 2: Get company facts from XBRL
        facts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        req = urllib.request.Request(facts_url, headers={"User-Agent": "OxfordLedge contact@oxfordledge.com"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            facts = json.loads(resp.read().decode("utf-8"))

        us_gaap = facts.get("facts", {}).get("us-gaap", {})
        if not us_gaap:
            raise ToolError(ToolError.DATA_UNAVAILABLE, f"No XBRL data found for '{ticker}'")

        # Extract key line items
        line_items = {
            "Revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
                        # investment companies (BDCs) tag revenue as gross
                        # investment income. 3.2.0 vet K-6 execution removed
                        # the sibling rung InvestmentIncomeOperating here:
                        # SEC frames CY2015+CY2023 report ZERO filers for it
                        # and both flagship BDC companyconcepts 404 -- a
                        # never-matching rung (the OCF defect class), while
                        # this one shows 182 filers in CY2023.
                        "GrossInvestmentIncomeOperating"],
            "NetIncome": ["NetIncomeLoss"],
            "EPS": ["EarningsPerShareDiluted", "EarningsPerShareBasic"],
            "TotalAssets": ["Assets"],
            "TotalLiabilities": ["Liabilities"],
            "StockholdersEquity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
            # 2026-08-24 MCP audit: the old sole rung named a NON-EXISTENT
            # us-gaap concept (SEC companyconcept 404-verified) -- the same
            # never-matching-rung class as the in-tree sharesOut fix. The
            # real concept, plus the continuing-operations variant some
            # filers use.
            "OperatingCashFlow": ["NetCashProvidedByUsedInOperatingActivities",
                                  "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
            "TotalDebt": ["LongTermDebt", "LongTermDebtNoncurrent"],
        }

        # Flow (duration) concepts: a 10-K's companyfacts entries ALSO carry
        # quarterly duration facts tagged form=10-K/fp=FY, so form+fp alone
        # mixes Q rows into the annual series (2026-08-10 field test).
        duration_labels = {"Revenue", "NetIncome", "EPS", "OperatingCashFlow"}

        def _days(e):
            try:
                s = _dt.date.fromisoformat(e.get("start", ""))
                t = _dt.date.fromisoformat(e.get("end", ""))
                return (t - s).days
            except ValueError:
                return -1

        result = {"ticker": ticker, "data": {}}
        for label, concepts in line_items.items():
            # Filers SWITCH concepts over a decade (AAPL: Revenues ->
            # RevenueFromContractWithCustomer... at FY2019), so first-hit
            # concept selection truncates history. Merge all listed
            # concepts per period end; earlier-listed concept wins a tie.
            by_end = {}
            for concept in reversed(concepts):
                if concept not in us_gaap:
                    continue
                units = us_gaap[concept].get("units", {})
                # Try USD first, then USD/shares for EPS
                unit_key = "USD/shares" if label == "EPS" else "USD"
                entries = units.get(unit_key, [])
                annual = [e for e in entries
                          if e.get("form") == "10-K" and e.get("fp") == "FY"
                          and (label not in duration_labels
                               or 330 <= _days(e) <= 400)]
                # Each fiscal year re-appears as a comparative in later
                # 10-Ks; keep ONE row per period end -- the latest-filed
                # within a concept (restatements win), then let the
                # higher-priority concept override cross-concept.
                per_concept = {}
                for e in annual:
                    k = e.get("end", "")
                    prev = per_concept.get(k)
                    if prev is None or e.get("filed", "") > prev.get("filed", ""):
                        per_concept[k] = e
                by_end.update(per_concept)
            if not by_end:
                continue
            newest_first = sorted(by_end.values(),
                                  key=lambda x: x.get("end", ""),
                                  reverse=True)
            result["data"][label] = [
                {"period": e.get("end", ""), "value": e.get("val")}
                for e in newest_first[:10]
            ]
        return result
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(ToolError.DATA_UNAVAILABLE, f"EDGAR XBRL lookup failed for '{ticker}': {e}")


#: Trading days pulled per series when the caller asks for history. ~252 in a
#: year; 400 covers a year plus the slack for holidays and a stale tail without
#: a second request per series.
_YC_HISTORY_LIMIT = 400
#: How far a matched "a year ago" observation may sit from the 365-day target
#: before it is refused. A curve is only comparable against a real prior point;
#: silently pairing today against a value 5 months old would answer the
#: steepening question with a number that does not mean what it says.
_YC_LOOKBACK_TOLERANCE_DAYS = 45


def _yc_pick_year_ago(observations, latest_date):
    """The observation closest to one year before ``latest_date``, or None.

    ``observations`` is FRED's newest-first list. Returns None rather than the
    nearest available point when nothing lands within the tolerance -- a
    comparison against whatever happens to be oldest is worse than no
    comparison, because the caller cannot see how far off it is.
    """
    import datetime as _dt

    try:
        anchor = _dt.date.fromisoformat(latest_date) - _dt.timedelta(days=365)
    except (TypeError, ValueError):
        return None
    best, best_gap = None, None
    for o in observations:
        if o.get("value") in (None, ".", ""):
            continue
        try:
            d = _dt.date.fromisoformat(o.get("date", ""))
        except ValueError:
            continue
        gap = abs((d - anchor).days)
        if best_gap is None or gap < best_gap:
            best, best_gap = o, gap
    if best is None or best_gap > _YC_LOOKBACK_TOLERANCE_DAYS:
        return None
    return best


@mcp_tool(name="get_yield_curve", cache=FUNDAMENTAL)
def tool_get_yield_curve(args):
    """Get Treasury yield curve from FRED.

    include_history=true adds the same curve as of ~1 year ago, for
    steepening/inversion work.

    2026-08-11 (#30): this handler did not read `args` AT ALL, while its
    inputSchema declared `include_history`. The dispatcher's own contract
    (`_echo_params_accepted`, mcp_server.py) is deliberately named
    params_ACCEPTED rather than honored because a downstream hop can drop a
    value it validated -- and this was a live instance of exactly that gap: a
    caller passed include_history, saw it echoed as accepted, and got the
    current curve regardless. Closing it per-tool is what that docstring
    prescribes.

    History costs no extra REQUESTS. The same one-call-per-series loop asks for
    a wider window and reads both ends out of it, so the difference is response
    size rather than round trips.
    """
    fred_key = os.environ.get("FRED_API_KEY", "")
    if not fred_key:
        raise ToolError(ToolError.API_REQUIRED, "Set FRED_API_KEY environment variable for yield curve data")
    include_history = bool(args.get("include_history", False))
    series_ids = {
        "1M": "DGS1MO", "3M": "DGS3MO", "6M": "DGS6MO",
        "1Y": "DGS1", "2Y": "DGS2", "3Y": "DGS3", "5Y": "DGS5",
        "7Y": "DGS7", "10Y": "DGS10", "20Y": "DGS20", "30Y": "DGS30",
    }
    limit = _YC_HISTORY_LIMIT if include_history else 1
    curve, year_ago, as_of = {}, {}, {}
    for label, sid in series_ids.items():
        try:
            url = (
                f"https://api.stlouisfed.org/fred/series/observations"
                f"?series_id={sid}&api_key={fred_key}&file_type=json"
                f"&sort_order=desc&limit={limit}"
            )
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            obs = data.get("observations", [])
            if not obs or obs[0].get("value") == ".":
                continue
            curve[label] = float(obs[0]["value"])
            as_of[label] = obs[0].get("date")
            if include_history:
                prior = _yc_pick_year_ago(obs[1:], obs[0].get("date"))
                if prior:
                    year_ago[label] = float(prior["value"])
        except Exception:
            continue
    if not curve:
        raise ToolError(ToolError.DATA_UNAVAILABLE, "Could not fetch yield curve data from FRED")
    out = {"yield_curve": curve, "as_of": as_of, "source": "FRED"}
    if include_history:
        # Emitted even when EMPTY, and that is deliberate: the caller asked for
        # history, so the key must be present to say it was applied. Omitting
        # it on a miss is indistinguishable from ignoring the parameter, which
        # is the bug being fixed.
        out["yield_curve_1y_ago"] = year_ago
        out["history_coverage"] = {
            "maturities_with_prior": len(year_ago),
            "maturities_total": len(curve),
            "lookback_tolerance_days": _YC_LOOKBACK_TOLERANCE_DAYS,
        }
    return out


# Third-party / copyrighted FRED-series carve-out (3.1.0; hardened FAIL-CLOSED per the
# 2026-07-21 CHAOS/DATA_CZAR/COUNSEL compliance review). FRED aggregates 800k+ series;
# U.S.-government series (BLS / BEA / Census / Federal Reserve / Treasury) are public
# domain and free to redistribute, but series from private commercial providers (S&P
# Dow Jones, ICE BofA, Moody's, CBOE, Nasdaq, FTSE Russell, ...) are non-commercial-
# only and may not be redistributed commercially. This gov-public-data-only package
# refuses them. FAIL-CLOSED design:
#   * Primary: fetch /fred/series metadata; if `notes`/`title` shows any copyright or
#     named-licensor marker, REFUSE.
#   * If the metadata probe is UNAVAILABLE (network/quota), DO NOT guess-serve — serve
#     ONLY a series matching the known U.S.-gov source allowlist, else REFUSE.
#   * Cache ONLY authoritative metadata verdicts (never a probe-failure fallback), so a
#     transient blip can't poison-cache a carve-out series as clean; recovery self-heals.
import re as _re

# Copyright / third-party markers in the FRED notes/title (ASCII word, the (c) glyph,
# or a named commercial licensor) — catches reworded / empty-"copyright" attributions.
_FRED_THIRDPARTY_NOTE = _re.compile(
    "copyright|©|all rights reserved|s&p|dow jones|standard & poor|case-shiller|"
    "ice data|ice bofa|bofa merrill|moody|cboe|nasdaq omx|ftse|russell|msci|bloomberg",
    _re.IGNORECASE)
# Known U.S.-government / public-domain source prefixes — the allowlist used ONLY when
# the metadata probe is unavailable (everything else fails closed / refused).
_FRED_GOV_PREFIXES = (
    "DGS", "DFF", "FEDFUNDS", "SOFR", "GDP", "CPIAUCSL", "CPILFESL", "PCEPI", "UNRATE",
    "PAYEMS", "T10Y", "T5Y", "DTB", "TB3MS", "DFEDTAR", "DEXUS", "DEXJP", "DEXCH",
    "M1SL", "M2SL", "HOUST", "RSAFS", "INDPRO", "PPIACO", "MICH", "RRPONTSYD", "WALCL")
_fred_thirdparty_cache: dict[str, bool] = {}


def _scrub_fred_key(text: str) -> str:
    """3.2.0 vet C-6 (defense-in-depth): FRED's documented auth rides the
    query string, so a urllib error repr can embed the caller's own key.
    Redact it before any exception text reaches a tool message."""
    return re.sub(r"api_key=[^&\s'\"]+", "api_key=REDACTED", text)


def _fred_series_is_thirdparty(series: str, key: str) -> bool:
    """Fail-closed: True if the FRED series is (or cannot be confirmed NOT to be)
    third-party copyright. Only authoritative FRED-metadata verdicts are cached."""
    s = (series or "").upper()
    if s in _fred_thirdparty_cache:
        return _fred_thirdparty_cache[s]
    try:
        url = (f"https://api.stlouisfed.org/fred/series"
               f"?series_id={urllib.parse.quote(s)}&api_key={key}&file_type=json")
        with urllib.request.urlopen(urllib.request.Request(url), timeout=10) as resp:
            rows = (json.loads(resp.read().decode("utf-8")).get("seriess") or [])
    except Exception:
        rows = None  # probe unavailable
    if rows is not None:
        # Authoritative FRED answer -> cache it.
        if rows:
            meta = (rows[0].get("notes") or "") + " " + (rows[0].get("title") or "")
            verdict = bool(_FRED_THIRDPARTY_NOTE.search(meta))
        else:
            verdict = True  # unknown/invalid series id -> refuse
        _fred_thirdparty_cache[s] = verdict
        return verdict
    # Probe unavailable: FAIL CLOSED. Serve ONLY a known U.S.-gov series; refuse the
    # rest. Do NOT cache (so a recovered probe re-decides authoritatively next time).
    return not s.startswith(_FRED_GOV_PREFIXES)


@mcp_tool(name="get_fred_data", cache=FUNDAMENTAL)
def tool_get_fred_data(args):
    """Get FRED economic data series (U.S.-government / public-domain series only)."""
    fred_key = os.environ.get("FRED_API_KEY", "")
    if not fred_key:
        raise ToolError(ToolError.API_REQUIRED, "Set FRED_API_KEY environment variable for FRED data")
    series = args["series"].strip().upper()
    if _fred_series_is_thirdparty(series, fred_key):
        raise ToolError(
            ToolError.INVALID_PARAMS,
            f"FRED series '{series}' carries third-party (non-U.S.-government) copyright "
            f"(e.g. S&P Dow Jones Indices, ICE BofA, Moody's, CBOE) and is licensed for "
            f"non-commercial use only. This gov-public-data package does not serve it. Use a "
            f"U.S.-government series (BLS / BEA / Census / Federal Reserve / Treasury), or "
            f"license the data directly from the copyright holder.")
    days = int(args.get("days", 365))
    from datetime import datetime, timedelta
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        url = (
            f"https://api.stlouisfed.org/fred/series/observations"
            f"?series_id={series}&api_key={fred_key}&file_type=json"
            f"&observation_start={start_date}&sort_order=desc"
        )
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        obs = data.get("observations", [])
        points = []
        for o in obs:
            if o.get("value") != ".":
                points.append({"date": o["date"], "value": float(o["value"])})
        return {"series": series, "data": points, "count": len(points)}
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(ToolError.DATA_UNAVAILABLE, f"FRED data fetch failed for '{series}': {_scrub_fred_key(str(e))}")


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


@mcp_tool(name="search_bdc_borrower", cache=FUNDAMENTAL)
def tool_search_bdc_borrower(args):
    # 2026-08-10 field test #2: /api/bdc/search never existed — the live
    # route is /api/bdc/borrower (same `q` param).
    return _api_get("/api/bdc/borrower", {"q": args["query"]})


@mcp_tool(name="get_bdc_list", cache=FUNDAMENTAL)
def tool_get_bdc_list(args):
    return _api_get("/api/bdc/list")


# min_tier="plus": canonical premium analytics (see get_options_chain
# note above). Mirrors mcp_server.py; sf_monetization_v3-compliant.
@mcp_tool(name="get_debt_maturities", cache=FUNDAMENTAL, heavy=True, min_tier="plus")
def tool_get_debt_maturities(args):
    ticker = normalize_ticker(args.get("ticker"))
    return _api_get("/api/debt-maturities", {"ticker": ticker})


# min_tier="plus": canonical premium analytics (see get_options_chain
# note above). Mirrors mcp_server.py; sf_monetization_v3-compliant.
@mcp_tool(name="get_capital_allocation", cache=FUNDAMENTAL, heavy=True, min_tier="plus")
def tool_get_capital_allocation(args):
    ticker = normalize_ticker(args.get("ticker"))
    return _api_get("/api/capital-structure", {"ticker": ticker})


# min_tier="plus": canonical premium analytics (see get_options_chain
# note above). Mirrors mcp_server.py; sf_monetization_v3-compliant.
@mcp_tool(name="get_13f_holdings", cache=FUNDAMENTAL, heavy=True, min_tier="plus")
def tool_get_13f_holdings(args):
    fund = args["fund"].strip()
    # 2026-08-10 field test #2: the route signature is cik-only
    # (server_asgi fund_holdings(cik=Query(""))); sending fund= fell through
    # to 400 "No CIK provided" on every call. The input schema now says CIK.
    params = {"cik": fund}
    if args.get("max_holdings"):
        params["max_holdings"] = str(int(args["max_holdings"]))
    # Emit boundary (2026-08-10 allowlist inversion): fail-CLOSED per-tool
    # allowlist first (`cusip` is deliberately absent from it -- the FactSet/
    # CGS carve-out that removed the bond tools in 3.1.0), carve-out strip
    # retained as defense-in-depth.
    return _strip_carveout_ids(filter_to_allowlist(
        "get_13f_holdings", _api_get("/api/fund-holdings", params)))


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
    "search_bonds": "removed in 3.1.0 (CUSIP carve-out — bond CUSIPs are FactSet IP, licensed separately from FINRA data). Available via the hosted Oxford Ledge MCP server.",
    "get_bond_data": "removed in 3.1.0 (CUSIP carve-out — bond CUSIPs are FactSet IP, licensed separately from FINRA data). Available via the hosted Oxford Ledge MCP server.",
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

def _execute_tool_with_limits(tool_name, args):
    """Execute a tool call with caching, concurrency limits, and structured errors."""
    handler = TOOL_DISPATCH.get(tool_name)
    if not handler:
        return None

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
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        tool_name = req.get("params", {}).get("name", "")
        tool_args = req.get("params", {}).get("arguments", {})
        fn = TOOL_DISPATCH.get(tool_name)
        if not fn:
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": _unknown_tool_text(tool_name)}],
                    "isError": True,
                },
            }
        try:
            result = _execute_tool_with_limits(tool_name, tool_args)
            text = json.dumps(result, indent=2, default=str)
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": text}], "isError": False},
            }
        except ToolError as e:
            _log(f"Tool error ({tool_name}): [{e.code}] {e.message}")
            error_json = json.dumps(e.to_dict(), default=str)
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": error_json}], "isError": True},
            }
        except Exception as e:
            _log(f"Tool error ({tool_name}): {traceback.format_exc()}")
            error_payload = {"error": {"code": "INTERNAL_ERROR", "message": str(e)}}
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(error_payload)}], "isError": True},
            }

    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown method: {method}"}}


def main():
    """Run the MCP server on stdin/stdout."""
    mode = "API" if _API_URL else "standalone"
    tool_count = len(TOOLS)
    _log(f"Oxford Ledge MCP Server v{__version__} starting ({tool_count} tools, {mode} mode)...")
    if _API_URL:
        _log(f"  API endpoint: {_API_URL}")
    else:
        _log("  Tip: Set OXFORD_LEDGE_URL for all 13 tools. Standalone mode serves only the keyless public-API tools (2 SEC EDGAR; FRED with FRED_API_KEY).")

    # Try to use the mcp package if available
    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        from mcp.types import Tool, TextContent
        import asyncio

        _log("Using mcp package for protocol handling")

        server = Server("oxford-ledge-mcp")

        @server.list_tools()
        async def list_tools():
            return [
                Tool(name=t["name"], description=t["description"], inputSchema=t["inputSchema"])
                for t in TOOLS
            ]

        @server.call_tool()
        async def call_tool(name: str, arguments: dict):
            if name not in TOOL_DISPATCH:
                return [TextContent(type="text", text=_unknown_tool_text(name))]
            try:
                result = _execute_tool_with_limits(name, arguments)
                text = json.dumps(result, indent=2, default=str)
                return [TextContent(type="text", text=text)]
            except ToolError as e:
                _log(f"Tool error ({name}): [{e.code}] {e.message}")
                return [TextContent(type="text", text=json.dumps(e.to_dict(), default=str))]
            except Exception as e:
                _log(f"Tool error ({name}): {traceback.format_exc()}")
                error_payload = {"error": {"code": "INTERNAL_ERROR", "message": str(e)}}
                return [TextContent(type="text", text=json.dumps(error_payload))]

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
                    out = json.dumps(response, default=str)
                    sys.stdout.write(out + "\n")
                    sys.stdout.flush()

            except json.JSONDecodeError as e:
                _log(f"JSON parse error: {e}")
                err = {"jsonrpc": "2.0", "error": {"code": -32700, "message": f"Parse error: {e}"}}
                sys.stdout.write(json.dumps(err) + "\n")
                sys.stdout.flush()
            except KeyboardInterrupt:
                break
            except Exception as e:
                _log(f"Unexpected error: {e}")
                traceback.print_exc(file=sys.stderr)

    _log("Oxford Ledge MCP server stopped.")


if __name__ == "__main__":
    main()
