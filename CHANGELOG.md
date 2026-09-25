# Changelog

All notable changes to `oxford-ledge-mcp` are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 3.7.1 (2026-09-25)

Everything under this heading landed on `main` after the 3.7.0 publish
(2026-09-25) and ships in 3.7.1; an installed 3.7.0 has none of the
package-side changes. **Cut 2026-09-25.** The publish waited on a CISO +
COUNSEL + CHAOS publish vet of this cut (2026-09-25), which read
PUBLISH-AFTER-FIXES on the condition that the Oxford Ledge server release
carrying these keys was deployed first; its corrections are in this cut
(*Corrected at the publish vet*, the last item under *Changed --
descriptions*).

**Why a patch release.** Three reviewed changes merged on the Oxford Ledge
server after the 3.7.0 cut put keys on the wire that this package's
fail-closed emit filter strips, and changed what several descriptions should
say. The sources are the CHAOS reviews of 2026-09-24/25 (BDC plausibility
gates; the BDC parse-registry integration; the EDGAR text-audit fixes; the
serve-honesty addendum on the issuer-self-filed Form 4 ruling).

**What 3.7.1 changes, by kind.** Nothing is renamed or removed; no argument,
schema bound or outbound request changes. Six keys are admitted by the emit
filter (additive); one reshape passes a key through (additive, absent when
the host does not send it); eight descriptions are corrected to the wire; the
README and the package summary stop calling the value-investing corpus
"quotations".

### Added -- six keys admitted by the fail-closed emit filter

The keys below were already on the hosted wire; 3.7.0 dropped them at its
emit boundary (`oxford_ledge_mcp_core/emit_allowlist.py`, which DROPS any
key a tool's allowlist does not name).

- **`get_bdc_list`, `get_bdc_holdings`: `fairValueGap` / `fairValueGapNote`**
  (MCP audit 2026-09-24, finding 6). A closed-vocabulary label --
  `rows_under_reported`, `rows_over_reported` or `funded_basis_presentation`
  (FSK's funded-amount schedule, a presentation difference, not an
  over-count), null when the parsed-row total and the filing's own total agree
  within 5% or cannot be compared -- plus one sentence stating the ratio. It
  is the only field that says when a mild under-count leaves `totalFairValue`
  (the parsed-row sum) UNDERSTATING the book: the swap to the filing's total
  is one-sided by design and fires only on an over-count or a parse that
  recovers under half the book. Lineage: Oxford Ledge's arithmetic over the
  SEC row sum and the filing's own total, the same as the admitted refusal
  pair.
- **`ol_bdc_credit_quality`: `withheld` / `parser_dialect_version`** on
  `latest` and every trend row (finding 1). `withheld` is
  `'implausible_flag_rate'` when the misread test (more than 25% of
  determinate debt fair value flagged AND the flagged loans marked near par,
  at or above 85 per 100 -- OWNER ruling 2026-09-25) is what nulled a rate
  that coverage would have allowed -- the host's `coverage_state`
  `implausible`, which 3.7.0 already passed, now arrives with its reason;
  `parser_dialect_version` is the oldest parser-generation stamp among the
  quarter's rows.
- **`get_value_investing_fact`: `verbatim`** (finding 10). True only for a
  text verified against its primary source; false for every entry today.
  `attribution` already passed as an envelope key, so 3.7.0 callers saw
  "Paraphrasing ..." without the boolean.
- **`get_insider_trades`, `ol_insider_recent_buys`: `issuerSelfFiled`**
  (OWNER ruling 2026-09-24: label the issuer's own Form 4 on lists, exclude it
  from counts). True when the reporting-owner CIK equals the issuer's CIK --
  the filing's owner field names the company, not a person. Always false on
  `ol_insider_recent_buys`, whose screen already excludes those purchases.
- **The hosted server changes at its next deploy, independently of this
  publish.** The hosted `/mcp` route imports this same table for ANONYMOUS
  callers, so the six keys reach anonymous hosted callers when the Oxford
  Ledge server next deploys.

### Changed -- `get_insider_trades` passes `issuerSelfFiled` through

The reshape of `/api/insider-activity` copies the row's `issuerSelfFiled`
as the host sent it. A host that does not send it (older than 2026-09-24)
leaves the key ABSENT -- never coerced to `false`, because "not the company's
own filing" is a claim an older host never made. The route declares the key
an Oxford Ledge derivation, so `_meta.derived_fields` lists
`trades[].issuerSelfFiled` whenever it is present. 3.7.0 served the same rows
unlabelled.

### Changed -- descriptions (no schema change)

- `get_value_investing_fact`: the entries' wording is not verified against
  the primary source -- most paraphrase or summarise the named author's ideas,
  some may repeat the author's own words -- so none is a verbatim quotation
  unless `verbatim` is true; `verbatim` and `attribution` are in the field
  list, with `attribution` as the credit line to use. "Quote" and "the
  quotations are their authors'" are gone (the `quote` key and the `quote`
  category value keep their names).
- `ol_bdc_credit_quality`: `coverage_state` is one of `none_parsed` /
  `partial` / `covered` / `unusually_high` / `implausible`; `withheld` and
  `parser_dialect_version` are described. `implausible` is the misread
  signature (more than 25% flagged AND the flagged loans marked near par);
  `unusually_high` is a rate above 25% that is STATED, with "unusually high
  -- check the filing".
- `get_bdc_list` / `get_bdc_holdings`: `fairValueGap` / `fairValueGapNote`;
  `reportedTotalFairValue` is null for two reasons (no usable filed total, or
  a stored reference that describes a different filing than the book served);
  `lastParsed` is the date Oxford Ledge last wrote the BDC's registry row;
  `get_bdc_holdings`' header (`filingType`, `periodEnd`, `totalHoldings`) is
  recomputed from the served rows when the registry row describes another
  filing.
- `get_insider_trades` / `ol_insider_recent_buys`: `issuerSelfFiled`.
- `ol_bdc_top_borrowers`: ranked by the ACTIVE lender count
  (`holder_count_active`), then `holder_count`, then exposure; `industry_basis`
  and its `contested` flag described, including a stale stored label.
- `ol_bdc_mark_changes`: the `coverage` exclusion reasons include
  `fair_value_refused`.
- README (the PyPI page): the corpus is "attributed paraphrases", not
  "attributed quotations"; the BDC count is the 48 active BDCs `get_bdc_list`
  serves (it said 54, an older parse-universe count); the tool table names the
  new keys. `pyproject.toml`'s summary says "value-investing corpus of
  attributed paraphrases", not "quotation corpus".
- **Corrected at the publish vet (2026-09-25): the corpus is UNVERIFIED, not
  "Oxford Ledge's own wording".** The cut described every entry as Oxford
  Ledge's own wording. Some entries are the author's own sentences -- the
  1989 Berkshire Hathaway letter's "It's far better to buy a wonderful company
  at a fair price than a fair company at a wonderful price." is in the corpus
  word for word -- so that claimed authorship of a third party's words. The
  description, the README and the host's `attribution` / `_meta.source`
  lines now say the wording is not verified against the source; every entry
  still reads as not a verbatim quotation, and the ideas stay credited to the
  named author. `ol_insider_recent_buys` now calls `issuerSelfFiled` Oxford
  Ledge's comparison of two SEC IDs (not a Form 4 field) and says to expect
  `false`, rather than promising it always is.

### Host-side changes an installed 3.7.0 also sees

These arrive as values under keys 3.7.0 already passes; 3.7.1 describes them.

