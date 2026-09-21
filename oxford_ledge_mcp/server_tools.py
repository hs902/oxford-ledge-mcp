"""The pip package's own MCP tool advertisement (the `TOOLS` list).

EXTRACTED FROM server.py 2026-09-08 (file-size-budget cut). This module
holds the list VERBATIM -- same entry order, same key order, same strings
-- and server.py re-exports it, so `from oxford_ledge_mcp.server import
TOOLS` and `oxford_ledge_mcp.server.TOOLS` keep their exact prior value.
The wire is unchanged by construction; the byte-equality of the canonical
serialization is pinned by
tests/test_mcp_server_tools_manifest_contract.py.

WHY THIS IS A SEPARATE MODULE FROM tools_manifest.py (one character apart,
deliberately different in kind -- read this before touching either):

  * THIS file (server_tools.py) is the PUBLISHED package's advertisement.
    It ships in the wheel. It is what an agent sees from list_tools after
    `pip install oxford-ledge-mcp`, and every name in it must have a
    handler in server.py.
  * tools_manifest.py is a GENERATED, monorepo-only projection of the root
    mcp_tool_definitions.py carrying the full hosted catalog (the ol_*
    moat set). tools/export_mcp_package.py EXCLUDES it from the wheel on
    purpose; do not merge the two, and do not add this file to that
    exclusion set -- the package ImportErrors at boot without it.

The banner explaining WHY the two lists differ stays in server.py, beside
the @mcp_tool handlers it also describes.

DESCRIPTION HONESTY PASS (2026-09-12, the 3.4.0 publish vet -- the FULL
29-tool audit, artifact in the main repo).
Every description below was re-read against the wire the wheel actually
serves (each tool driven through the real dispatcher with route-shaped
fixtures) and rewritten where the prose and the payload disagreed: units,
row shapes, empty-branch semantics, what is Oxford Ledge's derivation vs
the filer's / the agency's figure, which sibling tool the wheel really
ships, and what "FREE" means on a keyed call. Latency claims are gone from
every description (false through the proxy hop), and no description names
a tool the wheel does not advertise (the sentence says "hosted-only"
instead). The per-tool ledger and the contract that pins these invariants
live in the main repo beside the vet artifact.
"""

from __future__ import annotations

