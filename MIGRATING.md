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

## 3.6.0 — the 13F superseded-parent fold on `get_holders` (additive), one value correction, one config shorthand

**Tool names and argument schemas are unchanged; no key is renamed or
removed.** Almost everything here is a NEW key on `get_holders`; the two
exceptions are stated first so nobody has to find them. (1) `completeness.complete`
on `get_holders` now reads `false` whenever the fold withheld anything -- it used
to answer only "was every fetched row returned", which was `true` beside a
non-empty `superseded_parents`. A consumer that gated on `complete` will see
`false` more often, and `supersededWithheldTotal` beside it says how much was
withheld. (2) Config: the plaintext-key loopback exemption is an ADDRESS check,
so `OXFORD_LEDGE_URL=http://127.1:...` with an API key set is now refused; write
`http://127.0.0.1:...`. Every other `127.x.y.z`, `[::1]` and literal `localhost`
still pass. An installed 3.5.0
keeps working against the deployed host: its fail-closed emit allowlist
STRIPS every key below, so a 3.5.0 reader sees the 3.5.0 wire minus nothing it
already had. Upgrade to see them.

This section exists because the CHANGELOG's `## Unreleased` said the cut
changed no tool's served keys, and it changed nine. The delta vet's K-1 / C-3
is that a release record which denies its own largest wire change is worse
than one that is merely terse.

### `get_holders`: `stale_quarters` / `ahead_quarters` on each row

`stale_quarters` is the row's distance in quarters from the payload's as-of
anchor (`coverage.quarter`), 0 = current. It is **ABSENT, never 0**, when the
row could not be dated -- a fabricated 0 would turn "could not be dated" into
"current". `ahead_quarters` (>= 1, absent otherwise) marks a row struck NEWER
than the anchor; such a row keeps `stale_quarters` 0, so without this key it is
indistinguishable from a row AT the anchor. Both are range-guarded on the
wheel: a value outside the stated range is DROPPED, never clamped.

### `get_holders`: `superseded_parents` (top level) and `fund_cik` on every row

The host withholds a stale filer row from `holders` when its shares reconcile
within 1% to same-quarter siblings of its own fund-name family (the Vanguard
double count). The withheld rows now ride in `superseded_parents`, in the same
shape as a served row, plus:

- `superseded` -- the producer's own verdict, carried through, never
  synthesised;
- `superseded_by` -- the `fund_cik`s of the rows that supersede it. Every
  served row now carries `fund_cik` too, so the reference resolves inside the
  same payload whenever the superseding row survived the top-10 cut;
- `superseded_by_shares` + `reconciled_pct` -- BOTH operands of the
  reconciliation beside the row's own `shares`, so the verdict states its
  arithmetic instead of asserting it. `reconciled_pct` is a percentage of the
  withheld row's own `shares`;
- `unstated` -- present only when the producer did not state one of those
  parts in a usable form. The part is dropped rather than faked and this key
  names it. Read such a row as a withholding whose arithmetic or attribution
  is missing, never as a reconciled one.

`completeness.supersededReturned` / `completeness.supersededWithheldTotal`
disclose the cut: `superseded_parents` is capped at 10 exactly like `holders`.

**`[]` is not an all-clear.** It means the fold ran and withheld nothing
*among the rows it could date*. A row carrying no `stale_quarters` was never
eligible to be folded and is served in full beside its current sibling, so an
`[]` beside undated rows is a blind pass; the wire cannot distinguish the two.
The key is ABSENT only when the producer sent no fold at all.

- `also_in_holders` -- present only when this withheld row is ALSO in the
  served `holders` list. The two lists are built independently, so nothing
  stopped a filer appearing in both; for such a row the fold did NOT remove
  the double count, and the instruction below is inert because the row is
  already in the table. The row is annotated rather than dropped: the
  disagreement is the producer's, and the reader is the one who can act on it.

`completeness.complete` is **`false` whenever anything was withheld.** It
answers "is this every filer", and the fold reduced the list before this
client saw it -- it previously read `true` because it was really answering
"was every FETCHED row returned", and the withheld rows never reach the fetch.

An EMPTY `holders` list beside a non-empty `superseded_parents` now carries a
DIFFERENT `note`: it says the producer returned rows and the fold withheld
every one of them. The scope note ("13F-HR COM positions, last 6 quarters...")
would have sent a reader looking for a coverage gap when the answer is in the
next key.

