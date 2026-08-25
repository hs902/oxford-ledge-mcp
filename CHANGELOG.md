# Changelog

All notable changes to `oxford-ledge-mcp` are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 3.2.0 (2026-08-24)

Publish-vet-driven release (CISO+COUNSEL+CHAOS delta vet + the L-5
disclosure CYCLE, both OWNER-ratified; artifacts in the main repo under
docs/board/audit/2026-08-24_*). Everything below is wheel-shipping;
in-tree-only work is deliberately not credited here.

### Fixed

- `get_fundamentals` OperatingCashFlow named a us-gaap concept that does
  not exist (`NetCashProvidedByOperatingActivities` -- SEC 404s it), so
  the field was silently absent on every call since it shipped. The
  ladder now uses `NetCashProvidedByUsedInOperatingActivities` plus the
  continuing-operations variant, both live-verified against SEC
  companyconcept (134 + 30 facts on AAPL).
- A second never-matching rung removed: `InvestmentIncomeOperating`
  (BDC revenue) has zero filers in SEC frames CY2015+CY2023;
  `GrossInvestmentIncomeOperating` (182 filers CY2023) carries BDC
  revenue. The full concept ladder is now pinned against a reviewed,
  evidence-backed set.
- `get_yield_curve` declared `include_history` and never read it; the
  parameter is now honoured. New response keys: `as_of` (per maturity),
  `yield_curve_1y_ago` (present-even-when-empty so "applied and found
  nothing" is distinguishable from "ignored"), `history_coverage`.
- A 404 from a correctly-routed call whose filter matched nothing was
  reported as a client/server version mismatch, steering agents away
  from the one correct recovery (change the argument). The error path
  now discriminates on the response envelope -- and parses the full
  body, so large envelopes cannot regress it.
- Auth errors named credentials in a way that led consuming agents to
  ask their human to paste a key into the chat; every credential message
  now names the operator + config as the source and forbids in-chat
  solicitation.
- `get_holders` / `get_insider_trades` read response keys the API never
  emits; field chains now lead with the wire aliases actually served.
- `get_value_investing_fact` promised an `available_categories` recovery
  the API does not provide (removed) and declared a `query` parameter
  the handler never read (removed). The documented category vocabulary
  is now exactly the seven real values.
- FRED error text can no longer embed the caller's own `api_key=`
  (redacted before any exception message is emitted).

### Added

- Fail-closed per-tool emit allowlists at the redistribution boundary
  (`oxford_ledge_mcp_core/emit_allowlist.py`): an unrecognized field is
  dropped and a tool with no allowlist is refused with a structured
  INTERNAL_ERROR, replacing the fail-open denylist for the raw
  passthrough tools. `get_13f_holdings` keeps its full dating/identity
  envelope (fund name, filing date, period of report, totals) and the
  quarter-over-quarter changes tree; CUSIP remains excluded.
- A not-advice disclosure: `## Disclaimer` in this README and a
  server-level `instructions` string sent once at initialize on both
  protocol paths (guarded on older `mcp` SDKs).

### Changed

- `oxford_ledge_mcp_core/tool_partition.py` no longer ships in the
  wheel -- it was internal dead code (nothing in the package imports
  it). No public API change.

## 3.1.1 (2026-08-10)

Field-test-driven correctness release (2026-08-10 Desktop field tests #1/#2;
vet: docs/board/audit/2026-08-10_CISO_COUNSEL_CHAOS_mcp_publish_vet.md in the
main repo).

### Fixed

- Three API-mode tools called endpoints that never existed and 404'd on
  every call: `get_holders` -> `/api/institutional-holders`,
  `get_corporate_events` -> `/api/company/events` (param `type`),
  `search_bdc_borrower` -> `/api/bdc/borrower`.
- `get_13f_holdings` sent `fund=` to a cik-only route (400 every call);
  now sends `cik=`, and the input schema says CIK only.
- `get_insider_trades` read keys the wire never emits; field chains now
  lead with `insiderName` / `transactionType`.
- `get_sec_filings` silently defaulted to 10-K when no type was given;
  absent type now means all forms.
- serverInfo reported a stale hardcoded version; it now reports
  `__version__` on BOTH protocol paths (the mcp-SDK path previously
  reported the SDK library's own version).
- Startup banner version literal replaced with `__version__`.
- The heavy-tool concurrency limit was dead code (a local shadow set was
  never populated); the core registry's set is now used.

### Added

- `__main__.py` -- `python -m oxford_ledge_mcp` now works.
- `ToolError.NOT_FOUND`: a 404 on an endpoint path is reported as a
  client/server version mismatch, never as "data unavailable".

### Changed

- The optional `mcp` extra is pinned `>=1.0.0,<2` -- the mcp 2.0 major
  removed the low-level Server API this package uses (crash under uv).
- PyPI `Documentation` URL now points at https://www.oxfordledge.com/mcp.

## 3.1.0 (2026-07-21)

This release is a **third-party-IP compliance sweep** vetted by the CHAOS +
DATA_CZAR + COUNSEL personas. The 3.0.x "gov-public-data-only" claim had three
leaks (CUSIP dissemination, a fail-*open* FRED filter, and a vendor-lineage
reference tool) plus one advertised stub; all four are closed here.

### Removed (breaking) — CUSIP + FINRA-attribution carve-out
- **`search_bonds` and `get_bond_data` removed.** These disseminate bond **CUSIPs**,
  which are FactSet / CUSIP Global Services intellectual property — a third-party
  carve-out *within* FINRA data that requires a direct CUSIP license for commercial
  redistribution. (The FINRA TRACE aggregate itself is redistributable with
  attribution; the CUSIP field is not.)
- **`get_short_interest` removed.** It was an advertised stub with unresolved
  float-lineage and no FINRA attribution surface — it could not be shipped as a
  clean-core FINRA tool without a redistribution-license and attribution review, so
  it is retired from the pip package rather than shipped half-built.
- All three remain available via the **hosted Oxford Ledge MCP server**; pin
  `oxford-ledge-mcp==3.0.1` if you need them. Package now exposes **13 tools**
  (2 keyless SEC + 2 FRED standalone + 9 SEC/gov via `OXFORD_LEDGE_URL`).

### Changed — third-party-field stripping on retained tools
- **`get_13f_holdings` and `get_corporate_events` now strip CUSIPs and credit ratings**
  from their payloads before returning. 13F and 8-K parses can carry the same
  FactSet-licensed CUSIP (and agency-licensed rating) fields the bond tools were removed
  for; a recursive key-strip (`cusip`, `moodys_rating`, `sp_rating`, `fitch_rating`,
  `credit_rating`, …) keeps the retained tools' output free of third-party-licensed
  identifiers while preserving the SEC-sourced ownership/event data.
- **`get_value_investing_fact` repointed off a vendor endpoint.** It was mis-wired to a
  random-ticker profile endpoint that returned vendor-computed marketCap/sector fields;
  it now calls the curated public value-investing corpus (`/api/value-investing/random`),
  matching its documented purpose (Buffett / Graham / Munger principles) with no vendor
  data in the response.

### Changed — third-party FRED-series carve-out (now fail-**closed**)
- `get_fred_data` now **refuses FRED series that carry third-party (non-U.S.-government)
  copyright** — series sourced from private commercial providers (S&P Dow Jones Indices,
  ICE BofA, Moody's, CBOE, Nasdaq OMX, FTSE/Russell, MSCI, Bloomberg, …) that FRED
  licenses for non-commercial use only. FRED's documented tell (the series `notes`/`title`
  metadata matches a copyright/provider pattern) is checked against live `/fred/series`
  metadata at call time. The filter is **fail-closed**: a series whose metadata is empty
  or unresolvable is refused, and only *authoritative* verdicts are cached (a
  probe-failure guess is never cached, so it can't poison later calls). A U.S.-government
  prefix allowlist (BLS / BEA / Census / Federal Reserve / Treasury families) is the
  only fast-path accept. This closes the 3.0.0 fail-*open* gap where Moody's (DAAA/BAA),
  Case-Shiller-metro, and CBOE-family series slipped through on a probe failure. No tool
  added or removed by this change.

## 3.0.1 (2026-07-21)

### Changed (packaging only — no tool/behavior change)
- Adopted the PEP 639 license metadata: `license = "MIT"` (SPDX expression) +
  `license-files = ["LICENSE"]`, replacing the deprecated `license = {text = "MIT"}`
  table and the `License :: OSI Approved :: MIT License` trove classifier (both slated
  for removal by setuptools 2027-Feb-18). Build requirement bumped to
  `setuptools>=77.0.0` (needed for the SPDX form). No change to any tool, arg schema,
  or runtime behavior.

## 3.0.0 (2026-07-21)

### Removed (breaking) — gov-public-data-only surface
- **13 vendor-data-lineage tools removed** so the entire package surface is backed
  ONLY by public data (SEC EDGAR / FRED / U.S. Treasury / FINRA TRACE) — no
  commercial-vendor (FMP/Finnhub/options-vendor) feed anywhere:
  `get_stock_quote`, `get_financials`, `get_balance_sheet`, `get_cash_flow`,
  `get_analyst_recommendations`, `get_company_info`, `compare_stocks`,
  `screen_stocks`, `get_anomaly_flags`, `get_options_chain`, `get_economic_calendar`,
  `get_news`, `search_company`.
  These remain available via the **hosted Oxford Ledge MCP server**. Removing public
  tools is backward-incompatible → major version. **`2.1.0` remains installable** —
  pin `oxford-ledge-mcp==2.1.0` if you depend on any of the above. See `MIGRATING.md`.
- Package now exposes **16 tools** (6 keyless-standalone + 10 SEC/gov via
  `OXFORD_LEDGE_URL`). Description tool count corrected `29 → 16`.

### Changed
- A call to any removed tool returns a **structured migration pointer** (naming the
  SEC-XBRL / FRED replacement or the hosted server), not a bare `Unknown tool`.

### Unchanged
- Every surviving tool keeps its arg names, return shapes, and MCP wire format.
  Ticker-normalization behavior (`normalize_ticker`) is preserved.

## 2.1.0 (2026-07-21)

### Removed (breaking)
- **7 vendor-data-lineage tools** removed so the package's default tool
  surface is free of commercial-vendor data lineage (a redistributability
  tightening — the removed tools proxied FMP/Finnhub-derived data and have
  no distributable source):
  `calculate_intrinsic_value`, `get_company_data`, `get_company_profile`,
  `get_market_indicators`, `get_peer_comparison`, `get_price_history`,
  `get_valuation_history`.
  Removing public tools is backward-incompatible. **`2.0.4` remains
  installable on PyPI** — if you depend on any of the above, pin
  `oxford-ledge-mcp==2.0.4`. See `MIGRATING.md` for replacements.

### Changed
- Calling a removed tool now returns a **structured migration pointer**
  (naming the SEC-XBRL / hosted replacement) instead of a bare
  `Unknown tool: <name>` — so an agent can self-correct.
- Package metadata: the description's tool count is corrected `36 → 29`
  (the live `tools/list` surface), and the `Repository` URL now points at
  the public `github.com/hs902/oxford-ledge-mcp` (was the private monorepo).

### Unchanged
- The `2.0.4` ticker-normalization behavior (`normalize_ticker`) is
  preserved on every surviving tool — a missing/`null` `ticker` still
  surfaces as a structured `ToolError`, never a raw `KeyError`.
- All surviving tools keep their arg names, return shapes, and MCP wire
  format.

## 2.0.4 (2026-05-27)

### Added
- `oxford_ledge_mcp_core.ticker.normalize_ticker(symbol)` helper —
  stdlib-only ticker canonicalization (uppercase + whitespace strip).
  Exported from `oxford_ledge_mcp_core` for downstream callers.
- `min_tier="plus"` markings on five premium analytics tools to mirror
  the in-tree per-tool tier table: `get_options_chain`,
  `get_debt_maturities`, `get_capital_allocation`, `get_13f_holdings`,
  `get_valuation_history`. Standalone stdio mode is unaffected (no
  user-account context); API mode (`OXFORD_LEDGE_URL` set) enforces
  tier server-side as before — observable behavior is unchanged for
  current users.

### Changed
- F5 ticker-normalization callsite sweep across `oxford_ledge_mcp/
  server.py`: replaced inline `args["ticker"].upper().strip()` (and the
  multi-ticker `args["tickers"].split(",")` comprehension) with
  `normalize_ticker(args.get("ticker"))`. All tool input/output
  contracts (arg names, return shapes, MCP tool wire format) are
  unchanged.
- **Improved error message** for missing-`ticker` inputs. Previously a
  request omitting the required `ticker` arg surfaced as a bare
  `KeyError: 'ticker'` (`ToolError.UNKNOWN`). It now reaches the
  existing empty-string validators and surfaces as a structured
  `ToolError` with a friendly message. This is the only observable
  behavior change in 2.0.4 and is strictly improving.

### Fixed
- README install instruction typo: `pip install oxfordledge-mcp` →
  `pip install oxford-ledge-mcp` (matches `pyproject.toml` package
  name; the typo had no functional impact since the typo'd name does
  not resolve on PyPI).
- Version drift: `oxford_ledge_mcp/__init__.py` `__version__` now
  matches `pyproject.toml` `version`.

## 2.0.3 (prior release)

- Initial public release per `git log`.