- `reportedTotalFairValue` is null, never 0, when Oxford Ledge's stored
  reference describes a different filing than the book served (ARCC's registry
  row had been re-written by a 2023 filing's parse); the gap label and the
  refusal then stay off.
- `get_bdc_list`'s `lastParsed` is the registry-row write date, not the filing
  date.
- MRCC (Monroe Capital, merged into HRZN 2026-04-14) has left `get_bdc_list`;
  it is archived with successor HRZN.
- `ol_bdc_mark_changes`: `filters.debt_mark_band_pts` is `[30.0, 105.0]` (the
  3.7.0 entry below says 30-110, true when it was cut), so a mark in
  (105, 110] is held in `suspect_moves`; the `fair_value_refused` screen uses
  only a reference coherent with the latest book.
- `ol_bdc_top_borrowers` ranks on the active lender count.
- `ol_bdc_credit_quality` withholds a non-accrual rate only on evidence of a
  misread (OWNER ruling 2026-09-25): above 25% of determinate debt fair value
  AND the flagged loans' aggregate mark at or above 85 per 100 of par. A rate
  above 25% on marked-down loans (or with no mark to test) is now STATED, with
  `coverage_state` `unusually_high` and "unusually high -- check the filing" in
  `summary`; `summary` also states the flagged loans' mark. A 3.7.0 install
  receives the new state value too (a value, not a key) -- a client that reads
  `flagged_pct` only when `coverage_state` is `covered` will skip these rates
  rather than misstate them. An Oxford Ledge host older than the 2026-09-25
  release (a self-hosted instance not yet updated) still withholds every rate
  above 25% as `implausible`, whatever the mark, and never sends
  `unusually_high`; this description is of the host from that release on.
- `get_value_investing_fact`'s `_meta.source` and each row's `attribution`
  say the wording is not verified against the source and is not a verbatim
  quotation (earlier host builds said "the quoted words are the named
  author's"; a draft of this release said "Oxford Ledge's own wording" --
  both were wrong, in opposite directions).
- `get_fails_to_deliver` serves one row per ticker and settlement date. SEC's
  files are per CUSIP, so a symbol can appear twice on one date (a CUSIP
  change with both securities failing); until 2026-09-25 that pair made the
  whole half-month file fail to load, and five files were missing. From the
  2026-09-25 host release, `fails` on such a date is the SUM across the
  symbol's CUSIPs, and `price` / `description` follow the CUSIP with the
  larger fails; a repeated identical line replaces, never doubles. The
  description says so. The five missing files appear only once Oxford Ledge
  reloads them with the fixed loader; until then `coverage.files_missing`
  still names them.

## 3.7.0 (2026-09-24)

Everything under this heading landed on `main` after the 3.6.0 publish
(2026-09-21, 20:26Z) and ships in 3.7.0; an installed 3.6.0 has none of it.
It was carried as `## Unreleased` until the bump. **Cut 2026-09-24.** The
OWNER greenlit the publish on 2026-09-24 for when a CISO + COUNSEL + CHAOS
publish vet found it ready; the vet read PUBLISH-AFTER-FIXES, and its fixes
are in this cut (*Corrected at the publish vet*, the last item of *Fixed --
government feeds* below, and the Board release list under `get_fred_data`).

**Why the version moved before the publish.** An external MCP audit
(2026-09-24, finding 4) compared a running 3.6.0 with this source tree and
found two different packages under one number: `get_bdc_holdings`' `limit` /
`offset`, `get_fails_to_deliver`'s `end_date` and the `'xbrl'` debt-ladder
vocabulary were in the tree's schemas and in none of what the published
server advertised, while `pyproject.toml` and `__version__` both still read
3.6.0. The tree no longer calls itself a version PyPI already serves: a
contract in the main repo now records the published wheel's per-file and
per-tool digests and fails when a shipped file changes under a recorded
version, so the next cut takes its new number at its FIRST change, not at its
publish.

**What 3.7.0 changes, by kind.** Nothing is renamed or removed. One new
outbound request header (the nine REST-path tools name themselves, key set
only); six advertised tools change schema or description (`get_bdc_holdings`
gains `limit` / `offset`; `get_fails_to_deliver` gains `end_date` and a `days`
minimum; `ol_form_d_raises` declares a `days` minimum; `get_debt_maturities`,
`ol_federal_contracts` and `get_fred_data` are re-described); additive
`_meta` and row keys; one value correction (`get_fails_to_deliver`'s window is
`days` days, not `days + 1`); the loopback-proxy fix; and two kinds of value
3.6.0 accepted that 3.7.0 REFUSES: `get_fred_data`'s `MORTGAGE30US` and `AAA`,
and `days` below 1 on `ol_form_d_raises` / `get_fails_to_deliver` (see the
correction at the end of *Fixed -- government feeds*).

### Added -- the nine REST-path tools name themselves to the host

With `OXFORD_LEDGE_API_KEY` set, the nine tools whose handler calls a hosted
REST route directly (`get_holders`, `get_insider_trades`,
`get_corporate_events`, `search_bdc_borrower`, `get_bdc_list`,
`get_bdc_borrower_mark_history`, `get_bdc_holdings`, `get_13f_holdings`,
`get_value_investing_fact`) now send one extra request header,
**`X-OL-MCP-Tool`**, whose value is the name of the tool that made the call.
Oxford Ledge uses it to count those calls on the key owner's own activity
page: without it the host cannot tell a lookup an AI assistant made from any
other request on the same route. The name-proxied tools are counted by the
host's own dispatcher and do not send it; the four tools that run on your
own computer are unchanged.

- **Sent only with a key.** A keyless call carries no header, and neither
  does any request the package makes outside a tool call.
- **The value is the tool's registered name and nothing else** -- no package
  version, no arguments, no other identifier.
- **It stays off a redirect.** Like the key, it is an unredirected header, so
  a 3xx to another host does not forward it.
- **The header does not alter the response it rides on.** The host ignores a
  missing or unrecognised header, and an installed 3.6.0 or earlier (which
  never sends it) is simply not counted on these nine routes.

### Added -- three `_meta` / row keys, all additive (external live review of 3.6.0, 2026-09-21)

An external reviewer drove the published wheel and had two answers written to
disk by the MCP client instead of read: `get_bdc_holdings` for a mid-sized BDC
(~118,000 characters) and `ol_federal_contracts(ticker="LMT", limit=5)`
(~53,600). Nothing is trimmed anywhere -- "it reports, it never trims" is the
recorded design on both the hosted and the wheel surface -- but three things
the wire did not say, it now says:

- **`_meta.response_size` on the REST-path tools.** The nine tools whose
  handler calls a hosted REST route directly (`get_bdc_holdings`,
  `get_bdc_list`, `search_bdc_borrower`, `get_bdc_borrower_mark_history`,
  `get_holders`, `get_insider_trades`, `get_corporate_events`,
  `get_13f_holdings`, `get_value_investing_fact`) were never measured on
  either side: a REST route runs no dispatcher, and the wheel's own seam
  attached nothing. They now carry the same block the hosted dispatcher has
  attached to every name-proxied tool since #105 -- `{chars, approx_tokens,
  budget_chars, over_budget}` plus a `hint` when over budget -- measured on
  the filtered payload with the disclosure literals on it, i.e. what ships.
  The budget is the hosted policy number, 32,000 characters, so a consumer
  sees ONE budget on both channels. The name-proxied tools keep the host's
  block and are not measured twice; the four standalone tools are unchanged.
  The hint for a tool with no `limit` says so rather than naming a parameter
  the tool does not have; it is read off the live schema, so a tool that
  gains a `limit` starts being told to use it with no change here. ~~Pagination
  on `get_bdc_holdings` is NOT in this release: the hosted route takes only
  `ticker`, so it is a route change and awaits an OWNER decision.~~ **Struck
  2026-09-22: the decision came back, and it is the next item. The sentence is
  struck rather than deleted so a reader who acted on it can see it changed.**
- **`get_bdc_holdings` takes `limit` and `offset`.** The OWNER ruling on the
  oversize answer above was to make the payload FIT rather than truncate it,
  so the hosted route gained the two parameters and this tool forwards them.
  `limit` / `offset` page the `holdings` rows ONLY: `totalHoldings`,
  `holdingsReturned`, `nonBorrowerRowsExcluded`, `excludedRowsFairValue`,
  `totalFairValue` and its arbitration triple, `weightedAvgPrice`,
  `byLienPosition`, `topIndustries` and `portfolioStructure` all stay computed
  over the whole book, so a page is a window on the rows and never a
  restatement of the filing. A declaring call gets `page` `{limit, offset,
  returned, total, hasMore}` -- where `total` is the served row count, equal to
  `holdingsReturned` -- plus a `completeness` block carrying `total_available`.
  An offset past the end is an empty page with `total` intact, not an error.
  Out-of-range values are REFUSED, never clamped, on both the seam and the
  route. Same key set, same vocabulary and same rules as the `limit` /
  `offset` that `search_bdc_borrower` has taken since 3.5.0.
  **A call that declares NEITHER parameter is byte-for-byte what 3.6.0
  returned** -- neither is sent upstream, so an installed reader sees nothing
  new. Still nothing is ever trimmed to fit: the measurement above reports,
  and the caller decides. Measured on a 325-row book of the real wire shape:
  unpaged ~125,000 characters, `limit=100` ~39,000, `limit=25` ~10,700.
- **`_meta.served_from_cache: true` + `_meta.cache_age_seconds` on a replay.**
  A result served from the wheel's in-process cache used to be
  indistinguishable from a fresh read; an hour of identical replies read as an
  hour of identical data. Both keys appear ONLY on a replay (a fresh result
  carries neither -- absent, not `false`), the age is whole seconds since the
  entry was stored (0 .. the tool's TTL), and the replay minus the two keys is
  byte-identical to the first answer.
- **`ol_federal_contracts`: `recipients` is capped at the TEN largest by
  obligation amount per fiscal-year row, with `recipients_truncated: true` +
  `recipients_total` on a row that had more.** `limit` caps fiscal YEARS, but
  every row embedded every recipient the crosswalk kept (~70 for a defence
  prime, ~150 characters each), so the year count bounded nothing. The cap is
  applied at the hosted READ (the projection every served row passes through),
  not at the ingest or the store, so the full list is still kept; the wheel
  is a name-proxy and follows by construction. `entity_count` is unchanged
  (always the full count). Measured on synthetic LMT-shaped rows: `limit: 5`
  fell from ~55,400 to ~10,200 characters. The tool's description says so on
  both catalogs (TOOLS digest re-derived; prior value in the contract).

### Security
- **The loopback exemption decides an IPv4-mapped IPv6 host by the address it
  wraps, on every supported interpreter.** `OXFORD_LEDGE_URL=http://[::ffff:127.0.0.1]:...`
  with an API key set was accepted as loopback on CPython 3.13+ and refused on
  3.9-3.12, because `IPv6Address.is_loopback` changed in 3.13 to look through
  the mapping and the wheel had inherited whichever answer the consumer's
  interpreter gave (CISO re-seat 2026-09-21, L-10). The wheel now unwraps the
  mapping itself: `::ffff:127.0.0.1` is loopback (the socket reaches the local
  interface) and `::ffff:8.8.8.8` is not, on 3.9 through 3.14 alike. Pinned
  in both directions by the transport-seam contract.
- **A key-carrying loopback request no longer goes to an environment proxy.**
  `urllib.request.urlopen` honours `http_proxy` and, unlike `requests`, has
  no implicit localhost bypass, so with `http_proxy` set and no `no_proxy`
  the plaintext-key loopback exemption delivered `OXFORD_LEDGE_API_KEY` to
  the PROXY in the clear -- for `localhost`, `127.0.0.1` and
  `[::ffff:127.0.0.1]` alike, on both key-carrying legs (CISO read of L-10,
  2026-09-21, amendment A2; measured with a local listener standing in as
  the proxy: the key arrived there and nothing reached the loopback port).
  The two key-carrying legs now open a plain-http (loopback) request through
  an opener with an empty `ProxyHandler`, so it reaches the local interface
  whatever the environment says; `https://` and keyless requests honour the
  environment proxy exactly as before. The README's `http://localhost:10000`
  setup keeps working under a corporate proxy with no `no_proxy` entry.
  Pinned by a contract that runs a local listener as the proxy on both arms.
- **The adjacent address families are pinned as NOT loopback** (same read,
  amendment A1): the IPv4-compatible `[::127.0.0.1]`, NAT64
  `[64:ff9b::7f00:1]` (translated off-host -- the embedded v4 address is not
  the destination) and the unspecified `0.0.0.0` / `[::]` / `[::ffff:0.0.0.0]`
  were all already refused, and the hex spelling `[::ffff:7f00:1]` already
  accepted. No behaviour changed; the classification table now has a red for
  a later "unwrap more forms" change to hit.

### Changed -- BDC mark changes (read layer)
- **`ol_bdc_mark_changes` holds implausible single-quarter moves out of the
  rankings instead of ranking them.** A borrower-grain move of more than
  `filters.max_abs_mark_delta_pts` (15 points) in one quarter, a `latest_mark`
  of exactly 100.00 (fair value equal to par to the cent -- the commitment-
  total shape, not a priced loan) or a prior/latest mark outside
  `filters.debt_mark_band_pts` (30-110, percent of par, at this cut; the
  host narrowed it to 30-105 on 2026-09-24 -- see 3.7.1) now lands in a new
  top-level `suspect_moves` list, each row in the same shape as a ranked row
  plus a `reason` from a closed vocabulary (`mark_at_par_exactly`,
  `delta_exceeds_threshold`, `prior_or_latest_outside_debt_band`;
  `filters.suspect_reasons` carries the sentence for each code). This is a
  QUARANTINE at the read, not a clamp: no stored value changes, and
  `suspect_moves_completeness` counts every held-out row so the ranking says
  what it did not rank. `coverage.covered_detail[*].suspect_moves_found` is the
  per-BDC count. `increases` / `decreases` keep their shape; rows that used to
  rank on a 45-point jump now appear under `suspect_moves` instead.
- **`latest_mark` / `prior_mark` are rounded to 2 dp at emit**, matching
  `mark_delta` (a row read `latest_mark: 89.34989...` beside `mark_delta:
  45.35`).