A `superseded_parents` that arrives as something other than a list (a dict, a
string, an explicit `null`) is now marked with a top-level
`unstated: ["superseded_parents"]` instead of being dropped to key-absent --
dropping it rendered a BROKEN producer identical to a host that never folded,
erasing the one distinction (`absent` vs `[]`) the design exists to preserve.
Treat it as "the fold did not run", never as "the fold withheld nothing".

**Do NOT add these rows back into `holders` or into any total** -- that
restores the double count the fold removes. The one case where that
instruction cannot help you is the `also_in_holders` row above; there, the
double count is already in `holders` and the flag is the only thing that says
so.

### `search_bdc_borrower`: the `descriptionSource` prose (no value change)

The description now enumerates all five `descriptionSource` values, names the
three that suppress the AI-generated flag, and states that `manual` is the
store's DEFAULT and therefore not an attestation of a human author. No served
value changes; the label is decided producer-side for every channel.

## 3.5.0 — additive wire changes and one value correction (the delta vet)

**Tool names, argument schemas and config are unchanged; no key is renamed
or removed.** Everything here is a new key, a new optional argument, or a
VALUE correction inside a key that already existed. An installed 3.4.0
keeps working against the deployed host: its fail-closed emit allowlist
STRIPS every new key listed below (so a 3.4.0 reader sees the 3.4.0 wire,
minus nothing it already had), and only the value corrections reach it.
Upgrade to see the keys.

### `get_fundamentals`: `basis.basisConsistent` is a tri-state (value change)

`true` used to be served beside a populated `basisAdvisory` -- the advisory
tier fires on an implied-share jump with no issuer refiling to corroborate
it, and a field named "consistent" answering `true` on a measured 3.8x
discontinuity read as a certification. It is now `null` in that case, the
same value the unexamined branch already used (`basisChecked: false`), with
`basisNote` saying which case it is. `true` still means examined and clean;
`false` still means a corroborated break that withheld cells
(`basis.gapBreaks` / `basis.gapNote` unchanged). A consumer that treated
`basisConsistent !== false` as "certified single-basis" must treat `null`
as "not certified" -- which is what the advisory always meant.

### `search_bdc_borrower`: `limit` / `offset` (additive) and the ambiguous ladder

- `limit` (1..5000) and `offset` (0..5000) are new OPTIONAL integer
  arguments on the inputSchema. A call declaring NEITHER is byte-for-byte
  the 3.4.0 wire (every `holders` row up to the host store's 5000-row
  backstop; no `page`, no `completeness`). A call declaring either slices
  ONLY `holders` -- every aggregate, `holdingRowCount`, `priceHistory` and
  the relatedNorms disclosure stay computed over all rows -- and carries
  `page` {limit, offset, returned, total, hasMore} plus a `completeness`
  block with `total_available`. Out-of-range values are REFUSED as
  INVALID_PARAMS on both transports, never clamped; an offset past the end
  is an honest empty page with `total` intact. Omit the argument rather
  than sending an explicit `null` (the wheel refuses `null` for an
  integer; the hosted catalog treats it as unset -- a known divergence,
  tracked).
- The ambiguous `matches[]` rows carry `totalFvBasis`
  (`current_holders_only`) and, when a candidate has stored rows but no
  current holder, `totalFv: null` + `totalFvRefusalReason` instead of a
  `0.0` summed over an empty partition. The sentence is about Oxford
  Ledge's parsed store ("no CURRENT holder in Oxford Ledge's parsed store
  ..."), never a claim about what any BDC filed. `relatedNormsStale` lists
  prefix siblings with zero current holders on a resolved hit.

### `get_insider_trades` / `ol_insider_recent_buys`: the 4/A fold (row count + four keys)

A Form 4 and its 4/A that report the same line are served ONCE (the
amendment), so a 3.4.0 consumer sees FEWER `trades` rows on deploy
(host-side fold; a value change it receives). The four keys that explain
the fold -- `isAmendment`, `accessionNumber`, `supersedesAccession`,
`formType` -- are new on every row and reach only 3.5.0. `null` in
`formType` means the store holds no form type for the row; it is served,
not dropped. `totalValue` is rounded to cents at ingest.

### `ol_cftc_cot`: `matched_market` / `candidates` / `markets_available` (additive)

