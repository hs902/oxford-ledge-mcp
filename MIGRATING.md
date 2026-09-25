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

## 3.7.1 — six keys the host already sends now pass the emit filter, `get_insider_trades` carries `issuerSelfFiled`, and eight descriptions are corrected to the wire

Cut 2026-09-25, after the 3.7.0 publish the same day; an installed 3.7.0 has
none of the package-side changes below. **No tool, argument, schema bound or
key is renamed or removed, and this client sends nothing new.** Everything in
the package is additive: a reader that ignores keys it does not know sees no
difference except the description text.

### Six keys admitted by the fail-closed emit filter (additive)

The package filters every payload through a per-tool allowlist and DROPS any
key it does not recognise -- so a key the Oxford Ledge server started sending
after a release is stripped until the next release admits it. 3.7.1 admits
six (lowercased in the table; they arrive in the host's own spelling):

| tool | keys | what they say |
|---|---|---|
| `get_bdc_list`, `get_bdc_holdings` | `fairValueGap`, `fairValueGapNote` | a label (`rows_under_reported` / `rows_over_reported` / `funded_basis_presentation`, or null) plus one sentence whenever Oxford Ledge's parsed-row total and the filing's own total differ by more than 5% |
| `ol_bdc_credit_quality` | `withheld`, `parser_dialect_version` | on `latest` and every trend row: `'implausible_flag_rate'` when the misread test nulled the rate (more than 25% flagged AND the flagged loans marked near par), and the oldest parser-generation stamp among the quarter's rows |
| `get_value_investing_fact` | `verbatim` | true only for a text verified against its primary source; false for every entry today |
| `get_insider_trades`, `ol_insider_recent_buys` | `issuerSelfFiled` | true when the Form 4 was filed under the company's own SEC ID; always false on `ol_insider_recent_buys`, which excludes those purchases |

- **Before (3.7.0):** a BDC whose parsed rows recovered 73% of the filing's own
  total came back with `fairValueBasis: "parsed-rows"`, a `totalFairValue` that
  understates the book by a quarter, and nothing saying so; an
  `ol_bdc_credit_quality` quarter read `coverage_state: "implausible"` with
  `flagged_pct: null` and no reason code; an issuer-self-filed Form 4 row read
  like any officer's trade.
- **After (3.7.1):** the same payloads carry the label, the reason code and
  the flag.
- **What to do:** read `fairValueGap` beside `fairValueBasis` before quoting a
  BDC's size -- on `rows_under_reported` the size of the book is
  `reportedTotalFairValue`, not `totalFairValue`; leave rows with
  `issuerSelfFiled: true` out of any insider buy/sell total (Oxford Ledge
  never counts them in its own summaries, net figures or clusters); repeat a
  value-investing text with its `attribution` line, not as a quotation.
- **The hosted server changes too.** The hosted `/mcp` route applies this same
  allowlist table to ANONYMOUS callers, so the six keys reach anonymous hosted
  callers from the next Oxford Ledge deploy, independent of this publish.

### `get_insider_trades`: `issuerSelfFiled` on each row (additive)

The reshape of `/api/insider-activity` now passes the row's `issuerSelfFiled`
through as the host sent it. When the host does NOT send it -- an Oxford Ledge
server older than the 2026-09-24 change -- the key is ABSENT from the row,
never `false`: read absence as "unknown". The route declares the key an
Oxford Ledge derivation, so when it is present `_meta.derived_fields` also
lists `trades[].issuerSelfFiled`.

### Descriptions corrected to the wire (no schema change)

- **`get_value_investing_fact`**: the entries' wording is not verified against
  the primary source -- most paraphrase or summarise the named author's ideas,
  some may repeat the author's own words -- so none is a verbatim quotation
  unless `verbatim` is true; `attribution` is the credit line to use. The
  description no longer calls the text a "quote" or says the quotations are
  their authors'. The `quote` KEY keeps its name, and `quote` stays a valid
  `category` value.
- **`ol_bdc_credit_quality`**: `coverage_state` has two new values.
  `implausible`: more than 25% of determinate debt fair value flagged AND the
  flagged loans marked near par (their aggregate mark at or above 85 per 100
  of par, while a loan a lender has stopped accruing on is marked down) -- a
  sign the parse misread the schedule, so the rate is withheld.
  `unusually_high`: more than 25% flagged WITHOUT that signature -- the rate
  is stated, and `summary` says "unusually high -- check the filing". The
  description names `withheld` and `parser_dialect_version`.
- **`get_bdc_list` / `get_bdc_holdings`**: name `fairValueGap` /
  `fairValueGapNote`; state the two cases in which `reportedTotalFairValue` is
  null; say what `lastParsed` is; say that `get_bdc_holdings`' header is
  recomputed from the served rows when the stored registry row describes
  another filing.
- **`get_insider_trades` / `ol_insider_recent_buys`**: name `issuerSelfFiled`
  (on the screen: Oxford Ledge's comparison of two SEC IDs, expected `false`
  because the screen excludes those purchases; a `true` row is one the
  exclusion missed).
- **`ol_bdc_top_borrowers`**: ranked by the ACTIVE lender count, then
  `holder_count`, then exposure; `industry_basis` and its `contested` flag are
  described (a stale stored label counts as contested).
- **`ol_bdc_mark_changes`**: the `coverage` exclusion reasons include
  `fair_value_refused`.

### Host-side changes the descriptions now state (an installed 3.7.0 sees these too)

These are Oxford Ledge server changes of 2026-09-24/25. They arrive as VALUES
under keys 3.7.0 already passes, so upgrading the package is not what brings
them; 3.7.1 is what describes them.

- **`reportedTotalFairValue` is null, never 0, in two cases** on `get_bdc_list`
  and `get_bdc_holdings`: the filing tags no usable grand total, OR Oxford
  Ledge's stored reference describes a different filing than the book served
  (it cannot reconcile). A null reference carries no swap, no gap label and no
  refusal.
- **`get_bdc_list`'s `lastParsed`** is the date Oxford Ledge last wrote the
  BDC's registry row (a repair counts), no longer the filing date.
- **`get_bdc_holdings`' `periodEnd` / `totalHoldings` / `filingType`** are
  recomputed from the served rows when the stored registry row names another
  filing (previously the registry's values, which described that other filing).
- **MRCC has left `get_bdc_list`.** Monroe Capital merged into HRZN
  (2026-04-14); MRCC is archived with successor HRZN, and `get_bdc_holdings`
  for it serves the frozen final filing labelled `filerStatus: "inactive"`,
  `successorTicker: "HRZN"`. `get_bdc_list` now returns 48 BDCs.
- **`ol_bdc_mark_changes`' `filters.debt_mark_band_pts` is `[30.0, 105.0]`**
  (it was `[30.0, 110.0]` when 3.7.0 was cut and is described that way below):
  a prior or latest mark in (105, 110] is now held in `suspect_moves` with
  `reason: "prior_or_latest_outside_debt_band"` instead of ranked. Its
  `fair_value_refused` screen judges a book only against a reference coherent
  with it.
- **`ol_bdc_top_borrowers`** ranks on `holder_count_active`, so a wound-down
  filer and its successor holding one book no longer count as two lenders;
  `holder_count` itself is unchanged.
- **`ol_bdc_credit_quality` withholds a rate only on evidence of a misread**
  (OWNER ruling 2026-09-25). Before: any rate above 25% of determinate debt
  fair value was withheld as `implausible`. After: only when the flagged
  loans are ALSO marked near par (aggregate mark >= 85 of 100); a rate above
  25% on marked-down loans, or with no mark to test, is stated with
  `coverage_state: "unusually_high"` and "unusually high -- check the
  filing" in `summary`, which also states the flagged loans' mark. What to
  do: treat `unusually_high` as a stated rate that needs the filing checked
  before you rely on it; a client that reads `flagged_pct` only on `covered`
  skips it rather than misstating it. An Oxford Ledge host older than the
  2026-09-25 release (a self-hosted instance not yet updated) still withholds
  every rate above 25% as `implausible`, whatever the mark, and never sends
  `unusually_high`; the description is of the host from that release on.
- **`get_value_investing_fact`'s `_meta.source` and each row's
  `attribution`** say the wording is not verified against the source and is
  not a verbatim quotation. (A draft of this release called the whole corpus
  "Oxford Ledge's own wording"; the publish vet found entries that are the
  author's own sentences -- the 1989 Berkshire letter's "wonderful company at
  a fair price" line is one -- and corrected it before the publish.)
- **`get_fails_to_deliver` is one row per ticker and settlement date.** SEC's
  files are per CUSIP; where a symbol appears under two CUSIPs on one date
  (a CUSIP change with both securities failing), `fails` is the SUM across
  them and `price` / `description` follow the CUSIP with the larger fails.
  Before 2026-09-25 such a pair made the whole half-month file fail to load
  (five files were missing from the store); once Oxford Ledge reloads them
  with the fixed loader, a window that reaches into those periods has rows it
  did not have, and until then `coverage.files_missing` still names them.
  What to do: nothing on the client; read `coverage.files_missing` as before.

## 3.7.0 — the REST-path tools name themselves to the host, three additive `_meta` / row keys, new optional arguments on `get_bdc_holdings` and `get_fails_to_deliver`, the loopback exemption ignores `http_proxy`, and two FRED series stop serving

Cut 2026-09-24 (it was `## Unreleased` until the bump); an installed 3.6.0
has none of it.
**Tool names are unchanged. Nothing is removed, renamed or trimmed.** A reader
that ignores keys it does not know, and passes only the arguments it already
passed, sees nothing new.

**Correction, 2026-09-22.** Until today this paragraph denied any change to
tool names AND to argument schemas, in one sentence. The second half is now
false for exactly one tool: `get_bdc_holdings` gained two OPTIONAL arguments,
`limit` and `offset` (see below). The clause is corrected rather than quietly
dropped, because a migration note that denies an argument-schema change is
worse than no note -- the same reason the 3.5.0 section below carries its own
struck sentence. (The superseded wording is deliberately not re-quoted: a gate
hunts that exact sentence, so a correction repeating it verbatim would red on
its own fix.)

**Second correction, 2026-09-22 (same day, later).** "A reader that passes only
the arguments it already passed sees nothing new" is now false for two ARGUMENT
VALUES rather than for any schema: `get_fred_data` refuses `MORTGAGE30US` and
`AAA`, which it previously served some of the time. That is the only breaking
change in this section and it has its own heading at the end. The sentence
above is left standing and qualified here rather than rewritten, because a
reader who acted on it should be able to see that it changed.

**Third correction, 2026-09-24 (at the bump).** "False for exactly one tool"
in the first correction, and "the only argument-schema change in this release" in the
`get_bdc_holdings` item below, were each true of the sub-section they were
written in and false of the release: `get_fails_to_deliver` also gained an
OPTIONAL argument, `end_date`, and it and `ol_form_d_raises` now declare
`days` minimums (see *Fixed -- government feeds*). The new argument is
additive; the minimums are not quite -- `days: 0` is now refused on both tools
(the correction at the end of that section), so "the only breaking change in
this section" in the second correction has a sibling too. All three sentences
are qualified here rather than rewritten, for the same reason as the two
corrections above.

### What this client now sends (with `OXFORD_LEDGE_API_KEY` set)

The nine tools that call a hosted REST route directly (`get_holders`,
`get_insider_trades`, `get_corporate_events`, `search_bdc_borrower`,
`get_bdc_list`, `get_bdc_borrower_mark_history`, `get_bdc_holdings`,
`get_13f_holdings`, `get_value_investing_fact`) add ONE request header,
`X-OL-MCP-Tool`, whose value is the calling tool's registered name -- no
arguments, no package version, nothing else. Oxford Ledge uses it to count
those lookups on the key owner's own activity page; without it the host cannot
tell an assistant's lookup from any other request on the same route.

- **Keyless calls send nothing new.** The header rides only a request that
  already carries your key, and never a request the package makes outside a
  tool call.
- **It never crosses a redirect**, exactly like the key.
- **Nothing in any response changes because of it.** The host ignores a
  missing header, so an installed 3.6.0 keeps working; its lookups on these
  nine routes are simply not counted.

**What to do:** nothing. If your organisation reviews outbound headers, this
is the one addition in 3.7.0.

### What you may now see (external live review of 3.6.0, 2026-09-21)

- **`_meta.response_size`** on the nine REST-path tools (`get_bdc_holdings`,
  `get_bdc_list`, `search_bdc_borrower`, `get_bdc_borrower_mark_history`,
  `get_holders`, `get_insider_trades`, `get_corporate_events`,
  `get_13f_holdings`, `get_value_investing_fact`): `{chars, approx_tokens,
  budget_chars: 32000, over_budget}` and, when over budget, a `hint`. The
  name-proxied tools already carried this block from the hosted server;
  it is the same shape and the same budget. **Nothing is dropped** to fit --
  a `get_bdc_holdings` answer for a large BDC is still every row, now
  labelled `over_budget: true`. If your client has a tool-result ceiling
  (the reviewing one refused answers above ~50,000 characters), read
  `over_budget` before you read the rows. ~~`get_bdc_holdings` takes no
  `limit`; paging it is a hosted-route change and is not in this release.~~
  **Struck 2026-09-22: it takes one now -- see the next item.**
- **`get_bdc_holdings` accepts `limit` and `offset` (both OPTIONAL).** The
  only argument-schema change in this release, and it is additive: **a call
  that declares neither is byte-for-byte what 3.6.0 returned**, every row, no
  new keys. Declare either and you get that window of `holdings` plus two
  blocks: `page` `{limit, offset, returned, total, hasMore}` and
  `completeness` `{returned, limit, total_available, complete,
  completeness_basis, rows_key}`.
  - **The page never restates the book.** `totalHoldings`,
    `holdingsReturned`, `nonBorrowerRowsExcluded`, `excludedRowsFairValue`,
    `totalFairValue` and its arbitration triple, `weightedAvgPrice`,
    `byLienPosition`, `topIndustries` and `portfolioStructure` stay computed
    over every row the store returned. `page.total` is the served row count
    and equals `holdingsReturned`. So `returned < total` -- not a smaller
    `totalHoldings` -- is how you know you hold a window.
  - `limit` is 1..5000 and defaults to 5000 (the store's own row backstop, so
    the default is "every row"); `offset` is 0..5000 and defaults to 0.
    **Out-of-range values are REFUSED, not clamped** -- `limit: 0` or
    `offset: -1` comes back as an invalid-params error, never as a silently
    adjusted page. An offset past the end is NOT an error: it is an empty
    `holdings` list with `page.total` intact and `hasMore: false`.
  - Same key set, same vocabulary and same rules as `search_bdc_borrower`'s
    `limit` / `offset`. If you have paged that tool, you have paged this one.
  - Nothing is trimmed to fit, here or anywhere: `_meta.response_size` still
    reports, and you decide. A 325-row book serialises to ~125,000 characters
    whole, ~39,000 at `limit: 100`, ~10,700 at `limit: 25`.
- **`_meta.served_from_cache: true` and `_meta.cache_age_seconds`** on any
  result replayed from the wheel's in-process cache (TTL per tool: 300 s
  market, 3600 s fundamental). A fresh result carries neither key. If you
  need a fresh read, change an argument or wait out the TTL; the marker tells
  you which you got.
- **`ol_federal_contracts`: `obligations[].recipients` is the ten largest by
  `amount`.** A fiscal-year row that had more carries
  `recipients_truncated: true` and `recipients_total`; a row with ten or
  fewer is served as stored and carries neither. `entity_count` was always the
  full count and still is; `total_obligations_usd` still sums every kept
  recipient, not just the ten shown.

**What to do:** nothing, unless you summed `recipients[].amount` to rebuild
`total_obligations_usd` -- the two agreed before this change and now agree
only on a row with ten or fewer recipients. Use `total_obligations_usd`; it
is still the sum over every kept recipient.

### The loopback exemption ignores `http_proxy` (behaviour change, nothing on the wire)

One behaviour changes, and only for the configuration where `OXFORD_LEDGE_API_KEY`
is set AND `OXFORD_LEDGE_URL` is a plain `http://` loopback address
(`localhost`, `127.x.y.z`, `[::1]`, `[::ffff:127.0.0.1]`):

- **Before:** the request honoured `http_proxy` / `HTTP_PROXY` from the
  environment, and Python's urllib has no implicit localhost bypass -- so
  unless `no_proxy` named the host, the request (with the key on it, in the
  clear) went to the proxy, not to the local instance.
- **After:** a key-carrying plain-http request opens with no environment
  proxy at all and reaches the local interface directly. `no_proxy` is no
  longer needed for this setup, and a corporate or system proxy never sees
  the key.

**What to do:** nothing, unless you relied on the old behaviour -- for
example an intercepting debug proxy at `http_proxy=http://127.0.0.1:8080`
that captured this client's keyed traffic to `localhost:10000`. It will no
longer see that traffic; that is the fix. Requests to an `https://` host, and
every keyless request, honour the environment proxy exactly as before.

### Changed -- BDC mark changes (read layer)

Also in 3.7.0 (an installed 3.6.0 does not have it; this sub-section was
under `## Unreleased` until the bump). **Tool names are unchanged, and no
argument schema changes in THIS sub-section** -- `get_bdc_holdings` gained two
optional arguments elsewhere in the release, recorded at the top of this
section. This
paragraph used to make that denial for names and argument schemas together,
without the qualifier, and it is narrowed rather than deleted: a blanket
denial in one sub-section reads as a denial for the whole release. (The
original wording is not quoted here -- a gate hunts that exact sentence, and
a correction that reproduces it verbatim reds the gate on its own fix.) Two
additive output changes and one value correction on the hosted-leg BDC tools:

- **`ol_bdc_mark_changes`: `suspect_moves` (top level, additive) and three
  new `filters` keys.** A move of more than `filters.max_abs_mark_delta_pts`
  (15) points in one quarter, a `latest_mark` of exactly 100.00, or a mark
  outside `filters.debt_mark_band_pts` ([30.0, 110.0] at this cut; the host
  narrowed it to [30.0, 105.0] on 2026-09-24 -- see 3.7.1) is now held in
  `suspect_moves` with a `reason` code instead of being ranked in
  `increases` / `decreases`. Rows have the ranked-row shape plus `reason`;
  `filters.suspect_reasons` maps each code to a sentence, and
  `suspect_moves_completeness` counts the held-out rows.
  - **Before:** a 45-point single-quarter jump ranked #1 among increases.
  - **After:** it is the first row of `suspect_moves` with
    `reason: "delta_exceeds_threshold"`; `increases` starts at the largest
    move that survived. Nothing stored changed.
  - **What to do:** a reader that summarises "the biggest moves" should
    read `suspect_moves` too and say they were held out, not omit them; a
    reader that treated every ranked row as a credit event no longer needs
    to second-guess the top of the list.
- **`ol_bdc_mark_changes`: `latest_mark` / `prior_mark` are 2 dp** (value
  correction at emit only; `mark_delta` already was).
- **`ol_bdc_top_borrowers`: `holder_count_active` / `holder_count_ever` on
  each row (additive).** `holder_count` is unchanged. The pair is summed over
  `holder_ticker_status`, so `ever - active` is the number of wound-down or
  merged-away filers in the syndicate; both are `null` when the roster could
  not be checked. The `summary` now says "syndicated across N active BDCs
  (M ever)" for rows where the two differ.

### Fixed -- government feeds (gov_feeds / mcp_tools_gov)

Also in 3.7.0; an installed 3.6.0 does not have them. **Tool names are
unchanged. Three argument schemas gain properties or
bounds (additive). One tool's wire VALUES move by one day; one tool gains a
key.**

- **`get_fails_to_deliver` -- a value change you may notice.** A `days`
  window is now `days` calendar days inclusive (it was `days + 1`). On the
  wire: `coverage.window_start` and `window.from` are ONE DAY LATER than
  before for the same arguments; `coverage.days_covered` on a fully loaded
  window now equals `days` (it read `days + 1`, the "91 of the 90 requested
  days" sentence); `days_before_earliest` / `days_after_latest` cap at `days`;
  a `history` row dated exactly `days` days before the window's end is no
  longer served. If you re-implemented the count, use
  `days_before_earliest + days_covered + days_after_latest == days` as the
  check -- it holds whenever the window meets the loaded range.
  - **Before:** `days=30`, `as_of` 2026-08-22 -> `window.from` 2026-07-23,
    `days_covered` 31.
  - **After:** `window.from` 2026-07-24, `days_covered` 30.
- **`get_fails_to_deliver` schema (additive):** `end_date` (string, ISO date
  the window ends on; default the latest loaded settlement date, `as_of`) is
  declared -- the hosted handler already honoured it, so a client that passed
  it anyway saw no change; a client that validated arguments against this
  package's schema can now pass it. `days` declares `minimum: 1`.
- **`get_debt_maturities` (additive):** a top-level `summary` string joins
  the payload -- the reader that produced the ladder, the filing it is AS OF,
  and the bucket(s) that have wholly or partly elapsed since that filing. No
  existing key moved. The description's `source` vocabulary now matches the
  values you have been receiving: `'xbrl' | 'table' | 'regex' | null`, plus
  `'<source>_rejected'` and `'<source>_non_usd'`; `filing_date`,
  `report_date` and `cross_validated` were already served and are now
  documented (`cross_validated` is present only when true -- read
  `validation.valid` for the negative).
- **`ol_form_d_raises` schema (additive):** `days` declares `minimum: 1`
  (the handler's existing clamp floor; a value below 1 falls back to the
  365-day default, as before). No behaviour change.
- **Runtime prose (no shape change):** three sentences that named tools this
  package does not ship (`get_institutional_holders`,
  `ol_bank_structure_events`, `ol_13f_filer_search`) now name the wheel tool
  (`get_holders`) or say what the hosted-only record is. If you matched on
  those sentences, re-anchor.
- **Corrected at the bump, 2026-09-24: `days` below 1 is now REFUSED on both
  tools.** The two "`days` declares `minimum: 1`" items above said additive,
  and the Form D one said no behaviour change. Both were true of the hosted
  catalog and are false of this package: it validates every declared bound
  before the call, on both transports, so `days: 0` (or a negative) on
  `ol_form_d_raises` or `get_fails_to_deliver` now comes back as
  `INVALID_PARAMS` ("`days`: 0 is less than the minimum of 1"), where 3.6.0
  forwarded it and the host fell back to its default window. Measured on both
  builds. The Form D property text said "a value below 1 falls back to
  the 365-day default" at the bump; the publish vet corrected it to say omit
  `days` for the default and that a value below 1 is refused. The fallback is
  the host handler's behaviour and no longer
  reachable through this package.
  - **Before (3.6.0):** `{"days": 0}` -> the default window, served.
  - **After (3.7.0):** `{"days": 0}` -> `INVALID_PARAMS`, nothing sent.

**What to do:** nothing, unless you computed FTD window dates or day counts
yourself -- re-derive from `coverage` rather than from `days` -- or you pass
`days: 0` to mean "the default": omit `days` instead.

### `get_fred_data` — two ids stop serving, eight start surviving a FRED outage

**This is one of the two refusals in 3.7.0 of a value 3.6.0 accepted** (the
other is `days` below 1, at the end of *Fixed -- government feeds*). Two FRED
series ids are now refused before any request is made:

| series | publisher | what you used to get |
|---|---|---|
| `MORTGAGE30US` | Freddie Mac (Primary Mortgage Market Survey) | served, or refused, depending on whether FRED's `notes` text happened to carry a copyright word |
| `AAA` | Moody's (Seasoned Aaa Corporate Bond Yield) | the same coin-flip |

Both now raise `INVALID_PARAMS` naming the series, with no FRED request spent.
Neither is a U.S. Government work under 17 USC 105, so neither was ever safe
for this gov-public-data package to redistribute; the previous behaviour was
non-deterministic rather than permissive by design.

**What to do if you consumed either:** read them from FRED directly under your
own agreement with the rights holder, or substitute a federal series -- `DGS30`
or `DGS10` for a long-rate anchor. There is no flag to re-enable them, and
adding one would put the licensing decision in the caller's hands.

**In the other direction, and additive:** eight cleared federal series that
used to be refused as unverifiable whenever FRED's metadata endpoint was
unreachable now serve through an outage -- `JTSJOL`, `PCE`, `PSAVERT`,
`TOTALSA`, `PERMIT`, `DGORDER`, `ICSA`, `DTWEXBGS`. Nothing about a successful
call changes: the payload shape, the `name` / `units` / `frequency` keys (still
`null` when the probe did not run) and the values are what they were.

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
