"""Oxford Ledge MCP Server — financial data tools for Claude Desktop.

Provides 36 tools for querying stock data, SEC filings, credit data, BDC
holdings, macro indicators, and more.

Two modes:
  1. **API mode** (required for most tools): Set OXFORD_LEDGE_URL to your
     running Oxford Ledge instance. All 36 tools are available.
  2. **Standalone mode**: no server needed; 5-7 tools work directly against
     keyless public APIs (FRED macro, FINRA TRACE bonds, static reference).
     The other ~30 tools raise ToolError.API_REQUIRED in this mode and
     direct the user to set OXFORD_LEDGE_URL.

Standalone mode (no OXFORD_LEDGE_URL) covers only the keyless tools
described above; the rest return ToolError.API_REQUIRED directing the
user to set OXFORD_LEDGE_URL.

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
import urllib.request
import urllib.parse

# Add the package parent dir to sys.path so the sibling
# oxford_ledge_mcp_core subpackage imports reliably when this
# module is run as a script.
_pkg_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _pkg_parent not in sys.path:
    sys.path.insert(0, _pkg_parent)

import logging
import math

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
_logger = logging.getLogger("oxford_ledge.mcp")

# ── Configuration ─────────────────────────────────────────────────────────────

# Set OXFORD_LEDGE_URL to connect to a running Oxford Ledge instance
# e.g. OXFORD_LEDGE_URL=https://www.oxfordledge.com or http://localhost:10000
_API_URL = os.environ.get("OXFORD_LEDGE_URL", "").rstrip("/")

# ── Per-session concurrency limits ────────────────────────────────────────────
_MCP_MAX_CONCURRENT = 5
_MCP_HEAVY_MAX_CONCURRENT = 2
_mcp_semaphore = threading.Semaphore(_MCP_MAX_CONCURRENT)
_mcp_heavy_semaphore = threading.Semaphore(_MCP_HEAVY_MAX_CONCURRENT)

# Shared primitives (_MCP_HEAVY_TOOLS, _TOOL_TTL, cache, ToolError)
# come from the `oxford_ledge_mcp_core` subpackage. Tool registrations
# are done via @mcp_tool decorators on each `def tool_X(args):`
# function, which populate the core's REGISTRY at module-import time
# (36 tools).

_MCP_HEAVY_TOOLS: set = set()  # populated by @mcp_tool(heavy=True)

# Cache lock + dict (module-level for legacy callers; the core's
# versions are canonical — these aliases point at the same objects).
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
    cache_key as _cache_key,
    cache_get as _cache_get_core,
    cache_set as _cache_set_core,
    clear_cache as _clear_cache_core,
)
# F5 (2026-05-27): ticker-input normalization helper. Routes the
# `args["ticker"].upper().strip()` callsites through one helper so
# missing-key inputs surface as ToolError.BAD_INPUT (downstream
# validators) instead of raw KeyError.
from oxford_ledge_mcp_core.ticker import normalize_ticker
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



# Tools that need market/fundamentals data route through `_api_get()`
# against `OXFORD_LEDGE_URL`. In standalone mode (no OXFORD_LEDGE_URL)
# those tools return `ToolError.API_REQUIRED`; the keyless tools still
# work.


def _log(msg):
    print(msg, file=sys.stderr, flush=True)


# ── Tool definitions (36 tools) ──────────────────────────────────────────────
#
# The TOOLS list below is the tool catalog; the @mcp_tool decorators
# on each handler register them into the core REGISTRY at import time.

TOOLS = [
    # ── Core company data (API-mode via OXFORD_LEDGE_URL; Y1 2026-04-24) ──
    {
        "name": "get_stock_quote",
        "description": (
            "Get current stock price, change, volume, market cap, P/E, "
            "EV/EBITDA, dividend yield, beta, and 52-week range for a ticker."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol (e.g. AAPL, MSFT)"}
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_financials",
        "description": (
            "Get income statement data: revenue, net income, EBITDA, operating "
            "income, and gross profit for the last 4 years."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol"}
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_balance_sheet",
        "description": (
            "Get balance sheet data: total assets, liabilities, equity, debt, "
            "cash, current assets, and current liabilities for the last 4 years."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol"}
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_cash_flow",
        "description": (
            "Get cash flow statement: operating, investing, financing cash flows "
            "and free cash flow for the last 4 years."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol"}
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_analyst_recommendations",
        "description": (
            "Get analyst recommendations (buy/hold/sell counts), price targets "
            "(mean, high, low), and recommendation key for a stock."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol"}
            },
            "required": ["ticker"],
        },
    },
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
        "name": "get_company_info",
        "description": (
            "Get company profile: name, sector, industry, employee count, "
            "website, headquarters location, and business description."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol"}
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "compare_stocks",
        "description": (
            "Compare key metrics (P/E, EV/EBITDA, margins, growth, ROE, "
            "dividend yield, beta) across 2-5 stocks side by side."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "tickers": {"type": "string", "description": "Comma-separated ticker symbols (e.g. AAPL,MSFT,GOOG)"}
            },
            "required": ["tickers"],
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
    {
        "name": "get_options_chain",
        "description": "Get options chain (calls and puts) for a stock with nearest expiry date.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol"},
                "expiration": {"type": "string", "description": "Expiration date filter (YYYY-MM-DD format, optional)"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "screen_stocks",
        "description": (
            "Screen stocks by sector, market cap, P/E ratio, dividend yield, "
            "and other filters. Returns top matches from a curated universe."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "sector": {"type": "string", "description": "Sector filter (Technology, Healthcare, Financial, Energy, etc). Optional."},
                "min_market_cap_b": {"type": "number", "description": "Minimum market cap in billions. Optional."},
                "max_pe": {"type": "number", "description": "Maximum P/E ratio. Optional."},
                "min_dividend_yield": {"type": "number", "description": "Minimum dividend yield %. Optional."},
            },
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
    {
        "name": "search_bonds",
        "description": (
            "Search for bond issuers by company name. Returns CUSIP, coupon rate, "
            "maturity date, and debt type for matching bonds via FINRA TRACE."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Issuer name to search (e.g. Apple, Goldman Sachs)"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_bond_data",
        "description": (
            "Look up a specific bond by CUSIP identifier. Returns issuer, coupon rate, "
            "maturity date, last trade price, yield to maturity, and trading volume "
            "from FINRA TRACE."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "cusip": {"type": "string", "description": "9-character CUSIP identifier (e.g. 037833AK6 for Apple)"}
            },
            "required": ["cusip"],
        },
    },
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
    {
        "name": "get_short_interest",
        "description": (
            "Get short interest data for a ticker including short percent of float, "
            "short ratio (days to cover), and shares short."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol (e.g. AAPL)"}
            },
            "required": ["ticker"],
        },
    },
    # ── API-mode tools (require OXFORD_LEDGE_URL) ──
    {
        "name": "get_company_data",
        "description": (
            "Get key financials, valuation multiples, and current price for a "
            "stock ticker. Returns price, P/E, EV/EBITDA, market cap, dividend "
            "yield, 52-week range, and more. [Requires API mode]"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol (e.g. AAPL, MSFT)"}
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "search_company",
        "description": (
            "Fuzzy search for companies by name, ticker, or industry. Returns "
            "matching company profiles from the Oxford Ledge database. [Requires API mode]"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (company name, ticker, or industry)"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_company_profile",
        "description": (
            "Get company profile including business description, CEO, founding year, "
            "headquarters, employee count, sector, and industry classification. [Requires API mode]"
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
        "name": "get_market_indicators",
        "description": (
            "Get current market indicators: S&P 500, Dow Jones, NASDAQ, VIX, "
            "10-Year Treasury yield, gold, oil, bitcoin, and other key benchmarks "
            "with daily change, YTD, and year-over-year performance. [Requires API mode]"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
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
        "name": "calculate_intrinsic_value",
        "description": (
            "Calculate intrinsic value per share using DCF, EPV, and/or Graham "
            "models. Returns fair value estimates, margin of safety vs current "
            "price, and the inputs used in each model. [Requires API mode]"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol (e.g. AAPL)"},
                "method": {"type": "string", "enum": ["dcf", "epv", "graham", "all"], "description": "Valuation method to use (default: all)"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_anomaly_flags",
        "description": (
            "Run 15 automated anomaly checks on a stock: short interest, "
            "Altman Z-Score, leverage, negative FCF, extreme P/E, insider "
            "selling, and more. Returns severity, label, and detail for each flag. [Requires API mode]"
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
        "name": "get_peer_comparison",
        "description": (
            "Get comparative valuation and financial metrics for a stock vs "
            "its peers. Returns P/E, EV/EBITDA, margins, growth, and other "
            "key metrics side-by-side. [Requires API mode]"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol (e.g. AAPL)"},
                "peers": {"type": "array", "items": {"type": "string"}, "description": "Optional list of peer tickers to compare against"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_news",
        "description": (
            "Search the Oxford Ledge news archive for headlines with sentiment "
            "scores. Supports full-text search, ticker filtering, and pagination. [Requires API mode]"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (e.g. 'tariff', 'earnings beat')"},
                "ticker": {"type": "string", "description": "Filter to a specific ticker (e.g. AAPL)"},
                "limit": {"type": "number", "description": "Max results to return (default 25, max 100)"},
            },
        },
    },
    {
        "name": "get_price_history",
        "description": (
            "Get OHLCV price history for a ticker from the Oxford Ledge "
            "database. Returns date, open, high, low, close, and volume. [Requires API mode]"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol (e.g. AAPL)"},
                "days": {"type": "number", "description": "Number of days of history (default 365)"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_13f_holdings",
        "description": (
            "Get top institutional holdings from a fund's latest SEC 13F filing. "
            "Accepts a CIK number or fund ticker. Returns fund name, filing date, "
            "top holdings with share counts and market values. [Requires API mode]"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "fund": {"type": "string", "description": "Fund CIK number (e.g. 1067983 for Berkshire Hathaway) or fund ticker symbol"},
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
                "category": {"type": "string", "description": "Optional category: margin_of_safety, intrinsic_value, market_psychology, circle_of_competence, patience, contrarian, risk_management"},
                "query": {"type": "string", "description": "Optional search query to find facts by keyword (e.g. 'moat', 'fear')"},
            },
        },
    },
    {
        "name": "get_valuation_history",
        "description": (
            "Get historical valuation multiples (P/E, EV/EBITDA, P/B, P/S) for a "
            "ticker over time. Identifies if a stock is historically cheap or expensive. [Requires API mode]"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol (e.g. AAPL)"},
                "period": {"type": "string", "enum": ["1y", "2y", "5y"], "description": "Historical period (default: 5y)"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_economic_calendar",
        "description": (
            "Get upcoming economic events and data releases including "
            "FOMC meetings, jobs reports, CPI releases, and GDP prints. [Requires API mode]"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Number of days to look ahead (default 90)"},
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
    req = urllib.request.Request(url, headers={"User-Agent": "OxfordLedgeMCP/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")[:500]
        except Exception:
            pass
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


@mcp_tool(name="get_stock_quote", cache=MARKET)
def tool_get_stock_quote(args):
    """Current price + valuation multiples + market cap.

    Y1 (2026-04-24): migrated from yfinance to Oxford Ledge API.
    Requires OXFORD_LEDGE_URL — standalone mode no longer supports this
    tool because our data pipeline (FMP + SEC EDGAR + Finnhub) lives
    server-side.
    """
    ticker = normalize_ticker(args.get("ticker"))
    data = _api_get("/api/data", {"ticker": ticker})
    if not isinstance(data, dict):
        raise ToolError(ToolError.DATA_UNAVAILABLE, f"No data found for ticker '{ticker}'")
    price = data.get("price", {}) if isinstance(data.get("price"), dict) else {}
    metrics = data.get("metrics", {}) if isinstance(data.get("metrics"), dict) else {}
    return {
        "ticker": ticker,
        "company": _safe(data.get("company") or data.get("companyName"), ticker),
        "price": _safe(price.get("current") or data.get("lastPrice")),
        "change": _safe(price.get("change")),
        "changePct": _safe(price.get("changePct")),
        "volume": _safe(price.get("volume")),
        "marketCap": _safe(data.get("marketCap") or price.get("marketCap")),
        "pe": _safe(metrics.get("pe") or data.get("peRatio")),
        "forwardPe": _safe(metrics.get("forwardPE")),
        "evEbitda": _safe(metrics.get("evEbitda")),
        "pb": _safe(metrics.get("pb")),
        "dividendYield": _safe(metrics.get("dividendYield") or data.get("dividendYield")),
        "beta": _safe(metrics.get("beta") or data.get("beta")),
        "52weekHigh": _safe(price.get("week52High")),
        "52weekLow": _safe(price.get("week52Low")),
        "sector": _safe(data.get("sector")),
        "industry": _safe(data.get("industry")),
    }


@mcp_tool(name="get_financials", cache=FUNDAMENTAL)
def tool_get_financials(args):
    """Income statement — requires OXFORD_LEDGE_URL (Y1 2026-04-24)."""
    ticker = normalize_ticker(args.get("ticker"))
    data = _api_get("/api/company-financials", {"ticker": ticker, "years": 10})
    if not isinstance(data, dict):
        raise ToolError(ToolError.DATA_UNAVAILABLE, f"No financial data available for '{ticker}'")
    annual = data.get("annual") or []
    periods = []
    for row in annual[:4]:
        periods.append({
            "date": str(row.get("fiscal_year") or row.get("date") or ""),
            "total_revenue": _safe(row.get("revenue")),
            "net_income": _safe(row.get("net_income")),
            "ebitda": _safe(row.get("ebitda")),
            "operating_income": _safe(row.get("operating_income")),
            "gross_profit": _safe(row.get("gross_profit")),
        })
    return {"ticker": ticker, "periods": periods}


@mcp_tool(name="get_balance_sheet", cache=FUNDAMENTAL)
def tool_get_balance_sheet(args):
    """Balance sheet — requires OXFORD_LEDGE_URL (Y1 2026-04-24)."""
    ticker = normalize_ticker(args.get("ticker"))
    data = _api_get("/api/company-financials", {"ticker": ticker, "years": 10})
    if not isinstance(data, dict):
        raise ToolError(ToolError.DATA_UNAVAILABLE, f"No balance sheet data available for '{ticker}'")
    annual = data.get("annual") or []
    periods = []
    for row in annual[:4]:
        periods.append({
            "date": str(row.get("fiscal_year") or row.get("date") or ""),
            "total_assets": _safe(row.get("total_assets")),
            "total_liabilities_net_minority_interest": _safe(row.get("total_liabilities")),
            "stockholders_equity": _safe(row.get("stockholders_equity")),
            "total_debt": _safe(row.get("total_debt")),
            "cash_and_cash_equivalents": _safe(row.get("cash")),
            "current_assets": _safe(row.get("current_assets")),
            "current_liabilities": _safe(row.get("current_liabilities")),
        })
    return {"ticker": ticker, "periods": periods}


@mcp_tool(name="get_cash_flow", cache=FUNDAMENTAL)
def tool_get_cash_flow(args):
    """Cash flow statement — requires OXFORD_LEDGE_URL (Y1 2026-04-24)."""
    ticker = normalize_ticker(args.get("ticker"))
    data = _api_get("/api/company-financials", {"ticker": ticker, "years": 10})
    if not isinstance(data, dict):
        raise ToolError(ToolError.DATA_UNAVAILABLE, f"No cash flow data available for '{ticker}'")
    annual = data.get("annual") or []
    periods = []
    for row in annual[:4]:
        periods.append({
            "date": str(row.get("fiscal_year") or row.get("date") or ""),
            "operating_cash_flow": _safe(row.get("operating_cash_flow")),
            "capital_expenditure": _safe(row.get("capex")),
            "free_cash_flow": _safe(row.get("free_cash_flow")),
            "investing_cash_flow": _safe(row.get("investing_cash_flow")),
            "financing_cash_flow": _safe(row.get("financing_cash_flow")),
        })
    return {"ticker": ticker, "periods": periods}


@mcp_tool(name="get_analyst_recommendations", cache=FUNDAMENTAL)
def tool_get_analyst_recommendations(args):
    """Analyst target prices + consensus recommendation.
    Y1 (2026-04-24): now requires OXFORD_LEDGE_URL (routes via FMP)."""
    ticker = normalize_ticker(args.get("ticker"))
    data = _api_get("/api/analyst-estimates", {"ticker": ticker})
    if not isinstance(data, dict):
        raise ToolError(ToolError.DATA_UNAVAILABLE, f"No analyst data for '{ticker}'")
    return {
        "ticker": ticker,
        "targetMean": _safe(data.get("targetMeanPrice") or data.get("target_mean")),
        "targetHigh": _safe(data.get("targetHighPrice") or data.get("target_high")),
        "targetLow": _safe(data.get("targetLowPrice") or data.get("target_low")),
        "numberOfAnalysts": _safe(data.get("numberOfAnalysts") or data.get("num_analysts")),
        "recommendation": _safe(data.get("recommendation") or data.get("consensus")),
        "epsEstimates": data.get("epsEstimates") or [],
        "revenueEstimates": data.get("revenueEstimates") or [],
    }


@mcp_tool(name="get_holders", cache=FUNDAMENTAL)
def tool_get_holders(args):
    """Top institutional holders from SEC 13F filings.
    Y1 (2026-04-24): now requires OXFORD_LEDGE_URL (routes via
    Oxford Ledge's SEC EDGAR integration). Migration path for future
    standalone support: call SEC EDGAR 13F endpoint directly."""
    ticker = normalize_ticker(args.get("ticker"))
    data = _api_get("/api/13f-holdings", {"ticker": ticker})
    if not isinstance(data, dict):
        return {"ticker": ticker, "holders": []}
    raw = data.get("holders") or data.get("filings") or []
    holders = []
    for row in raw[:10]:
        holders.append({
            "holder": row.get("holder") or row.get("name", ""),
            "shares": _safe(row.get("shares")),
            "value": _safe(row.get("value")),
            "type": "institutional",
        })
    return {"ticker": ticker, "holders": holders}


@mcp_tool(name="get_company_info", cache=FUNDAMENTAL)
def tool_get_company_info(args):
    """Sector, industry, employees, description.
    Y1 (2026-04-24): now requires OXFORD_LEDGE_URL."""
    ticker = normalize_ticker(args.get("ticker"))
    data = _api_get("/api/company-profile", {"ticker": ticker})
    if not isinstance(data, dict):
        raise ToolError(ToolError.DATA_UNAVAILABLE, f"No company info for '{ticker}'")
    return {
        "ticker": ticker,
        "name": _safe(data.get("companyName") or data.get("name")),
        "sector": _safe(data.get("sector")),
        "industry": _safe(data.get("industry")),
        "employees": _safe(data.get("employees") or data.get("fullTimeEmployees")),
        "website": _safe(data.get("website")),
        "city": _safe(data.get("city")),
        "state": _safe(data.get("state")),
        "country": _safe(data.get("country")),
        "description": (_safe(data.get("description") or data.get("businessDescription")) or "")[:500],
    }


@mcp_tool(name="compare_stocks", cache=FUNDAMENTAL)
def tool_compare_stocks(args):
    """Side-by-side comparison of 2-5 tickers.
    Y1 (2026-04-24): now requires OXFORD_LEDGE_URL. Composes /api/data
    lookups per ticker; no new upstream dependency."""
    tickers = [normalize_ticker(t) for t in (args.get("tickers") or "").split(",") if t.strip()][:5]
    if len(tickers) < 2:
        raise ToolError(ToolError.INVALID_PARAMS, "Provide at least 2 comma-separated tickers")
    results = []
    for ticker in tickers:
        try:
            data = _api_get("/api/data", {"ticker": ticker})
            if not isinstance(data, dict):
                results.append({"ticker": ticker, "error": "Failed to fetch data"})
                continue
            metrics = data.get("metrics", {}) if isinstance(data.get("metrics"), dict) else {}
            price = data.get("price", {}) if isinstance(data.get("price"), dict) else {}
            results.append({
                "ticker": ticker,
                "name": _safe(data.get("company") or data.get("companyName"), ticker),
                "price": _safe(price.get("current") or data.get("lastPrice")),
                "marketCap": _safe(data.get("marketCap")),
                "pe": _safe(metrics.get("pe") or data.get("peRatio")),
                "forwardPe": _safe(metrics.get("forwardPE")),
                "evEbitda": _safe(metrics.get("evEbitda")),
                "profitMargin": _safe(metrics.get("profitMargins") or metrics.get("netMargin")),
                "revenueGrowth": _safe(metrics.get("revenueGrowth")),
                "roe": _safe(metrics.get("roe")),
                "dividendYield": _safe(metrics.get("dividendYield") or data.get("dividendYield")),
                "beta": _safe(metrics.get("beta") or data.get("beta")),
            })
        except ToolError:
            raise  # let API_REQUIRED propagate if URL is unset
        except Exception:
            results.append({"ticker": ticker, "error": "Failed to fetch data"})
    return {"comparison": results}


@mcp_tool(name="get_sec_filings", cache=FUNDAMENTAL)
def tool_get_sec_filings(args):
    ticker = normalize_ticker(args.get("ticker"))
    filing_type = args.get("filing_type", "").strip()
    try:
        cik_url = (
            f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=&CIK={ticker}"
            f"&type={filing_type or '10-K'}&dateb=&owner=include&count=10&search_text=&action=getcompany&output=atom"
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
        trades.append({
            "insider": str(row.get("insider") or row.get("name") or row.get("reportingOwner") or ""),
            "shares": _safe(row.get("shares") or row.get("transactionShares")),
            "value": _safe(row.get("value") or row.get("transactionValue")),
            "type": row.get("type") or row.get("transactionCode") or "",
            "date": row.get("date") or row.get("transactionDate") or "",
        })
    return {"ticker": ticker, "trades": trades}


# min_tier="plus": premium analytics tool. Mirrors canonical in-tree
# per-tool tier table. Standalone stdio mode is not tier-enforced;
# API mode (OXFORD_LEDGE_URL set) enforces tier server-side.
@mcp_tool(name="get_options_chain", cache=FUNDAMENTAL, min_tier="plus")
def tool_get_options_chain(args):
    """Options chain with Greeks.
    Y1 (2026-04-24): was yfinance; now routes to OL's options endpoint
    which is itself blocked on Tradier activation (OWNER #11). This
    tool is effectively a stub until Tradier lands — signals ApiRequired
    when OL is reachable but returns the upstream's 'not implemented'
    structured error."""
    ticker = normalize_ticker(args.get("ticker"))
    data = _api_get("/api/options", {"ticker": ticker})
    # Bubble up OL's response shape directly; OL may return
    # {"error": "not_implemented", "reason": "Tradier activation required"}
    return data if isinstance(data, dict) else {"ticker": ticker, "error": "Unexpected upstream response"}


@mcp_tool(name="screen_stocks", cache=NEVER)
def tool_screen_stocks(args):
    """Stock screener with financial filters.

    Y1 (2026-04-24): was a yfinance loop over 30 hard-coded mega-caps;
    now routes to OL's /api/screener endpoint which has the full
    5,407-ticker universe + proper indexing. Requires OXFORD_LEDGE_URL.
    Pre-Y1 mega-cap fallback deliberately dropped — hard-coded tickers
    drift and yfinance ToS-conflict was the whole point of Y1."""
    params = {
        "sector": args.get("sector"),
        "min_market_cap_b": args.get("min_market_cap_b"),
        "max_pe": args.get("max_pe"),
        "min_dividend_yield": args.get("min_dividend_yield"),
        "limit": args.get("limit") or 10,
    }
    data = _api_get("/api/screener", {k: v for k, v in params.items() if v is not None})
    if not isinstance(data, dict):
        return {"matches": [], "total_screened": 0, "error": "Upstream returned unexpected shape"}
    raw = data.get("results") or data.get("matches") or []
    matches = []
    for row in raw[:int(params["limit"])]:
        matches.append({
            "ticker": row.get("ticker"),
            "name": row.get("name") or row.get("companyName") or row.get("ticker"),
            "sector": row.get("sector"),
            "marketCap": _safe(row.get("marketCap")),
            "pe": _safe(row.get("pe") or row.get("peRatio")),
            "dividendYield": _safe(row.get("dividendYield")),
            "price": _safe(row.get("price") or row.get("lastPrice")),
        })
    return {"matches": matches, "total_screened": data.get("total_screened") or len(raw)}


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
            "Revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
            "NetIncome": ["NetIncomeLoss"],
            "EPS": ["EarningsPerShareDiluted", "EarningsPerShareBasic"],
            "TotalAssets": ["Assets"],
            "TotalLiabilities": ["Liabilities"],
            "StockholdersEquity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
            "OperatingCashFlow": ["NetCashProvidedByOperatingActivities"],
            "TotalDebt": ["LongTermDebt", "LongTermDebtNoncurrent"],
        }

        result = {"ticker": ticker, "data": {}}
        for label, concepts in line_items.items():
            for concept in concepts:
                if concept in us_gaap:
                    units = us_gaap[concept].get("units", {})
                    # Try USD first, then USD/shares for EPS
                    unit_key = "USD/shares" if label == "EPS" else "USD"
                    entries = units.get(unit_key, [])
                    # Filter to 10-K annual filings
                    annual = [e for e in entries if e.get("form") == "10-K" and e.get("fp") == "FY"]
                    if annual:
                        annual.sort(key=lambda x: x.get("end", ""), reverse=True)
                        result["data"][label] = [
                            {"period": e.get("end", ""), "value": e.get("val")}
                            for e in annual[:10]
                        ]
                        break
        return result
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(ToolError.DATA_UNAVAILABLE, f"EDGAR XBRL lookup failed for '{ticker}': {e}")


@mcp_tool(name="search_bonds", cache=FUNDAMENTAL)
def tool_search_bonds(args):
    """Search bond issuers via FINRA TRACE."""
    query = args["query"].strip()
    if len(query) < 2:
        raise ToolError(ToolError.INVALID_PARAMS, "Query must be at least 2 characters")
    try:
        search_url = (
            "https://services-dynarep.ddwa.finra.org/public/getIssueData/bond"
            f"?searchKey={urllib.parse.quote(query)}&count=25"
        )
        req = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        raw_results = []
        for item in (data if isinstance(data, list) else data.get("results", [])):
            raw_results.append({
                "cusip": item.get("cusip") or item.get("CUSIP", ""),
                "issuer": item.get("issuerName") or item.get("companyName", ""),
                "description": item.get("issueDescription") or item.get("bondDescription") or item.get("description", ""),
                "coupon": item.get("couponRate") or item.get("coupon"),
                "maturity": item.get("maturityDate", ""),
                "debtType": item.get("debtType") or item.get("SubProductType") or item.get("subProductType", ""),
            })
        # Group by issuer
        from collections import OrderedDict
        issuer_map = OrderedDict()
        for r in raw_results[:25]:
            issuer_key = (r.get("issuer") or "Unknown").strip()
            if issuer_key not in issuer_map:
                issuer_map[issuer_key] = []
            issuer_map[issuer_key].append({
                "cusip": r["cusip"], "description": r.get("description", ""),
                "coupon": r.get("coupon"), "maturity": r.get("maturity", ""),
                "debtType": r.get("debtType", ""),
            })
        issuers = []
        for name, bonds in issuer_map.items():
            bonds.sort(key=lambda b: (b.get("debtType") or "", b.get("maturity") or ""))
            issuers.append({"issuer": name, "bonds": bonds})
        return {"issuers": issuers, "totalBonds": len(raw_results)}
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(ToolError.DATA_UNAVAILABLE, f"Bond search failed: {e}")


@mcp_tool(name="get_bond_data", cache=MARKET)
def tool_get_bond_data(args):
    """Look up a bond by CUSIP via FINRA TRACE."""
    cusip = args["cusip"].strip().upper()
    if len(cusip) < 6:
        raise ToolError(ToolError.INVALID_PARAMS, "CUSIP must be at least 6 characters")
    try:
        url = (
            "https://services-dynarep.ddwa.finra.org/public/getIssueData/bond"
            f"?cusip={urllib.parse.quote(cusip)}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if isinstance(data, list) and data:
            item = data[0]
        elif isinstance(data, dict):
            results = data.get("results", [])
            item = results[0] if results else None
        else:
            item = None
        if not item:
            raise ToolError(ToolError.DATA_UNAVAILABLE, f"No bond found for CUSIP '{cusip}'")
        return {
            "cusip": cusip,
            "issuer": item.get("issuerName") or item.get("companyName", ""),
            "description": item.get("issueDescription") or item.get("bondDescription", ""),
            "coupon": item.get("couponRate") or item.get("coupon"),
            "maturity": item.get("maturityDate", ""),
            "debtType": item.get("debtType") or item.get("subProductType", ""),
            "lastPrice": item.get("lastSalePrice") or item.get("lastPrice"),
            "yield": item.get("yield") or item.get("yieldToMaturity"),
        }
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(ToolError.DATA_UNAVAILABLE, f"Bond lookup failed for '{cusip}': {e}")


@mcp_tool(name="get_yield_curve", cache=FUNDAMENTAL)
def tool_get_yield_curve(args):
    """Get Treasury yield curve from FRED."""
    fred_key = os.environ.get("FRED_API_KEY", "")
    if not fred_key:
        raise ToolError(ToolError.API_REQUIRED, "Set FRED_API_KEY environment variable for yield curve data")
    series_ids = {
        "1M": "DGS1MO", "3M": "DGS3MO", "6M": "DGS6MO",
        "1Y": "DGS1", "2Y": "DGS2", "3Y": "DGS3", "5Y": "DGS5",
        "7Y": "DGS7", "10Y": "DGS10", "20Y": "DGS20", "30Y": "DGS30",
    }
    curve = {}
    for label, sid in series_ids.items():
        try:
            url = (
                f"https://api.stlouisfed.org/fred/series/observations"
                f"?series_id={sid}&api_key={fred_key}&file_type=json"
                f"&sort_order=desc&limit=1"
            )
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            obs = data.get("observations", [])
            if obs and obs[0].get("value") != ".":
                curve[label] = float(obs[0]["value"])
        except Exception:
            continue
    if not curve:
        raise ToolError(ToolError.DATA_UNAVAILABLE, "Could not fetch yield curve data from FRED")
    return {"yield_curve": curve, "source": "FRED"}


@mcp_tool(name="get_fred_data", cache=FUNDAMENTAL)
def tool_get_fred_data(args):
    """Get FRED economic data series."""
    fred_key = os.environ.get("FRED_API_KEY", "")
    if not fred_key:
        raise ToolError(ToolError.API_REQUIRED, "Set FRED_API_KEY environment variable for FRED data")
    series = args["series"].strip().upper()
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
        raise ToolError(ToolError.DATA_UNAVAILABLE, f"FRED data fetch failed for '{series}': {e}")


@mcp_tool(name="get_short_interest", cache=MARKET)
def tool_get_short_interest(args):
    """Get short interest data.

    Y1 (2026-04-24): migrated off yfinance. Now routes to OL's
    /api/short-interest endpoint which is blocked on OWNER #23 (FINRA
    Data API creds). Until that clears, the tool surfaces OL's
    "not_implemented" structured response."""
    ticker = normalize_ticker(args.get("ticker"))
    data = _api_get("/api/short-interest", {"ticker": ticker})
    if not isinstance(data, dict):
        return {"ticker": ticker, "error": "Unexpected upstream response"}
    return {
        "ticker": ticker,
        "sharesShort": _safe(data.get("sharesShort")),
        "sharesFloat": _safe(data.get("sharesFloat") or data.get("floatShares")),
        "shortRatio": _safe(data.get("shortRatio")),
        "shortPercentOfFloat": _safe(data.get("shortPercentOfFloat") or data.get("percentFloat")),
        "priorMonthSharesShort": _safe(data.get("priorMonthSharesShort") or data.get("sharesShortPriorMonth")),
        **({"error": data.get("error"), "reason": data.get("reason")} if data.get("error") else {}),
    }


# ── API-mode tool implementations ────────────────────────────────────────────
# These tools proxy to a running Oxford Ledge instance.

@mcp_tool(name="get_company_data", cache=MARKET)
def tool_get_company_data(args):
    ticker = normalize_ticker(args.get("ticker"))
    return _api_get(f"/api/data", {"ticker": ticker})


@mcp_tool(name="search_company", cache=FUNDAMENTAL)
def tool_search_company(args):
    return _api_get("/api/fund-search", {"q": args["query"]})


@mcp_tool(name="get_company_profile", cache=FUNDAMENTAL)
def tool_get_company_profile(args):
    ticker = normalize_ticker(args.get("ticker"))
    return _api_get(f"/api/data", {"ticker": ticker})


@mcp_tool(name="get_corporate_events", cache=FUNDAMENTAL)
def tool_get_corporate_events(args):
    ticker = normalize_ticker(args.get("ticker"))
    params = {"ticker": ticker}
    if args.get("event_type"):
        params["event_type"] = args["event_type"]
    return _api_get("/api/corporate-events", params)


@mcp_tool(name="get_market_indicators", cache=MARKET)
def tool_get_market_indicators(args):
    return _api_get("/api/data-status")


@mcp_tool(name="search_bdc_borrower", cache=FUNDAMENTAL)
def tool_search_bdc_borrower(args):
    return _api_get("/api/bdc/search", {"q": args["query"]})


@mcp_tool(name="get_bdc_list", cache=FUNDAMENTAL)
def tool_get_bdc_list(args):
    return _api_get("/api/bdc/list")


@mcp_tool(name="calculate_intrinsic_value", cache=NEVER)
def tool_calculate_intrinsic_value(args):
    ticker = normalize_ticker(args.get("ticker"))
    params = {"ticker": ticker}
    if args.get("method"):
        params["method"] = args["method"]
    return _api_get("/api/cross-validate", params)


@mcp_tool(name="get_anomaly_flags", cache=MARKET)
def tool_get_anomaly_flags(args):
    ticker = normalize_ticker(args.get("ticker"))
    return _api_get("/api/data", {"ticker": ticker})


# min_tier="plus": premium analytics tool (see get_options_chain note).
@mcp_tool(name="get_debt_maturities", cache=FUNDAMENTAL, heavy=True, min_tier="plus")
def tool_get_debt_maturities(args):
    ticker = normalize_ticker(args.get("ticker"))
    return _api_get("/api/debt-maturities", {"ticker": ticker})


# min_tier="plus": premium analytics tool (see get_options_chain note).
@mcp_tool(name="get_capital_allocation", cache=FUNDAMENTAL, heavy=True, min_tier="plus")
def tool_get_capital_allocation(args):
    ticker = normalize_ticker(args.get("ticker"))
    return _api_get("/api/capital-structure", {"ticker": ticker})


@mcp_tool(name="get_peer_comparison", cache=FUNDAMENTAL)
def tool_get_peer_comparison(args):
    ticker = normalize_ticker(args.get("ticker"))
    return _api_get("/api/peers", {"ticker": ticker})


@mcp_tool(name="get_news", cache=MARKET)
def tool_get_news(args):
    params = {}
    if args.get("query"):
        params["q"] = args["query"]
    if args.get("ticker"):
        params["ticker"] = normalize_ticker(args.get("ticker"))
    if args.get("limit"):
        params["limit"] = str(int(args["limit"]))
    return _api_get("/api/news/search", params)


@mcp_tool(name="get_price_history", cache=MARKET)
def tool_get_price_history(args):
    ticker = normalize_ticker(args.get("ticker"))
    params = {"ticker": ticker}
    if args.get("days"):
        params["days"] = str(int(args["days"]))
    return _api_get("/api/price-history", params)


# min_tier="plus": premium analytics tool (see get_options_chain note).
@mcp_tool(name="get_13f_holdings", cache=FUNDAMENTAL, heavy=True, min_tier="plus")
def tool_get_13f_holdings(args):
    fund = args["fund"].strip()
    params = {"fund": fund}
    if args.get("max_holdings"):
        params["max_holdings"] = str(int(args["max_holdings"]))
    return _api_get("/api/fund-holdings", params)


@mcp_tool(name="get_value_investing_fact", cache=STATIC)
def tool_get_value_investing_fact(args):
    params = {}
    if args.get("category"):
        params["category"] = args["category"]
    if args.get("query"):
        params["q"] = args["query"]
    return _api_get("/api/random-ticker", params)


# min_tier="plus": premium analytics tool (see get_options_chain note).
@mcp_tool(name="get_valuation_history", cache=MARKET, min_tier="plus")
def tool_get_valuation_history(args):
    ticker = normalize_ticker(args.get("ticker"))
    params = {"ticker": ticker}
    if args.get("period"):
        params["period"] = args["period"]
    return _api_get("/api/price-history", params)


@mcp_tool(name="get_economic_calendar", cache=MARKET)
def tool_get_economic_calendar(args):
    params = {}
    if args.get("days"):
        params["days"] = str(int(args["days"]))
    return _api_get("/api/macro-events", params)


# Tool registrations are via the @mcp_tool decorators on each tool
# function above; the dispatcher reads the core's TOOL_DISPATCH view
# (imported above).
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

def handle_request(req):
    method = req.get("method", "")
    req_id = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "oxford-ledge-mcp", "version": "2.0.3"},
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
                    "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
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
    _log(f"Oxford Ledge MCP Server v2.0.3 starting ({tool_count} tools, {mode} mode)...")
    if _API_URL:
        _log(f"  API endpoint: {_API_URL}")
    else:
        _log("  Tip: Set OXFORD_LEDGE_URL for all 36 tools. Standalone mode has 18 tools available.")

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
                return [TextContent(type="text", text=f"Unknown tool: {name}")]
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
                await server.run(read_stream, write_stream, server.create_initialization_options())

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
