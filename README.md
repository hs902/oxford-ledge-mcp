# Oxford Ledge MCP Server

> **Last updated:** 2026-08-10
> **Version:** 3.2.0 (gov-public-data-only surface; CUSIP + third-party-FRED carve-outs)

Financial data tools for [Claude Desktop](https://claude.ai/download) via the [Model Context Protocol](https://modelcontextprotocol.io/).

**13 tools** for SEC filings & fundamentals, institutional & insider ownership, BDC/private-credit holdings, and macro rates. As of 3.1.0 this is a **gov-public-data-only** package: every tool is backed by **SEC EDGAR, FRED, or U.S. Treasury** (public data) — no commercial-vendor feed anywhere in the surface, and third-party-copyright data is excluded (S&P/ICE/Moody's/CBOE FRED series are refused; FactSet-licensed bond CUSIPs are not disseminated). MIT-licensed, Oxford-Ledge-authored. **4 tools run fully standalone** against keyless public APIs; the other 9 route SEC/gov data through a running Oxford Ledge instance via `OXFORD_LEDGE_URL`. (Vendor-fed quotes/estimates/screens/news and CUSIP bond lookups are no longer in the package — use the hosted Oxford Ledge MCP server for those.)

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

### 1. API mode (recommended) — all 13 tools

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

- **Without it**, this client is anonymous against the API. The free public-data tools (SEC EDGAR, FRED, Treasury) still work — that is deliberate — but every tier-gated tool answers `AUTH_REQUIRED` telling you to set the key.
- **With it**, tools resolve against your plan's tier, and calls are attributed to your account (see `/api/billing/agent-usage`). A trial key (`ol_trial_...`) works too — it lets you evaluate the paid tools for 14 days, no card, under a daily cap.

### 2. Standalone mode — 4 tools, no Oxford Ledge account needed

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

The four standalone tools split by their data source:

- **2 fully keyless** — `get_fundamentals` + `get_sec_filings` (direct SEC EDGAR). No env var of any kind.
- **2 require `FRED_API_KEY`** — `get_yield_curve` and `get_fred_data` call FRED directly and raise `ToolError.API_REQUIRED` with a "Set FRED_API_KEY" message if the key is unset. Get a free key at [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html). (`get_fred_data` serves U.S.-government / public-domain series only; third-party-copyright series — S&P, ICE BofA, Moody's, CBOE — are refused.)

The other 9 tools raise `ToolError.API_REQUIRED` with a pointer to set `OXFORD_LEDGE_URL` when called in standalone mode. **This is a change from 1.x / 2.0.0**, which used yfinance to cover more standalone tools. That path was removed in 2.0.1 — see [MIGRATING.md](./MIGRATING.md) for the rationale.

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

`OXFORD_LEDGE_USER_TIER` is enforced in dev-mode by the in-tree server (M2 tier-gate, 2026-04-24); set it to one of the real tier keys — `free`, `plus`, `pro`, `professional`, `institutional_plus`, `team`, or `team-member` (the ranking lives in `oxford_ledge_mcp_core/registry.py::TIER_RANK`) — to test tier-restricted tools. The old display-name spellings `learner` and `analyst` are NOT tiers: `learner` aliases to `free` (denied for gated tools) and `analyst` is deliberately unaliased (denied). Not used in API or standalone modes: API mode authenticates with your `OXFORD_LEDGE_API_KEY` (the hosted remote endpoint is key/Bearer-only — session cookies are deliberately not accepted there); standalone mode has no tiers at all.

After editing config, restart Claude Desktop. You'll see the tools available.

---

## Available tools (13)

`Mode` column: **S** = works in standalone (no OXFORD_LEDGE_URL required), **A** = API mode only. As of 3.1.0 **every tool is gov-public-data** (SEC EDGAR / FRED / Treasury), with third-party-copyright fields excluded — CUSIPs (FactSet IP) are stripped from 13F/event payloads, and S&P/ICE/Moody's/CBOE FRED series are refused.

> **Removed — vendor / third-party-copyright lineage** (pin an older version if you need them):
> **3.1.0** (CUSIP + FINRA-attribution carve-out): `search_bonds`, `get_bond_data` (bond CUSIPs are FactSet IP), `get_short_interest` (advertised stub, unresolved float-lineage + FINRA-attribution) — pin `==3.0.1`.
> **3.0.0** (keyless-public cut): `get_stock_quote`, `get_financials`, `get_balance_sheet`,
> `get_cash_flow`, `get_analyst_recommendations`, `get_company_info`, `compare_stocks`,
> `screen_stocks`, `get_anomaly_flags`, `get_options_chain`, `get_economic_calendar`,
> `get_news`, `search_company` (pin `==2.1.0`). **2.1.0** (FMP-removal): `get_company_data`,
> `get_company_profile`, `get_market_indicators`, `get_valuation_history`,
> `calculate_intrinsic_value`, `get_price_history`, `get_peer_comparison` (pin `==2.0.4`).
> These remain available via the hosted Oxford Ledge MCP server. See
> [CHANGELOG.md](./CHANGELOG.md) / [MIGRATING.md](./MIGRATING.md).

### SEC fundamentals & filings (4 tools)

| Tool | Mode | Description |
|------|:-:|-------------|
| `get_fundamentals` | **S** | 10-year XBRL financials from SEC EDGAR |
| `get_sec_filings` | **S** | Recent 10-K, 10-Q, 8-K filings from EDGAR |
| `get_capital_allocation` | A | 10-year buyback / dividend / debt scorecard (SEC XBRL) |
| `get_debt_maturities` | A | Maturity schedule from 10-K footnotes |

### Ownership & insiders — SEC (3 tools)

| Tool | Mode | Description |
|------|:-:|-------------|
| `get_13f_holdings` | A | Institutional 13F holdings from EDGAR (CUSIPs stripped) |
| `get_holders` | A | Top institutional shareholders (13F) |
| `get_insider_trades` | A | Recent insider Form 4 buy/sell transactions |

### Corporate events — SEC (1 tool)

| Tool | Mode | Description |
|------|:-:|-------------|
| `get_corporate_events` | A | M&A, executive changes, restructurings (8-K; CUSIPs/ratings stripped) |

### Macro — FRED / Treasury (2 tools)

| Tool | Mode | Description |
|------|:-:|-------------|
| `get_yield_curve` | **S** | Treasury yield curve from FRED |
| `get_fred_data` | **S** | U.S.-government FRED series (GDP, UNRATE, CPI, etc.); third-party-copyright series (S&P/ICE/Moody's/CBOE) refused |

### BDC & private credit — SEC / Oxford Ledge (2 tools)

| Tool | Mode | Description |
|------|:-:|-------------|
| `search_bdc_borrower` | A | Search BDC portfolio holdings by borrower (SEC SoI) |
| `get_bdc_list` | A | All tracked BDCs with AUM and holdings |

### Reference — Oxford Ledge (1 tool)

| Tool | Mode | Description |
|------|:-:|-------------|
| `get_value_investing_fact` | A | Buffett / Graham / Munger quotes and principles |

---

## Data sources

Every tool is backed by **public data** — SEC EDGAR, FRED, or U.S. Treasury. **Nothing in this package scrapes Yahoo Finance** (the 1.x / 2.0.0 yfinance path was removed in the 2.0.1 Y1 excision), and as of **3.0.0** there is **no commercial-vendor feed anywhere in the surface** (the FMP/Finnhub-backed quote/estimate/screen/news tools were removed — they live on the hosted Oxford Ledge MCP server). As of **3.1.0** the FINRA-sourced tools were also removed: bond search + CUSIP lookup (`search_bonds`/`get_bond_data`) disseminated FactSet-licensed CUSIPs, and `get_short_interest` was an advertised stub with unresolved float-lineage + attribution. FINRA data now lives only on the hosted server.

- **SEC EDGAR** — XBRL fundamentals (`get_fundamentals`) and 10-K/10-Q/8-K filing lists (`get_sec_filings`) are fetched directly from EDGAR by the pip package (keyless). Insider Form 4 (`get_insider_trades`), 13F holdings (`get_13f_holdings` / `get_holders`), 8-K events (`get_corporate_events`), capital-allocation + debt-maturity XBRL, and BDC Schedule-of-Investments parses route through `OXFORD_LEDGE_URL` (API mode) against Oxford Ledge's EDGAR-backed tables.
- **FRED / U.S. Treasury** — Treasury yield curve + any FRED series, fetched directly. **Requires `FRED_API_KEY`** (`get_yield_curve` / `get_fred_data` error out without it). `get_fred_data` serves U.S.-government / public-domain series only — third-party-copyright series (S&P, ICE BofA, Moody's, CBOE) are refused fail-closed.
- **Oxford Ledge proprietary parses** — BDC holdings (54 BDCs, 9K+ borrowers, from SEC SoI filings) + the curated value-investing corpus. API mode only.

---

## What we don't expose

**`get_ai_question` is intentionally not in the pip package.** Claude Desktop and every other MCP client is itself an LLM with the full user conversation in context. Having Oxford Ledge generate "what should I ask about AAPL next?" questions would be redundant with what the consuming LLM already does natively, and worse — we'd see only the ticker, not the reasoning trajectory. If you want AI-guided analysis, use the Oxford Ledge app directly at [www.oxfordledge.com](https://www.oxfordledge.com) where the RAG context + user session enable actually-useful suggestions. See `docs/reference/KNOWN_GAPS.md` in the main repo for the decision record.

---

## The Full Platform

For the complete experience with 45+ databases, news archive, credit analysis, BDC data, and AI-powered analysis, visit [www.oxfordledge.com](https://www.oxfordledge.com).

---

## Disclaimer

Oxford Ledge is a research and education platform for lifelong students and
investors. This software is provided "as is", without warranty of any kind,
under the MIT License (see LICENSE). It is an MCP server for accessing and
parsing public financial data. **It is not investment, financial, legal, or
tax advice, and nothing it returns is a recommendation to buy, sell, or hold
any security.** Data may be incomplete, delayed, or inaccurate — SEC filings
are periodic and lagged, and FRED series are revised. You are responsible for
independently verifying anything you rely on and for your own investment
decisions. Full terms: https://www.oxfordledge.com/terms

---

## License

MIT