- **`ol_bdc_top_borrowers` rows carry `holder_count_active` and
  `holder_count_ever`**, summed over the existing `holder_ticker_status` map.
  `holder_count` is unchanged (a wound-down filer's frozen last filing is its
  own latest filing, so it still counts there); the new pair splits it, and
  the `summary` folds the split into a sentence ("... syndicated across 2
  active BDCs (3 ever)") for each affected row. Both are `null` when the
  filer roster could not be checked, never a guessed count.

### Fixed -- government feeds (gov_feeds / mcp_tools_gov)
- **`get_fails_to_deliver`: a `days` window is `days` calendar days.** The served
  window was `[end - days, end]` -- one day wider than the sentence describing
  it -- so a fully loaded 90-day window summarised itself as "91 of the 90
  requested days fall inside the loaded data" (external review, 2026-09-21).
  The window is now `days` days INCLUSIVE, ending at `as_of` or `end_date`:
  `coverage.window_start` and `window.from` are one day later than before,
  `coverage.days_covered` on a fully loaded window equals `days`, and
  `days_before_earliest` + `days_covered` + `days_after_latest` partition the
  window whenever it meets the loaded range. A row dated exactly `days` days
  before the end is no longer inside the window. Pinned on both arms.
- **`get_fails_to_deliver` schema: `end_date` is declared.** The hosted handler
  has honoured `end_date` (the ISO date the window ends on; default the latest
  loaded settlement date) since the window was anchored to `as_of`, and the
  runtime note said "Pass `end_date` to anchor the window elsewhere" -- but
  this package's schema declared `ticker` and `days` only, so the advice could
  not be followed from here. `days` also declares `minimum: 1` and says the
  count is inclusive. Additive.
- **Runtime prose names only tools this package ships.** Three sentences the
  hosted handlers build at runtime, and which ride this package's wire
  verbatim, pointed at names not on it: `get_activist_stakes`' summary said
  "cross-check the 13F view (get_institutional_holders)" (now `get_holders`,
  qualified by channel); `ol_fdic_bank`'s note said "see
  ol_bank_structure_events {cert: N}" (now "the failure / merger record for
  cert N is a hosted-only FDIC structure-events read"); `get_13f_holdings`'
  name-resolution error said "or ol_13f_filer_search" in two places (now "the
  hosted 13F filer search (a name query)"). A contract now scans every
  proxied handler's runtime strings (787 sites across 21 tools at authoring)
  for hosted-only tool names and for parameters this package's schema drops.
- **`get_debt_maturities` description: `source` is the producer's vocabulary.**
  Both surfaces said `'table'|'regex'|null`; the producer has emitted `'xbrl'`
  (its FIRST reader) since the XBRL-first read, and suffixes `_rejected` /
  `_non_usd` onto whichever base produced a ladder a gate then refused. The
  description now lists all three readers and both suffixes, and documents
  the served `filing_date` / `report_date` (the ladder is AS OF the filing)
  and `cross_validated` (present, true, only when the ladder total matched
  the balance sheet; absent otherwise). Pinned to the producer's assignments
  by contract so the two cannot drift again.
- **`get_debt_maturities` gains `summary` with the elapsed-bucket disclosure.**
  A ladder parsed from a 10-K filed 2025-10-31 labels its first bucket
  "2026"; read in September 2026 that bucket is mostly behind the reader. The
  hosted payload now carries a one-sentence `summary` naming the reader that
  produced the ladder, the filing it is as of, and the bucket(s) that have
  wholly or partly elapsed since -- a note rather than a machine key, because
  `summary` reaches this package's wire through the envelope today while a
  new key would be stripped by the fail-closed emit filter until admitted;
  the machine form is the recorded follow-on. Additive.
- **`ol_form_d_raises` schema: `days` declares `minimum: 1` and where the lag
  is.** The handler already falls back to its 365-day default below 1 and
  already names `data_through` when a window is empty by construction; the
  schema now says both. A floor ABOVE 1 (the reviewer's alternative,
  `minimum: 90`) was considered and refused: the posting lag is a property of
  the loaded data -- days behind on the day a quarter's set lands, months
  behind just before the next -- not a constant a schema could state. Additive.
- **Correction at the 3.7.0 bump (2026-09-24): the two `days` minimums above
  are NOT purely additive on this package.** "Additive" was true of the
  hosted catalog and false here: this package validates every declared bound
  before the call, on both transports, so from 3.7.0 `days: 0` (or below) on
  `ol_form_d_raises` and on `get_fails_to_deliver` is REFUSED as
  `INVALID_PARAMS` ("`days`: 0 is less than the minimum of 1"), where 3.6.0
  forwarded it and the host fell back to its default window. Measured on the
  published 3.6.0 wheel and on this cut with the host stubbed. That is the
  "nothing is silently clamped" rule applied to a bound that is newly declared;
  a caller that sends `days` of 1 or more sees nothing new. The two entries
  above keep their wording so a reader who acted on them can see it changed.
- **Corrected at the publish vet (2026-09-24): the `ol_form_d_raises` `days`
  property text.** At the bump it still said "a value below 1 falls back to
  the 365-day default" -- the host handler's behaviour, which this package's
  own `minimum: 1` makes unreachable. It now says to omit `days` for the
  default and that a value below 1 is refused as `INVALID_PARAMS` before any
  request. Description only; the schema and the behaviour are the ones
  described above.

### Changed -- `get_fred_data` carries both halves of the redistribution decision

Until now the only licensing control on `get_fred_data`'s caller-supplied
series id was a DENYLIST: twelve hard-denied ids, plus a word match over the
`notes` / `title` text FRED returns. A denylist cannot see the series nobody
has looked at -- a newly licensed series FRED adds upstream serves until
somebody notices -- and that argument bears harder on a package a third party
installs than on a service its author operates. Two rosters now decide, in
this order, and the second is new:

- **The REFUSED roster grew from 12 ids to 14.** `MORTGAGE30US` (Freddie Mac's
  Primary Mortgage Market Survey -- a GSE, so not a U.S. Government work under
  17 USC 105) and `AAA` (Moody's Seasoned Aaa Corporate Bond Yield) join the
  ICE BofA OAS family, `VIXCLS`, `UMCSENT`, `MICH`, `SP500`, `DJIA` and
  `NASDAQCOM`. Both were previously refused only when FRED's own prose
  happened to carry a licensor word; both are now refused with **no request at
  all**, the marker regex never consulted and nothing cached. If you called
  `get_fred_data` for either id you now get `INVALID_PARAMS` naming the series
  and the rights holder's class, deterministically.
- **A CLEARED roster of 40 reviewed U.S.-federal series is new.** BLS, BEA,
  Census, the Employment and Training Administration, the Board of Governors'
  H.15 / H.4.1 / H.6 / H.10 / G.17 releases, five St. Louis Fed breakeven and spread
  series, and the New York Fed's SOFR. Each entry was reviewed against its
  publisher, and the clearance does two things: a cleared id **serves when
  FRED's metadata endpoint is unreachable** (eight of them -- `JTSJOL`, `PCE`,
  `PSAVERT`, `TOTALSA`, `PERMIT`, `DGORDER`, `ICSA`, `DTWEXBGS` -- are not
  covered by the known-government prefix fallback and used to be refused as
  `unverifiable` on any FRED outage), and the copyright-marker regex **cannot
  refuse it**, because a reviewed entry naming a federal statistical program
  outranks a word match over prose we do not write. That false-positive class
  is measured, not hypothetical: it is the same one that made `MIUR`
  ("Unemployment Rate in Michigan") unservable until 3.4.0.

**What did NOT change, stated plainly rather than left to be discovered.** An
id on neither roster is still decided exactly as before: FRED's metadata is
probed, a copyright notice or a named licensor refuses it, an unknown id is
refused as unknown, and a probe outage falls back to the government prefixes.
So for the long tail this package still runs a denylist, and the hole above is
narrowed rather than closed. Enumerating every public-domain series is not
possible -- FRED carries more than 800,000 -- and a `get_fred_data` that
served only an enumerated 40 would refuse most of the U.S. statistical system
to close a gap the probe already covers. The residual is recorded here so a
reader can judge it instead of inferring a guarantee that is not offered.

The tool's description says all of this on both catalogs (TOOLS digest
re-derived; the prior value is recorded in place in the contract).

### Internal -- no wire change
- **The REST-path tool set is an explicit constant.** The size measurement
  above keys on the nine REST-path tools; the first cut found them at call
  time by reading each handler's source, and the first CI run after it served
  `ESCAPED:OSError` on every REST call from a child process that could not
  read `.py` files. A runtime decision must not depend on source being
  findable, so the set is now stated, and a test-time derivation asserts the
  two agree.
- **`_route_fault`'s docstring names both answers a host gives a failed
  read** -- HTTP 200 wrapping an `error` (handled there, never cached) and
  HTTP 503 + `Retry-After` (raised by the transport as `DATA_UNAVAILABLE`
  carrying `retry_after`, never cached) -- and no longer cites file paths from
  the host's source tree.

## 3.6.0 (2026-09-21)

Everything under this heading landed on `main` after the 3.5.0 publish and
ships in 3.6.0; an installed 3.5.0 has none of it. (It was carried as
`## Unreleased` from the CISO re-seat of 2026-09-21 until the bump, because
this CHANGELOG is GitHub-only and the installed package cannot otherwise
learn of a security-relevant change.) OWNER greenlit the bump + publish in
chat on 2026-09-21 after CISO, CHAOS and COUNSEL each read PUBLISH-WITH-FIXES
and the fixes landed.

**Correction, 2026-09-21.** This section previously read "Every item below is
in the transport or cache seam; **no tool's served keys change**". That was
false twelve minutes after it was written and is false three times over now:
`get_holders` gained the 13F superseded-parent fold on the wire and
`search_bdc_borrower` gained a description correction, all after the sentence
landed. The clause is struck rather than quietly deleted, because a released
changelog that denies the cut's largest wire change is the defect
(delta vet K-1 / C-3). The **Added** section below is that change.

### Added -- `get_holders`: the 13F superseded-parent fold reaches the wire

The hosted route withholds a stale filer row from `holders` when its shares
reconcile within 1% to same-quarter siblings of its own fund-name family (the
Vanguard double count) and records what it withheld. The wheel's reshape
dropped all of it, so a holders table whose fold had run was byte-identical to
one where nothing was ever withheld. Now served, and admitted by the
fail-closed emit allowlist:

- `holders[].stale_quarters` -- the row's distance in quarters from the
  payload's as-of anchor (0 = current). ABSENT, never 0, when the row could
  not be dated.
- `holders[].ahead_quarters` (>= 1) -- present only on a row struck NEWER
  than the anchor, which keeps `stale_quarters` 0 and is otherwise
  indistinguishable from a row AT the anchor.
- `superseded_parents` (top level) -- the withheld rows, in the same shape as
  a served row, each with `superseded`, `superseded_by` (the `fund_cik`s that
  supersede it) and BOTH operands of the reconciliation,
  `superseded_by_shares` (the sibling sum) and `reconciled_pct` (their
  distance apart as a percentage of the withheld row's own `shares`). `[]`
  means the fold ran and withheld nothing among the rows it could date.
  NEVER merge these back into `holders` or any total: that restores the
  double count the fold removes.
- `holders[].fund_cik` and `superseded_parents[].fund_cik` -- the filer's SEC
  CIK. Added 2026-09-21: `superseded_by` is a list of fund_ciks and no row
  carried one, so the attribution named identifiers absent from the same
  document.
- `completeness.supersededReturned` / `completeness.supersededWithheldTotal`
  -- `superseded_parents` is capped at 10 like `holders`, and the cut is
  disclosed with both operands.
- `superseded_parents[].unstated` -- names any part of the verdict the
  producer did not state in a usable form (a non-numeric or non-finite
  operand, a missing `superseded_by`). The part is dropped rather than
  faked, and the row says so instead of asserting a reconciliation with
  nothing behind it.
- `superseded_parents[].also_in_holders` (2026-09-21, delta vet K-7) --
  present only when the withheld row is ALSO in the served list. The two
  lists are built independently, so nothing stopped the same filer appearing
  in both, and for that row the fold did not remove the double count: the
  advice "do not add these rows back into `holders`" is inert when the row is
  already there. Annotated, not dropped -- the disagreement is the producer's
  and the reader is the one who can act on it.
- Top-level `unstated: ["superseded_parents"]` (2026-09-21, delta vet K-9) --
  the producer sent the key in a shape this client could not read (a dict, a
  string, an explicit `null`). It used to collapse to key-ABSENT, which is
  exactly how a host that never folded at all renders; the marker restores the
  one distinction the design exists to preserve. Read it as "the fold did not
  run", never as "the fold withheld nothing".

### Fixed -- `get_holders`: two sentences that were false in the fold's own headline case

Delta vet K-8. Both were true before the fold existed and stopped being true
when it landed:

- `completeness.complete` read `true` beside a non-empty `superseded_parents`,
  because it answered "was every FETCHED row returned" and the withheld rows
  never reach the fetch. A reader asking "is this every filer?" got yes over a
  list the producer had already reduced. It is now `false` whenever anything
  was withheld; `supersededWithheldTotal` beside it says how much.
- An EMPTY `holders` list beside a non-empty `superseded_parents` emitted the
  scope note ("...not evidence that nobody holds X"), which sends a reader
  looking for a coverage gap when the producer returned rows and the fold
  withheld all of them. That case now gets its own sentence naming the fold
  and pointing at the withheld rows. A genuinely empty result still gets the
  scope note.

An installed 3.5.0's fail-closed allowlist STRIPS every key above until the
consumer upgrades; nothing it already reads changes. `MIGRATING.md` carries
the consumer-facing list.

### Fixed -- `search_bdc_borrower` description: `manual` is not an attestation

The `descriptionSource` prose now enumerates all five values, names the three
that suppress the AI-generated flag, and states that `manual` is the store's
DEFAULT and therefore not an attestation of a human author. The label itself
is unchanged -- it is decided producer-side for every channel.

### Security
- **Plaintext-key refusal: the loopback exemption is now an address check,
  not a string prefix.** `OXFORD_LEDGE_URL=http://...` with
  `OXFORD_LEDGE_API_KEY` set is refused (the key would travel in the clear)
  unless the host parses as a loopback ADDRESS (`127.0.0.1`, `127.x.y.z`,
  `[::1]`) or is literally `localhost`. Previously any hostname that merely
  began with `127.` passed, so `http://127.evil.invalid/` carried the key.
  **Config-breaking for one shorthand:** `http://127.1:...` no longer counts
  as loopback (it is not a parseable address); write `http://127.0.0.1:...`.
- Exceptions urllib does not wrap (`http.client.BadStatusLine`,
  `RemoteDisconnected`, `IncompleteRead`, `OSError`, `ConnectionResetError`,
  `socket.timeout`, `ValueError` from `urlopen`) are now caught on all three
  request legs and reported as a bounded `DATA_UNAVAILABLE`; the seam's
  TIMEOUT / INVALID_PARAMS / INTERNAL_ERROR arms bound the upstream text at
  500 characters (a hostile status line could previously reach the client
  at 60,000+ characters).
- **Success-body ceilings, per host.** A success body over its host's
  ceiling is refused before it is read in full -- nothing is parsed, served
  or cached, and the refusal names the ceiling so an operator can tell it
  from an outage. **Correction, 2026-09-21:** this line previously read "a
  success body larger than 8 MB is refused", which described only the three
  Oxford Ledge request legs. Four sibling reads -- SEC submissions, SEC
  companyfacts, SEC's ticker map and FRED -- were unbounded while this
  sentence, the constant's own comment and the vet artifact all read as
  class-extinction (CISO reseat L-1). They are bounded now, and the ceiling
  is PER HOST rather than one reused figure, because SEC companyfacts for a
  large filer legitimately exceeds 8 MB (Citigroup, CIK 0000831001, measured
  8,785,882 bytes on 2026-09-21): reusing the Oxford Ledge number would have
  refused a correct answer for the largest filers. The numbers and the
  measurements behind them live in `oxford_ledge_mcp_core/body_limits.py` --
  8 MB for the operator-configurable Oxford Ledge host, 32 MB for SEC
  companyfacts, 16 MB for SEC submissions, 8 MB for SEC's ticker map, 16 MB
  for FRED (that last one reasoned from the document shape, not measured:
  a keyed FRED request was out of scope).
- `params_accepted` echoes from the host are bounded at 200 characters per
  value on the wheel, matching the hosted bound (previously unbounded on the
  client side). **Correction, 2026-09-21:** this line previously said "per
  DICT value" and named a bare string or a list under that key as an
  uncovered shape. Both were measured passing 5 KB through untouched
  (5,046 and 5,048 characters), and both are now bounded -- a truncated
  string states the length it truncated and a structure is replaced by its
  type and size, so nothing is invented and nothing is amputated
  (reseat L-2 / delta vet K-10). TWO residuals remain, deliberately: an echo
  nested deeper than the walk goes (an uncapped walk over an untrusted body
  is its own defect), and 5 KB under any OTHER `_meta` key (a client that
  rewrote arbitrary host keys would be editing the host's document). Both are
  bounded by the success-body ceiling above, and both are pinned as residuals
  by contract, so a silent change in either direction has to be written down.

### Fixed
- FRED `series` is case-folded in the cache key, so `dgs10` and `DGS10` are
  one entry and one upstream call.
- The cache no longer serves the stored object itself: a consumer that
  mutates a served payload no longer changes what the next caller receives
  (deep copy on both store and serve).
- **The cache has a BYTE budget, not only an entry count** (2026-09-21,
  reseat L-3). It bounded 500 entries and nothing else, which was a fair
  approximation while a response was ~32 KB and stopped being one the moment
  the success-body ceiling sanctioned 8 MB per entry -- 500 of those is a
  number no small instance survives, and an 8 MB body was traced at ~53.7 MB
  peak resident through parse + store-copy + serve-copy. Now: at most 500
  entries AND at most 32 MB of aggregate serialized payload, evicting
  earliest-expiry first. A single result too large for the budget is not
  cached at all rather than emptying the cache for itself, and the call still
  returns normally -- a cache miss is not an error. `cache_stats()` reports
  `bytes` and `bytes_budget`. Disclosed in the README's new
  "Resource limits this client enforces on itself" section.
- **A response nested deeper than the isolation copy can reach is refused by
  NAME** (2026-09-21, reseat L-5). The deep copy added above recurses, so it
  gives up at roughly 500 levels while the allowlist pass tolerates ~1000 and
  the parser more still; that band used to surface as an opaque
  `INTERNAL_ERROR` after the upstream call had already been paid for. The
  band stays refused -- raising the interpreter's recursion limit would trade
  a bounded refusal for a stack overflow, which kills the process rather than
  erroring -- but the refusal now says the response is nested deeper than
  this client will copy, that nothing was served or cached, and that it is a
  property of the document rather than of the caller's arguments.
- A hosted `NOT_FOUND` refusal (a permanent miss, HTTP 404 with
  `code: "NOT_FOUND"`) surfaces as `ToolError.NOT_FOUND` carrying the host's
  sentence, not as a dead-endpoint error. Since 2026-09-21 that sentence is
  FRAMED on all three request legs the way every sibling branch already
  frames an upstream string: the wheel names the subject and the code, and
  the host's words are quoted as data, with newlines collapsed and
  role-marker / fence shapes neutralised. It was relayed bare, which handed
  an operator-configurable host up to 500 characters in the client's own
  voice.

## 3.5.0 (2026-09-14)

Measured against the WHEEL, as 3.4.0 was. Every wire change in this cut is
ADDITIVE or a VALUE correction inside a key that already existed -- no key
is renamed or removed -- and MIGRATING.md carries the consumer-facing list.
Published after the CISO + COUNSEL + CHAOS delta vet of 2026-09-14
(`docs/board/audit/2026-09-14_{CISO,COUNSEL,CHAOS}_wheel_3_5_0_delta_vet.md`
in the monorepo), whose four fix-before-publish items landed in the bump
commit: the hosted bond-directory twin the retired-bond pointers name no
longer serves an identifier per row (its rows carry an identifier-free
`key`), the shape-guard specimens below are synthetic, the borrower
refusal sentence is store-framed, and the version attribution in this file
is corrected where it overstated what reaches an installed 3.4.0.

### Added -- from the external strategic review (2026-09-13, OWNER B5a; wave K / K4)

- **`search_bdc_borrower` takes a declared `limit` / `offset` page on its
  tranche rows.** Additive, gating nothing: a call declaring neither is
  byte-for-byte what it was (every `holders` row, up to the host store's
  5000-row backstop). A call declaring either slices ONLY `holders` -- every
  aggregate, `holdingRowCount`, `priceHistory` and the relatedNorms
  disclosure stay computed over all rows -- and carries `page` {limit,
  offset, returned, total, hasMore} plus a `completeness` block with
  `total_available` (the total is known, so the tool states it rather than
  letting a default guess "at cap, total unknown"). `limit` is 1..5000 and
  `offset` 0..5000 on the inputSchema; an out-of-range value is REFUSED
  with the SDK's sentence on both transports, never clamped; an offset past
  the end is an honest empty page with `total` intact. The wheel pages the
  `/api/bdc/borrower` envelope in-process (that route takes only `q`, and a
  forwarded limit would have been dropped silently -- the `get_13f_holdings`
  `max_holdings` shape) so the wheel and the hosted server slice identically.
  The ambiguous `matches[]` ladder is not paged and no tier was added.

### Changed -- from the external 3.4.0 review (2026-09-13, same day as the publish)

- **The key pointer opens YOUR API KEYS directly.** Every place the wheel
  tells an operator where a key is created (the 402 refusal, the keyless tier
  refusal, this README) now says `https://www.oxfordledge.com/?panel=api-keys`
  -- the deep link that opens the keys panel for a signed-in user -- with the
  in-app route beside it (press K, or click the key icon in the bottom bar).
  It said `/?view=settings`, which is the settings view; the panel is reached
  from the bottom bar, and the settings view only carried a row pointing at
  it (the OWNER's own correction, 2026-09-13).
- **`basis.basisConsistent` is `null`, not `true`, beside a populated
  `basisAdvisory`.** The advisory tier fires on an implied-share jump with no
  issuer refiling to corroborate it; that series is NOT withheld and NOT
  certified single-basis, and a field literally named "consistent" answering
  `true` on a measured 3.8x discontinuity (AAPL 2017->2018 without refiling
  evidence) read as a certification. `null` is the same value the unexamined
  branch already uses, for the same reason; `basisNote` says which case it
  is. `false` stays reserved for a corroborated break that withheld cells.
  Both channels (the wheel's own `split_basis` and the hosted gate the proxy
  serves). The `get_fundamentals` description names the tri-state.
- **The `DATA_KEY_SHAPES` import-time guard tests identifier VALUES, not
  carve-out key NAMES.** A shape admits key values (a CUSIP-keyed dict has
  a nine-character identifier as the key, never the word `cusip`), so a
  future `[A-Z0-9]{9}` shape passed the old name test and would have
  admitted every CUSIP-keyed container. The guard now full-matches every
  shape against one specimen value per licensed class (CUSIP, ISIN, SEDOL,
  LEI, FIGI, the three agency rating formats -- `LICENSED_VALUE_SPECIMENS`)
  and still against the names. The specimens are SYNTHETIC -- shape-valid
  and check-digit-valid, built from the reserved end of each namespace, no
  real issuer's (COUNSEL delta vet W-2: a test value in shipped source is
  held to the same never-leaves-through-the-wheel frame as a wire value).
  No wire change today (a four-digit year cannot spell an identifier); the
  false assurance the next shape would have been added under is gone.

### Changed -- from the external LIVE battery of 3.4.0 (2026-09-13, wave G). The wheel
### proxies the hosted server, so the VALUE fixes below reach an installed 3.4.0 on
### deploy (the credit-quality headline number, the folded Form 4 rows, `summary`
### text, the 503 pass-through); the new KEYS do not -- 3.4.0's fail-closed emit
### allowlist strips every one of them until this cut. Corrected 2026-09-14 (COUNSEL
### delta vet W-4a); the earlier wording ("most of this reaches an installed 3.4.0")
### overstated it.

- **`ol_bdc_credit_quality` had never returned its headline number** for an
  XBRL-path filer (ARCC / FSK / PSEC: `determinate_fv 0.0` on every filing):
  the non-accrual row channel existed only on the HTML path. The host now
  joins each XBRL row to its inline-XBRL `<tr>` by context id and reads the
  footnote marks (ARCC 1.38% of FV vs the 10-Q's own "1.4%"; FSK 3.78% vs
  "3.8%"); `latest.coverage_state` / each trend row's `coverage_state` is
  `none_parsed` | `partial` | `covered`, and the three sentences differ --
  0% coverage is a parser gap, never "withheld".
- **`search_bdc_borrower`**: `relatedNormsStale` lists prefix siblings with zero
  current holders (discovery on key existence; the fully-exited obligor is no
  longer invisible), and the ambiguous `matches[]` list refuses an unmeasured
  total as `totalFv: null` + `totalFvBasis` + `totalFvRefusalReason` (the
  3.4.0 changelog's "all six return sites share one shape" held on the detail
  sites only).
- **`get_insider_trades` / `ol_insider_recent_buys`**: a Form 4 and its 4/A that
  report the same line are served ONCE (the amendment), with `isAmendment`,
  `accessionNumber`, `supersedesAccession`, `formType` on every row; the wheel
  passes the four through. `totalValue` is rounded to cents at ingest.
- **`get_bdc_holdings`**: `parseQuality` (`suspect` when >= 50% of a filing's
  rows carry no borrower identity) + `parseQualityNote`, and
  `portfolioStructureBasis: "all_parsed_rows"` names the row set the structure
  metrics are computed over.
- **`ol_bdc_borrower_dispersion`**: `maturity_date_precision` +
  `margin_suppressed_note` -- a month-precision maturity is partial, not
  missing.
- **`get_activist_stakes`**: `stale` is tri-state with `stale_basis` (`age` /
  `edgar_index` / `no_refresh_evidence`; null when this call gathered no EDGAR
  evidence); rows carry `reports_zero` (the cover page states 0 -- Vanguard's
  2026-01-12 realignment under Release 34-39538, not a sale) and `unparsed`;
  `summary` explains a filed zero.
- **`get_fails_to_deliver`**: `coverage` names both edges of the window
  (`window_end`, `days_covered`, `days_before_earliest`, `days_after_latest`),
  `files_expected` / `files_missing` inside the loaded range, and
  `window_postdates_coverage` is true when a whole un-loaded half-month lies
  inside the window. (The loader itself skipped 40 of 48 SEC periods whose
  zip member has no `.txt` extension -- fixed on the host.)
- **`get_corporate_events`**: `coverage` {rows_stored, oldest_event_date,
  newest_event_date} + `summary` on every payload; an unreachable store
  answers 503 (passed through) instead of `events: []`.
- **`ol_fdic_bank`**: `coverage` {institutions_loaded, active_loaded,
  inactive_loaded, newest_repdte, last_loaded_at, ingest_scope} + `as_of`; the
  not-found sentence is about the loaded store, never the world (Comerica Bank
  filed Form 15 in Feb 2026; "The Huntington National Bank" is found by
  "Huntington").
- **`ol_federal_contracts`**: per-row `period_complete` / `days_elapsed` /
  `days_in_period` + payload `as_of`; `ueis` dropped (it duplicated
  `recipients[].uei` and pushed the payload to 98% of budget).
- **`ol_cftc_cot`**: the description names the THREE curated markets; the
  payload carries `markets_available`.

### Operator -- the stale-install class, third occurrence

- `pip install --upgrade` on a Windows box where the MCP client is running
  fails with WinError 32 (the running `oxford-ledge-mcp.exe` holds its file)
  and pip rolls back, leaving `site-packages/~xford_ledge_mcp-<old>.dist-info`
  stashes. One box carried stashes for 3.1.1, 3.2.0 AND 3.3.0 on the day
  3.4.0 shipped, and an external reviewer probed 3.3.0 answers against this
  changelog. The handshake has carried `serverInfo.version` since 3.2.0; what
  was missing was something that READS it. `tools/smoke_installed_mcp_wheel.py`
  (monorepo) launches the console script a client would launch, drives
  `initialize` + `tools/list` over stdio, and fails with the exact remedy when
  the wire version is not the published one or residue is present. Quit the
  client (or stop every `oxford-ledge-mcp.exe`) BEFORE upgrading; a restart
  alone never upgrades anything.

### Hosted catalog index (2026-09-13, /mcp redesign C6-a; wave M / M1) -- not in the wheel

- The monorepo-only `tools_manifest.py` (excluded from the wheel on purpose) now carries `group` (one of nine), `summary` (a <=120-char index line; the description stays the contract) and `in_pip_subset` (True iff this package's `server_tools.TOOLS` advertises the name -- 24 of the 59 hosted tools at the time, 62 at the 3.5.0 cut; the wheel's other five are PIP_ONLY with no hosted row) on every entry, and `GET /api/mcp/tools.json` rows expose all three beside `requires_key` / `min_tier`; nothing on the wire this package serves changed.

## 3.4.0 (2026-09-13)

Everything in this section is measured against the WHEEL -- the artifact
`pip install oxford-ledge-mcp` delivers -- not against the hosted server.
Hosted-only work that the wheel merely proxies is under its own heading at
the end, so a reader cannot mistake a hosted change for a wheel one (the
3.2.0 vet's K-4 rule: credit only what ships). Note that this file and
MIGRATING.md are GitHub-only -- neither lands in the sdist or the wheel;
README.md is the PyPI long description and is the one to read first.

### 2026-09-13 -- the DELTA re-vet of the wave-D merge (CISO / COUNSEL / CHAOS + skeptic)

Three persona lanes re-read the merged range with tree drives only (zero
live calls) and a skeptic re-drove every non-CLEAN finding. What changed in
the WHEEL as a result:

- `transport._tier_refusal_message`: the host's `upgrade_url` is rendered
  only as a PATH on `https://www.oxfordledge.com` (a foreign or
  protocol-relative URL falls back to `/pricing`), and a tier name is a
  short plain token or the generic phrase -- a compromised or misdirected
  host can no longer put a URL or an instruction sentence into the model's
  context through a 402 (CISO-5; pinned).
- `get_13f_holdings`: the CIK arm is 1-10 ASCII digits (`_13F_CIK_RE`);
  `str.isdigit()` admitted Arabic-Indic digits and a 30-digit "CIK", each a
  guaranteed-404 EDGAR request (CISO-4 / CHAOS-8). Same fork on the hosted
  twin.
- Descriptions corrected to the wire the wheel proxies: `get_capital_
  allocation` now describes the merged hosted scorecard (up to 30
  fiscal-year labels with `periods` and a split-basis `basis` block, a
  10-year summary window, IPO proceeds netted, the TSM refusal shape) --
  it had said "up to 10 fiscal years" (COUNSEL-1); `ol_fdic_bank` no longer
  explains a blank `ticker` with "most banks are not listed" (COUNSEL-6);
  `get_activist_stakes` states the widened `stale` rule and the
  `newest_filing_*` / `fetched_rows` keys (COUNSEL-9); `ol_bdc_credit_
  quality` names `latest.flagged_pct_basis`, `filer_status` and
  `successor_ticker`, and the determinate-gate figure reads "up to 10%
  lower", not "~11%" (COUNSEL-10). README's scorecard row and the
  pyproject storefront sentence follow ("29 tools built on U.S.-government
  public data ... 28 served as filed or as Oxford Ledge derivations of it,
  plus 1 Oxford Ledge-authored quotation corpus" -- "28 government
  sources" had counted six Oxford Ledge parses as sources).

- Schema tightening (CHAOS-4): `get_13f_holdings.max_holdings`,
  `ol_bdc_common_borrowers.min_holders` / `limit` and
  `ol_bdc_mark_changes.limit` are `integer`, not `number`, on both catalogs
  -- a fractional count used to be truncated while `params_accepted` echoed
  the fraction. MIGRATING.md carries the note.

Hosted-side changes visible on the wheel wire (no wheel code): the hosted
seam refuses a 400-digit integer as INVALID_PARAMS again (it had escaped as
a Python OverflowError sentence), bounds the echoed value in every refusal,
refuses `nan`/`inf` for a `number`, and refuses JSON null for a REQUIRED
parameter; the hosted terminal 500 now carries a fixed sentence plus a
reference id instead of the exception text; `ol_ownership_changes` refuses
an unreachable or failed store instead of serving "0 new, 0 increased".

### 2026-09-13 -- the MCP deep audit, wave D (the wheel's share)

The deep audit that followed the publish vet drove every tool on diverse
issuers -- 52/53-week filers, dual-class, the reverse-split cohort, foreign
filers, small BDCs -- and its documentation auditors read every wheel
sentence against the wire (artifact
`docs/board/audit/2026-09-13_DEEP_AUDIT_mcp_functionality_and_docs.md` in
the main repo; this wave's CHAOS artifact
`docs/board/audit/2026-09-13_CHAOS_wave_d_D6_wheel.md`). What changed on the
wheel, per finding:

- **Python 3.9 import** (d2-wheel-prose-1): `fred_tools.py` carried a PEP
  604 union (`int | None`) in a `def` signature with no `from __future__
  import annotations`, evaluated at definition time -- the package could
  not be IMPORTED on the 3.9 floor `pyproject.toml` and README advertise
  (measured on CPython 3.9.25: `TypeError: unsupported operand type(s) for
  |`). Every wheel module now carries the future import and a contract
  ast-scans every shipped file at the 3.9 feature level. The published
  3.3.0 was unaffected (the union landed 2026-09-12).
- `get_insider_trades` (d2-wheel-prose-2): the handler cut the route's
  20-row window to `[:15]` while the description and README said 20; rows
  16-20 were unreachable. It serves the window; `complete` keeps its
  null-when-full meaning and a partial window is complete by construction.
- `get_holders` / `get_insider_trades` (d2-wheel-prose-3): the two
  RESHAPING tools passed the route's `_meta` through verbatim, so
  `derived_fields` named `transactions[].totalValue` over rows that live
  under `trades[].value`, and four `holders[]` QoQ paths the allowlist never
  admits, while the wheel's own `vintages` / `rankingBasis` /
  `transTypeLabel` / `is_open_market` went unnamed. The paths are
  translated at the reshape from a small per-tool map; `source`, `basis`
  and `terms_url` stay the route's.
- `ol_bdc_common_borrowers` (d2-wheel-prose-4): the description said
  "bdc_tickers truncated at 25" while the wheel schema's `maxItems: 25`
  REFUSES a 26th ticker as INVALID_PARAMS (deliberate, vet K-6: a cap is
  declared, not discovered). The sentence says refused.
- The two Plus tools' keyless refusal (d2-wheel-prose-5) and keyed
  refusal (f8-transport-errors-1): keyless, both tools are on the
  clean-core allowlist, so an anonymous call reaches the hosted TIER gate
  and the wheel said "Upgrade at oxfordledge.com/pricing" -- to a paying
  subscriber who had not set the key. Keyed on a lower plan, the message
  was the code word `tier_required` followed by the "do not paste a key"
  warning: tier, sentence and upgrade URL dropped, and the remedy implied
  (check the key) wrong. Both legs now say which tier, and which of the
  two things is missing: keyless -> the client is anonymous and the
  operator sets `OXFORD_LEDGE_API_KEY` (or upgrades); keyed -> THE KEY IS
  VALID and the plan is not, with the host's own sentence and the absolute
  upgrade URL, and no anti-phishing text (there is no key to ask for). A
  bare code token in the host's `error` field never becomes the message
  when a `message` sentence exists.
- README (d2-wheel-prose-6/-7/-9): the body no longer describes 3.4.0 as
  the current build (the version literals stay 3.3.0 until the publish
  bump); MIGRATING.md / CHANGELOG.md are linked by absolute GitHub URL
  (they are GitHub-only, and the PyPI long description had relative
  links to files pypi.org does not host); "every tool is gov-public-data"
  is "28 of 29" with `get_value_investing_fact` named as ol-authored.
- `get_13f_holdings` (d2-wheel-prose-8 / f2-ownership-6 / -7): the
  identifier fork was `isalpha()`, which refused BRK-B / BRK.B BEFORE the
  dot/dash-aware resolver it hands to, and SEC's map has no bare "BRK"
  (BRK-A / BRK-B only) -- so the schema's own example could not resolve.
  A ticker with one class suffix now resolves; the example is BLK /
  BRK-B. The description's "Alphabet A and C both resolve to GOOGL" was
  the PRE-T8 crosswalk; it now says classes may map to distinct tickers
  (GOOGL / GOOG) or, where the crosswalk is still class-blind, to one, and
  that `title_of_class` is the authoritative class.
- `get_fundamentals` (f1-sec-fundamentals-4): the G1 non-controlling-
  interest eviction dropped JNJ's WHOLE StockholdersEquity label -- JNJ
  tags its 10-K equity only on the Including-NCI rung and carries NCI
  concept names, so the parent-only ladder had no annual fact and an
  $81.5B-equity mega-cap served no equity, no coverage row, no note. The
  Including rung is now admitted per period the parent does not serve,
  when the NCI is demonstrably zero there (no non-zero NCI instant, or a
  same-instant parent figure equal to it -- JNJ's are equal at every FY
  end where both exist); a period with a non-zero NCI is withheld ON THE
  WIRE as `{value: null, withheld: "nci_consolidated"}` with
  `equityWithheldNci`, never blanked. AGL's FY2025 (Including rung only)
  is served beside its FY2025 assets. `equityNote` says which rule decided.
- `get_fundamentals` (f1-sec-fundamentals-5): Danaos' 1-for-14 reverse
  split sits inside a 2012-2016 hole in its share/EPS tagging, so the
  10-newest window paired FY2011 (109,045,468, pre-split) beside FY2017
  (7,844,595) under `basisConsistent: true` -- the gate examines
  consecutive pairs and none spans the hole. A wheel-side step after the
  gate withholds the older side of a >= 5x step across a hole as
  `basis_unverified` (values in `withheldValues`, `basis.gapBreaks` +
  `gapNote`, `basisConsistent` false). `coverage[label].contiguous` is new
  and the coverageNote no longer claims "not missing rows".
- `get_fundamentals` (f1-sec-fundamentals-10): the refusal for a US-GAAP
  filer whose fp=FY facts ride Form 6-K in CAD (CNI) names
  `annualFormsSeen` / `unitsSeen` and the USD / 10-K-20-F-40-F scope
  instead of blaming the ladder; the hint names data.sec.gov/submissions.
- `get_fred_data` (f6-macro-events-8): the third-party marker regex
  matched the bare words `michigan` / `russell` / `moody` in a series
  TITLE, refusing public-domain BLS series -- MIUR "Unemployment Rate in
  Michigan", KSRUSS0URN "Unemployment Rate in Russell County, KS" -- as
  third-party-licensed, a same-day regression of the b02-fred-2 remedy.
  The markers are the licensor's NAME now ("University of Michigan",
  "Survey(s) of Consumers", "FTSE Russell" / "Russell <index>",
  "Moody's"); the hard-deny roster is unchanged.
- Descriptions (f3-bdc-core-7 / f4-bdc-derived-18 / f5-gov-feeds-2):
  the ABOVE-PAR TRAP sentence T12 put on `ol_bdc_borrower_dispersion` now
  rides `search_bdc_borrower`, `get_bdc_holdings` and
  `get_bdc_borrower_mark_history` (the same par-basis marks, bare);
  `ol_bdc_credit_quality` names its denominator (`flagged_fv /
  determinate_fv`, never `total_debt_fv`); `get_fails_to_deliver` no
  longer teaches that an empty window is "normal" -- the store's loaded
  settlement-date range bounds every answer.

### 2026-09-12 -- the 3.4.0 publish vet fix wave

The FULL 29-tool audit (CISO + COUNSEL + CHAOS, every tool driven through
the wheel's real dispatcher with route-shaped fixtures; artifact
`docs/board/audit/2026-09-12_CISO_COUNSEL_CHAOS_wheel_3_4_0_publish_vet.md`
in the main repo) returned BLOCK on seven findings and FIX-BEFORE-PUBLISH on
fifty-nine. What changed on the wire, per tool:

- `get_fundamentals` -- **key rename**: the series `TotalDebt` is gone and
  `LongTermDebt` replaces it. It was always `us-gaap:LongTermDebt` with an
  unlabelled `LongTermDebtNoncurrent` fallback -- commercial paper,
  short-term borrowings and (in fallback years) the current portion were
  never in it -- so the old key asserted a total the value did not carry
  (AAPL FY2025 served 90.7B under "total debt" against ~98.7B of debt on
  the balance sheet). A rename in a minor release, because the old key was
  a lie. New top-level `concepts` mirrors `data`: for EVERY served label a
  list `[{period, concept}]` index-aligned with `data[label]`, naming the
  us-gaap concept that served each cell (with a `conceptsNote`), so a series
  that mixes concepts across years is visible; `basis.attribution` names the split-basis block
  as Oxford Ledge's derivation. Ticker resolution now reuses the sibling
  guard (dot/dash fallback, numeric CIK passthrough, INVALID_PARAMS before
  any fetch -- `BRK.B` no longer reads "Could not find CIK"); the
  split-basis gate keys by the full period end, so a 52/53-week filer whose
  fiscal year ends Jan 1-3 cannot collide two fiscal years into one key.
- `get_holders` / `get_insider_trades` -- a route HTTP-200 body carrying
  `error` (PostgreSQL unavailable, a swallowed helper exception) was
  reshaped into `holders: []` / `trades: []` with `completeness.complete:
  true` and cached for an hour: a backend outage shipped as the fact "no
  institutional holders". The route's `error` now passes through,
  `completeness.complete` is null, and the seam never caches a dict that
  carries a string `error`. A legitimately empty result carries a `note`
  naming the scope (holders: 13F-HR COM positions, last 6 quarters;
  trades: the issuer's latest 20 Form 4 rows). `ticker` is required before
  any fetch (a missing ticker used to switch the insider route to its
  market-wide branch and serve other issuers' trades under `ticker: ""`).
- `get_insider_trades` -- `dateBasis` now names the date `date` actually
  carries: 'filing' when `date` is filingDate (every normal row), and
  'transaction' only when no filing date exists. Before, every row said
  'transaction' while serving the filing date. `date` itself is unchanged.
  Rows gain `securityTitle` and `isDerivative` (an RSU grant or an option
  leg no longer reads as a common-stock trade); `pricePerShare` is served
  unrounded (a sub-cent filed price no longer becomes 0.0); `completeness.
  totalFetched` is described as what it is -- the route's 20-row window --
  and `complete` is null when that window was full.
- `get_debt_maturities` / `get_capital_allocation` -- **shape change**: both
  are now NAME-PROXIES of the hosted EDGAR-only tools, the shapes their
  descriptions and allowlists were written for. Until now the wheel proxied
  two REST routes: `/api/debt-maturities`, whose `schedule[].amount` was in
  whole dollars under a description that said "in millions", and which
  fabricated a 15/15/12/12/46% ladder from Finnhub debt totals whenever the
  ticker was not warm in the web app's cache; and `/api/capital-structure`,
  a Finnhub-fed layers snapshot under a description promising a 10-year
  XBRL scorecard (and whose hit branch was unreachable with the real
  provider shape, so the description was false on every call). The wheel
  now serves `{ticker, maturities:[{year, amount}], thereafter, confidence,
  confidence_score, source, validation}` in MILLIONS of USD and `{ticker,
  capitalAllocation:{years, dividends, netBuybacks, netDebtChange,
  acquisitions, sharesOut, isDilutive, summary}}` in whole USD. No vendor
  data reaches the wheel through either tool; both stay Plus-tier.
- `get_corporate_events` -- **key removal**: `events[].id` (the
  corporate_events SERIAL row id) no longer ships; the same row-id class
  stripped from the insider tools on 2026-09-12.
- `get_sec_filings` -- each row now carries `form`, and a top-level
  `completeness` block `{returned, cap: 10, windowRows, windowFrom}` says
  the read covers SEC's most-recent-1000 index only. The description says
  what the 2026-08-10 handler decision already did: absent `filing_type`
  means ALL forms (Form 4 / 144 dominate for large filers), not the four
  the old text listed.
- `get_yield_curve` -- a partial curve (fewer than 11 tenors readable)
  carries `completeness {maturities_total: 11, maturities_missing, reason}`
  instead of shipping silently; an all-fail run says why (credential
  rejected vs transport vs suppressed observation).
- `get_fred_data` -- `series` is validated against FRED's id charset
  before any URL is built and quoted on the observations leg (a `#` in the
  id used to strip the api_key and every other parameter from the outbound
  request); `MICH` is no longer a "known U.S.-government prefix" (the
  University of Michigan is the same non-government licensor UMCSENT is
  refused for) and the in-tree third-party roster is a hard deny; a probe
  HTTP 400 is read ("does not exist" vs a rejected key) instead of being
  treated as "probe unavailable"; `days` is bounded 1..36500; an empty
  observation window carries a `note`; and `name`, `units`, `frequency`
  from FRED's series metadata reach the wire (values were unit-less).
- `get_13f_holdings` -- `changesTotals` / `changesTruncated` (the route's
  own disclosure that a `changes` bucket was cut) now survive the filter;
  an empty `holdings` list carries `error` (no 13F-HR filed / latest could
  not be parsed) instead of a bare `totalValue: 0`; a non-object body and
  a missing `fund` are structured errors, not a bare list or a KeyError;
  `max_holdings` outside 1..500 is refused as INVALID_PARAMS and the schema
  says so.
- `ol_bdc_borrower_dispersion` -- `lenders[].filer_status` and
  `lenders[].successor_ticker` are admitted (the summary already told the
  agent to read them while the filter dropped them).
- **The dispatcher seam** (one change, ~25 findings): a non-dict result from
  any proxying handler raises DATA_UNAVAILABLE and is never cached (23
  tools served a bare `[]` as `isError: false` and cached it); a dict
  carrying a string `error` is served but never cached (26 of 29 cached a
  200-with-error envelope for 3600s, including `get_sec_filings`' 404 /
  empty-window / no-match envelopes -- the 3.3.0 note below that said "a
  failure ... is not cached" was true only of RAISED failures); a 200 whose
  body is not JSON is DATA_UNAVAILABLE on all three legs ("a transport
  problem, not your arguments" -- it used to surface as INVALID_PARAMS with
  the json module's message); 400/422 map to INVALID_PARAMS and 503 to
  DATA_UNAVAILABLE with `retry_after`; the API key is attached with
  `add_unredirected_header` on both legs so urllib cannot forward it on a
  cross-host redirect, and is refused over plain `http://` except to
  loopback; every argument with a schema `minimum` / `maximum` is validated
  BEFORE the call, on both transports, and an out-of-range number is refused
  as INVALID_PARAMS naming the bound (the SDK's own sentence -- the wave's
  first cut clamped-and-served on the built-in loop only, and the re-vet
  measured the two transports answering one call two ways), so the hosted
  completeness block can never say `complete: true` at the cap.
- **Transports**: on the `mcp`-SDK path every wheel error was returned with
  `isError: false` (the built-in loop said `true`); `call_tool` now returns
  an error-flagged result for the ToolError / INTERNAL_ERROR / unknown-tool
  arms, and a contract drives BOTH transports. The built-in loop's
  `tools/list` now applies the derived `[Tier: free|plus]` prefix (it was
  wired only on the SDK path -- the one a bare `pip install` does not use).
- **Every response carries `_meta`** (the README said so since 3.2.0; it was
  true for 14 of 29). The 4 standalone tools attach a wheel-side
  `{source, source_url, terms_url, basis: primary}` table at the dispatch
  seam, kept in vocabulary parity with the hosted provenance registry by a
  contract; the 9 REST-proxied tools inherit the hosted route's provenance
  (see the hosted heading below) and the 16 name-proxies (the 14 keyless ones
  plus the two Plus tools) pass the hosted `_meta` through as before.
- **Descriptions** (27 of 29 changed; digest pin re-derived once): every
  description was re-read against the wire and rewritten where the prose and
  the payload disagreed -- units and row shapes (`get_13f_holdings`,
  `get_bdc_holdings`, `search_bdc_borrower`, `get_bdc_list`,
  `ol_bdc_borrower_dispersion`'s stale UNITS TRAP now points at
  `spread_bps`), empty-branch semantics, what an Oxford Ledge derivation is
  vs the source's figure (the `ATTRIBUTION:` / ol-derived sentence on every
  BDC parse tool and both remaining hybrids), `ol_form_d_raises` stops
  steering a model to a 'filed this week' claim over a QUARTERLY data set,
  `get_activist_stakes` tells the truth about freshness (keyless callers are
  served stored rows and never trigger the refresh; read `stale` /
  `age_seconds` / `refreshed`) and stops advertising `purpose` (nothing
  populates it), `ol_cftc_cot` says the `tff` rows are the Leveraged Funds
  category (the TFF report has no Managed Money column),
  `ol_bdc_borrower_dispersion` no longer claims 'honest-empty when only one
  BDC holds the name' (a single lender is one row), `get_bdc_borrower_mark_
  history`'s `rowCount` is a holding-row count (not tranches), the four
  cross-references to tools the wheel does not ship now say "hosted-only"
  (and no longer name them -- a follower got a bare 'Unknown tool'; the
  wheel's one-ticker insider sibling is `get_insider_trades`), every latency figure is
  gone (false through a proxy hop), and FREE is scoped to "no paywall on the
  hosted channel" (a keyed call still counts toward the agent-API
  allowance).
- **README** (the PyPI long description): the gating claim is now measured
  -- 27 of 29 tools are keyless-reachable (it said 3); the `_meta` sentence
  is true and says where each `_meta` comes from; the four gov feeds are all
  `basis: hybrid` with their derived paths named (it said two, one field
  each); a Data license section quotes the operative terms sentences beside
  the MIT software license; the two transports' agreement is stated; the
  argument-bounds rule is stated once.
- **Package layout, no wire change**: the HTTP transport -- `_api_get` and
  its status ladder, the hosted name-proxy bridge `_api_tool_call` with its
  keyed / keyless legs, the error translation and the attribution /
  not-advice literals -- moved verbatim from `server.py` to a new
  `transport.py` (the third file-size cut of the wave; the standalone SEC
  and FRED handlers had already gone to `sec_tools.py` /
  `sec_fundamentals.py` / `fred_tools.py`). `server.py` re-exports every
  name, so `oxford_ledge_mcp.server.<name>` keeps resolving; `OXFORD_LEDGE_URL`
  / `OXFORD_LEDGE_API_KEY` are still read once in `server.py` and the
  transport consults them per call. Error text, status codes and headers
  are byte-identical.

#### Hosted channel (not in the wheel)

Deployed to the web service BEFORE the wheel publishes; the wheel inherits
them by proxy and ships no code for them.

- `ol_form_d_raises` emits `data_through` / `newest_quarter_loaded` and a
  scoped empty-window sentence ("no filings in the loaded data sets") --
  the store is the SEC's quarterly Form D data set, ~1 quarter behind.
- `middleware/route_provenance` classifies the routes the wheel REST-proxies
  (BDC borrower / holdings / list / mark history, company events, insider
  activity, institutional holders, fund holdings, value investing), so those
  nine tools carry `_meta` with one source of truth; the two routes the Plus
  tools used to proxy are reclassified too (`/api/capital-structure` stops
  citing EDGAR for Finnhub numbers; `/api/debt-maturities` names its
  `finnhub-estimate` branch) even though the wheel no longer reaches them.
- The license-class map follows the OUTPUT axis (COUNSEL R-1): the
  SOI-parse family (`get_bdc_list`, `get_bdc_holdings`,
  `search_bdc_borrower`) is OL first-party; `get_bdc_list` is hybrid; the
  wheel's REST path for `get_13f_holdings` is hybrid (`holdings[].ticker`,
  `holdings[].lots`, `changes`); `get_debt_maturities` is hybrid
  (confidence / validation are our parser's assessment);
  `ol_insider_recent_buys` is hybrid (`buys[].totalValue`, `buys[].position`).
- `get_bdc_list` answers `holdingCount: null` plus a `notice` when the
  store does not answer (it measured zeros over nothing measured);
  `ol_bdc_mark_changes` / `ol_bdc_credit_quality` read with a strict pool
  and refuse on saturation instead of reporting an outage as
  `no_parsed_holdings` / "no non-accrual data".
- `search_bdc_borrower.description` is labelled as a compiled company
  profile with `descriptionSource` (it is citation-reviewed research prose,
  not filing text); `ol_bdc_borrower_dispersion` suppresses serve-time
  yields on rows above par and its empty-branch summary no longer says "it
  may be held by only one BDC"; the hosted completeness default compares
  against the EFFECTIVE limit; the delisted-notice text says only what its
  predicate knows; the corporate-events hosted `derived_fields` are trimmed
  to the one path a live writer derives (`events[].eventType`); the BDC
  holdings "Try refreshing." text is reworded.

### 2026-09-05 .. 2026-09-12 -- the redistribution-boundary arc (corrected)

CISO SECURITY_REVIEW v1 F1-F7, CHAOS P2 items, COUNSEL COMPLIANCE_REVIEW v1
+ the F-4 basis ruling, and the two external MCP field tests of 09-08 and
09-12. Every item below was measured on the released 3.3.0 wheel or the
hosted twin before it was touched; the artifacts live in the main repo
under `docs/board/audit/2026-09-0[89]_*` and `2026-09-1[12]_*`. Seven
sentences in the first draft of this section were measured FALSE for the
wheel by the 3.4.0 vet (CHAOS K-1); each is corrected in place below and
marked `[corrected]`.

- `get_holders` / `get_insider_trades`: neither tool answers with a bare
  empty list any more. When the API replied with a body that was not a
  JSON object, both returned `{"ticker", "holders": []}` /
  `{"ticker", "trades": []}` with no `error` key -- and an agent reads
  `"trades": []` as a fact, so it published "no insider bought or sold"
  about an issuer it had learned nothing about. Both now return the same
  three-key envelope `get_sec_filings` already used on its empty path:
  the collection stays (a client that iterates it still can) and a
  plain-string `error` says what happened. The message describes the
  state that actually occurs -- the endpoint answered with HTTP success
  and the body was a JSON array/string/number/boolean/null rather than an
  object, i.e. a client/server contract mismatch -- and explicitly says
  the empty list is NOT a finding about the issuer. It deliberately does
  NOT say the API was unreachable: every HTTP-status failure and every
  transport failure raises `ToolError` out of `_api_get` and so cannot
  reach that branch, and a "could not reach the API" line would have been
  a fresh false explanation of exactly the class being fixed. The success
  path is byte-identical (pinned against output frozen from the
  pre-change tool). `[corrected]` The first draft said "a class gate now
  fails the build if any `@mcp_tool` handler builds an empty list without
  an `error` key"; the scanner flags dict-LITERAL empty lists in wheel
  handlers and caught exactly one (`tool_get_sec_filings`) -- a
  name-bound `points = []` and the nine passthrough handlers were
  invisible to it. What closes the class is the 3.4.0 seam (above): a
  non-dict result is refused and an `error` envelope is never cached.
- `oxford_ledge_mcp_core.errors`: new `non_object_response()` builds that
  envelope, so the two tools cannot drift into two different sentences.
- `get_fundamentals`: a foreign private issuer is never served as
  `{"data": {}}` at full confidence again (external field report
  2026-09-04, DAC/Danaos -- an agent reading that learns "no
  financials"). Two distinct causes, both closed: (1) a filer that
  reports under US GAAP on Form 20-F/40-F (DAC: 309 us-gaap concepts,
  zero ifrs-full) was dropped by the `form == "10-K"` filter -- the
  series now admits 10-K/20-F/40-F, the same tuple the hosted twin
  admits; (2) an IFRS reporter (companyfacts carries `ifrs-full`, no
  `us-gaap`) now gets a LOUD structured refusal -- `DATA_UNAVAILABLE`
  with `taxonomy: "ifrs-full"`, `ticker`, `cik` and a `hint` naming
  `get_sec_filings` -- instead of the taxonomy-blind "No XBRL data
  found". A payload with neither taxonomy refuses with `taxonomy: null`;
  a us-gaap block whose annual facts match no rung refuses with
  `taxonomy: "us-gaap"`. The ifrs-full ladder itself is deliberately NOT
  added (OWNER licensing gate, `docs/plans/IFRS_XBRL_EXTRACTION.md`). A
  us-gaap 10-K filer's output is byte-identical (pinned).
- `ToolError` (`oxford_ledge_mcp_core.errors`): optional `details`
  mapping, merged into the `error` object by `to_dict()`; the envelope
  keys (`code`, `message`, `retry_after`) cannot be shadowed. Absent
  details leave every existing error byte-identical. The refusal policy
  itself (admitted annual forms, the refusal messages, the hint) is the
  new `oxford_ledge_mcp_core.fundamentals_policy` module.
- Structured-error hatch in the emit filter (`c5a667c4`): a hosted
  `{code, message, retry_after}` error object survives `filter_to_allowlist`
  through the `_ERROR_DETAIL_KEYS` set, so a name-proxied tool's refusal
  reaches the wire with its code rather than being filtered to `{}`.
  `[corrected]` The first draft credited this commit as "Concurrency: the
  per-tool singleflight ... now coalesces outside the pool" -- there is no
  singleflight in any shipped file (it is hosted, `mcp_server.py`); the
  wheel change in that commit was this hatch.
- `[Tier: free|plus]` description prefix on `tools/list` (`39c9eaff`,
  uncredited in the first draft): the tier tag is DERIVED from the
  dispatcher's registry (`min_tier`), never hand-written, so prose cannot
  claim a gate the dispatcher does not apply. Field-test P3: "a model
  can't predict which call will 402". (Wired on the SDK path only until
  the 3.4.0 wave put it on the built-in loop as well.)
- Emit-filter robustness (`e17f8da1`): tuple values are walked like lists,
  an import-time validator refuses a mixed-case allowlist key, and `hint`
  is an envelope key.
- README: the "Available tools" section listed 13 of the 18 tools the 3.3.0
  wheel advertises -- the five BDC reads added on 2026-09-05
  (`get_bdc_holdings`, `get_bdc_borrower_mark_history`, `ol_bdc_top_borrowers`,
  `ol_bdc_borrower_dispersion`, `ol_bdc_common_borrowers`) now have rows, and
  the heading count is contract-derived from the server's `TOOLS` table so it
  cannot drift again. Docs-only; no code change.

External field-test report #2 F5/F6/F7 batch (Pattern-T triage
`docs/board/audit/2026-09-05_PATTERN_T_field_report_2_triage.md`).

- `get_insider_trades` (F5): each trade now carries BOTH
  `transactionDate` and `filingDate`, plus `dateBasis` -- the old chain
  preferred filingDate silently, and the serving pg helper never SELECTed
  `transaction_date` at all (fixed in the main repo the same day). `date`
  keeps the exact value it emitted before (filingDate-preferred) for
  compatibility. `[corrected]` The first draft defined `dateBasis` as
  "'transaction' when the filing supplied a transaction date, else
  'filing'" -- which contradicted `date` on every normal row (the 3.4.0
  BLOCK above); `dateBasis` now names the date `date` carries. Also new:
  `pricePerShare`, `position`, `sharesOwned`, `url` (direct EDGAR
  filing link), a `transTypeLabel` decode of the raw SEC code
  (verified against the ingest writer's 18-code domain),
  `is_open_market` (code P or S), `value` rounded to cents (and, since
  3.4.0, `pricePerShare` NOT rounded), and a `completeness` block
  disclosing the previously-silent [:15] cut -- `[corrected 2026-09-13]`
  the cut itself is gone: the tool serves the route's full 20-row window
  (deep audit d2-wheel-prose-2, below). NOTE: `value` is computed
  at ingest as |shares| x price from the filing's own figures.
- `get_holders` (F5): a `completeness` block (returned / totalFetched
  / totalHolders) discloses the top-10 cut. `[corrected]` The first
  draft said "`asOf` carries the route's `as_of_quarter` when present
  (never invented)"; that was superseded the same week by the T7 bullet
  below (`asOf` survives ONLY when every returned row shares one
  quarter), which is the measured behaviour.
- `get_13f_holdings` (F6): input guard ported from the in-tree twin
  (SEC-F1 shape) -- an all-letters ticker resolves via SEC's public
  company map; a mixed identifier like "BRK.B" is rejected as
  INVALID_PARAMS naming the fix ("provide a numeric CIK"), never
  surfaced as an SEC-availability error. `[corrected 2026-09-13]` the
  class-share forms BRK-B / BRK.B now RESOLVE (deep audit
  f2-ownership-6, above); the rejection is reserved for shapes that are
  neither a CIK nor a ticker. Served `changes[]` entries
  (new_positions/increased/decreased/closed) now carry a resolved
  `ticker` where the hosted API can resolve the CUSIP (the CUSIP
  itself remains stripped per the carve-out), so change entries are
  no longer name-only.
- `get_sec_filings` (F7): the ticker is charset-validated
  (`^[A-Z0-9.\-]{1,10}$`) BEFORE URL interpolation -- URL
  metacharacters are rejected with INVALID_PARAMS instead of being
  interpolated into the outbound EDGAR query string.
- `get_corporate_events` (F7): the `event_type` enum widened in
  lock-step with the route to the emitted 8-K category vocabulary
  (material_agreement, acquisition_disposition, executive_change,
  shareholder_vote, ...) -- the previous 5-value set intersected the
  stored eventType domain at exactly {earnings}, so e.g. "merger"
  matched nothing even where acquisition_disposition rows existed.
- `get_fundamentals` (F7): a `coverage` map disclosing
  `yearsAvailable` per label (series depth is per-concept XBRL fact
  availability, so 6y can sit beside 10y); the data is unchanged.

#### Surface

- **18 -> 29 tools.** Eleven COUNSEL-cleared tools join the pip
  advertisement (all API-key tools; nothing removed, nothing renamed):
  `ol_form_d_raises`, `ol_insider_recent_buys`, `get_fails_to_deliver`,
  `get_activist_stakes`, `ol_treasury_debt`, `ol_cftc_cot`, `ol_fdic_bank`,
  `ol_federal_contracts`, `ol_patents`, `ol_bdc_mark_changes`,
  `ol_bdc_credit_quality`. Each ships with a fail-closed emit allowlist
  seeded from what the tool actually EMITS (captured responses, not SELECT
  lists) and every COUNSEL C2/C3 attribution / strip condition. The pip
  `TOOLS` table moved verbatim to `server_tools.py` (server.py re-exports
  it); the digest pin in the main repo makes any description change a
  deliberate act.

#### The emit boundary (what the wheel will and will not ship)

- **The filter runs centrally.** Twenty handlers called
  `filter_to_allowlist` themselves; nine did not and shipped whatever they
  returned. The dispatcher now applies the table to EVERY tool after the
  handler and before the cache write (idempotent over the twenty), and a
  tool with no allowlist is a CI red in the main repo, not a runtime 500.
  29 of 29 filtered. (`get_capital_allocation` in-tree vs wheel served two
  different shapes under one name until the 3.4.0 name-proxy above; the
  dead REST-shape half of its allowlist and `get_debt_maturities`' are
  pruned with it.)
- **`_meta` survives the filter.** The provenance block (`disclaimer`,
  `terms_url`, `source`, `source_url`, `source_key`, `basis`,
  `delisted_notice`) was in no allowlist and NONE of its keys were envelope
  keys, so the fail-closed filter dropped the whole block on every filtered
  tool -- the attribution COUNSEL's conditions exist to guarantee. Envelope
  keys are now a first-class set beside the per-tool tables. `[corrected]`
  "survives the filter" described the 14 name-proxied tools, the only ones
  that RECEIVED a `_meta` before 3.4.0; the other 15 carry one only since
  the wave above.
- **Dicts keyed by DATA are not field names.** `search_bdc_borrower`'s
  `priceHistory.<BDC_TICKER>[]` and `ol_bdc_top_borrowers`'
  `borrowers[].holder_ticker_status.<BDC_TICKER>` came back as `{}` in the
  released wheel because a ticker is not an allowlisted key. Per-tool
  data-keyed containers are declared (and capped); a dict keyed entirely
  by four-digit years is data by SHAPE (the split-basis gate's
  `withheldValues.<metric>.<year>` and the advisory tier now reach the
  wire); and `_meta.params_accepted`, keyed by the caller's own parameter
  names, is a universal hatch -- it was empty on the way out for 3 of 17
  tools (`get_13f_holdings` lost both `fund` and `max_holdings`, the very
  parameters the echo was written for) and is now bounded on the way in
  (200-char echo cap; caller-meta arguments stripped first).
- **The disclosure literals attach at the dispatch seam** (L-5 Layer 3):
  15 of 29 tools shipped without the disclaimer / attribution sentence
  because the per-handler attach was, again, "remember to". One line in
  `_execute_tool_with_limits`, after the filter and before the cache, with
  setdefault semantics so a hosted `_meta` sentence is never overwritten.
- **`basis: "hybrid"`** (COUNSEL F-4 ruling, 2026-09-12). A payload whose
  substantive values are the cited primary source's, verbatim, EXCEPT an
  enumerable derived subset now says so: `_meta.basis: "hybrid"` with
  `derived_fields` (paths in the tool's own emitted key names; `[]` marks
  list rows) and `derived_basis: "ol-derived"`. `source` / `source_url` keep
  naming the primary source -- that is where the acknowledgment is owed.
  `[corrected]` The first draft listed fourteen hybrids and eight
  ol-derived reclassifications; thirteen of those twenty-two names are not
  wheel tools, and four of the wheel-named ones served no `_meta` at all on
  the wheel wire. What the WHEEL carried on the wire from this ruling:
  four hybrids -- `ol_fdic_bank` (the CERT->ticker map is ours),
  `ol_federal_contracts` (the ticker crosswalk and per-ticker sums, eight
  paths), `ol_patents` (the applicant->ticker resolution), `ol_cftc_cot`
  (`market_key`, `market_label`, `mm_net`) -- and one reclassification to
  `ol-derived`, `ol_bdc_top_borrowers`. The remaining hosted
  classifications reach the wheel only with the 3.4.0 `_meta` work above.

#### Per-tool corrections

- `get_sec_filings`: read the legacy `cgi-bin/browse-edgar` atom feed, which
  SEC now times out server-side (~10s 503 for every ticker), and the
  returned error envelope was CACHED for an hour, so a retry came back
  instantly with the same "check the ticker symbol" advice. Now reads
  `data.sec.gov/submissions` (~0.2s); an HTTP or transport failure RAISES
  and is not cached; the `filings[]` shape is unchanged. `[corrected]` The
  first draft said "a failure names SEC and is not cached" -- the RETURNED
  envelopes (submissions 404, empty window, filter-no-match) were still
  cached for 3600s until the 3.4.0 seam stopped caching any dict carrying
  `error`.
- `get_fundamentals`: (1) an EPS series spanning a stock split is REFUSED
  rather than served -- a split-year 10-K restates only the comparative
  years it displays, so the array sat on two or three share bases with
  every cell individually plausible (NVDA spans three; ServiceNow read
  1.60 -> 1.68, an ordinary year, where the honest comparison is +425%).
  The corpus-calibrated basis-break detector (`split_basis.py`) withholds
  the pre-split cells, carries them into `withheldValues` with the observed
  jump, and says so in `note`; (2) `sharesOut` is a balance-sheet INSTANT
  and lagged the split boundary by one year -- the hosted twin served AAPL
  2018 = 4.75B beside 2019 = 17.77B inside `firstComparableYear`; the
  boundary is now admitted per instant metric only when it corroborates the
  EPS jump (`instantMetrics`, `instantWithheldThrough`,
  `instantObservedJump`, `instantNote`). The wheel's own `DilutedShares` is
  a duration fact and does not share the defect; the no-op is pinned.
- `get_holders` (T7): each row now carries its own 13F `quarter` + `filingDate`.
  `asOf` survives ONLY when every returned row shares one quarter (the
  rows', not the route's mode); otherwise a `vintages` histogram
  (`{quarter, count}` newest-first, null bucket last, sums to `returned`)
  and a `rankingBasis` sentence replace it. A non-empty `coverage` block
  passes through verbatim. Legacy dateless rows leave the payload
  byte-identical.
- `get_13f_holdings` (13F identity): a share class is identity.
  `titleOfClass` is read from the infotable and served as `title_of_class`
  on every holding row and change entry; the CUSIP->ticker resolver sees a
  classed issuer name, so Alphabet A/C and Lennar A/B no longer collapse
  onto one ticker (reflexive overrides for both, because the vendor name
  index is class-blind for them). A never-seen CUSIP whose title carries a
  class no longer takes the bare-name tier -- `None, not a guess`.
  `[corrected]` The first draft credited `get_holders` with the same
  `title_of_class` row field; `get_holders` rows never carried it (the
  route does not emit it and the allowlist does not admit it).
- `search_bdc_borrower`: a search MISS echoed the query back as a resolved
  borrower (`{"borrowerName": "Mozart", "totalHolders": 0}` reads to a model
  as "exists, zero exposure"; Medline's credit entity is Mozart Borrower
  LP). All six return sites share one shape: a hit carries `match_type`, a
  miss and an ambiguous result carry `found: false` (a hit carries no
  `found` key) plus an honest-empty note. `[corrected]` The first draft
  said "an explicit `match_type` / `found`" as if both rode every branch.
  A resolved key now names its sibling keys (`relatedNorms`), and an
  all-stale key refuses its totals (`None` + `aggregatesRefusalReason`)
  instead of reporting 0.
- `get_bdc_holdings`: rows the borrower filter drops are now COUNTED --
  `holdingsReturned`, `nonBorrowerRowsExcluded`, `excludedRowsFairValue`;
  `totalHoldings` is the registry count. One fair-value arbiter now serves
  both `get_bdc_list` and `get_bdc_holdings` (the field test read OXSQ at
  $15.4M on one and $708M on the other; both surfaces carry
  `fairValueBasis` / `reportedTotalFairValue` / `parsedRowSumFairValue`),
  and a refused basis reaches every row-DERIVED aggregate (honest-null with
  `holdingsReconciled: false`), not just the headline scalar.
- `ol_bdc_borrower_dispersion`: serve-time loan yields (`current_yield_pct`,
  `spread_to_maturity_bps`, all-in; SOFR read at serve time, never stored)
  with machine-readable suppressions (non-accrual, pure PIK, unpriced
  floors); and a mark above par is disclosed as a BASIS question
  (`mark_above_par`, `mark_above_par_basis`, `rows_above_par`) -- the
  comparable cost figure is not on this wire, and the note says so rather
  than inventing a ratio.
- `ol_bdc_top_borrowers` / `ol_bdc_common_borrowers`: the borrower filters
  fail OPEN in both halves and now say whether they ran -- a
  `borrower_filters` block (`nonborrower: applied|unavailable`,
  `industry_label: applied|vocab_unavailable`, `industry_vocab_size`,
  `rows_removed`) plus a one-clause note in `summary` only when a half did
  not run. The `ol_bdc_top_borrowers` description no longer promises "clean
  borrowers only" unconditionally.
- `ol_insider_recent_buys`: `buys[].id` (a `form4_transactions` row id,
  measured 1,620,478..) no longer ships on any channel -- it was a
  corpus-size readout on a surface with no account. The same strip now
  applies on the hosted anonymous `/mcp` (the control lived only in the
  wheel, and the wheel is not a trust boundary).
- `get_insider_trades` / `get_holders`: the wheel's reshape never emitted
  the row id either; the allowlist now GUARANTEES it rather than relying on
  the reshape's shape.

#### Docs

- README: the tool count and the capability split (keyless SEC-EDGAR / FRED-
  keyed / keyless-hosted / API-key) are derived from `tool_partition`, not
  typed; the key-creation pointer goes to `/?view=settings` (there is no
  `/account` page); Verify-your-install + Troubleshooting sections from the
  OWNER's field friction log.

## 3.3.0 (2026-09-05)

- Three BDC moat tools promoted into the package as thin name-proxies to
  the hosted MCP dispatch (CISO+COUNSEL+CHAOS publish vet 2026-09-05 +
  OWNER ratification): `ol_bdc_top_borrowers` (most-widely-syndicated
  cross-BDC borrowers), `ol_bdc_borrower_dispersion` (cross-lender
  pricing dispersion for one borrower), `ol_bdc_common_borrowers`
  (borrowers common to a given SET of BDCs). All three are FREE,
  SEC-EDGAR Schedule-of-Investments derived (Oxford Ledge first-party
  parse), and inherit the hosted gate chain by construction. Vet
  conditions closed in this change: transport split (keyed callers POST
  the metered `/api/mcp/tool`; keyless callers POST the anonymous-by-
  design `/mcp` JSON-RPC transport — never a fabricated Origin header);
  hardcoded tool-name literals per handler (tool-identity integrity);
  error translation keyed on the hosted body's `code` field (same-named
  ToolError, hosted message verbatim; an unknown-tool 404 maps to
  NOT_FOUND version-skew, never a data condition); fail-closed emit
  allowlists registered for all three, seeded from the hosted emit
  builders including every nested sub-tree; attribution +
  not-investment-advice travel on every success (hosted `_meta`
  passed through on the keyless leg, the same literals attached on the
  keyed leg); schemas/descriptions copied from the reviewed in-tree
  literals with every cap declared (`bdc_tickers` max 25, `min_holders`
  2..50 on common_borrowers, limit maxima 100/100/200), the
  completeness-block clamp semantics named, and the "<400ms" latency
  claims dropped (false through the proxy hop); the API key rides only
  in the `x-api-key` header, never the URL or any error text.
- `get_corporate_events` advertises the vocabulary the route actually
  accepts (`earnings/dividend/split/merger/all`, lowercase, now a schema
  enum): four of the six previously-documented values 400'd, and even
  "ALL" failed on case. Parity contract-pinned in the main repo
  (`tests/test_mcp_event_vocab_parity_contract.py`).
- `get_fred_data` splits its refusals: a typo'd/unknown series id (FRED
  metadata confirms nonexistence) now says so instead of delivering the
  third-party-licensing lecture; probe-unavailable keeps the fail-closed
  licensing refusal with its own wording. The licensing gate is unchanged.
- `get_sec_filings` no longer surfaces raw parser text ("syntax error:
  line 2, column 61") for a bad ticker -- clean check-the-ticker envelope
  with the exception type labeled as upstream detail.
- The MCP handshake now carries the package version (client UIs display
  it), so a stale install announces itself -- a 3.1.1 field-tested for a
  full session while PyPI served 3.2.0.

- New tool `get_bdc_borrower_mark_history`: a REAL multi-quarter mark
  series for one borrower across every BDC holding its debt -- per-quarter
  min/max/par-weighted marks (percent of par), tranche and holder counts,
  contributing BDC tickers (external field-test F4: the borrower panel's
  `priceHistory` was 8 tranches of ONE quarter, never 8 quarters).
  SEC-EDGAR Schedule-of-Investments derived; ships through the fail-closed
  emit allowlist; exact `borrower_norm` match with an honest-empty note.
- New tool `get_bdc_holdings`: the entity->portfolio read the package
  lacked -- full latest-filing holdings for one BDC (borrower, lien, rate,
  maturity, par/cost/fair value, mark) plus portfolio structure metrics,
  proxying the existing `/api/bdc/holdings` route (`ticker`-only, the
  route's real signature). Emit-allowlisted; `byLienPosition` is
  deliberately not emitted (data-keyed dict vs the key filter -- the
  per-row `lienPosition` carries the same information).

- `get_13f_holdings` no longer declares `min_tier="plus"` (OWNER ruling
  2026-09-05): the 13F surface is free product-wide -- the backing routes
  carry no tier gate and the 13F pages are public. The declaration was a
  false paywall (the package 402-refused calls the server serves freely);
  found by an external field test, parity now contract-pinned in the main
  repo (`tests/test_mcp_package_tier_parity_contract.py`).

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
