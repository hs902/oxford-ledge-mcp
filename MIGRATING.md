# Migrating `oxford-ledge-mcp` from 1.x to 2.0

**TL;DR:** 2.0 is an internal architecture refactor. Your Claude Desktop config does not change. Tool names, argument schemas, and output shapes are unchanged. If you already have Oxford Ledge MCP working, the upgrade is a one-line `pip install --upgrade oxford-ledge-mcp`.

---

## What changed (and why)

Before 2.0, the in-tree Oxford Ledge MCP server (`mcp_server.py` in
the `OxfordLedge/OxfordLedge` repo) and the pip-installable twin
(`oxford-ledge-mcp` on PyPI) had **overlapping but independent
implementations** of the same primitives — tool registry, cache
layer, error classes, concurrency semaphores. This created
structural drift: a fix in one place would be forgotten in the
other, and over time the two servers diverged in subtle ways.

2.0 extracts those shared primitives into a new subpackage
`oxford_ledge_mcp_core` that both servers consume. The
`@mcp_tool(name=..., cache=..., heavy=...)` decorator, the
`ToolError` class, and the cache primitives now live in one place.

**For end users, nothing observable changes.** The same 36 tools are
exposed by the pip package under the same names with the same
argument schemas. Output shapes are byte-equivalent to 1.x.

## What's still unchanged

- **Claude Desktop config** stays the same:
  ```json
  {
    "mcpServers": {
      "oxford-ledge": {
        "command": "oxford-ledge-mcp",
        "env": { "OXFORD_LEDGE_URL": "https://www.oxfordledge.com" }
      }
    }
  }
  ```
- **Tool names and schemas** — every tool that worked in 1.x works in 2.0
  with the same inputs.
- **Modes** — standalone mode (no `OXFORD_LEDGE_URL`) and API mode (all 36
  tools with `OXFORD_LEDGE_URL` set) both still exist. NOTE: 2.0.1 removed
  yfinance, so standalone no longer covers the former 18 yfinance tools — it
  now serves only the keyless public-API tools (FRED / SEC; the FINRA TRACE
  bond tools were removed in 3.1.0 -- this line previously listed them).
  See the "2.0.1 — yfinance removed" section below.
- **Environment variables** — same list (`OXFORD_LEDGE_URL`,
  `FRED_API_KEY`).

## What moved under the hood

For package maintainers / contributors reading the source:

- `TOOL_MAP` (old flat dispatch dict in `oxford_ledge_mcp/server.py`)
  is removed. Tool registrations happen via `@mcp_tool(name="…",
  cache=…, heavy=…)` decorators above each handler function; the
  decorator writes to `oxford_ledge_mcp_core.TOOL_DISPATCH` which the
  dispatcher reads.
- `class ToolError` is no longer defined in `oxford_ledge_mcp/server.py`
  — imported from `oxford_ledge_mcp_core.errors`.
- Cache primitives (`_cache_key`, `_cache_get`, `_cache_set`) are
  imported from `oxford_ledge_mcp_core.cache`.
- TTL tier constants (`_CACHE_TTL_MARKET`, etc.) are imported as
  short aliases (`MARKET`, `FUNDAMENTAL`, `STATIC`, `NEVER`) from
  `oxford_ledge_mcp_core`.
- A new `ToolError.API_REQUIRED` code signals "this tool needs
  `OXFORD_LEDGE_URL` set" — previously this was ad-hoc.

## Upgrading

```bash
pip install --upgrade oxford-ledge-mcp
```

After the upgrade, restart Claude Desktop so it re-spawns the MCP
subprocess against the new version. Verify with a test prompt:
*"Using Oxford Ledge, get the SEC fundamentals for AAPL."* (calls
`get_fundamentals` — a live tool in every current build; the previously
suggested `get_stock_quote` was removed in 3.0.0).

## Rolling back

If 2.0 breaks something for you:

```bash
pip install "oxford-ledge-mcp==2.0.2"
```

> [CORRECTED 2026-08-10: this section previously said `pip install
> "oxford-ledge-mcp<2.0"` and claimed "1.x installs stay available on PyPI
> indefinitely" -- PyPI has NO 1.x release (the earliest published version
> is 2.0.0), so that rollback failed to resolve. 2.0.2 is the last 2.x.]
>
> [CORRECTED AGAIN 2026-09-01: "2.0.2 is the last 2.x" was also wrong --
> the CHANGELOG records 2.0.3, 2.0.4 (2026-05-27) and 2.1.0 (2026-07-21),
> all published. To pin the newest 2.x: `pip install "oxford-ledge-mcp<3"`
> (resolves to 2.1.0).]

