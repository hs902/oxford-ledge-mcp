# Oxford Ledge MCP Server

> **Last updated:** 2026-07-21
> **Version:** 2.1.0 (clean-core: vendor-fed tools removed)

Financial data tools for [Claude Desktop](https://claude.ai/download) via the [Model Context Protocol](https://modelcontextprotocol.io/).

**29 tools** for stocks, SEC filings, bonds, credit data, BDC holdings, macro indicators, and more. This is an MIT-licensed, Oxford-Ledge-authored client: several tools **proxy the Oxford Ledge hosted service (a licensed data service) at runtime** rather than bundling any vendor data. **Best experienced with `OXFORD_LEDGE_URL` set** — routes through a running Oxford Ledge instance whose pipeline draws on SEC EDGAR, FRED, FINRA TRACE, and licensed commercial feeds. A small subset of tools also works standalone against keyless public APIs.

**Upgrading from 1.x / 2.0.0 / 2.0.1?** See [MIGRATING.md](./MIGRATING.md). Short version: tool names, arg schemas, and config are unchanged across the 2.x series. Two substantive changes:

1. 2.0 extracted the shared tool registry into an `oxford_ledge_mcp_core` subpackage consumed by both the pip-installable server and Oxford Ledge's in-tree server. No user-visible behavior change.
2. 2.0.1 removed yfinance from this package (it was a ToS-violating scraper dependency). 11 tools that used to work standalone now require `OXFORD_LEDGE_URL`.
3. 2.0.2 internal-refactor cleanup; no behavior change.

---

## Install

```bash
pip install oxford-ledge-mcp
```

The base install has **zero third-party dependencies** (stdlib only, since the
2.0.1 yfinance excision). The server ships with a built-in JSON-RPC-over-stdio
fallback, so it runs as-is. For the canonical [`mcp`](https://pypi.org/project/mcp/)
protocol library path, install the optional extra:

```bash
pip install "oxford-ledge-mcp[mcp]"
```

If the `mcp` package is present the server uses it; otherwise it transparently
falls back to the built-in stdio loop. Either way, requires Python ≥ 3.9.

> **Running via `uvx` (no install).** You can skip `pip install` and let
> [uv](https://docs.astral.sh/uv/) fetch + run the package on demand — set
> `"command": "uvx"`, `"args": ["oxford-ledge-mcp"]`. Because the package
> declares no required deps, plain `uvx oxford-ledge-mcp` runs the **built-in
> JSON-RPC loop** (complete, zero extra deps); add the official library with
> `"args": ["--with", "mcp", "oxford-ledge-mcp"]` only if you specifically want
> its protocol handling. Both connect to Claude Desktop. On Windows, if Claude
> Desktop reports the server failed to start, it usually can't find `uvx` on the
> GUI's PATH — use the absolute path as the command
> (e.g. `C:\\Users\\<you>\\.local\\bin\\uvx.exe`).

---

## Three modes

This server runs in one of three modes — pick the one that matches your Oxford Ledge subscription state. **The pip package is the user-distributed canonical path; the in-tree dev server is for Oxford Ledge contributors only.**

### 1. API mode (recommended) — all 29 tools

For full functionality, point the server at a running Oxford Ledge instance. Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "oxford-ledge": {
      "command": "oxford-ledge-mcp",
      "env": {
        "OXFORD_LEDGE_URL": "https://www.oxfordledge.com",
        "OXFORD_LEDGE_API_KEY": "ol_live_..."
      }
    }
  }
}
```

`OXFORD_LEDGE_URL` should be the URL of an Oxford Ledge instance you have access to (the public app, your own self-hosted deploy, or `http://localhost:5000` for local dev).

`OXFORD_LEDGE_API_KEY` is your Oxford Ledge API key (create one at [oxfordledge.com/account](https://www.oxfordledge.com/account)). It is sent as the `x-api-key` header and it is what makes the tools **yours**:

- **Without it**, this client is anonymous against the API. The free public-data tools (SEC EDGAR, FRED, Treasury, FINRA) still work — that is deliberate — but every tier-gated tool answers `AUTH_REQUIRED` telling you to set the key.
- **With it**, tools resolve against your plan's tier, and calls are attributed to your account (see `/api/billing/agent-usage`). A trial key (`ol_trial_...`) works too — it lets you evaluate the paid tools for 14 days, no card, under a daily cap.

### 2. Standalone mode — 6 tools, no Oxford Ledge account needed

A small subset of tools works without an Oxford Ledge instance — the ones backed by direct public APIs:

```json
{
  "mcpServers": {
    "oxford-ledge": {
      "command": "oxford-ledge-mcp",
      "env": {
        "FRED_API_KEY": "your-fred-key"
      }
    }
  }
}
```

The six standalone tools split by their data source:

- **4 fully keyless** — `get_fundamentals` + `get_sec_filings` (direct SEC EDGAR) and `search_bonds` + `get_bond_data` (FINRA TRACE). No env var of any kind.
- **2 require `FRED_API_KEY`** — `get_yield_curve` and `get_fred_data` call FRED directly and raise `ToolError.API_REQUIRED` with a "Set FRED_API_KEY" message if the key is unset. Get a free key at [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html).

The other 23 tools raise `ToolError.API_REQUIRED` with a pointer to set `OXFORD_LEDGE_URL` when called in standalone mode. **This is a change from 1.x / 2.0.0**, which used yfinance to cover more standalone tools. That path was removed in 2.0.1 — see [MIGRATING.md](./MIGRATING.md) for the rationale.

### 3. Dev mode — in-tree from an Oxford Ledge checkout

If you're an Oxford Ledge contributor working on the parser/dispatcher itself, run `mcp_server.py` directly from your checkout:

```json
{
  "mcpServers": {
    "oxford-ledge-dev": {
      "command": "python",
      "args": ["/abs/path/to/oxford_ledge/mcp_server.py"],
      "env": {
        "OXFORD_LEDGE_USER_TIER": "pro"
      }
    }
  }
}
```

`OXFORD_LEDGE_USER_TIER` is enforced in dev-mode by the in-tree server (M2 tier-gate, 2026-04-24); set it to `learner` / `analyst` / `plus` / `pro` / `investor_plus` to test tier-restricted tools. Not used in API or standalone modes (those enforce via session cookies / not at all). See [MCP_FOLLOWUPS.md §8.2](../docs/plans/MCP_FOLLOWUPS.md) for the design record.

After editing config, restart Claude Desktop. You'll see the tools available.

---

## Available tools (29)

`Mode` column: **S** = works in standalone (no OXFORD_LEDGE_URL required), **A** = API mode only.

> **Removed in 2.1.0** (vendor-data lineage; pin `oxford-ledge-mcp==2.0.4` if you
> need them): `get_company_data`, `get_company_profile`, `get_market_indicators`,
> `get_valuation_history`, `calculate_intrinsic_value`, `get_price_history`,
> `get_peer_comparison`. See [CHANGELOG.md](./CHANGELOG.md) / [MIGRATING.md](./MIGRATING.md).

### Stocks & quotes (4 tools)

| Tool | Mode | Description |
|------|:-:|-------------|
| `get_stock_quote` | A | Current price, P/E, EV/EBITDA, market cap, beta |
| `search_company` | A | Fuzzy search by name, ticker, or industry |
| `compare_stocks` | A | Side-by-side comparison of 2-5 stocks |
| `get_company_info` | A | Sector, industry, employees, description |

### Fundamentals & valuation (7 tools)

| Tool | Mode | Description |
|------|:-:|-------------|
| `get_fundamentals` | **S** | 10-year XBRL financials from SEC EDGAR |
| `get_financials` | A | Income statement (revenue, net income, EBITDA) |
| `get_balance_sheet` | A | Assets, liabilities, equity, debt, cash |
| `get_cash_flow` | A | Operating, investing, financing cash flows, FCF |
| `get_capital_allocation` | A | 10-year buyback / dividend / debt scorecard |
| `get_debt_maturities` | A | Maturity schedule from 10-K footnotes |
| `get_anomaly_flags` | A | 15 automated red-flag checks |

### News, events & estimates (8 tools)

| Tool | Mode | Description |
|------|:-:|-------------|
| `get_news` | A | News archive search with sentiment scores |
| `get_corporate_events` | A | M&A, executive changes, restructurings |
| `get_economic_calendar` | A | FOMC, CPI, GDP, jobs-report dates |
| `get_analyst_recommendations` | A | Buy/hold/sell counts, price targets |
| `get_holders` | A | Top institutional shareholders |
| `get_13f_holdings` | A | Institutional 13F holdings from EDGAR |
| `get_insider_trades` | A | Recent insider buy/sell transactions |
| `get_short_interest` | A | Short percent of float, days to cover |

### Options & screening (2 tools)

| Tool | Mode | Description |
|------|:-:|-------------|
| `get_options_chain` | A | Calls and puts with expiry filtering |
| `screen_stocks` | A | Filter by sector, market cap, P/E, dividend yield |

### SEC filings (1 tool)

| Tool | Mode | Description |
|------|:-:|-------------|
| `get_sec_filings` | **S** | Recent 10-K, 10-Q, 8-K filings from EDGAR |

### Bonds — FINRA TRACE (2 tools)

| Tool | Mode | Description |
|------|:-:|-------------|
| `search_bonds` | **S** | Search bond issuers via FINRA TRACE |
| `get_bond_data` | **S** | Look up bonds by CUSIP |

### Macro — FRED (2 tools)

| Tool | Mode | Description |
|------|:-:|-------------|
| `get_yield_curve` | **S** | Treasury yield curve from FRED |
| `get_fred_data` | **S** | Any FRED series (GDP, UNRATE, CPI, etc.) |

### BDC & credit (2 tools)

| Tool | Mode | Description |
|------|:-:|-------------|
| `search_bdc_borrower` | A | Search BDC portfolio holdings by borrower |
| `get_bdc_list` | A | All tracked BDCs with AUM and holdings |

### Static reference (1 tool)

| Tool | Mode | Description |
|------|:-:|-------------|
| `get_value_investing_fact` | A | Buffett / Graham / Munger quotes and principles |

---

## Data sources

All data in 2.0.1+ flows through Oxford Ledge's licensed providers or keyless public APIs. **Nothing in this package scrapes Yahoo Finance** (the previous 1.x / 2.0.0 yfinance path was removed in the 2.0.1 Y1 excision sprint).

- **FMP** (Financial Modeling Prep) — real-time quotes, financials, analyst estimates. Routed through `OXFORD_LEDGE_URL` (API mode) — the pip package carries no FMP keys and bundles no FMP data; it proxies Oxford Ledge's licensed hosted service. (The vendor-price/profile tools that leaned on FMP were removed in 2.1.0.)
- **SEC EDGAR** — XBRL fundamentals (`get_fundamentals`) and 10-K/10-Q/8-K filing lists (`get_sec_filings`) are fetched directly from EDGAR by the pip package (keyless). Form 4 insider transactions (`get_insider_trades`) and 13F holdings (`get_13f_holdings`) route through `OXFORD_LEDGE_URL` (API mode) against Oxford Ledge's EDGAR-backed tables.
- **FINRA TRACE** — corporate bond search + CUSIP lookup, fetched directly by the pip package. Keyless public API.
- **FRED** — Treasury yield curve + any FRED series, fetched directly by the pip package. **Requires `FRED_API_KEY`** (`get_yield_curve` / `get_fred_data` error out without it).
- **Finnhub** — supplementary quotes + profile. Paid legitimate API (not scraper); routed through `OXFORD_LEDGE_URL`.
- **Oxford Ledge proprietary data** — BDC holdings (54 BDCs, 9K+ borrowers), news archive, 176K+ Form 4 transactions, valuations history. API mode only.

---

## What we don't expose

**`get_ai_question` is intentionally not in the pip package.** Claude Desktop and every other MCP client is itself an LLM with the full user conversation in context. Having Oxford Ledge generate "what should I ask about AAPL next?" questions would be redundant with what the consuming LLM already does natively, and worse — we'd see only the ticker, not the reasoning trajectory. If you want AI-guided analysis, use the Oxford Ledge app directly at [www.oxfordledge.com](https://www.oxfordledge.com) where the RAG context + user session enable actually-useful suggestions. See `docs/reference/KNOWN_GAPS.md` in the main repo for the decision record.

---

## Full Terminal

For the complete experience with 45+ databases, news archive, credit analysis, BDC data, and AI-powered analysis, visit [www.oxfordledge.com](https://www.oxfordledge.com).

---

## License

MIT