(2026-09-14, from the 2026-09-13 professional-persona audit.) The `market`
argument is normalised by the hosted resolver -- case-folded, punctuation
stripped, desk aliases (`CL` / `WTI` / `crude` -> `crude_oil`, `ES` / `SPX`
/ `S&P` -> `sp500`, `GC` / `XAU` -> `gold`), substring match on the stored
keys and labels -- and the wheel's emit allowlist admits the resolver's keys:
`matched_market` (which curated key answered; null on the all-market
snapshot), `candidates` (up to five nearest stored names on a miss) and
`markets_available`. Before this the description said the keys were
case-sensitive and a miss reached you as a bare `{error, rows: []}`.
Additive; no key renamed.

### `get_13f_holdings`: which side resolves a filer NAME (prose, no wire change)

The hosted server's tool resolves a filer NAME to a CIK since 2026-09-13
(`resolved_from` on its payload). THIS package does not -- its handler
proxies the CIK-keyed route and refuses a name as INVALID_PARAMS, unchanged
-- and the description now says which side does what instead of copying
the hosted sentence.

### Coverage and basis keys the hosted server added on 2026-09-13 (additive, wave G)

Each of these is a new key beside an unchanged payload; 3.5.0's allowlist
admits them, 3.4.0's strips them:

- `get_corporate_events`: `coverage` {rows_stored, oldest_event_date,
  newest_event_date} + `summary`; an unreachable store answers
  DATA_UNAVAILABLE (the host's 503, passed through) instead of `events: []`.
- `ol_fdic_bank`: `coverage` {institutions_loaded, active_loaded,
  inactive_loaded, newest_repdte, last_loaded_at, ingest_scope} + `as_of`.
- `get_fails_to_deliver`: `coverage` {window_end, days_covered,
  days_before_earliest, days_after_latest, files_expected, files_missing,
  window_postdates_coverage}.
- `get_bdc_holdings`: `parseQuality` + `parseQualityNote` +
  `portfolioStructureBasis`.
- `ol_bdc_borrower_dispersion`: `maturity_date_precision` +
  `margin_suppressed_note`.
- `get_activist_stakes`: `stale_basis` (tri-state `stale`), per-row
  `reports_zero` + `unparsed`.
- `ol_federal_contracts`: per-row `period_complete` / `days_elapsed` /
  `days_in_period` + payload `as_of`.
- `ol_bdc_credit_quality`: `coverage_state` (`none_parsed` | `partial` |
  `covered`) on `latest` and on each trend row -- and the headline
  non-accrual number itself, which an XBRL-path filer had never returned
  (a value change a 3.4.0 install also receives).

### The key pointer

Every sentence that tells an operator where an API key is created now
says `https://www.oxfordledge.com/?panel=api-keys` (the deep link that
opens the keys panel for a signed-in user; in-app: press K, or the key
icon in the bottom bar). 3.4.0 said `/?view=settings`, which still
resolves.

## 3.4.0 — four wire changes (the full 29-tool publish vet)

**Tool names and config are unchanged; four argument schemas tighten.** Four
payloads change shape or key names; each is a case where the old wire said
something that was not true, so a consumer that keyed on the old name was
keying on a false label. Everything else in 3.4.0 is additive (new keys, new
`_meta`, new notes on empty results) or an error-path correction.

### Four count arguments are `integer`, not `number` (schema tightening)

`get_13f_holdings.max_holdings`, `ol_bdc_common_borrowers.min_holders`,
`ol_bdc_common_borrowers.limit` and `ol_bdc_mark_changes.limit` were declared
`number`, so `2.9` conformed, was truncated by the handler, and `_meta.
params_accepted` echoed the fraction as accepted (2026-09-13 DELTA re-vet
CHAOS-4). They are `integer` now on both the wheel and the hosted catalog:
`2.9` is refused as INVALID_PARAMS naming the argument; `25`, `25.0` and the
integral string `"25"` still pass. A client that sent a fraction was never
getting what it asked for.

### `get_fundamentals`: `TotalDebt` -> `LongTermDebt` (key rename)

The series under `data.TotalDebt` was always `us-gaap:LongTermDebt` with an
unlabelled `LongTermDebtNoncurrent` fallback -- commercial paper, short-term
borrowings and, in fallback years, the current portion were never in it. The
key now says what the value is: `data.LongTermDebt`. There is no `TotalDebt`
key any more and no total-debt series (building one is a separate, later
feature). Also new and additive: a top-level `concepts` that mirrors `data`
-- for EVERY served label a list `[{period, concept}]` index-aligned with
`data[label]` (plus a `conceptsNote`) -- and `basis.attribution`. A consumer reading `data.TotalDebt` must
read `data.LongTermDebt` and must stop calling it total debt.

### `get_debt_maturities` / `get_capital_allocation`: the hosted shapes

Both tools are now name-proxies of the hosted EDGAR-only tools instead of
proxies of two REST routes. The wire changes from the route shapes to the
shapes the descriptions always advertised:

- `get_debt_maturities`: was `{ticker, totalDebt, schedule:[{year, amount}],
  source, confidence}` with `amount` in whole DOLLARS and `source` possibly
  `finnhub-estimate` (a modelled 15/15/12/12/46% ladder from vendor debt
  totals). Now `{ticker, maturities:[{year, amount}], thereafter,
  confidence, confidence_score, source, validation}` with amounts in
  MILLIONS of USD, `source` = `table` | `regex` | null (parser method), and a
  `validation` block cross-checking the ladder against the balance sheet. No
  vendor branch exists. A consumer that multiplied nothing must now multiply
  by 1e6 to get dollars; a consumer that read `schedule` must read
  `maturities` + `thereafter`.
- `get_capital_allocation`: was `{ticker, layers:[{layer, amount,
  percentage}]}` (a Finnhub-fed capital-STRUCTURE snapshot, and empty with an
  `error` on every real call). Now `{ticker, capitalAllocation:{years,
  dividends, netBuybacks, netDebtChange, acquisitions, sharesOut, isDilutive,
  summary}}` -- parallel arrays newest-first, whole USD, the NET series being
  Oxford Ledge derivations (`_meta.basis: hybrid`). Nothing in the old shape
  survives.

Both remain Plus-tier. The refusal is still `AUTH_REQUIRED`, but its sentence
changed (deep audit 2026-09-13): keyless, it names the tier, says the client is
anonymous and tells the operator where `OXFORD_LEDGE_API_KEY` is set; with a
valid key on a plan below Plus it says THE KEY IS VALID and the plan is what
is missing (it used to read the code word `tier_required` followed by the
"do not paste a key" warning). A consumer that string-matched
`tier_required` in the message must key on the `AUTH_REQUIRED` code instead.

### `get_corporate_events`: `events[].id` removed

The corporate_events SERIAL row id no longer ships (the same row-id class
stripped from the insider tools). Nothing in the wheel or the description
ever consumed it; key on `sourceUrl` + `eventDate` + `eventType` instead.

### `get_insider_trades`: `dateBasis` now names the date `date` carries

`date` is unchanged (the filing date when the filing carries one). `dateBasis`
used to say `transaction` whenever a transaction date existed -- which was
every normal row, while `date` was the filing date -- so the label contradicted
the value on every row. It now says `filing` when `date` is `filingDate` and
`transaction` only when no filing date exists. A consumer that branched on
`dateBasis == "transaction"` to mean "`date` is the trade date" was wrong
before and is now told so; read `transactionDate` for the trade date. Rows
also gain `securityTitle` and `isDerivative` (additive), and `pricePerShare`
is no longer rounded to cents.

### Additive changes from the 2026-09-13 deep audit (no key renamed)

Each of these is a case where the wheel served fewer rows, a blank, or a
label it could not stand behind; none renames or removes a key.

- `get_insider_trades` serves the route's full 20-row window (it served
  the newest 15 of the 20 while the description said 20). `completeness`
  keeps its meaning: `complete` is null when the window came back full.