Report the issue
at https://github.com/hs902/oxford-ledge-mcp/issues (the package's public
home, per pyproject `Repository`) so we can fix it.

## Reporting issues

Include in your bug report:
1. The tool name that failed (e.g. `get_fundamentals`).
2. The argument dict you passed.
3. The error message Claude Desktop surfaced.
4. Whether you're in standalone mode or API mode
   (`OXFORD_LEDGE_URL` set or not).
5. `pip show oxford-ledge-mcp | grep Version` so we know which release.

## 2.0.1 — yfinance removed (Y1 sprint, 2026-04-24)

**Breaking change affecting standalone-mode users.** If you were
using `oxford-ledge-mcp` WITHOUT `OXFORD_LEDGE_URL` set, 11 tools
that worked in 1.x + 2.0.0 will now raise `ToolError.API_REQUIRED`
until you set the env var.

### Why we did this

yfinance is a community reverse-engineered client that scrapes
Yahoo Finance. Yahoo's ToS prohibits unofficial scraping, and the
endpoint breaks regularly when Yahoo changes internals. Oxford
Ledge's brand rests on trust + accuracy — we can't depend on a
ToS-violating upstream. The full rationale lives in the Oxford Ledge
monorepo's yfinance-excision decision record (private; summarized in this
package's CHANGELOG 2.0.1 entry).

### What changed

- **`yfinance` removed from pip dependencies.** 2.0.1 installs with zero third-party deps (stdlib only until you opt into `[mcp]` extra).
- **11 tools now require API mode:** `get_stock_quote`, `get_financials`, `get_balance_sheet`, `get_cash_flow`, `get_analyst_recommendations`, `get_holders`, `get_company_info`, `compare_stocks`, `get_insider_trades`, `get_short_interest`, `screen_stocks`. Set `OXFORD_LEDGE_URL` to continue using them.
- **Standalone-mode now covers 5-7 tools** (FRED macro, FINRA TRACE bonds, static-reference facts). Exact count depends on your environment — anything that routed through yfinance is gone.
- **Data sources are now:** FMP (fundamentals + quotes via Oxford Ledge server), SEC EDGAR (filings, Form 4, 13F), FRED (macro, yield curve), FINRA TRACE (bonds), Finnhub (supplementary; paid). **No Yahoo Finance anywhere in the stack.**

### If you relied on standalone mode

You have two options:

1. ~~Pin 1.x~~ **Not possible** — PyPI has no 1.x release (earliest published version is 2.0.0; see the corrected "Rolling back" section above). If you need the old tool set, pin the newest 2.x: `pip install "oxford-ledge-mcp<3"`.
2. **Set `OXFORD_LEDGE_URL`** — see the main README. This routes your MCP tools through an Oxford Ledge instance that has the proper FMP + SEC EDGAR integrations.

### CI gate

As of 2.0.1, the Oxford Ledge repo has a permanent CI gate at
`.github/workflows/ci.yml` that blocks any future PR reintroducing
yfinance imports. Accidental regression is impossible.

---

## 3.0.0 — gov-public-data-only surface (keyless-public cut, 2026-07-21)

**Breaking change: 13 vendor-data-lineage tools removed.** As of 3.0.0 the package
is **gov-public-data-only** — every one of its 16 tools is backed solely by SEC
EDGAR, FRED, U.S. Treasury, or FINRA TRACE. The following tools were removed (they
no longer appear in `tools/list`; calling one returns a structured migration
pointer):

`get_stock_quote`, `get_financials`, `get_balance_sheet`, `get_cash_flow`,
`get_analyst_recommendations`, `get_company_info`, `compare_stocks`, `screen_stocks`,
`get_anomaly_flags`, `get_options_chain`, `get_economic_calendar`, `get_news`,
`search_company`.

### Why

These tools proxied commercial-vendor data (FMP quotes/financials/estimates,
options-vendor chains, aggregated third-party news, a blended-profile search). The
2.1.0 FMP-removal narrowed the *default* surface; 3.0.0 finishes the job so the
package is unambiguously public-data-only — a clean, redistributable, gov-sourced
tool set with no commercial feed anywhere.

