# Oxford Ledge MCP Server

> **Last updated:** 2026-09-24
> **Version:** 3.7.0 (gov-public-data-only surface; CUSIP + third-party-FRED carve-outs)

Financial data tools for [Claude Desktop](https://claude.ai/download) via the [Model Context Protocol](https://modelcontextprotocol.io/).

**29 tools** for SEC filings & fundamentals, institutional & insider ownership, BDC/private-credit holdings, macro rates, and federal reference data (FDIC, USAspending, USPTO, CFTC). As of 3.1.0 this is a **gov-public-data-only** package: 28 of the 29 tools are backed by a **U.S.-government public source** — SEC EDGAR, FRED, U.S. Treasury, FDIC, USAspending, USPTO or CFTC — and the one exception, `get_value_investing_fact`, is Oxford Ledge-authored (`basis: ol-authored`, a curated corpus of attributed quotations -- `author` / `source` on every row); there is no commercial-vendor feed anywhere in the surface, and third-party-copyright data is excluded (S&P/ICE/Moody's/CBOE FRED series are refused; FactSet-licensed bond CUSIPs are not disseminated). The software is MIT-licensed and Oxford-Ledge-authored; the **data** it returns carries its own terms (see [Data license](#data-license) below). **27 of the 29 tools are reachable with no Oxford Ledge account:** 4 run fully standalone against public APIs (2 SEC EDGAR, keyless; 2 FRED, needing a free `FRED_API_KEY`), and 23 more answer keyless once `OXFORD_LEDGE_URL` points at a running Oxford Ledge instance (14 name-proxies of the hosted MCP's anonymous `/mcp` transport plus 9 proxies of unauthenticated REST routes). Only the two Plus-tier tools (`get_debt_maturities`, `get_capital_allocation`) need an `OXFORD_LEDGE_API_KEY`. API mode **with** a key is still the recommended install: it attributes calls to your account, unlocks the two paid tools, and is the only leg that can refresh a stale EDGAR cache (see `get_activist_stakes`). (Vendor-fed quotes/estimates/screens/news and CUSIP bond lookups are no longer in the package — use the hosted Oxford Ledge MCP server for those.)

**Upgrading from 1.x / 2.0.0 / 2.0.1?** See [MIGRATING.md](https://github.com/hs902/oxford-ledge-mcp/blob/main/MIGRATING.md) (GitHub — this file and CHANGELOG.md are not in the wheel or the sdist). Short version: tool names, arg schemas, and config are unchanged across the 2.x series. Two substantive changes:

1. 2.0 extracted the shared tool registry into an `oxford_ledge_mcp_core` subpackage consumed by both the pip-installable server and Oxford Ledge's in-tree server. No user-visible behavior change.
2. 2.0.1 removed yfinance from this package (it was a ToS-violating scraper dependency). 11 tools that used to work standalone now require `OXFORD_LEDGE_URL`.
3. 2.0.2 internal-refactor cleanup; no behavior change.

**This is 3.7.0.** Its changes from 3.6.0 are in [MIGRATING.md](https://github.com/hs902/oxford-ledge-mcp/blob/main/MIGRATING.md). No tool or key is renamed or removed, and two kinds of value that 3.6.0 accepted are now REFUSED: `get_fred_data` refuses `MORTGAGE30US` (Freddie Mac) and `AAA` (Moody's) before any request is made, because neither is a U.S.-government work -- while 40 reviewed federal series now serve even when FRED's metadata endpoint is down -- and `days` below 1 on `ol_form_d_raises` / `get_fails_to_deliver` is refused as `INVALID_PARAMS` (3.6.0 forwarded it and the host fell back to its default window; omit `days` for the default). **One new outbound header:** with `OXFORD_LEDGE_API_KEY` set, the nine REST-proxied tools send `X-OL-MCP-Tool` carrying the calling tool's own name and nothing else, so your Oxford Ledge activity page can count those lookups; a keyless call sends nothing new, and the header never crosses a redirect. Everything else is additive: `get_bdc_holdings` takes optional `limit` / `offset` (a call declaring neither is byte-for-byte what 3.6.0 returned; a declaring call gets a `page` block and the book-wide totals unchanged), `get_fails_to_deliver` takes an optional `end_date`, the nine REST-proxied tools carry `_meta.response_size` (`{chars, approx_tokens, budget_chars, over_budget}` -- it reports, nothing is trimmed), a result replayed from this client's cache carries `_meta.served_from_cache` + `_meta.cache_age_seconds`, `ol_federal_contracts` rows carry the ten largest recipients with `recipients_truncated` / `recipients_total`, `ol_bdc_mark_changes` holds implausible single-quarter moves in `suspect_moves` instead of ranking them, `ol_bdc_top_borrowers` rows add `holder_count_active` / `holder_count_ever`, and `get_debt_maturities` adds a `summary` naming the buckets that have elapsed since the filing. **One value correction:** a `get_fails_to_deliver` window of `days` is now `days` calendar days (it was one day wider). **One behaviour change:** a key-carrying request to a loopback `http://` host never goes through an environment `http_proxy`. The 3.6.0 changes (the 13F superseded-parent fold on `get_holders`, the per-host body ceilings and cache budget, `http://127.1` no longer counting as loopback) are under their own heading there.

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

**The two transports agree.** The 3.4.0 publish vet drove both and found them
disagreeing on three things a client keys on; all three are closed in 3.4.0.
On **both** transports in 3.4.0: a tool error (AUTH_REQUIRED, INVALID_PARAMS,
DATA_UNAVAILABLE, RATE_LIMITED, an unknown tool) comes back flagged
`isError: true`, so an agent framework that retries or aborts on the flag sees
the same thing either way; a call missing a required argument is refused as
`INVALID_PARAMS` naming the argument, and so is a number outside its declared
`minimum` / `maximum` (see *Argument bounds* below — nothing is clamped on
either transport); and `tools/list` carries the derived
`[Tier: free|plus]` prefix on every description. How to pick: the built-in loop
when you want zero dependencies (this is what a bare `pip install` or plain
`uvx` runs); the `[mcp]` extra when your client or framework wants the
reference protocol library's own framing and schema validation. Neither serves
different data.

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

`OXFORD_LEDGE_URL` should be the URL of an Oxford Ledge instance you have access to (the public app, your own self-hosted deploy, or `http://localhost:5000` for local dev). If `OXFORD_LEDGE_API_KEY` is also set, a plain `http://` URL is refused unless the host is a loopback address (`127.0.0.1`, `127.x.y.z`, `[::1]`) or literally `localhost` -- the key would otherwise travel in the clear. Note that the `127.1` shorthand is not a parseable address and is refused; write `127.0.0.1`. A key-carrying request to a loopback host is opened without any `http_proxy` / `HTTP_PROXY` from the environment -- it reaches the local interface directly, so a corporate or system proxy neither sees the key nor needs a `no_proxy` entry for this setup. Requests to an `https://` host still honour the environment proxy.

`OXFORD_LEDGE_API_KEY` is your Oxford Ledge API key — create one in the app under **YOUR API KEYS → + Create Key**: sign in, then press **K** or click the key icon in the bottom bar, or open [oxfordledge.com/?panel=api-keys](https://www.oxfordledge.com/?panel=api-keys), which opens the panel directly (there is no `/account` page). It is sent as the `x-api-key` header (never in a URL, a log line or an error message, and never forwarded across a redirect) and it is what makes the tools **yours**:

- **Without it**, this client is anonymous against the API — and 27 of the 29 tools still answer, deliberately: the 4 standalone tools never touch Oxford Ledge, the 14 name-proxied `ol_*` / gov tools ride the hosted server's anonymous `/mcp` transport, and the 9 REST-proxied tools call routes that carry no auth. What you do NOT get without a key: the two Plus-tier tools are refused as a free-tier caller — the hosted server's tier gate answers, and the wheel translates it to `AUTH_REQUIRED` saying which tier the tool needs, that this client is anonymous, that the operator sets `OXFORD_LEDGE_API_KEY` if they already have a plan that includes it (a paying subscriber who has not set the key gets exactly this refusal), and where to upgrade otherwise; and reads that only a keyed caller may trigger serve stored rows (the EDGAR refresh behind `get_activist_stakes`, which then reports `stale: true`).
- **With it**, tools resolve against your plan's tier, and calls are attributed to your account (see `/api/billing/agent-usage`). A valid key on a plan below Plus gets `AUTH_REQUIRED` too, but the sentence then says the key was accepted and the **plan** is what is missing — never "check the key". A trial key (`ol_trial_...`) works too — it lets you evaluate the paid tools for 14 days, no card, under a daily cap. With the key set, the nine REST-proxied tools also send one `X-OL-MCP-Tool` header whose value is the tool's own name (no arguments, no package version), so those lookups count on your own activity page; it is never sent without the key and, like the key, never forwarded across a redirect.

**What "FREE" means in a tool description.** No plan tier is required — there is no paywall on the hosted channel for that tool, keyed or keyless. It does not mean unmetered: keyed calls (trial keys aside) count toward your account's agent-API allowance like every other keyed call. Keyless calls are not metered against any account.

**Argument bounds.** Every argument that declares a schema `minimum` / `maximum` (`limit`, `days`, `since_days`, `quarters`, `max_holdings`) or `maxItems` (`ol_bdc_common_borrowers.bdc_tickers`, 25) is **validated before the call, on both transports**: an out-of-range number is refused as `INVALID_PARAMS` naming the argument and the bound (`` `limit`: 5000 is greater than the maximum of 100 `` — the reference library's own sentence), an over-long list as `` `bdc_tickers`: [...] is too long ``, nothing is sent, and nothing is silently clamped or truncated. The hosted server refuses the same numeric bounds the same way (its own handler would slice a 26-ticker list at 25, which the wheel's schema declares instead of discovering). `_meta.params_accepted` echoes the arguments the host received; the `completeness` block on the payload reports what was actually served (`complete: null` at exactly the cap means undecidable — read `more_available_hint`). This is said once here rather than in every description.

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
- **2 require `FRED_API_KEY`** — `get_yield_curve` and `get_fred_data` call FRED directly and raise `ToolError.API_REQUIRED` with a "Set FRED_API_KEY" message if the key is unset. Get a free key at [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html). (`get_fred_data` serves U.S.-government / public-domain series only; third-party-copyright series — S&P, ICE BofA, Moody's, CBOE, University of Michigan — are refused.)

The other 25 tools raise `ToolError.API_REQUIRED` with a pointer to set `OXFORD_LEDGE_URL` when called in standalone mode. **This is a change from 1.x / 2.0.0**, which used yfinance to cover more standalone tools. That path was removed in 2.0.1 — see [MIGRATING.md](https://github.com/hs902/oxford-ledge-mcp/blob/main/MIGRATING.md) for the rationale.

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

## Available tools (29)

`Mode` column: **S** = works in standalone (no OXFORD_LEDGE_URL required), **A** = API mode only (needs `OXFORD_LEDGE_URL`; a key only for the two marked **Plus**). As of 3.1.0 **28 of the 29 tools are gov-public-data** (SEC EDGAR / FRED / Treasury / FDIC / USAspending / USPTO / CFTC) and the 29th, `get_value_investing_fact`, is Oxford Ledge-authored, with third-party-copyright fields excluded — CUSIPs (FactSet IP) are stripped from 13F/event payloads, and S&P/ICE/Moody's/CBOE FRED series are refused. Each tool's description (what `tools/list` returns) is the contract: it states units, the row shape, what an empty result means, and which fields are Oxford Ledge derivations rather than the source's own figures.

> **Removed — vendor / third-party-copyright lineage** (pin an older version if you need them):
> **3.1.0** (CUSIP + FINRA-attribution carve-out): `search_bonds`, `get_bond_data` (bond CUSIPs are FactSet IP), `get_short_interest` (advertised stub, unresolved float-lineage + FINRA-attribution) — pin `==3.0.1`. **A `==3.0.1` pin does NOT bring the two bond tools back as working tools:** FINRA auth-walled the public TRACE hosts they scraped in 2026-07, and on 2026-09-13 both were RETIRED on the hosted server as well (the hosted names answer `status: "retired"` with empty lists / null prices, never data). For corporate-bond discovery use the hosted server's `ol_bond_directory_screen` (LQD/HYG directory — reference data, no prices); for one issuer's own maturity schedule, `get_debt_maturities` in this package.
> **3.0.0** (keyless-public cut): `get_stock_quote`, `get_financials`, `get_balance_sheet`,
> `get_cash_flow`, `get_analyst_recommendations`, `get_company_info`, `compare_stocks`,
> `screen_stocks`, `get_anomaly_flags`, `get_options_chain`, `get_economic_calendar`,
> `get_news`, `search_company` (pin `==2.1.0`). **2.1.0** (FMP-removal): `get_company_data`,
> `get_company_profile`, `get_market_indicators`, `get_valuation_history`,
> `calculate_intrinsic_value`, `get_price_history`, `get_peer_comparison` (pin `==2.0.4`).
> These remain available via the hosted Oxford Ledge MCP server. See
> [CHANGELOG.md](https://github.com/hs902/oxford-ledge-mcp/blob/main/CHANGELOG.md) / [MIGRATING.md](https://github.com/hs902/oxford-ledge-mcp/blob/main/MIGRATING.md).

### SEC fundamentals & filings (4 tools)

| Tool | Mode | Description |
|------|:-:|-------------|
| `get_fundamentals` | **S** | Up to 10 years of XBRL financials from SEC EDGAR companyfacts (`LongTermDebt`, not total debt; per-period `concepts`; NCI-aware equity rung; Oxford Ledge split-basis check on EPS / diluted shares incl. steps across tagging holes; `coverage[].contiguous`) |
| `get_sec_filings` | **S** | The 10 newest EDGAR submissions of any form (`filing_type` narrows), with `form`, date, link and a window disclosure |
| `get_capital_allocation` | A · Plus | Capital-allocation scorecard from SEC XBRL — up to 30 fiscal-year labels with `periods` and a split-basis `basis` block, a 10-year summary window; dividends, net buybacks (issuance, IPO proceeds and SBC netted), net debt change, acquisitions, shares outstanding (hosted tool, name-proxied; the net series are Oxford Ledge derivations) |
| `get_debt_maturities` | A · Plus | Forward maturity ladder from 10-K/20-F footnotes, in millions of USD, with parser confidence + balance-sheet validation (hosted tool, name-proxied; EDGAR only) |

### Ownership & insiders — SEC (6 tools)

| Tool | Mode | Description |
|------|:-:|-------------|
| `get_13f_holdings` | A | One filer's latest 13F-HR positions + quarter-over-quarter changes (CUSIPs stripped; `ticker` is an Oxford Ledge CUSIP crosswalk, `title_of_class` the authoritative share class; PUT/CALL/PRN rows labelled; `fund` takes a CIK or a ticker incl. class-share forms like BRK-B) |
| `get_holders` | A | Top 10 institutional shareholders (13F-HR common-stock positions, each filer's latest filing; scoped `note` when empty) |
| `get_insider_trades` | A | Form 4 transactions for one issuer — latest 20, every code, derivative rows labelled, `dateBasis` names the served date |
| `ol_insider_recent_buys` | A | Market-wide OPEN-MARKET insider purchases across the Oxford Ledge issuer catalog, newest first — a daily insider screen (Form 4; `totalValue`/`position` are Oxford Ledge derivations) |
| `get_activist_stakes` | A | Schedule 13D/13G >5% beneficial-owner filings for a ticker (stored rows with `stale`/`age_seconds`; only a keyed caller refreshes from EDGAR) |
| `get_fails_to_deliver` | A | SEC fails-to-deliver settlement history for a ticker (biweekly CNS files) |

### Corporate events & private placements — SEC (2 tools)

| Tool | Mode | Description |
|------|:-:|-------------|
| `get_corporate_events` | A | The 20 most recent 8-K item events (material agreements, M&A, executive changes, earnings releases, ...; `eventType` is Oxford Ledge's item map; CUSIPs/ratings stripped) |
| `ol_form_d_raises` | A | Form D private-placement filings from the SEC's QUARTERLY data set (~1-quarter posting lag), optionally by industry / trailing window |

### Macro — FRED / Treasury / CFTC (4 tools)

| Tool | Mode | Description |
|------|:-:|-------------|
| `get_yield_curve` | **S** | Treasury constant-maturity yield curve from FRED (11 tenors, percent; per-tenor `completeness` when partial) |
| `get_fred_data` | **S** | U.S.-government FRED series (GDP, UNRATE, CPI, etc.) with `units`/`frequency`; third-party-copyright series (S&P/ICE/Moody's/CBOE/U-Michigan) refused |
| `ol_treasury_debt` | A | Monthly Statement of the Public Debt — outstanding by security type/class, millions of USD (Treasury MSPD, verbatim) |
| `ol_cftc_cot` | A | CFTC Commitments of Traders — Managed Money (disaggregated) / Leveraged Funds (TFF) positioning by market; `market_key`, `market_label`, `mm_net` are Oxford Ledge's |

### BDC & private credit — SEC / Oxford Ledge (9 tools)

| Tool | Mode | Description |
|------|:-:|-------------|
| `search_bdc_borrower` | A | Which BDCs lend to a borrower — one row per tranche, stale holders labelled, current-holder aggregates; optional `limit`/`offset` page the tranche rows with a `page` block (SEC SoI; Oxford Ledge parse, ol-derived) |
| `get_bdc_list` | A | Active tracked BDCs with `totalFairValue` (arbitrated — read `fairValueBasis`), holding counts and filing dates (Oxford Ledge parse) |
| `get_bdc_holdings` | A | One BDC's full latest-filing portfolio: borrower, industry, security type, lien, rate, maturity, par/cost/fair value (USD) and mark (percent of par) per position, arbitrated totals (SEC SoI; Oxford Ledge parse) |
| `get_bdc_borrower_mark_history` | A | Multi-quarter fair-value mark history for one borrower across every BDC that holds its debt, newest quarter first (per-quarter min/max/par-weighted marks, holding-row and holder counts; SEC SoI; Oxford Ledge parse, ol-derived) |
| `ol_bdc_top_borrowers` | A | Borrowers syndicated across the MOST BDCs, ranked by lender count then exposure — the private-credit discovery entrypoint (SEC SoI; Oxford Ledge parse; free) |
| `ol_bdc_borrower_dispersion` | A | Cross-lender pricing dispersion for one borrower — how N BDCs each mark the SAME loan (`spread_bps` to compare on, marks, serve-time yields; SEC SoI; Oxford Ledge parse; free) |
| `ol_bdc_common_borrowers` | A | Borrowers common to a given set of BDCs — the cross-portfolio set question (SEC SoI; Oxford Ledge parse; free) |
| `ol_bdc_mark_changes` | A | Quarter-over-quarter mark moves across a set of BDCs, with an explicit `coverage` block (SEC SoI; Oxford Ledge parse) |
| `ol_bdc_credit_quality` | A | Non-accrual share and its trend for one BDC, withheld below 90% determinate coverage (SEC SoI; Oxford Ledge parse) |

### Federal reference data — FDIC / USAspending / USPTO (3 tools)

| Tool | Mode | Description |
|------|:-:|-------------|
| `ol_fdic_bank` | A | Active FDIC-insured banks and thrifts by name prefix or largest-asset (FDIC BankFind; $thousands). `ticker` is an Oxford Ledge CERT-to-ticker mapping, not an FDIC field |
| `ol_federal_contracts` | A | Federal-contract obligations by ticker, or the fiscal-year leaderboard (USAspending). Ticker attribution and per-ticker totals are an Oxford Ledge crosswalk; `dropped_unresolved` is an upper bound on its gap |
| `ol_patents` | A | Recent USPTO patent filings for a ticker's applicant (USPTO ODP; `ticker` is an Oxford Ledge applicant-name resolution) |

### Reference — Oxford Ledge (1 tool)

| Tool | Mode | Description |
|------|:-:|-------------|
| `get_value_investing_fact` | A | Buffett / Graham / Munger quotes and principles from Oxford Ledge's curated corpus, with citation (ol-authored) |

---

## What `_meta.basis` means

Every successful tool response carries a `_meta` block (`terms_url`,
`source`, `source_url`, `basis`, and when the payload says so `as_of` /
`period`; the 25 proxied tools also carry `source_key` and the host's
`disclaimer` -- the four standalone tools carry the not-advice literal at the
top level instead). An error envelope carries the error, not `_meta`. Where it comes from depends on how the tool reaches its
data, and all three paths share one vocabulary:

- the **16 name-proxied tools** (the 14 keyless `ol_*` / gov tools plus the two
  Plus-tier tools) pass the hosted server's `_meta` through verbatim;
- the **9 REST-proxied tools** carry the `_meta` the hosted route's provenance
  middleware attaches to that route (one source of truth with the hosted
  catalog, so the wheel and the hosted server cannot say two different things
  about the same payload). The two of them that RESHAPE the route's payload
  under their own keys — `get_holders` and `get_insider_trades` — translate
  the route's `derived_fields` paths into their own key names at the reshape
  (`trades[].value`, not the route's `transactions[].totalValue`; the route's
  QoQ paths that never ship on the wheel are dropped; the wheel's own
  `vintages` / `rankingBasis` / `transTypeLabel` / `is_open_market` are
  added), so the list is resolvable on the payload it rides;
- the **4 standalone tools** (`get_fundamentals`, `get_sec_filings`,
  `get_yield_curve`, `get_fred_data`) never touch Oxford Ledge, so the wheel
  attaches its own table — `{source, source_url, terms_url, basis: primary}` —
  at the dispatch seam, kept in vocabulary parity with the hosted provenance
  registry by a contract test in the main repo.

`basis` tells you WHOSE numbers you are reading. The six values, and what you
may conclude from the field alone:

| value | what it means | companions |
|---|---|---|
| `basis: primary` | every substantive value is the cited `source`'s, verbatim (a filing, an agency table, a FRED series) | -- |
| `basis: hybrid` | the cited source's values verbatim EXCEPT the fields listed in `derived_fields`, which are Oxford Ledge derivations (an entity attribution, a crosswalk sum, a classification flag). `source` still names the primary source: that is where the acknowledgment is owed and where the other values can be verified | `derived_fields` (paths in the tool's own key names; `[]` marks list rows, `.` a nested dict; a path may name a key only one branch of the tool emits) and `derived_basis` (today always `ol-derived`) -- both present iff `hybrid`, absent otherwise |
| `basis: ol-derived` | the payload is an Oxford Ledge computation OVER primary inputs (a tally, a screen, a cross-filer join, a compiled profile). `source` names the input. Do not quote it as the filer's or the agency's own figure | a tool that serves model-written or compiled prose labels it in-payload (`ai_generated` / `descriptionSource`): the text is not filing text |
| `basis: ol-authored` | Oxford Ledge wrote it (the value-investing corpus, glossary, methodology) | -- |
| `basis: vendor-derived` | computed by a data vendor, not by a filer and not by us | -- |
| `basis: aggregated` | a roll-up across sources (news) | -- |

A `hybrid` example, `ol_fdic_bank`: `institutions[].ticker` is our
CERT-to-ticker map; every other field is FDIC BankFind's. The tool
description says the same thing in prose (`ATTRIBUTION: ...`), because a
reader of `tools/list` needs it before calling; the field says it on the
payload, because the payload is the only channel a machine consumer reads.

## Data sources

28 of the 29 tools are backed by **U.S.-government public data** — SEC EDGAR, FRED, U.S. Treasury, FDIC, USAspending, USPTO or CFTC; the 29th, `get_value_investing_fact`, is Oxford Ledge-authored (`basis: ol-authored`, attributed quotations with `author` / `source` on every row). **Nothing in this package scrapes Yahoo Finance** (the 1.x / 2.0.0 yfinance path was removed in the 2.0.1 Y1 excision), and as of **3.0.0** there is **no commercial-vendor feed anywhere in the surface** (the FMP/Finnhub-backed quote/estimate/screen/news tools were removed — they live on the hosted Oxford Ledge MCP server). As of **3.1.0** the FINRA-sourced tools were also removed: bond search + CUSIP lookup (`search_bonds`/`get_bond_data`) disseminated FactSet-licensed CUSIPs, and `get_short_interest` was an advertised stub with unresolved float-lineage + attribution. FINRA data now lives only on the hosted server — and the TRACE half of it is gone there too: FINRA auth-walled its public TRACE hosts in 2026-07 and Oxford Ledge holds no licence to redistribute TRACE data, so the hosted `search_bonds` / `get_bond_data` were RETIRED on 2026-09-13 (they answer `status: "retired"`, never data); hosted corporate-bond discovery is `ol_bond_directory_screen`, a persisted LQD/HYG directory with no prices, and the hosted short-interest tools (FINRA's biweekly series) are unaffected. **In 3.4.0 one leak the full audit found is re-closed:** from 3.1.0 through 3.3.0, `get_debt_maturities` and `get_capital_allocation` proxied two REST routes that could fall back to a Finnhub-fed capital-structure snapshot and a modelled maturity ladder; in 3.4.0 both tools are name-proxies of the hosted EDGAR-only tools, and the surface is vendor-free again.

- **SEC EDGAR** — XBRL fundamentals (`get_fundamentals`) and any-form EDGAR submission lists (`get_sec_filings`) are fetched directly from EDGAR by the pip package (keyless). Insider Form 4 (`get_insider_trades`), 13F holdings (`get_13f_holdings` / `get_holders`), 8-K events (`get_corporate_events`) and BDC Schedule-of-Investments parses route through `OXFORD_LEDGE_URL` (API mode) against Oxford Ledge's EDGAR-backed tables; the capital-allocation scorecard and the debt-maturity ladder are the hosted EDGAR-XBRL / 10-K-footnote tools, proxied by name.
- **FRED / U.S. Treasury** — Treasury yield curve + FRED series, fetched directly, verbatim (`basis: primary`, nothing derived). **Requires `FRED_API_KEY`** (`get_yield_curve` / `get_fred_data` error out without it). `get_fred_data` serves U.S.-government / public-domain series only — third-party-copyright series (S&P, ICE BofA, Moody's, CBOE, University of Michigan) are refused fail-closed.
- **FDIC / USAspending / USPTO / CFTC** — BankFind institution records, federal-contract obligations, patent filings and Commitments-of-Traders positioning, all routed through `OXFORD_LEDGE_URL`. **All four are `basis: hybrid`** and say so in their descriptions (`ATTRIBUTION: ...`) and in `_meta.derived_fields`: `ol_fdic_bank` — `institutions[].ticker` is our verified CERT-to-ticker map (one path); `ol_federal_contracts` — the ticker attribution, the per-ticker `total_obligations_usd` and `entity_count` sums and `dropped_unresolved` are our crosswalk, on both the ticker and the leaderboard branches (eight paths; `dropped_unresolved` is an upper bound on the crosswalk's gap, not a count of missed subsidiaries); `ol_patents` — `filings[].ticker` is our applicant-name resolution (one path); `ol_cftc_cot` — `rows[].market_key` and `rows[].market_label` are our curated market catalog and `rows[].mm_net` is our `mm_long − mm_short` (three paths). Every other field in those payloads is the agency's, verbatim.
- **Oxford Ledge proprietary parses** — BDC holdings (54 BDCs, 9K+ borrowers, from SEC SoI filings) + the curated value-investing corpus. API mode only; their payloads say `ol-derived` / `hybrid` / `ol-authored` in `_meta.basis`, and their descriptions say it in prose.

---

## Data license

The MIT license below covers the **software** in this package. The **data** the
tools return is governed by the Oxford Ledge terms of service
(https://www.oxfordledge.com/terms), which every payload links in
`_meta.terms_url`. The operative sentences, quoted:

- **Attribution (section 5b):** "Values derived by Oxford Ledge must be
  attributed to Oxford Ledge (oxfordledge.com) when restated to an end user.
  This applies whether the value reaches the end user as a number, a chart, or
  prose an agent has written around it. The underlying public filings (SEC
  EDGAR, U.S. Treasury and similar U.S. government sources) are public records
  and carry no such requirement; the obligation attaches to **our** derived
  layer — our parses of business-development-company Schedules of Investments,
  our borrower normalization and loan-identity keying, our dispersion and
  pricing aggregates, and our computed model outputs." In this package that is
  exactly what `_meta.basis` of `ol-derived`, `hybrid` (the `derived_fields`
  paths) or `ol-authored` marks; `basis: primary` payloads are the agency's
  public records.
- **No bulk extraction (section 5b):** "You may not use the agent interfaces
  to systematically enumerate, download, or reconstruct the Oxford Ledge corpus
  or any substantial part of it, to build a competing or substitute dataset, or
  to resell or redistribute our derived values as a data product. Per-query and
  per-entity research use is exactly what these interfaces are for; corpus
  reconstruction is not."
- **Personal and internal use (section 8):** "Data obtained through Oxford
  Ledge is licensed for personal and internal use only. You may not
  redistribute, resell, republish, sublicense, or make available to third
  parties any data, datasets, or content obtained from the Service, whether in
  raw, aggregated, or derived form, without prior written permission from
  Oxford Ledge."

---

## Resource limits this client enforces on itself

These are properties of the CLIENT, not of any server. They exist because a
desktop MCP client holds whatever a host sends in the memory of the process
your editor launched, and because `OXFORD_LEDGE_URL` is operator-supplied.

- **Response size.** A success body over its host's ceiling is refused before
  it is read in full: nothing is parsed, served or cached, and the refusal
  names the ceiling so you can tell it from an outage. The ceilings are per
  host -- 8 MB for the Oxford Ledge instance you configure, 32 MB for SEC
  XBRL companyfacts (a large filer's document legitimately exceeds 8 MB),
  16 MB for SEC submissions, 8 MB for SEC's ticker map, 16 MB for FRED.
- **Cache size.** Tool results are cached in-process for the tool's TTL,
  under TWO budgets: at most 500 entries, and at most 32 MB of aggregate
  serialized payload. When the total would exceed the byte budget the
  earliest-expiring entries are dropped; a single result too large for the
  budget is simply not cached, and the call still returns normally. A cache
  miss is never an error. Both budgets are per process, and the cache is not
  shared between processes.
- **Response nesting.** A response nested deeper than roughly 500 levels is
  refused with a message saying so, rather than served. This is the depth at
  which the copy that keeps one caller's result from mutating another's stops
  being safe; real Oxford Ledge and SEC documents are a handful of levels
  deep.

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

MIT (the software). The data is licensed separately — see [Data license](#data-license) above.


## Verify your install

After (re)starting your MCP client, check the server handshake: the client
shows the server as `oxford-ledge-mcp <version>` on connect (in Claude
Desktop: Settings → Developer → oxford-ledge). **If the version is older
than the one you installed, the client is still running a previous
install** — see the first troubleshooting entry below.

## Troubleshooting

Real friction seen in the field — each with the fix that worked:

- **`pip install --upgrade` fails with `WinError 32` (file in use)** —
  the running MCP server processes hold `oxford-ledge-mcp.exe`. Quit your
  MCP client (Claude Desktop) fully, or kill the `oxford-ledge-mcp`
  processes, then re-run the upgrade.
- **A `~xford-ledge-mcp` directory appears in site-packages** — residue
  from an interrupted upgrade (the `WinError 32` case above). Safe to
  delete after the upgrade succeeds.
- **`oxford-ledge-mcp` not found after install** — pip printed a PATH
  warning during install. Either add the named Scripts directory to PATH,
  or put the **full path** to the executable in the `command` field of
  your client config.
- **Handshake shows an old version** — the client cached the old process.
  Quit the client fully and restart it. `uvx` users: the uvx environment
  cache can pin an old version — refresh it (`uvx --refresh
  oxford-ledge-mcp`) or pin the version explicitly.
- **A tool answers `NOT_FOUND: unknown tool`** — your installed package
  is newer than the hosted server or vice versa (version skew). Check the
  handshake version against this README's, and upgrade the older side.