- `get_holders` / `get_insider_trades`: `_meta.derived_fields` now names
  the WHEEL's key paths (`trades[].value`, `trades[].position`,
  `trades[].transTypeLabel`, `trades[].is_open_market`; `vintages`,
  `rankingBasis`) instead of the route's (`transactions[].totalValue`,
  `holders[].change_type` ... -- keys that never existed on the wheel's
  wire). `source`, `basis`, `terms_url` are the route's, unchanged.
- `get_fundamentals`: `StockholdersEquity` is served for a filer that
  publishes non-controlling-interest concepts when its NCI is demonstrably
  zero at the period end (JNJ, whose 10-K equity is tagged ONLY on the
  consolidated rung, was served no equity at all); `equityNote` and, when
  a period is refused, `{value: null, withheld: "nci_consolidated"}` +
  `equityWithheldNci` are new. `coverage[label].contiguous` is new.
  A >= 5x step across a tagging hole in EPS / DilutedShares (DAC's
  1-for-14 reverse split inside its untagged 2012-2016) withholds the
  older side as `{value: null, withheld: "basis_unverified"}`, with
  `basis.gapBreaks` + `basis.gapNote` (and `basis.basisConsistent` false).
  The refusal for a US-GAAP filer whose facts ride Form 6-K in CAD (CNI)
  names `annualFormsSeen` / `unitsSeen`.