TOOLS = [
    # ── Core company data (API-mode via OXFORD_LEDGE_URL; Y1 2026-04-24) ──
    {
        "name": "get_holders",
        "description": (
            "Top 10 institutional shareholders of a stock from SEC 13F-HR "
            "filings -- common-stock (COM) positions only, one row per filer at "
            "that filer's LATEST 13F within the last 6 quarters, ranked by "
            "reported dollar value. Returns {ticker, holders, completeness}; "
            "each row is {holder, fund_cik (the filer's SEC CIK, when the "
            "filing carries one -- it is what `superseded_by` below names), "
            "shares, value (whole USD, as reported at the "
            "filer's own period-end), type, quarter, filingDate}. Because rows "
            "are each filer's latest filing, one call can mix quarters: `asOf` "
            "is present only when every returned row shares one quarter; "
            "otherwise `vintages` lists {quarter, count} over the returned rows "
            "and `rankingBasis` says the ranking is not price-normalised. "
            "`coverage` (when present) is the single-quarter 13F snapshot: its "
            "`quarter` is the honest as-of anchor. Each row's `stale_quarters` "
            "is its distance from that anchor (0 = current; the key is ABSENT, "
            "never 0, when the row could not be dated); a row struck NEWER "
            "than the anchor keeps `stale_quarters` 0 and adds "
            "`ahead_quarters` (>= 1, absent otherwise), which is the only "
            "thing separating it from a row AT the anchor. A stale filer whose "
            "shares reconcile to same-quarter siblings of its own fund-name "
            "family is WITHHELD from `holders` and recorded in "
            "`superseded_parents` -- the same row shape plus `superseded: "
            "true`, `superseded_by` (the `fund_cik`s of the rows that "
            "supersede it; each served row carries `fund_cik`, so the "
            "reference resolves inside this same payload whenever the "
            "superseding row survived the top-10 cut) and BOTH "
            "operands of the reconciliation: the row's own `shares`, "
            "`superseded_by_shares` (the sibling sum) and `reconciled_pct` "
            "(their distance apart AS A PERCENTAGE OF THE WITHHELD ROW'S OWN "
            "`shares`), so the verdict states its arithmetic "
            "instead of asserting it. When the producer did not state one of "
            "those parts in a usable form, that key is ABSENT and the row "
            "carries `unstated` naming it -- read such a row as a withholding "
            "whose arithmetic or attribution is missing, never as a "
            "reconciled one. A withheld row that is ALSO present in `holders` "
            "carries `also_in_holders: true`: the two lists are built "
            "independently, so for that row the fold did NOT remove the double "
            "count -- it is already in the served table, and counting the "
            "withheld copy as well doubles it again. If the whole key "
            "`superseded_parents` is missing while the top level carries "
            "`unstated: [\"superseded_parents\"]`, the producer sent the key "
            "in a shape this client could not read: treat the fold as NOT "
            "RUN rather than as having withheld nothing. "
            "`superseded_parents` is capped at 10 like "
            "`holders`, and `completeness.supersededReturned` / "
            "`completeness.supersededWithheldTotal` disclose that cut. `[]` "
            "means the fold ran and withheld nothing AMONG THE ROWS IT COULD "
            "DATE: a row carrying no `stale_quarters` was never eligible to "
            "be folded and is served in full, so an `[]` beside undated rows "
            "is not a finding that no double count exists -- the wire cannot "
            "distinguish the two cases. Do NOT add those rows "
            "back into `holders` or into any total: that restores the "
            "double count the fold removes. `vintages`, `rankingBasis`, "
            "`coverage`, `stale_quarters`, `ahead_quarters` and the "
            "`superseded_parents` fold "
            "are Oxford Ledge computations over the 13F rows; "
            "the rows themselves are the filings' figures. The `completeness` "
            "block discloses the top-10 cut against the total holder count. An "
            "EMPTY `holders` list comes with a `note` naming the scope (13F-HR "
            "COM positions, last 6 quarters; the ticker must be in the 13F "
            "universe) -- a scoped statement, not proof that nobody owns the "
            "stock. When `holders` is empty because the fold withheld every "
            "row the producer returned, the `note` says THAT instead: the "
            "result is not empty and not a coverage gap, and the withheld "
            "rows are in `superseded_parents`. `completeness.complete` is "
            "`false` whenever anything was withheld -- it answers \"is this "
            "every filer\", and the fold reduced the list before this client "
            "saw it. If the API answers with an error body, its `error` string "
            "is passed through and `completeness.complete` is null: read "
            "`error` before reading `holders`. `ticker` is required. "
            "[Requires API mode]"),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol"}
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_sec_filings",
        "description": (
            "The 10 most recent EDGAR submissions for a company, of ANY form "
            "(Form 4 and Rule 144 notices dominate for large filers), unless "
            "`filing_type` narrows it to one exact form plus its /A amendments. "
            "Returns {ticker, filings, completeness}; each row is {form, title, "
            "date, url} (date = filing date; url = the EDGAR document). "
            "`completeness` is {returned, cap: 10, windowRows, windowFrom}: the "
            "read covers only SEC's most-recent-1000 submissions index for the "
            "filer (`windowRows` rows, back to `windowFrom`), so a filtered read "
            "can return fewer than 10 rows and nothing older than `windowFrom` "
            "is visible through this tool. An empty `filings` list carries an "
            "`error` string naming the window. Fetched directly from "
            "data.sec.gov (no key needed); cached 1h."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol"},
                "filing_type": {"type": "string", "description": "Filing type filter (10-K, 10-Q, 8-K, etc). Optional."},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_insider_trades",
        "description": (
            (
            "Form 4 insider transactions for one issuer -- the latest 20 rows by filing date (the "
            "route's window), every SEC transaction code (P/S/A/M/F/G ...), from Oxford Ledge's "
            "Form 4 ingest of SEC EDGAR. Returns {ticker, trades, completeness}; each trade is "
            "{insider, position, shares, pricePerShare, value, sharesOwned, type, transTypeLabel, "
            "is_open_market, securityTitle, isDerivative, transactionDate, filingDate, dateBasis, "
            "date, url}. `date` is the filing date when the filing carries one, and `dateBasis` "
            "names the date actually served ('filing' when `date` is filingDate, 'transaction' "
            "only when no filing date exists) -- read `transactionDate` for when the trade "
            "happened. `type` is the raw SEC code, `transTypeLabel` its decode, `is_open_market` "
            "is true only for codes P and S. `shares` is SIGNED (negative on dispositions); "
            "`pricePerShare` is the filed price unrounded (4 dp); `value` = |shares| x price, "
            "computed by Oxford Ledge at ingest from the filing's own figures; both are null when "
            "the filed price failed the ingest plausibility gate or the filing carried none. "
            "`position` is the filer's reported title, or Officer / Director / 10% Owner / "
            "Insider when the filing left it blank. Rows with `isDerivative` true (RSU awards, "
            "option legs, notes; `securityTitle` names the instrument) carry derivative-security "
            "counts and exercise prices, not common-stock trades -- do not add them to share "
            "counts. `url` is the EDGAR filing document for current rows and the issuer's Form 4 "
            "index for legacy rows. `completeness` is {returned, totalFetched, complete}: "
            "`totalFetched` is the route's 20-row window, not the issuer's total, and `complete` "
            "is null when the window was full (older filings exist beyond it). An empty `trades` "
            "list carries a `note` naming the scope; an API error body passes through as `error` "
            "with `completeness.complete` null. `ticker` is required. Each row also carries "
            "formType (the Form 4 type as filed, '4' or '4/A'), accessionNumber (the filing), "
            "isAmendment (true for a 4/A; null when the store holds no form type), and "
            "supersedesAccession: a Form 4 and its 4/A that report the SAME line (identical "
            "filer, date, code, shares, price, shares-owned-after, security title and derivative "
            "flag) are served ONCE, as the amendment, with supersedesAccession naming the folded "
            "original -- so summing shares or value over the list no longer double-counts an "
            "amended filing. A 4/A that CORRECTED a value is a different line and is served "
            "beside its original; isAmendment says which is which. [Requires API mode]"
        )),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol"}
            },
            "required": ["ticker"],
        },
    },
    # ── SEC EDGAR tools (standalone via direct API) ──
    {
        "name": "get_fundamentals",
        "description": (
            "XBRL-parsed annual financial statements for one ticker, fetched "
            "directly from SEC EDGAR companyfacts (10-K, 20-F and 40-F filers "
            "reporting under US GAAP in USD; an IFRS reporter gets a structured "
            "DATA_UNAVAILABLE refusal naming `taxonomy`, and a Canadian MJDS "
            "filer whose XBRL is furnished on Form 6-K in CAD (CNI) is refused "
            "with `annualFormsSeen` / `unitsSeen` naming why). Returns {ticker, "
            "data, concepts, coverage, coverageNote, basis}. `data` maps each "
            "label -- Revenue, NetIncome, EPS, DilutedShares, TotalAssets, "
            "TotalLiabilities, StockholdersEquity, OperatingCashFlow, "
            "LongTermDebt -- to up to 10 annual points {period (the fiscal-"
            "period END date), value}, newest first. UNITS: whole USD; EPS is "
            "USD per share; DilutedShares is a share count. `LongTermDebt` is "
            "us-gaap:LongTermDebt with a LongTermDebtNoncurrent fallback -- it "
            "is NOT total debt (commercial paper, short-term borrowings and, in "
            "fallback years, the current portion are excluded); the pre-3.4.0 "
            "label `TotalDebt` was this same series under a false name. "
            "`StockholdersEquity` is the parent-only rung; for a filer that "
            "tags non-controlling interests, the consolidated rung (...Including"
            "PortionAttributableToNoncontrollingInterest) fills a period only "
            "when its NCI is demonstrably zero there (JNJ tags its 10-K equity "
            "ONLY on that rung), `equityNote` says so, and a period with a "
            "non-zero NCI and no parent figure is withheld as {value: null, "
            "withheld: 'nci_consolidated'} with the NCI in `equityWithheldNci`. "
            "`concepts` mirrors `data`: for EVERY served label, a list "
            "[{period, concept}] index-aligned with data[label], naming the "
            "us-gaap concept that served each cell, so a series that mixes "
            "concepts across years is visible (`conceptsNote` explains the "
            "fallback rung). `coverage` discloses per label {yearsAvailable "
            "(per-concept XBRL depth, counted before any withholding), "
            "contiguous} -- contiguous=false means the served periods skip at "
            "least one fiscal year (a tagging hole), so neighbouring rows are "
            "not year-over-year. `basis` is Oxford Ledge's split-basis check: "
            "an EPS or DilutedShares series that spans a stock split is "
            "withheld on the pre-split side ({value: null, withheld: "
            "'split_basis'}) with the withheld values, the observed jump and "
            "the reasoning in `basis` (basisConsistent true = examined, one basis; false = a "
            "corroborated break, cells withheld; null = unexamined, OR an implied-share jump "
            "with no issuer refiling listed in basisAdvisory -- nothing withheld, nothing "
            "certified, basisNote says which); a >= 5x step across a tagging hole that "
            "no examined year pair spans (DAC's 1-for-14 inside its 2012-2016 "
            "hole) withholds the older side as {value: null, withheld: "
            "'basis_unverified'} with `basis.gapBreaks` / `gapNote`; and "
            "`basis.attribution` names that block as Oxford Ledge's derivation "
            "over the filed facts -- every other value is the filing's, "
            "verbatim."
            " NOTE: for investment companies (BDCs, closed-end funds), OperatingCashFlow"
            " is routinely NEGATIVE because portfolio purchases run through operating"
            " activities under ASC 946 -- it is not a distress signal there."
            " No key needed; cached 1h."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol (e.g. AAPL)"}
            },
            "required": ["ticker"],
        },
    },
    # ── Bond / credit tools (standalone via FINRA TRACE) ──
    # ── Macro / economic tools (standalone via FRED) ──
    {
        "name": "get_yield_curve",
        "description": (
            "Current U.S. Treasury constant-maturity yield curve read directly "
            "from FRED's DGS series (1M, 3M, 6M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y, 20Y, "
            "30Y). Returns {yield_curve: {tenor: percent}, as_of: {tenor: "
            "observation date}, source}; values are PERCENT numbers (4.18 means "
            "4.18%), the newest non-suppressed observation per tenor. "
            "include_history=true adds `yield_curve_1y_ago` (the FRED "
            "observation nearest one year before each tenor's as_of, within a "
            "45-day tolerance; empty when none qualifies) and "
            "`history_coverage` {maturities_with_prior, maturities_total, "
            "lookback_tolerance_days}. When fewer than 11 tenors could be read, "
            "a `completeness` block {maturities_total: 11, maturities_missing, "
            "reason} says which are missing and why; a curve with no readable "
            "tenor raises DATA_UNAVAILABLE naming the cause. Verbatim FRED "
            "values, nothing derived. Requires FRED_API_KEY; cached 1h."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "include_history": {"type": "boolean", "description": "Include yield curve from 1 year ago for comparison (default false)"}
            },
        },
    },
    {
        "name": "get_fred_data",
        "description": (
            "One FRED series' observations, read directly from the FRED API. "
            "Returns {series, name, units, frequency, data, count}; `data` is "
            "[{date, value}] NEWEST FIRST over the trailing `days` calendar "
            "days (default 365, 1..36500), `count` is len(data), and `name` / "
            "`units` / `frequency` come from FRED's series metadata -- units "
            "vary BY SERIES (GDP is billions of dollars, UNRATE is percent), so "
            "read `units` before comparing anything. An empty window carries a "
            "`note` saying the window returned no observations (a quarterly "
            "series with a short `days`, or all-suppressed newest cells) -- not "
            "that the series has no data. Series ids must match FRED's id "
            "charset (^[A-Z0-9_.-]{1,40}$); anything else is refused with "
            "INVALID_PARAMS before any request is made. U.S.-government / "
            "public-domain series only: a series whose FRED metadata carries a "
            "third-party copyright notice or a named licensor (S&P Dow Jones, "
            "ICE BofA, Moody's, CBOE, University of Michigan ...) is refused "
            "with INVALID_PARAMS -- a BLS/BEA series whose title merely "
            "contains such a word (MIUR, 'Unemployment Rate in Michigan') is "
            "served -- and an id FRED does not know is refused as unknown. "
            "Requires FRED_API_KEY; cached 1h."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "series": {"type": "string", "description": "FRED series ID (e.g. GDP, UNRATE, CPIAUCSL, DFF); must match ^[A-Z0-9_.-]{1,40}$"},
                "days": {"type": "integer", "description": "Number of calendar days of history back from today (default 365; 1..36500)", "minimum": 1, "maximum": 36500},
            },
            "required": ["series"],
        },
    },
    # ── Short interest (API-mode via OXFORD_LEDGE_URL; Y1 2026-04-24) ──
    # ── API-mode tools (require OXFORD_LEDGE_URL) ──
    {
        "name": "get_corporate_events",
        "description": (
            (
            "The 20 most recent 8-K item events for a ticker from Oxford Ledge's 8-K index of SEC "
            "EDGAR, NEWEST FIRST -- a fixed window with no caller-settable limit, so a "
            "recent-events feed, not a history. Returns {ticker, count, events, coverage, "
            "summary}; `coverage` = {rows_stored, oldest_event_date, newest_event_date} is what "
            "the store holds for the ticker regardless of the filter, and `summary` says why a "
            "result is empty (nothing indexed for the ticker vs the filter matched none of the N "
            "stored); each event is {ticker, eventDate, eventType, headline, description, amount, "
            "counterparty, counterpartyTicker, status, source, sourceUrl}. `eventType` is Oxford "
            "Ledge's 8-K item-to-category map (the one derived field; e.g. Item 1.01 -> "
            "material_agreement, Item 2.02 -> earnings, Item 5.02 -> executive_change); "
            "`headline` is the SEC item title; `description` is an excerpt of the filing text; "
            "`sourceUrl` is the EDGAR filing. `amount`, `counterparty`, `counterpartyTicker` and "
            "`status` are UNPOPULATED today (always null -- no writer fills them). No row id "
            "ships. `event_type` filters on the stored category; dividend / split / merger are "
            "accepted for compatibility but no 8-K writer emits them (for M&A use "
            "acquisition_disposition). An unreachable store REFUSES (the route answers 503 with "
            "an error body, passed through) rather than serving events=[]. `ticker` is required. "
            "[Requires API mode]"
        )
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol (e.g. AAPL)"},
                # 2026-09-05 (field-test F8, Pattern-T CONFIRMED): the prior
                # advertised vocabulary (acquisition/divestiture/executive_change/
                # restructuring/ALL) matched NOTHING the route accepts -- four of
                # six documented values 400'd, and even "ALL" failed (the route
                # is lowercase-only). This enum IS the route's _VALID_EVENT_TYPES;
                # parity contract-pinned in the main repo.
                # 2026-09-05 later same day (field-report-#2 F7-events): the
                # route set itself was widened to the emitted 8-K category
                # vocabulary -- the old 5-value set intersected the STORED
                # eventType domain at exactly {earnings}, so "merger" returned
                # nothing even where acquisition_disposition rows existed.
                # Enum = the route's widened _VALID_EVENT_TYPES (three-way
                # parity: emitted <= route == this enum, pinned by
                # tests/test_mcp_event_vocab_parity_contract.py).
                "event_type": {"type": "string",
                               "enum": ["all", "earnings", "dividend", "split", "merger",
                                        "material_agreement", "material_agreement_termination",
                                        "bankruptcy", "acquisition_disposition",
                                        "new_debt_obligation", "debt_obligation_trigger",
                                        "material_impairment", "delisting", "auditor_change",
                                        "financial_restatement", "change_of_control",
                                        "executive_change", "bylaw_amendment",
                                        "shareholder_vote", "reg_fd_disclosure", "other_event"],
                               "description": (
                                   "Optional filter (lowercase, case-sensitive). 8-K item "
                                   "categories (material_agreement, acquisition_disposition, "
                                   "executive_change, shareholder_vote, ...) are what the "
                                   "8-K writers actually store; dividend/split/merger are "
                                   "accepted for compatibility but no 8-K writer emits them "
                                   "today -- for M&A use acquisition_disposition. Use all "
                                   "(or omit) for every type.")},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "search_bdc_borrower",
        "description": (
            (
            "Which BDCs lend to one private-credit borrower, matched fuzzily on name -- Oxford "
            "Ledge's parse of SEC EDGAR BDC schedules of investments (ol-derived: canonical-name "
            "pick, borrower normalisation, group merge, current-holder aggregates), not "
            "filer-published data. Envelope: borrowerName, borrowerNorm (the canonical key "
            "get_bdc_borrower_mark_history and the ol_bdc_* tools take), description, "
            "descriptionSource, industry, totalHolders, totalParAmount, totalFairValue, "
            "avgMarkedPrice/min/max, match_type, units, and `holders` -- one row per TRANCHE "
            "(bdcTicker, bdcName, filingDate, securityType, lienPosition, interestRate as filed, "
            "maturityDate, parAmount, fairValue, markedPrice, stale, staleBasis, holderStatus, "
            "successorTicker). `units` says it: USD; markedPrice is percent of par. ABOVE-PAR "
            "TRAP: markedPrice (and the avgMarkedPrice / min / max aggregates over it) is fair "
            "value over the FILED principal, and filers differ on what principal tracks -- par "
            "may exclude capitalised PIK/OID accretion, or the filer's principal field may equal "
            "cost -- so a row marked above 100 (Caitec at 145.74 is the measured case) is a "
            "par-basis artifact until fairValue is checked against cost, NOT a credit premium. "
            "`description` is a compiled company profile (public sources, citation-reviewed), NOT "
            "filing text -- `descriptionSource` names its writer. Five values: `csv`, `wellknown` "
            "and `template` are Oxford Ledge's static directory writers, and for those `_meta` "
            "carries NO `ai_generated` flag; anything else -- the research-seed tag, `manual` "
            "(the store's DEFAULT when a writer was not stated, so NOT an attestation of a human "
            "author), or an ABSENT source -- is served with `_meta.ai_generated: true`. Read that "
            "flag as WRITER NOT ESTABLISHED, not as proof the text is model-written: "
            "over-labelling a one-line profile is the cheap error, under-labelling model prose is "
            "not, so the flag is deliberately conservative and `_meta.ai_generated_note` says "
            "which entries are known to be model-written. `priceHistory` holds "
            "ONE quarter per BDC -- not a time series; use get_bdc_borrower_mark_history. "
            "AGGREGATES count CURRENT holders only (aggregatesBasis 'current_holders_only'): a "
            "row filed before that BDC's latest filing (staleBasis 'exited_position') or by a "
            "wound-down filer (staleBasis 'inactive_filer') stays in holders with stale=true but "
            "is excluded, so `holders` can have more rows than totalHolders; "
            "staleRowCount/staleHolderCount count them. All rows stale -> "
            "totalParAmount/totalFairValue null (not 0) with aggregatesRefusalReason; marks stay "
            "in holders[].fairValue. RELATED KEYS: a hit is ONE borrower_norm key, not "
            "necessarily the whole obligor; relatedNorms lists other keys sharing its prefix with "
            "current holders ({borrowerNorm, borrowerName, holderCount, holdingRowCount, "
            "totalFv}; relatedNormsBasis 'prefix_of_resolved_key'; [] when none). "
            "relatedNormsStale lists prefix siblings with ZERO current holders (every row exited "
            "or filed by an inactive filer): holderCount 0, totalFv null (not measured on the "
            "current basis), holdingRowCount as stored; [] when none. Discovery is on key "
            "existence -- a fully-exited obligor still shows the other keys it is filed under. In "
            "the ambiguous `matches[]` list every candidate carries totalFvBasis "
            "'current_holders_only', and a candidate with stored rows but no current holder "
            "carries totalFv null with totalFvRefusalReason -- never 0. A brand and its 'X "
            "Acquisition, LLC' vehicle can be separate keys: check it before reading totalHolders "
            "as the lender count, and query ol_bdc_borrower_dispersion per key. A MISS returns "
            "{found: false, match_type: null, message} -- a search miss, not a finding of no BDC "
            "exposure; ambiguous: {found: false, ambiguous: true, matches: [...], holders: []} -- "
            "re-call with a specific name (matches[].holderCount/totalFv are latest-filing-only). "
            "A hit carries match_type and no `found` key. Debt and equity included. PAGING "
            "(additive): `limit` / `offset` page the `holders` rows only -- every aggregate, "
            "holdingRowCount, priceHistory and relatedNorms stay computed over ALL rows; a call "
            "declaring either gets `page` {limit, offset, returned, total, hasMore} and a "
            "`completeness` block with total_available; an offset past the end is an empty "
            "page with total intact; out-of-range values are REFUSED, never clamped; a call "
            "declaring neither is unchanged (every row, up to the store's 5000-row backstop). "
            "Source: SEC EDGAR BDC schedules of investments (Oxford Ledge parse, ~45-60 day "
            "lag). [Requires API mode]"
        )
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Borrower/company name to search (e.g. Finastra, Medline)"},
                "limit": {"type": "integer", "description": "Max `holders` rows to return (default 5000 = every row; hard cap 5000, refused above). Pages the tranche rows only.", "minimum": 1, "maximum": 5000},
                "offset": {"type": "integer", "description": "Rows to skip before the page (default 0; max 5000). Past the end returns an empty page with `page.total` intact.", "minimum": 0, "maximum": 5000},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_bdc_list",
        "description": (
            "Roster of the ACTIVE BDCs tracked by Oxford Ledge, sorted by "
            "portfolio size -- this is our coverage, not the whole BDC "
            "universe; wound-down / de-BDC'd issuers are excluded by design, so "
            "it is not a historical universe. No arguments. Returns {bdcs}; "
            "per BDC: ticker, name, listed, holdingCount, totalFairValue (whole "
            "USD, latest filing), filingDate, lastParsed, plus the "
            "reconciliation triple reportedTotalFairValue (the filing's OWN "
            "stated grand total), fairValueBasis ('parsed-rows' or "
            "'filing-reported') and parsedRowSumFairValue, and the refusal pair "
            "fairValueRefused / fairValueRefusalReason. READ fairValueBasis "
            "BEFORE using totalFairValue: when a parse over-counts, "
            "totalFairValue is swapped to the filing-reported figure and the "
            "raw row sum is preserved in parsedRowSumFairValue, so the two "
            "disagreeing numbers are both visible rather than silently "
            "reconciled. When the store does not answer, holdingCount is null "
            "(never a measured 0) and a top-level `notice` says the counts were "
            "not measured. holdingCount, totalFairValue and the arbitration are "
            "Oxford Ledge's parse, not filer-published figures; ticker / name / "
            "listed are the registry. Borrower-keyed counterpart: "
            "search_bdc_borrower. Source: SEC EDGAR BDC filings (Oxford Ledge "
            "parse). [Requires API mode]"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_bdc_borrower_mark_history",
        "description": (
            "Multi-quarter fair-value mark history for one borrower across "
            "every BDC that holds its debt, NEWEST QUARTER FIRST: per-quarter "
            "min/max and par-weighted average marks (percent of par, 2dp), the "
            "holding-row count and holder count, and the contributing BDC "
            "tickers. ABOVE-PAR TRAP: the marks are fair value over the FILED "
            "principal and filers differ on what principal tracks (par may "
            "exclude capitalised PIK/OID accretion, or the principal field may "
            "equal cost), so a minMark / maxMark / parWeightedMark above 100 "
            "is a par-basis artifact until fair value is checked against cost "
            "on the holding rows (get_bdc_holdings), NOT a credit premium. "
            "Returns {borrowerNorm, count, quarters, units}; each "
            "quarter is {quarterKey, periodEnd, minMark, maxMark, "
            "parWeightedMark, rowCount, holderCount, bdcs}. `rowCount` is a "
            "HOLDING-ROW count (one row per BDC position, so a tranche co-held "
            "by N BDCs counts N times), not a tranche count; `holderCount` is "
            "distinct BDCs. Rows are priced, funded, non-equity debt positions "
            "only (unpriced, unfunded and equity rows are outside both counts). "
            "Exact borrower_norm match only -- resolve the key with "
            "search_bdc_borrower first; an unknown key returns an empty series "
            "with a `note`, not an error (an unreachable store returns the same "
            "note today, so pair an empty series with a second read before "
            "concluding the key is unknown). ATTRIBUTION: Oxford Ledge's parse "
            "of SEC EDGAR BDC schedules of investments (ol-derived), not a "
            "filer-published series. [Requires API mode]"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "borrower_norm": {"type": "string", "description": "Normalized borrower key, matched EXACTLY (take borrowerNorm from a search_bdc_borrower result)"},
                "quarters": {"type": "integer", "minimum": 1, "maximum": 16, "default": 8, "description": "Most-recent quarters to return (1-16, default 8)"},
            },
            "required": ["borrower_norm"],
        },
    },
    {
        "name": "get_bdc_holdings",
        "description": (
            (
            "Full portfolio holdings for one BDC's latest SEC filing: borrower, industry, "
            "security type, lien position, rate, maturity, par/cost/fair value and mark per "
            "position, plus portfolio-level totals, structure metrics (floating-rate %, "
            "senior-secured %, equity %, PIK count) and `topIndustries` ([industry, "
            "positionCount] pairs, top 10). UNITS: parAmount / costAmount / fairValue and every "
            "total are whole USD; markedPrice and weightedAvgPrice are percent of par; "
            "portfolioStructure values are percentages (0-100). ABOVE-PAR TRAP: markedPrice is "
            "fair value over the FILED principal and filers differ on what principal tracks (par "
            "may exclude capitalised PIK/OID accretion, or the principal field may equal cost), "
            "so a row above 100 -- and a weightedAvgPrice above 100 (RAND's registry 111.49 is "
            "the measured case) -- is a par-basis artifact until fairValue is checked against "
            "costAmount, NOT a credit premium. `totalFairValue` is ARBITRATED: read "
            "`fairValueBasis` ('parsed-rows' | 'filing-reported') and `fairValueRefused` first -- "
            "when the parse over-counts against the filing's own total, totalFairValue is the "
            "filing-reported figure, `reportedTotalFairValue` is that figure, "
            "`parsedRowSumFairValue` is the raw row sum, `fairValueRefusalReason` says why, and "
            "every row-derived aggregate (totalParAmount, weightedAvgPrice, topIndustries, "
            "portfolioStructure) is null with `holdingsReconciled: false`. `totalHoldings` is the "
            "REGISTRY count of parsed positions (the population the totals and percentages "
            "cover); the served `holdings` list may be SHORTER because rows whose borrower cell "
            "carries no issuer identity are dropped at read -- `holdingsReturned`, "
            "`nonBorrowerRowsExcluded` and `excludedRowsFairValue` disclose the gap so you can "
            "reconcile served rows against the header. parseQuality 'ok' | 'suspect' (suspect "
            "when >= 50% of the filing's parsed rows carry no borrower identity -- a parse "
            "failure of that schedule, not a portfolio; parseQualityNote says so and names what "
            "is unverified). portfolioStructureBasis 'all_parsed_rows': portfolioStructure, "
            "byLienPosition and topIndustries are computed over EVERY parsed row including "
            "nonBorrowerRowsExcluded, not over holdings[]. An unknown or retired ticker returns "
            "`error` beside an empty list. The totals, structure metrics and the arbitration are "
            "Oxford Ledge's parse of SEC EDGAR Schedule-of-Investments filings (10-Q/10-K), not "
            "filer-published figures. `ticker` is required. [Requires API mode]"
        )
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "BDC ticker symbol (e.g. ARCC, OBDC — see get_bdc_list)"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_debt_maturities",
        "description": (
            "Forward debt maturity ladder parsed by Oxford Ledge from the "
            "latest 10-K/20-F footnote (the hosted EDGAR-only tool, proxied by "
            "name). Returns {ticker, maturities:[{year, amount}], thereafter, "
            "confidence, confidence_score, source, validation}. AMOUNTS ARE IN "
            "MILLIONS OF USD, not raw dollars -- 400 means $400M. `maturities` "
            "is a LIST of year/amount pairs (not a year-keyed map), normally the "
            "next ~5 years, with everything beyond the table in `thereafter`. "
            "`confidence` is high|medium|low|none and `source` is "
            "'table'|'regex'|null (a ladder the balance-sheet cross-check "
            "rejected is served as 'table_rejected' / 'regex_rejected' beside "
            "maturities=[] and confidence 'none') -- all describe PARSER "
            "certainty, not filer "
            "accuracy; `validation` carries {valid, maturity_total, bs_total, "
            "diff_pct, warning} cross-checking the ladder against the balance "
            "sheet, so check it before quoting a total. confidence / "
            "confidence_score / validation are Oxford Ledge's assessment of its "
            "own parse; the amounts are the filing's. An unparseable filer "
            "returns maturities=[] with confidence 'none'. EDGAR only -- no "
            "vendor debt totals and no modelled ladder. For historical "
            "issuance/repayment use get_capital_allocation. Source: SEC EDGAR "
            "10-K note extraction. Plus tier: the refusal is AUTH_REQUIRED "
            "naming the tier -- keyless, it says the client is anonymous and "
            "the operator sets OXFORD_LEDGE_API_KEY; with a valid key on a "
            "lower plan, it says THE KEY IS VALID and the plan is what is "
            "missing. [Requires API mode]"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol (e.g. AAPL)"}
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_capital_allocation",
        "description": (
            "Where a company sent its cash, up to 30 annual labels (not 10), from SEC EDGAR XBRL cash-flow tags (the hosted scorecard tool, proxied by name). Returns {ticker, capitalAllocation:{years, periods, dividends, netBuybacks, netDebtChange, acquisitions, sharesOut, isDilutive, basis, summary}}. `years` is newest-first and the rest are PARALLEL ARRAYS aligned to it by index; `periods` is the ISO period-end list beside it and each label is the filer's FISCAL year (the same axis as get_fundamentals -- JNJ FY2022, ended 2023-01-01, is served as 2022). These are NET, DERIVED series, not raw cash-flow lines: netBuybacks = repurchases minus equity issuance minus IPO proceeds minus share-based comp (NEGATIVE when a company is a net issuer, which isDilutive[i] mirrors as a boolean), netDebtChange = repayments minus issuance (positive means net paydown). netBuybacks is computed from issuance and SBC even when no repurchase fact exists, so an IPO year (RDDT) reads isDilutive true; a year with none of the four facts is null (isDilutive null, never false). IPO proceeds count only as the filer's OWN IPO: the first non-zero ProceedsFromIssuanceInitialPublicOffering in the filer's series with no non-zero PaymentsForRepurchaseOfCommonStock in any earlier year (a subsidiary's IPO tagged by a repurchasing parent -- Kenvue in JNJ's FY2023 -- is excluded; summary.dilutionNote states the rule and names what it admitted or excluded). `dividends` reads PaymentsOfDividendsCommonStock / PaymentsOfDividends / PaymentsOfOrdinaryDividends (earlier rung wins; a subsidiary's minority-interest payout is never read). Gross issuance, gross repayment and SBC are NOT emitted separately. `sharesOut` reads CommonStockSharesOutstanding, then the diluted weighted average for a dual-class filer with no non-dimensional instant (RDDT). `basis` is the same split-basis gate get_fundamentals serves: shareCountChange10yr is split-basis-gated (a reverse-split issuer such as DAC is served null or split-adjusted, never a phantom buyback) -- pre-split share-count cells are withheld into basis.withheldValues.sharesOut and summary.shareCountNote states the comparable-basis move. `summary` carries windowYears (the number of newest fiscal years EVERY summary figure is computed over, 10 or fewer), shareCountChange10yr (percent, newest vs oldest cell in that window), shareCountNote, dilutiveYears (fiscal years in the window judged dilutive; null when none could be judged), yearsJudged, dilutionNote, totalDividends (null, not 0, when no dividend rung is tagged in the window), dividendsNote, totalNetBuybacks, totalNetDebt, totalAcquisitions. All money is whole USD; sharesOut is a share count. Untagged years are null. A filer with no annual us-gaap cash-flow fact (an IFRS reporter such as TSM) is REFUSED with {error, taxonomy, usGaapConceptCount, formsSeen, unitsSeen}, never served years=[] with zeros. The net series and the summary are Oxford Ledge derivations over the filed tags (basis hybrid); the inputs are the filing's. Complements get_fundamentals (P&L and balance sheet) and get_debt_maturities (forward ladder). Source: SEC EDGAR XBRL cash-flow tags, 24h cache. Plus tier: the refusal is AUTH_REQUIRED naming the tier -- keyless, it says the client is anonymous and the operator sets OXFORD_LEDGE_API_KEY; with a valid key on a lower plan, it says THE KEY IS VALID and the plan is what is missing. [Requires API mode]"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol (e.g. AAPL)"}
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_13f_holdings",
        "description": (
            "What one institutional filer owns: the largest positions in its "
            "latest SEC 13F-HR, plus quarter-over-quarter changes. Accepts a "
            "numeric CIK (preferred) or a ticker resolved via SEC's company "
            "map -- letters with at most one class suffix (BLK; BRK-B or "
            "BRK.B for Berkshire, which SEC lists as BRK-A / BRK-B, never bare "
            "BRK). A filer NAME ('Berkshire Hathaway', 'Baupost') is NOT "
            "resolved by this package: its handler proxies the CIK-keyed "
            "route and refuses any other shape as INVALID_PARAMS -- pass the "
            "CIK. The hosted server's own get_13f_holdings does resolve a "
            "name (since 2026-09-13: 3-80 characters; ONE name-prefix match "
            "in the curated 13F filer universe becomes its CIK and the payload "
            "carries `resolved_from` {query, cik, name}; zero or several "
            "matches is an INVALID_PARAMS error listing up to three candidates "
            "and pointing at its hosted-only filer-search tool -- the first of "
            "an ambiguous list is never picked), so `resolved_from` is a "
            "hosted-channel key that never appears on this package's wire. "
            "Returns {cik, fundName, filingDate, "
            "periodOfReport, totalHoldings, totalValue, holdings}; each holding "
            "is {name (issuer name as filed), title_of_class, value, shares, "
            "type, position_type, lots, ticker}. `value` is whole USD (13F "
            "values are dollars despite the form's 'x$1000' wording); "
            "`position_type` is COM|PRN|PUT|CALL and options/notes are kept "
            "separate -- `shares` on a PUT/CALL row is the option's underlying "
            "and on a PRN row the note principal, so do NOT sum across types; "
            "`ticker` is an Oxford Ledge CUSIP-to-ticker crosswalk, ABSENT on "
            "unmapped rows (CUSIPs themselves are stripped): share classes of "
            "one issuer may map to distinct tickers (Alphabet A -> GOOGL, C -> "
            "GOOG; Lennar A/B) or, where the crosswalk is still class-blind, "
            "to one ticker -- `title_of_class` is the authoritative class "
            "discriminator, read it before adding rows of one issuer; `lots` is Oxford "
            "Ledge's count of infotable rows merged into the position. "
            "`totalValue` and `totalHoldings` cover the WHOLE filing while "
            "`holdings` is truncated to max_holdings (default 50, cap 500), "
            "value-ranked. When a prior filing exists the response also carries "
            "prevFilingDate and changes:{new_positions, increased, decreased, "
            "closed} (rows with prevShares / sharesChange / pctChange), plus "
            "`changesTotals` (the full per-bucket counts) and "
            "`changesTruncated` when a bucket was cut; the `changes` key is "
            "ABSENT when only one filing was found. An empty `holdings` list "
            "carries `error` saying either that no 13F-HR is on file for the "
            "CIK or that the latest filing could not be parsed -- never a bare "
            "totalValue 0. Source: SEC EDGAR 13F-HR, ~45-day quarterly delay; "
            "heavy operation, max 2 concurrent. [Requires API mode]"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                # 2026-09-05 F6-validation: the SEC-F1 guard port added an
                # all-alpha ticker resolve (SEC company_tickers.json), so the
                # "CIK only" claim is stale. 2026-09-13 (f2-ownership-6): the
                # example was "BRK", which SEC's map does not carry (BRK-A /
                # BRK-B only), and the gate refused the class-share forms the
                # resolver was written for; both are fixed.
                # 2026-09-14 (W1, MCP audit P2-3): the hosted server resolves a
                # filer NAME since 2026-09-13; this package's handler does NOT
                # (it proxies the CIK-keyed /api/fund-holdings route and gates
                # on the CIK / ticker shapes), so the text says which side does
                # what rather than copying the hosted sentence.
                "fund": {"type": "string", "description": "Fund CIK number (e.g. 1067983 for Berkshire Hathaway) -- preferred. A ticker is resolved via SEC's company map: letters with at most one class suffix (e.g. BLK, or BRK-B / BRK.B -- SEC lists Berkshire as BRK-A / BRK-B, so bare 'BRK' does not resolve). A filer NAME ('Berkshire Hathaway') is refused by THIS package as INVALID_PARAMS -- only the hosted server resolves one to a CIK (its `resolved_from` never appears here); any other shape is rejected as INVALID_PARAMS -- provide the numeric CIK instead."},
                "max_holdings": {"type": "integer", "description": "Maximum number of holdings to return (default 50, cap 500)", "minimum": 1, "maximum": 500},
            },
            "required": ["fund"],
        },
    },
    {
        "name": "get_value_investing_fact",
        "description": (
            "A value-investing quote, principle, or historical fact from "
            "Oxford Ledge's curated corpus (~2,000 entries: Buffett, Graham, "
            "Munger, Klarman and others) with its citation. Returns a flat fact: "
            "{quote, author, source (the book, letter or speech), source_year, "
            "category, subcategory, era, difficulty}. The corpus and its "
            "classification are Oxford Ledge-authored (basis ol-authored); the "
            "quotations are their authors'. Cached 24h per argument set -- vary "
            "`category` for a different pick. [Requires API mode]"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Optional category, matched case-insensitively. The vocabulary is EXACTLY: principle, historical_fact, psychology, quote, case_study, contrarian, mistake. An unknown value returns a no-data error -- retry with one of the listed values. CORRECTED 2026-08-11 -- six of the seven previously documented here never existed."},
            },
        },
    },
    # ── 2026-09-05 moat promotion (docs/board/audit/
    # 2026-09-05_CISO_COUNSEL_CHAOS_moat_promotion_vet.md, OWNER-ratified):
    # three BDC moat tools promoted from IN_TREE_ONLY as thin name-proxies
    # to the hosted MCP dispatch. Descriptions/schemas are COPIED from the
    # reviewed in-tree literals (mcp_tool_definitions.py -- vet L-4:
    # "the reviewed text is the asset, re-authoring is the risk"), adjusted
    # ONLY for transport facts: the "<400ms typical" latency claims are
    # dropped (false through an HTTP proxy hop), and each description names
    # the completeness-block semantics (vet K-6) since the hosted caps
    # CLAMP rather than reject.
    {
        "name": "ol_bdc_top_borrowers",
        "description": (
            "MOAT / BDC discovery: the private-credit borrowers syndicated "
            "across the MOST BDCs, ranked by lender count then exposure -- the "
            "entrypoint for the BDC/private-credit category no generic MCP "
            "touches. Pairs with `ol_bdc_borrower_dispersion` (feed a returned "
            "`borrower_norm` into it to see cross-lender pricing). Returns "
            "{summary, count, borrowers}; each row is {borrower (display name), "
            "borrower_norm (the key other ol_bdc_* tools take), holder_count "
            "(distinct BDC lenders), total_fair_value (whole USD across "
            "lenders, latest filings; null when unpriced), industry}. Caps: "
            "limit default 25 / hard 100; min_holders default 2 (max 50). "
            "Parser mis-ingests (subtotals, maturity-date and instrument-"
            "descriptor rows, bare industry-taxonomy labels) are filtered out "
            "when the filter is available; the `borrower_filters` block says "
            "whether each half ran (nonborrower / industry_label, with "
            "industry_vocab_size) and `rows_removed` how many rows it took "
            "out. Cell-bleed names ('Acme, LLC, Diversified Financial "
            "Services') are deliberately NOT filtered. TRUNCATION: the "
            "`completeness` block in the "
            "payload is the runtime truth -- complete=true means under-cap "
            "(this IS everything), complete=null means exactly-at-cap and "
            "genuinely undecidable (read `more_available_hint`). An "
            "out-of-range `limit` is REFUSED as INVALID_PARAMS naming the "
            "bound (nothing is clamped), so the schema maximum is the rule "
            "and `completeness` is the check. Source: SEC EDGAR BDC schedules of "
            "investments (Oxford Ledge parse; ol-derived); FREE (no paywall on "
            "the hosted channel). [Requires API mode]"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "min_holders": {
                    "type": "integer",
                    "description": "Minimum number of BDC lenders a borrower must appear in (default 2).",
                    "maximum": 50,
                },
                "limit": {
                    "type": "integer",
                    "description": "Max borrowers to return (default 25, hard cap 100).",
                    "maximum": 100,
                },
            },
        },
    },
    {
        "name": "ol_bdc_borrower_dispersion",
        "description": (
            (
            "MOAT: cross-lender loan-pricing DISPERSION for one private-credit borrower -- how N "
            "different BDCs each price the SAME loan (spread / mark / fair value). The "
            "credit-mispricing signal no generic MCP has: when one BDC marks a borrower S+550 @ "
            "98 and another S+575 @ 99, the lenders disagree on the credit. Pass the borrower's "
            "canonical `borrower_norm` key (from `ol_bdc_top_borrowers` or "
            "`search_bdc_borrower`). Returns {summary, borrower_norm, count, lenders, "
            "spread_unit, base_rate, yield_disclosure, rows_above_par, as_of, completeness}, "
            "ordered widest-spread-first; each lender row is {bdc_ticker, bdc_name, filing_date, "
            "bdc_latest_filing, is_stale_vs_bdc_latest, filer_status, successor_ticker, "
            "security_type, lien_position, rate_type, maturity_date, spread, spread_bps, "
            "marked_price, mark_as_of, mark_above_par, mark_above_par_basis, fair_value, "
            "non_accrual, current_yield_pct, spread_to_maturity_bps, all_in_simple_yield_pct, "
            "yield_basis, yield_suppressed, pik_leg_excluded}. UNITS TRAP: `spread` is the RAW "
            "AS-FILED number and is MIXED-UNIT across filers -- one BDC files 5.75 (percent) for "
            "what another files as 575 (bps) -- so never average or diff `spread` blind; compare "
            "lenders on `spread_bps` (normalised basis points, the ranking key; `spread_unit` "
            "says so). marked_price is out of 100; fair_value is whole USD. STALENESS: "
            "`filing_date` is the filing the row came from and `bdc_latest_filing` that BDC's "
            "newest filing; `is_stale_vs_bdc_latest` true means the BDC has filed since without "
            "this borrower (an exited position), and `filer_status` 'inactive' with "
            "`successor_ticker` marks a wound-down lender whose frozen final filing still "
            "appears. YIELDS: current_yield_pct / spread_to_maturity_bps / "
            "all_in_simple_yield_pct are serve-time Oxford Ledge computations (SOFR read at serve "
            "time from `base_rate`, never stored); `yield_suppressed` names why a yield is null "
            "(non-accrual, pure PIK, unpriced floor) and `yield_disclosure` states the method; "
            "rows with mark_above_par carry no serve-time yields at all. ABOVE-PAR TRAP: "
            "marked_price is fair value over FILED principal, and filers differ on what principal "
            "tracks -- a row above 100 carries mark_above_par=true plus a mark_above_par_basis "
            "sentence (par may exclude capitalised PIK/OID accretion, or the filer's principal "
            "field may equal cost; FV/par and FV/cost differ) and rows_above_par counts them, so "
            "do NOT read such a row as a credit premium without checking fair_value against cost. "
            "Debt tranches only (equity excluded). Rows are each BDC's most recent filing THAT "
            "HOLDS this borrower, so vintages can differ across lenders. A single lender comes "
            "back as ONE row (count=1); an empty result means the key is not in the corpus as a "
            "funded debt position (equity-only, unfunded-only, or an unknown key). Default 25 "
            "rows, hard cap 100. TRUNCATION: the `completeness` block in the payload is the "
            "runtime truth -- complete=true means under-cap, complete=null means exactly-at-cap "
            "and undecidable (read `more_available_hint`); an out-of-range `limit` is REFUSED as "
            "INVALID_PARAMS, never clamped. Source: SEC EDGAR BDC schedules of investments "
            "(Oxford Ledge parse; ol-derived); FREE (no paywall on the hosted channel). "
            "maturity_date_precision ('day' | 'month' | 'year' | null) is the precision the "
            "filer's SOI printed; a month-precision maturity cannot anchor the day-count, so "
            "spread_to_maturity_bps is null with margin_suppressed_reason 'no_maturity' and "
            "margin_suppressed_note saying the maturity is partial, not missing (likewise when "
            "the served date is already past). [Requires API mode]"
        )
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "borrower_norm": {
                    "type": "string",
                    "description": "Canonical normalized borrower key (from ol_bdc_top_borrowers or borrower search).",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max lender positions to return (default 25, hard cap 100).",
                    "maximum": 100,
                },
            },
            "required": ["borrower_norm"],
        },
    },
    {
        "name": "ol_bdc_common_borrowers",
        "description": (
            "Borrowers common to a GIVEN SET of BDCs -- the cross-portfolio set "
            "question ('what do ARCC, OBDC and AGTC all lend to?'). Every other "
            "BDC tool runs borrower -> lenders; this one runs lenders -> shared "
            "borrowers, so a portfolio-overlap question takes ONE call instead "
            "of N per-borrower calls. Returns per borrower: borrower, "
            "borrower_norm, holder_count, holder_tickers (the bare BDC "
            "symbols), holders ([{ticker, name}] -- name is null when the "
            "registry has no row, never a guessed name), total_fair_value + "
            "total_par_amount in USD, and as_of_oldest/as_of_newest. Each BDC "
            "is read at ITS most recent filing and BDCs file on different "
            "calendars, so rows MIX filing dates -- read as_of_range before "
            "treating the marks as contemporaneous. Debt positions only "
            "(equity stakes are not lending relationships). Ordered "
            "most-widely-held first. Caps: more than 25 bdc_tickers is REFUSED "
            "as INVALID_PARAMS before any request (the schema's maxItems; "
            "nothing is truncated), limit 50/200, min_holders max 50; a "
            "min_holders above the number of BDCs supplied is rejected rather "
            "than returning a misleading empty list. TRUNCATION: the "
            "`completeness` block in the payload is the "
            "runtime truth -- complete=true means under-cap, complete=null "
            "means exactly-at-cap and undecidable (read `more_available_hint`); "
            "an out-of-range `limit` is REFUSED as INVALID_PARAMS, never clamped. Feed "
            "a returned borrower_norm to ol_bdc_borrower_dispersion for "
            "cross-lender pricing. Source: SEC EDGAR BDC schedules of "
            "investments (Oxford Ledge parse: normalised borrower keys, "
            "cross-BDC sums, artifact filters -- ol-derived); FREE (no paywall "
            "on the hosted channel). [Requires API mode]"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "bdc_tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 25,
                    "description": "BDC symbols to intersect, e.g. [\"ARCC\",\"OBDC\",\"AGTC\"] (max 25; more than 25 is refused as INVALID_PARAMS, nothing is truncated)",
                },
                "min_holders": {
                    "type": "integer",
                    "description": "Minimum number of the supplied BDCs that must hold the borrower (default 2, min 2 -- this answers what is SHARED; for one BDC's book use ol_bdc_top_borrowers)",
                    # minimum 2, not 1 (CLEANCORE vet 2026-08-12; copied
                    # from the in-tree schema): at 1 a single-ticker call
                    # became an anonymous portfolio dump. The hosted
                    # handler floors it too; this keeps the schema honest.
                    "minimum": 2,
                    "maximum": 50,
                },
                "limit": {
                    "type": "integer",
                    "description": "Max borrowers to return (default 50, max 200)",
                    "minimum": 1,
                    "maximum": 200,
                },
            },
            "required": ["bdc_tickers"],
        },
    },
    # ── The eleven, promoted from IN_TREE_ONLY 2026-09-09 ────────────────
    # COUNSEL COMPLIANCE_REVIEW_v1: ADMIT-WITH-CONDITIONS on all eleven, zero
    # refusals. Every one is a NAME-PROXY to the hosted dispatch (see the
    # handlers in server.py) and every one rides `filter_to_allowlist`, whose
    # key sets were seeded from LIVE payloads rather than SELECT lists.
    #
    # Descriptions are the hosted catalog's own (tools_manifest.py) rather than
    # retyped, so the wheel and the hosted server cannot drift into two truths.
    # Four edits on top, each a COUNSEL condition: `id` / `ingested_at` removed
    # from the advertised row shape where C3 strips them (a description that
    # promises a field the filter removes is a documented lie); the two HYBRIDS
    # carry an ATTRIBUTION sentence because `_meta.source` would otherwise be
    # false for exactly one field; `get_activist_stakes.updated_at` says it is
    # OUR cache stamp; the two BDC tools say ol-derived, not primary.
    #
    # 2026-09-12 (3.4.0 vet): the wheel copies now ALSO differ from the hosted
    # text in three transport-honest ways -- latency figures are dropped (a
    # proxy hop makes them false), cross-references to tools the wheel does
    # not ship say "hosted-only", and FREE is scoped to the hosted channel
    # (a keyed call still counts toward the caller's agent-API allowance).
    {
        "name": "ol_form_d_raises",
        "description": "Recent SEC Form D private-placement filings from the SEC's QUARTERLY Form D data set -- newest first, optionally scoped to an industry group and/or a trailing filing-date window. Returns {summary, count, days, industry, offerings}; each offering is {accession, submission_type, filing_date, issuer_cik, issuer_name, entity_type, state, industry_group, investment_fund_type, is_equity, is_debt, total_offering_amount, offering_indefinite, total_amount_sold, total_remaining, investors_count, date_of_first_sale, first_sale_yet_to_occur, federal_exemptions, quarter}, NEWEST FIRST. Amounts are whole USD AS DISCLOSED -- total_offering_amount is a ceiling, not money raised (use total_amount_sold), and offering_indefinite means no cap was stated. `limit` default 50, hard cap 200. CADENCE: the source is the SEC quarterly Form D data set, posted about one quarter after quarter-end; `quarter` on each row is the DATA-SET VINTAGE it came from, not a filing quarter, and the envelope's `data_through` (newest filing_date loaded) and `newest_quarter_loaded` say how far the store reaches. A trailing `days` window shorter than that lag is EMPTY BY CONSTRUCTION -- it is not evidence that nothing was filed -- and the empty-window summary says so; there is no 'filed this week' read on this data set. WITHOUT `days` the read is a top-N over the whole table. `industry` must match the stored industry_group label exactly. Source: SEC EDGAR Form D data sets (public domain); FREE (no paywall on the hosted channel). [Requires API mode]",
        "inputSchema": {
            "type": "object",
            "properties": {
                "industry": {
                    "type": "string",
                    "description": "Industry group filter (optional).",
                },
                "days": {
                    "type": "integer",
                    "description": "Trailing filing-date window in days (optional). The data set is quarterly with ~1 quarter of posting lag: a window shorter than that is empty by construction.",
                    "maximum": 1825,
                },
                "limit": {
                    "type": "integer",
                    "description": "Max offerings (default 50, hard cap 200).",
                    "maximum": 200,
                },
            },
            "required": [],
        },
    },
    {
        "name": "ol_insider_recent_buys",
        "description": "Recent OPEN-MARKET insider PURCHASES across the Oxford Ledge issuer catalog (~5.3k tickers) -- a daily insider screen. Returns {summary, since_days, count, buys}; each buy is {ticker, filingDate, transactionDate, insiderName, position, title, transType, shares, pricePerShare, totalValue, sharesOwned, securityTitle, isDerivative, url (SEC filing)}, NEWEST FIRST. since_days default 30 (hard cap 180), limit default 25 (hard cap 100). SAMPLING TRAP: when the window holds more purchases than `limit`, you get the NEWEST N filings, not the whole window -- so never total these rows and call it the period's insider buying. Open-market purchases only (SEC transaction_code 'P'); option exercises, grants and sales are excluded, as are issuers filing on themselves. `totalValue` is USD (dollars, with cents) = |shares| x price, computed by Oxford Ledge at ingest and null when the filed price failed the plausibility gate; `position` is the filer's reported title, or an Oxford Ledge fallback label (Officer / Director / 10% Owner / Insider) when the filing left it blank -- both are Oxford Ledge derivations (basis hybrid); every other field is the Form 4's. Source: SEC EDGAR Form 4 (public domain); FREE (no paywall on the hosted channel). Pairs with get_insider_trades (one ticker). Multi-buyer cluster detection is hosted-only. Each row also carries formType (the Form 4 type as filed, '4' or '4/A'), accessionNumber (the filing), isAmendment (true for a 4/A; null when the store holds no form type), and supersedesAccession: a Form 4 and its 4/A that report the SAME line (identical filer, date, code, shares, price, shares-owned-after, security title and derivative flag) are served ONCE, as the amendment, with supersedesAccession naming the folded original -- so summing shares or value over the list no longer double-counts an amended filing. A 4/A that CORRECTED a value is a different line and is served beside its original; isAmendment says which is which. [Requires API mode]",
        "inputSchema": {
            "type": "object",
            "properties": {
                "since_days": {
                    "type": "integer",
                    "description": "Trailing window in days (default 30, hard cap 180).",
                    "maximum": 180,
                },
                "limit": {
                    "type": "integer",
                    "description": "Max purchases (default 25, hard cap 100).",
                    "maximum": 100,
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_fails_to_deliver",
        "description": "SEC fails-to-deliver history for one ticker -- the settlement-failure side of short pressure. Returns {ticker, days, history, count}; each row is {date (the SETTLEMENT date, as ISO text -- the field is `date`, not settlement_date), fails (SHARES failed, not dollars), price (closing price that day, USD), description (issue name)}, OLDEST-FIRST so it charts left to right. `days` is a trailing window, default 180, hard cap 730, ANCHORED TO THE LATEST LOADED SETTLEMENT DATE (`as_of`), not to today: each SEC half-month file lands ~3 weeks after the period ends, so a window measured back from today was empty for every ticker on most days of the month; the served span ends at `as_of` and `coverage.window_start` / `coverage.window_end` say where it ran. Coverage is sparse by nature: SEC publishes a row only on days a ticker actually had fails, so gaps between rows are normal -- but the STORE holds only the SEC half-month files Oxford Ledge has loaded, so an empty or thin `history` is a statement about the loaded settlement-date range, not evidence of no fails: a `days` window that reaches before the earliest loaded file is empty by construction. THE COVERAGE FLOOR rides every payload: `coverage` = {earliest_settlement_date, latest_settlement_date, files_loaded, files_expected, files_missing (the SEC half-month file labels absent INSIDE the loaded range, e.g. 202608b -- a gap there is a missing file, not a fail-free stretch; null if the store could not list its periods), window_start, window_end, days_covered, days_before_earliest, days_after_latest, window_predates_coverage, window_postdates_coverage (true when the window starts after the newest loaded date OR at least one whole half-month after it lies inside the window)}, `as_of` (the latest settlement date loaded) and a `summary` that states how many of the requested days fall inside the loaded data and names the head, the tail and the missing files as NOT LOADED rather than fail-free -- when none of the window is loaded it says so instead of \"0 fails\" -- read them before quoting a window as fail-free. Figures are as SEC published for that settlement date: NOT split-adjusted, and a renamed ticker's earlier rows sit under the old symbol; class shares use SEC's concatenated symbol (BRKB), which BRK.B / BRK-B also match. The short-interest half of that picture is hosted-only. Source: SEC Fails-to-Deliver dataset (published twice monthly, ~3-week lag). [Requires API mode]",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g. GME)",
                },
                "days": {
                    "type": "integer",
                    "description": "Trailing window in days (default 180, max 730)",
                    "maximum": 730,
                },
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_activist_stakes",
        "description": "Schedule 13D/13G >5% beneficial-owner filings for a ticker -- event-driven stake-building, unlike quarterly 13F. Returns {ticker, count, filings}, newest first, limit default 50 (hard cap 200). Each filing: ticker, filer_name, filing_date, form_type, shares, percent_of_class (a percent number), accession_number (build the EDGAR document URL from it), updated_at, plus a derived is_activist that is true IFF form_type contains '13D' -- i.e. it is a FORM-TYPE label, not a judgement: 13D signals active intent (proxy fight, takeover), 13G a passive index/institutional holder. Each filing also carries `reports_zero` (the cover page states 0 shares / 0% -- the filer's own statement that it no longer beneficially owns more than 5% of the class; an exit OR a reporting realignment such as Vanguard's 2026-01-12 disaggregation under SEC Release 34-39538, so cross-check get_holders before reading it as a sale) and `unparsed` (shares and percent are null because the cover page could not be read: unknown, not zero); `summary` spells both out. FRESHNESS: keyless (anonymous) callers are served STORED rows and never trigger the EDGAR refresh -- read `stale` (null = the store was touched within 24h by some caller but THIS call did not compare it against EDGAR's index -- keyless callers never refresh -- so freshness is not certified; `stale_basis` names the evidence: 'age', 'edgar_index' or 'no_refresh_evidence'; true = the stored rows are older than 24h, or nothing is on file, OR EDGAR's index lists a newer Schedule 13D/13G than the newest stored row -- `newest_filing_seen` > `newest_filing_stored` -- or a family label this writer does not ingest; `notice` says which, and `fetched_rows` is the last refresh's admitted row count, null when no refresh ran), `age_seconds` (null = no rows have ever been fetched for this ticker, and none will be without an API key) and `refreshed` (whether this call refreshed). Keyed callers refresh from EDGAR when the store is older than 24h; that refresh is bounded to 20s and falls back to the stored rows on timeout, and it is SKIPPED for up to an hour after any caller's result for the same arguments was cached (the hosted tool-level cache; this package caches its own copy for an hour as well), so `refreshed` can be false on a keyed call. `updated_at` is OUR CACHE stamp for the row, not a filing date -- read `filing_date` for when the filer filed. The 13D Item 4 purpose text is not served (nothing populates it). The institutional-consensus cross-check is hosted-only. Source: SEC EDGAR. [Requires API mode]",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g. AAPL)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max filings to return (default 50)",
                    "maximum": 200,
                },
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "ol_treasury_debt",
        "description": "US Treasury debt composition from the Monthly Statement of the Public Debt. Omit BOTH args for the newest month's full class breakdown (one row per security class, in statement order); pass security_type AND security_class together for that one class's monthly history -- passing only one of them is IGNORED and you get the latest-month breakdown. Returns {summary, rows} with rows of {record_date, security_type_desc, security_class_desc, debt_held_public_mil_amt, intragov_hold_mil_amt, total_mil_amt} (the latest-month shape also carries src_line_nbr). AMOUNTS ARE IN MILLIONS OF USD -- a 28,000,000 value means $28 trillion. Because the breakdown contains both component and Total rows, summing a column double-counts; filter by security_class_desc first. `limit` (series only) default 120 months, hard cap 360. Monthly, published a few business days after month-end. Sibling of get_yield_curve. Source: Treasury.gov MSPD (public domain); FREE (no paywall on the hosted channel). [Requires API mode]",
        "inputSchema": {
            "type": "object",
            "properties": {
                "security_type": {
                    "type": "string",
                    "description": "e.g. 'Total Public Debt Outstanding' (with security_class for a series).",
                },
                "security_class": {
                    "type": "string",
                    "description": "Class within the type; '_' for Total rows.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Monthly points for a series (default 120, hard cap 360).",
                    "maximum": 360,
                },
            },
            "required": [],
        },
    },
    {
        "name": "ol_cftc_cot",
        # 2026-09-14 (W1, MCP professional-persona audit P2-6): the keys were
        # advertised as "case-sensitive" after the hosted resolver had started
        # normalising them (wave N, 2026-09-13). The wheel is a name-proxy, so
        # 'GOLD' and 'wti' resolve here too; `matched_market` and `candidates`
        # are admitted to the emit allowlist in the same commit so the two
        # resolver keys named below actually arrive.
        "description": "CFTC Commitments-of-Traders positioning for THREE curated markets (keys gold, crude_oil, sp500). Pass a `market` for that market's weekly history (NEWEST FIRST), or omit it for the latest report across those three markets (one row per market). MARKET NAMES ARE NORMALISED, not matched by exact key: the value is case-folded and stripped of punctuation, then matched through a desk-alias table (CL / WTI / crude / 'Crude Oil, Light Sweet' -> crude_oil; ES / SPX / S&P / 'E-mini S&P 500' -> sp500; GC / XAU / gold -> gold) and as a substring of the stored keys and labels, so 'GOLD', 'wti' and 'e-mini s&p' all resolve; `matched_market` names the key that answered (null on the all-market snapshot). A name that resolves to NOTHING stored returns {error, matched_market: null, candidates (up to five nearest stored names), rows: []} -- and a name matching SEVERAL stored markets is that same miss, never the first of an ambiguous list. Every payload carries `markets_available` naming the three keys. Returns {summary, market (as sent), matched_market, rows}; a series row is {report_date, market_key, market_label, report_type, contract_code, mm_long, mm_short, mm_net, open_interest, source_dataset} (the all-market snapshot omits contract_code and source_dataset). mm_* and open_interest are CONTRACT counts, not dollars, and mm_* cover ONE speculative category per report family -- commercials, swap dealers and other reportables are not returned: report_type `disaggregated` rows (gold, crude_oil) are the CFTC Managed Money category; report_type `tff` rows (sp500) are the CFTC Leveraged Funds category -- the closest speculative analogue, since the Traders-in-Financial-Futures report has no Managed Money column. `limit` (series only) default 52, hard cap 156. An unresolvable name returns rows=[] with `candidates` (the store answered); an unreachable store is REFUSED (DATA_UNAVAILABLE), never served as rows=[]. Weekly, published Friday for Tuesday positions. Source: CFTC.gov (public domain); FREE (no paywall on the hosted channel). ATTRIBUTION: every field is CFTC verbatim EXCEPT market_key and market_label (Oxford Ledge's curated market catalog), matched_market and candidates (Oxford Ledge's resolver over that catalog) and mm_net (mm_long minus mm_short, computed by Oxford Ledge). [Requires API mode]",
        "inputSchema": {
            "type": "object",
            "properties": {
                "market": {
                    "type": "string",
                    "description": "Market key, CFTC report name or desk symbol -- gold / GC / XAU, crude_oil / CL / WTI, sp500 / ES / S&P (case-insensitive; omit for the latest all-market snapshot).",
                },
                "limit": {
                    "type": "integer",
                    "description": "Weekly reports for a market series (default 52, hard cap 156).",
                    "maximum": 156,
                },
            },
            "required": [],
        },
    },
    {
        "name": "ol_fdic_bank",
        "description": "FDIC-insured banks and thrifts. Pass `query` for a name PREFIX search against ACTIVE institutions (largest-asset first; a leading 'The ' on the legal name is ignored, so 'Huntington' finds 'The Huntington National Bank'), or omit it for the largest active institutions. Every payload carries `coverage` {institutions_loaded, active_loaded, inactive_loaded, newest_repdte, last_loaded_at, ingest_scope} and `as_of` (= newest_repdte): the store is loaded ACTIVE-ONLY from the live FDIC API, so a bank that merged away or failed before a load (e.g. Comerica Bank, cert 983, acquired Feb 2026) is absent by construction -- an empty search is a fact about the loaded store, never about the world. Returns {summary, query?, institutions}; each institution is {cert (FDIC certificate number, the identifier), name, stname, city, bkclass, active, asset, dep, estymd, webaddr, ticker (non-null only for the ~34 CERTs on Oxford Ledge's verified CERT-to-ticker map -- blank does NOT mean the bank is unlisted), repdte (the report date the figures are as of)}. UNITS: `asset` and `dep` are raw FDIC units, i.e. THOUSANDS of dollars -- 3,200,000 means $3.2 billion, not $3.2 million. `limit` default 25, hard cap 100, so the prefix search returns at most 25 matches unless you raise it. Call reports only: no branch, CRA or enforcement data. Source: FDIC.gov (public domain); FREE (no paywall on the hosted channel). ATTRIBUTION: every field is FDIC BankFind verbatim EXCEPT `ticker`, which is an Oxford Ledge-verified CERT-to-ticker mapping, not an FDIC-published field. [Requires API mode]",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Institution name prefix (omit for the top-by-assets list).",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max institutions (default 25, hard cap 100).",
                    "maximum": 100,
                },
            },
            "required": [],
        },
    },
    {
        "name": "ol_federal_contracts",
        "description": "Federal-contract obligation history for a ticker, OR the fiscal-year leaderboard -- for government-revenue-dependence diligence. TWO SHAPES, and one of `ticker` or `fiscal_year` is REQUIRED (neither raises INVALID_PARAMS; if both are given, `ticker` wins and `fiscal_year` is ignored). With `ticker`: {summary, ticker, as_of, obligations} where each row is {ticker, fiscal_year, total_obligations_usd (USD with cents -- units of dollars, not thousands), entity_count, recipients (each {name, uei, recipient_id, amount}), dropped_unresolved (how many awardee search hits the crosswalk did NOT attribute to this ticker -- read it before treating the total as complete), start_date, end_date, fetched_at, period_complete, days_elapsed, days_in_period}, NEWEST FY FIRST; `as_of` is the date USAspending was last read. A fiscal year whose end_date lies after `as_of` is PARTIAL (period_complete false, days_elapsed < days_in_period) and its total is year-to-date -- never compare it to a full year. `ueis` is no longer emitted (it duplicated recipients[].uei). With `fiscal_year` only: {summary, fiscal_year, leaderboard} of {ticker, fiscal_year, total_obligations_usd, entity_count, fetched_at}, largest first (the envelope carries period_complete / days_elapsed / days_in_period for the requested year). `limit` default 20, hard cap 100. Obligations are federal awards, not company-reported revenue. Obligations are the ISSUER's while the crosswalk keys one share class: a ticker with no rows whose share-class sibling has them is served the sibling's rows under the sibling's `ticker`, with `requested_ticker` carrying the symbol you asked for and the summary saying so; a ticker off the crosswalk honestly returns []. Source: USAspending.gov (public domain; OL ticker-crosswalked); FREE (no paywall on the hosted channel). ATTRIBUTION: the per-recipient amounts and UEIs are USAspending verbatim; attributing them to a TICKER is an Oxford Ledge curated crosswalk, the per-ticker total and entity_count are Oxford Ledge sums over the rows the crosswalk kept, and `dropped_unresolved` is an UPPER BOUND on that crosswalk's coverage gap -- it also counts unrelated name matches (a 'Lockheed ...' credit union), so it never says how many related entities were missed. [Requires API mode]",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker (omit for the FY leaderboard).",
                },
                "fiscal_year": {
                    "type": "integer",
                    "description": "Fiscal year for the top-contractors leaderboard.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max rows (default 20, hard cap 100).",
                    "maximum": 100,
                },
            },
            "required": [],
        },
    },
    {
        "name": "ol_patents",
        "description": "Recent USPTO patent filings for a ticker (innovation-intensity diligence). Returns {summary, ticker, count, filings}; each filing is {applicant_name, application_number, publication_number, patent_number, title, filing_date, status, application_type}, NEWEST FIRST. `limit` default 50, hard cap 200 -- so this is a recent slice, never a full portfolio, and `count` is the number RETURNED, not the company's total patent estate. Filings reflect Oxford Ledge's last on-demand USPTO ingest for this ticker, not a schedule: the newest `filing_date` is the recency bound, and a stale ingest, a company that stopped filing, and an alias this ingest never keyed all look the same here. OL alias-resolves the applicant (GOOGL spans Alphabet + Google LLC + DeepMind + Waymo). Patents are the ISSUER's while the store is keyed by one share class: a ticker with no rows whose share-class sibling has them (GOOG -> GOOGL) is served the sibling's rows under the sibling's `ticker`, with `requested_ticker` carrying the symbol you asked for and the summary saying so. TRAP: a non-empty patent_number means this application is a continuation of an already-granted PARENT, NOT that this application itself was granted -- read `status` for that. Source: USPTO (public domain); FREE (no paywall on the hosted channel). ATTRIBUTION: every filing field is USPTO ODP verbatim EXCEPT `ticker`, which is an Oxford Ledge applicant-name resolution, not a USPTO field. [Requires API mode]",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker (e.g. GOOGL).",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max filings (default 50, hard cap 200).",
                    "maximum": 200,
                },
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "ol_bdc_mark_changes",
        "description": "MOAT / private credit: the largest quarter-over-quarter MARK moves across a SET of BDC portfolios -- 'which borrowers got marked up or down the most last quarter, and by whom' in ONE deterministic call. Built because the alternative is stitching it by hand: a model asked this question fanned out per-BDC calls, worked from portfolio AVERAGES (the wrong grain), hit a rate limit, and fabricated a row by copying another BDC's numbers. Returns {increases, decreases}, each a global ranking across every portfolio supplied; each row is {borrower, portfolio (the BDC ticker holding it), prior_mark, latest_mark, mark_delta, prior_filing, latest_filing}. Marks are PERCENT OF PAR, fair-value-weighted across all tranches the BDC holds of that borrower; mark_delta is in percentage points. INCLUSION THRESHOLDS: a borrower enters a ranking only when |mark_delta| >= 1.0 point and its fair value is >= $500k, so 'no moves' can hide sub-point drifts and tiny positions. Grain is BORROWER, not position: security_type is deliberately NOT returned, because rolling up across tranches is what stops a continuously-held borrower reading as both entered and exited when its tranche mix is re-parsed. Each BDC is read at ITS two most recent filings and BDCs file on different calendars, so rows MIX vintages -- read `as_of` before treating the moves as contemporaneous. `coverage` names every BDC that was and was NOT read, with a reason per exclusion (no_prior_quarter / no_parsed_holdings / query_failed / over_ticker_cap), so a partial sweep can never read as a complete one. Caps: bdc_tickers truncated at 25 (the excess is listed in coverage, not dropped silently), limit default 10 / hard 50 per direction. Source: SEC 10-K/10-Q schedules of investments (Oxford Ledge parse); FREE (no paywall on the hosted channel). ATTRIBUTION: Oxford Ledge's parse of SEC EDGAR BDC schedules of investments (ol-derived), not a filer-published series. [Requires API mode]",
        "inputSchema": {
            "type": "object",
            "properties": {
                "bdc_tickers": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                    "description": "BDC symbols to compare, e.g. [\"ARCC\",\"FSK\",\"OBDC\"] (max 25; the excess is reported in `coverage.not_covered_detail` rather than dropped)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Rows per direction (default 10, hard cap 50). Ranking is GLOBAL across the supplied portfolios, not per BDC.",
                    "maximum": 50,
                },
            },
            "required": ["bdc_tickers"],
        },
    },
    {
        "name": "ol_bdc_credit_quality",
        "description": "BDC non-accrual credit-deterioration signal: the share of debt fair value on non-accrual (loans that stopped paying) in the latest filing, plus the trailing-quarter trend -- the earliest public read on a private-credit book going bad. Returns {summary, ticker, latest, trend}. `latest` = {filing_date, flagged_fv, determinate_fv, total_debt_fv, flagged_pct, flagged_pct_basis (the denominator sentence), determinate_coverage}; the envelope also carries `filer_status` ('active'|'inactive') and `successor_ticker` -- an INACTIVE filer's frozen final filing is labelled in `summary` (BKCC -> TCPC); `trend` is per-quarter OLDEST-FIRST with the same fields plus quarter_key. UNITS: the *_fv figures are whole USD of fair value, flagged_pct is a percentage number, determinate_coverage is a 0-1 fraction. DENOMINATOR: flagged_pct = flagged_fv / determinate_fv x 100 -- the DETERMINATE-flag denominator (the rows whose non-accrual status the parse could read), never total_debt_fv; multiply it by determinate_coverage for the share of the whole debt book, which is up to 10% lower relative at the 90% gate. `flagged_pct` is deliberately NULL whenever determinate coverage is under 90% of debt fair value -- a partially-determinate quarter never reports a rate computed over a fraction of the book, so treat null as 'withheld', never as zero. `quarters` default 12, hard cap 24. Unparsed or non-BDC tickers return latest=null, trend=[]. Pairs with ol_bdc_borrower_dispersion and ol_bdc_top_borrowers. Source: SEC EDGAR BDC schedule-of-investments non-accrual flags (Oxford Ledge parse); FREE (no paywall on the hosted channel). ATTRIBUTION: Oxford Ledge's parse of SEC EDGAR BDC schedules of investments (ol-derived), not a filer-published series. `latest.coverage_state` and every trend row's `coverage_state` is one of `none_parsed` (0% determinate: no non-accrual flag was parsed from the filing -- a parser gap, not a withholding and not a 0% rate), `partial` (0-90% determinate: the rate is withheld and the sentence carries the coverage number) or `covered` (>= 90%: the rate is stated). Read the state before reading a null flagged_pct. [Requires API mode]",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "BDC ticker (e.g. ARCC, ORCC, FSK).",
                },
                "quarters": {
                    "type": "integer",
                    "description": "Trailing quarters of trend (default 12, hard cap 24).",
                    "maximum": 24,
                },
            },
            "required": ["ticker"],
        },
    },
]
