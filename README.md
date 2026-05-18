> **Last Updated:** 2026-04-24 ET — 2.0.2 (clean architecture, post-yfinance excision)

# Oxford Ledge MCP Server

Financial data tools for [Claude Desktop](https://claude.ai/download) via the [Model Context Protocol](https://modelcontextprotocol.io/).

**36 tools** for stocks, SEC filings, bonds, credit data, BDC holdings, macro indicators, and more. **Best experienced with `OXFORD_LEDGE_URL` set** — routes through a running Oxford Ledge instance that has the full data pipeline (FMP, SEC EDGAR, FRED, FINRA TRACE, Finnhub). A small subset of tools also works standalone against keyless public APIs.

**Upgrading from an earlier 2.x version?** Tool names, argument
schemas, and Claude Desktop config are unchanged. One substantive
change: standalone mode (no `OXFORD_LEDGE_URL`) now covers fewer
tools; the rest require an Oxford Ledge API endpoint — see
"Standalone mode" below.

---

## Install

```bash
pip install oxfordledge-mcp
```

---

## Three modes

This server runs in one of three modes — pick the one that matches your Oxford Ledge subscription state. **The pip package is the user-distributed canonical path; the in-tree dev server is for Oxford Ledge contributors only.**

### 1. API mode (recommended) — all 36 tools

For full functionality, point the server at a running Oxford Ledge instance. Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "oxford-ledge": {
      "command": "oxford-ledge-mcp",
      "env": {
        "OXFORD_LEDGE_URL": "https://www.oxfordledge.com"
      }
    }
  }
}
```

`OXFORD_LEDGE_URL` should be the URL of an Oxford Ledge instance you have access to (the public app, your own self-hosted deploy, or `http://localhost:5000` for local dev).

### 2. Standalone mode — 6 tools, no Oxford Ledge account needed

A small subset of tools works without an Oxford Ledge instance — the ones backed by keyless public APIs:

```json
{
  "mcpServers": {
    "oxford-ledge": {
      "command": "oxford-ledge-mcp",
      "env": {
        "FRED_API_KEY": "your-fred-key-optional"
      }
    }
  }
}
```

The `FRED_API_KEY` is optional but improves rate limits on FRED queries (`get_yield_curve`, `get_fred_data`). Get a free key at [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html).

The other 30 tools raise `ToolError.API_REQUIRED` with a pointer back to this README when called in standalone mode.

After editing config, restart Claude Desktop. You'll see the tools available.

---

## Available tools (36)

`Mode` column: **S** = works in standalone (no OXFORD_LEDGE_URL required), **A** = API mode only.

### Stocks & quotes (7 tools)

| Tool | Mode | Description |
|------|:-:|-------------|
| `get_stock_quote` | A | Current price, P/E, EV/EBITDA, market cap, beta |
| `get_company_data` | A | Full company snapshot with valuation multiples |
| `search_company` | A | Fuzzy search by name, ticker, or industry |
| `compare_stocks` | A | Side-by-side comparison of 2-5 stocks |
| `get_company_info` | A | Sector, industry, employees, description |
| `get_company_profile` | A | Business description, CEO, founding year |
| `get_market_indicators` | A | S&P 500, VIX, Treasury yields, gold, oil |

### Fundamentals & valuation (9 tools)

| Tool | Mode | Description |
|------|:-:|-------------|
| `get_fundamentals` | **S** | 10-year XBRL financials from SEC EDGAR |
| `get_financials` | A | Income statement (revenue, net income, EBITDA) |
| `get_balance_sheet` | A | Assets, liabilities, equity, debt, cash |
| `get_cash_flow` | A | Operating, investing, financing cash flows, FCF |
| `get_valuation_history` | A | Historical P/E, EV/EBITDA, P/B, P/S |
| `get_capital_allocation` | A | 10-year buyback / dividend / debt scorecard |
| `get_debt_maturities` | A | Maturity schedule from 10-K footnotes |
| `calculate_intrinsic_value` | A | DCF, EPV, Graham fair-value models |
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

### Pricing, options & screening (3 tools)

| Tool | Mode | Description |
|------|:-:|-------------|
| `get_price_history` | A | OHLCV price history |
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

### BDC & credit (3 tools)

| Tool | Mode | Description |
|------|:-:|-------------|
| `search_bdc_borrower` | A | Search BDC portfolio holdings by borrower |
| `get_bdc_list` | A | All tracked BDCs with AUM and holdings |
| `get_peer_comparison` | A | Peer valuation and financial metrics |

### Static reference (1 tool)

| Tool | Mode | Description |
|------|:-:|-------------|
| `get_value_investing_fact` | A | Buffett / Graham / Munger quotes and principles |

---

## Data sources

All data in 2.0.1+ flows through Oxford Ledge's licensed providers or keyless public APIs. **Nothing in this package scrapes Yahoo Finance** (the previous 1.x / 2.0.0 yfinance path was removed in the 2.0.1 Y1 excision sprint).

- **FMP** (Financial Modeling Prep) — real-time quotes, financials, analyst estimates, company profiles, historical prices. Routed through `OXFORD_LEDGE_URL` (API mode) — pip package doesn't carry FMP keys.
- **SEC EDGAR** — XBRL fundamentals, 10-K/10-Q/8-K filings, Form 4 insider transactions, 13F institutional holdings. Keyless public API.
- **FINRA TRACE** — corporate bond search + CUSIP lookup. Keyless public API.
- **FRED** — Treasury yields, economic indicators, data-release calendar. Optional `FRED_API_KEY` for higher rate limits.
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

## Disclaimer

This software is provided "as is", without warranty of any kind, under
the MIT License (see LICENSE). It is a developer tool for accessing and
parsing financial data. **It is not investment, financial, legal, or
tax advice, and nothing it returns is a recommendation to buy, sell, or
hold any security.** Data may be incomplete, delayed, or inaccurate.
You are responsible for independently verifying anything you rely on
and for your own investment decisions. Data returned by the Oxford
Ledge API is governed by the terms at https://www.oxfordledge.com.

## Contributions

By submitting a pull request or patch, you agree your contribution is
licensed under the same MIT License as this project (inbound = outbound).