- `get_13f_holdings`: `fund` accepts a class-share ticker (`BRK-B`,
  `BRK.B`) and resolves it via SEC's company map; it used to be rejected
  as INVALID_PARAMS before the resolver ran. The all-letters and numeric
  forms are unchanged.
- `get_fred_data`: a BLS/BEA series whose TITLE merely contains a licensor's
  word (`MIUR`, "Unemployment Rate in Michigan"; a Russell County or Moody
  County series) is served; it was refused as third-party-licensed. The
  hard-deny roster (UMCSENT, MICH, the ICE BofA OAS set, VIXCLS, SP500,
  DJIA, NASDAQCOM) is unchanged.
- The package imports on Python 3.9 again (a PEP 604 union evaluated at
  definition time in `fred_tools.py` broke the advertised `>=3.9` floor on
  the unreleased tree; the published 3.3.0 was unaffected).

(Two bullets that sat here until 2026-09-14 -- the `ol_cftc_cot` resolver
keys and the `get_13f_holdings` name-resolution note -- were filed under
3.4.0 but landed AFTER the 3.4.0 publish; they are 3.5.0 wire changes and
now sit under `## 3.5.0` above. COUNSEL delta vet W-4b.)

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
**SEC EDGAR company-facts XBRL only** — DCF / EPV / Graham per-share, peer
fundamentals, and a bounded fundamentals screen, with **no price leg** (fetch
a price from your own source to compute upside). Those tools are hosted-only
today; they arrive in this pip package only once the redistribution vet
clears them.

### If you relied on the removed tools

For raw price history or a vendor company profile, query your Oxford
Ledge instance's REST API directly. For fundamentals + valuation, prefer
the SEC-XBRL tools (`get_fundamentals`, and the hosted valuation tools
if and when they land here).

---

## Version history

- **3.5.0** (2026-09-14) — the delta vet: additive keys (the wave-G
  coverage / basis keys, `search_bdc_borrower` paging, the `ol_cftc_cot`
  resolver keys, the insider 4/A fold's four keys) and one value correction
  (`basis.basisConsistent` tri-state). No key renamed or removed. See above.
- **3.4.0** (2026-09-13; this row read "unreleased" until 2026-09-14 -- the
  publish landed the same day the row was written) — the full 29-tool publish vet: four wire changes
  (`TotalDebt` -> `LongTermDebt`; the two Plus tools serve the hosted EDGAR
  shapes; `events[].id` removed; `dateBasis` truthful), `_meta` on every
  response, one dispatcher seam that refuses non-object bodies and never
  caches an error envelope. See above.
- **3.1.0** (2026-07-21) — third-party-IP compliance sweep (CHAOS+DATA_CZAR+
  COUNSEL vetted): `search_bonds` + `get_bond_data` removed (bond CUSIPs are
  FactSet-licensed IP) and `get_short_interest` removed (advertised stub,
  unresolved float-lineage + FINRA attribution); `get_13f_holdings` +
  `get_corporate_events` now strip CUSIPs/ratings; `get_value_investing_fact`
  repointed off a vendor endpoint; `get_fred_data` refuses third-party-copyright
  FRED series (S&P/ICE/Moody's/CBOE) **fail-closed**. 13 tools. Pin `==3.0.1`
  for the removed tools. [Annotated 2026-09-14: a `==3.0.1` pin no longer
  restores `search_bonds` / `get_bond_data` as WORKING tools -- FINRA
  auth-walled the public TRACE hosts they scraped in 2026-07, and on
  2026-09-13 both were RETIRED on the hosted server as well (`status:
  "retired"`, `use_instead: ol_bond_directory_screen`). The dated record
  above is kept as written.]
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