### What to do

- **Need any of the removed tools?** They live on the **hosted Oxford Ledge MCP
  server** (the in-tree server behind `www.oxfordledge.com`), or pin
  `pip install "oxford-ledge-mcp==2.1.0"` (which still ships them). PyPI is immutable
  — 2.1.0 stays installable forever.
- **For fundamentals**, prefer `get_fundamentals` (SEC XBRL) — it was always the
  cleaner source than the removed `get_financials`/`get_balance_sheet`/`get_cash_flow`.
- **For macro**, use `get_fred_data` / `get_yield_curve` (FRED/Treasury) instead of
  the removed `get_economic_calendar`.

### What's unchanged

Every surviving tool keeps its name, argument schema, and return shape. Standalone
mode is unaffected (the 6 keyless tools are all gov-public and all survive).

---

## 2.1.0 — vendor-fed valuation tools removed (FMP-removal, 2026-07-21)

**Breaking change affecting API-mode users of 7 tools.** The following
tools have been removed from the package entirely (they no longer appear
in `tools/list` and calling them returns an unknown-tool error):

`get_company_data`, `get_company_profile`, `get_market_indicators`,
`calculate_intrinsic_value`, `get_peer_comparison`, `get_price_history`,
`get_valuation_history`.

### Why we did this

These 7 tools proxied Oxford Ledge REST endpoints whose data carries
commercial-vendor lineage (FMP fundamentals/quotes, Finnhub-derived
intrinsic values, vendor price history). Oxford Ledge is consolidating
its distributable MCP surface onto a **clean core** — tools whose output
is derivable purely from public-domain sources (SEC EDGAR XBRL, U.S.
Treasury, FRED, and other U.S.-government data) — so the package can be
redistributed without re-licensing a vendor's data. A tool whose value
depends on a vendor feed does not belong in a redistributable package.

### What replaces them

The intrinsic-value / peer / screen capability is being rebuilt from
**SEC EDGAR company-facts XBRL only** (`ol_intrinsic_value`,
`ol_peer_fundamentals`, `ol_fundamentals_screen`) — DCF / EPV / Graham
per-share, peer fundamentals, and a bounded fundamentals screen, with
**no price leg** (fetch a price from your own source to compute upside).
These currently ship in the in-tree server; they arrive in this pip
package in a later release once the redistribution vet completes.

### If you relied on the removed tools

For raw price history or a vendor company profile, query your Oxford
Ledge instance's REST API directly. For fundamentals + valuation, prefer
the SEC-XBRL tools (`get_fundamentals`, and the `ol_*` valuation tools
when they land here).

---

## Version history

- **3.1.0** (2026-07-21) — third-party-IP compliance sweep (CHAOS+DATA_CZAR+
  COUNSEL vetted): `search_bonds` + `get_bond_data` removed (bond CUSIPs are
  FactSet-licensed IP) and `get_short_interest` removed (advertised stub,
  unresolved float-lineage + FINRA attribution); `get_13f_holdings` +
  `get_corporate_events` now strip CUSIPs/ratings; `get_value_investing_fact`
  repointed off a vendor endpoint; `get_fred_data` refuses third-party-copyright
  FRED series (S&P/ICE/Moody's/CBOE) **fail-closed**. 13 tools. Pin `==3.0.1`
  for the removed tools.
- **3.0.0** (2026-07-21) — gov-public-data-only surface: 13 more vendor
  tools removed; the package is now 16 SEC/FRED/Treasury/FINRA tools. See above.
- **2.1.0** (2026-07-21) — FMP-removal: 7 vendor-fed valuation/price
  tools removed for a clean-core redistributable surface. See above.
- **2.0.1** (2026-04-24) — yfinance excision (Y1 sprint). See above.
- **2.0.0** (2026-04-24 — YANKED) — M1 twin-dedup. Shared
  `oxford_ledge_mcp_core` subpackage. Yanked when yfinance dep was
  discovered post-publish; 2.0.1 is the clean shipping version of
  the same architecture refactor.
- **1.x** (2026-04-04 → 2026-04-23) — Initial pip release; 36 tools
  using independent primitives + yfinance for standalone mode.
