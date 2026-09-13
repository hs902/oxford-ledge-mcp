# Changelog

All notable changes to `oxford-ledge-mcp` are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
