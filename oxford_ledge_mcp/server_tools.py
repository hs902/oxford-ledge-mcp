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
            "filings: common-stock (COM) positions only, one row per filer at "
            "that filer's LATEST 13F within the last 6 quarters, ranked by "
            "reported dollar value. Returns {ticker, holders, completeness}; each "
            "row carries holder, fund_cik, shares, value (whole USD), type, "
            "quarter, filingDate. One call can mix quarters: read `asOf`, "
            "`vintages` and `coverage` before comparing rows. A stale filer whose "
            "shares reconcile to same-quarter siblings of its own fund family is "
            "WITHHELD into `superseded_parents`; do NOT add those rows back into "
            "`holders` or into any total, which restores the double count the "
            "fold removes. An empty `holders` list is a scoped statement, not "
            "proof that nobody owns the stock. `ticker` is required. Caveats ride "
            "the response's tool_notes. [Requires API mode]"),
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
            "date (filing date), url (the EDGAR document)}. The read covers only "
            "SEC's most-recent-1000 submissions index for the filer, so nothing "
            "older than `completeness.windowFrom` is visible here. Fetched "
            "directly from data.sec.gov (no key needed); cached 1h. Caveats ride "
            "the response's tool_notes."
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
            "Form 4 insider transactions for one issuer from Oxford Ledge's Form "
            "4 ingest of SEC EDGAR: the latest `limit` rows by filing date "
            "(default 20, cap 100; `days` keeps rows filed in the last N days), "
            "every SEC transaction code. Returns {ticker, trades, completeness}; "
            "rows carry insider, position, signed shares, pricePerShare, value, "
            "type (raw SEC code), transTypeLabel, is_open_market (P and S only), "
            "isDerivative, transactionDate, filingDate, url. Rows with "
            "isDerivative true are option legs, awards or notes, not common-stock "
            "trades: do not add them to share counts. A 4/A that repeats its "
            "original line is served once (supersedesAccession names the folded "
            "original). Leave issuerSelfFiled rows out of any total. `ticker` is "
            "required. Caveats ride the response's tool_notes. [Requires API "
            "mode]"
        )),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol"},
                # MCP-B B5 (2026-09-26): the tool had no row limit and no
                # date window; the route honours both since the same change.
                "limit": {"type": "integer", "minimum": 1, "maximum": 100,
                          "description": "Max rows, newest filing first (default 20, hard cap 100)."},
                "days": {"type": "integer", "minimum": 1, "maximum": 3650,
                         "description": "Only rows FILED in the last N days (optional; default: no window)."},
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
            "reporting under US GAAP in USD). Returns {ticker, data, concepts, "
            "coverage, coverageNote, basis}; `data` maps Revenue, NetIncome, EPS, "
            "DilutedShares, TotalAssets, TotalLiabilities, StockholdersEquity, "
            "OperatingCashFlow and LongTermDebt -- to up to 10 annual {period, "
            "value} points, newest first, in whole USD (EPS in USD per share). "
            "`LongTermDebt` is NOT total debt. An EPS or share series that spans "
            "a stock split is withheld on the pre-split side ({value: null, "
            "withheld: 'split_basis'}), never rescaled; `basis` is Oxford Ledge's "
            "split-basis check and every other value is the filing's, verbatim. "
            "An IFRS reporter, or a Canadian MJDS filer reporting on 6-K in CAD, "
            "is refused as DATA_UNAVAILABLE. No key needed; cached 1h. Caveats "
            "ride the response's tool_notes."),
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
            "include_history=true adds `yield_curve_1y_ago` (the observation "
            "nearest one year before each tenor's as_of, within 45 days) and "
            "`history_coverage`. A partial curve carries a `completeness` block "
            "naming the missing tenors; a curve with no readable tenor raises "
            "DATA_UNAVAILABLE. Verbatim FRED values, nothing derived. Requires "
            "FRED_API_KEY; cached 1h. Caveats ride the response's tool_notes."
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
            "[{date, value}] NEWEST FIRST over the trailing `days` calendar days "
            "(default 365, 1..36500). Units vary BY SERIES, so read `units` "
            "before comparing anything. U.S.-government / public-domain series "
            "only, decided in three steps: a REFUSED roster of 14 ids with a "
            "known non-government rights holder (the ICE BofA OAS family, VIXCLS, "
            "UMCSENT, MICH, SP500, DJIA, NASDAQCOM, MORTGAGE30US, AAA) is refused "
            "with INVALID_PARAMS and NO request at all; a CLEARED roster of 40 "
            "reviewed federal series always serves; anything else is decided by "
            "FRED's own series metadata -- a third-party copyright notice or a "
            "named licensor is refused. Requires FRED_API_KEY; cached 1h. Caveats "
            "ride the response's tool_notes."
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
            "The 20 most recent 8-K item events for a ticker from Oxford Ledge's "
            "8-K index of SEC EDGAR, NEWEST FIRST -- a fixed window with no "
            "caller-settable limit, so a recent-events feed, not a history. "
            "Returns {ticker, count, events, coverage, summary}; each event is "
            "{ticker, eventDate, eventType, headline, description, counterparty, "
            "counterpartyTicker, source, sourceUrl}. `eventType` is Oxford "
            "Ledge's 8-K item-to-category map (the one derived field); "
            "`description` is an excerpt of the filing text. `event_type` filters "
            "on the stored category; for M&A use acquisition_disposition. An "
            "unreachable store REFUSES rather than serving events=[]. `ticker` is "
            "required. Caveats ride the response's tool_notes. [Requires API "
            "mode]"
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
            "Which BDCs lend to one private-credit borrower, matched fuzzily on "
            "name -- Oxford Ledge's parse of SEC EDGAR BDC schedules of "
            "investments (ol-derived), not filer-published data. Returns "
            "borrowerName, borrowerNorm (the key get_bdc_borrower_mark_history "
            "and the ol_bdc_* tools take), description, descriptionSource, "
            "industry, aggregates over CURRENT holders (totalHolders, "
            "totalParAmount, totalFairValue, avgMarkedPrice) and `holders`, one "
            "row per TRANCHE. ABOVE-PAR TRAP: a mark above 100 is a par-basis "
            "artifact until fairValue is checked against cost, NOT a credit "
            "premium. `description` is a company profile, NOT filing text; a "
            "profile whose writer is not established is served with "
            "`_meta.ai_generated: true`. A miss is {found: false} -- a search "
            "miss, not a finding of no BDC exposure. `limit` / `offset` page "
            "`holders` only. Source: SEC EDGAR BDC schedules of investments "
            "(~45-60 day lag). Caveats ride the response's tool_notes. [Requires "
            "API mode]"
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
            "portfolio size -- our coverage, not the whole BDC universe; "
            "wound-down issuers are excluded by design. No arguments. Returns "
            "{bdcs}; per BDC: ticker, name, listed, holdingCount, totalFairValue "
            "(whole USD, latest filing), filingDate, lastParsed and a "
            "reconciliation block (reportedTotalFairValue, fairValueBasis, "
            "parsedRowSumFairValue, fairValueRefused, fairValueGap, "
            "fairValueGapNote). READ fairValueBasis BEFORE using totalFairValue, "
            "and fairValueGap with it: an under-counting parse keeps the "
            "parsed-row sum, which UNDERSTATES the book. holdingCount, "
            "totalFairValue and the arbitration are Oxford Ledge's parse, not "
            "filer-published figures. Borrower-keyed counterpart: "
            "search_bdc_borrower. Source: SEC EDGAR BDC filings (Oxford Ledge "
            "parse). Caveats ride the response's tool_notes. [Requires API mode]"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_bdc_borrower_mark_history",
        "description": (
            "Multi-quarter fair-value mark history for one borrower across every "
            "BDC that holds its debt, NEWEST QUARTER FIRST: per-quarter min/max "
            "and par-weighted average marks (percent of par, 2dp), holding-row "
            "and holder counts, and the contributing BDC tickers. Returns "
            "{borrowerNorm, count, quarters, units}. Exact borrower_norm match "
            "only -- resolve the key with search_bdc_borrower first. ABOVE-PAR "
            "TRAP: a mark above 100 is a par-basis artifact until fair value is "
            "checked against cost on the holding rows (get_bdc_holdings), NOT a "
            "credit premium. ATTRIBUTION: Oxford Ledge's parse of SEC EDGAR BDC "
            "schedules of investments (ol-derived), not a filer-published series. "
            "Caveats ride the response's tool_notes. [Requires API mode]"
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
            "Full portfolio holdings for one BDC's latest SEC filing: borrower, "
            "industry, security type, lien position, rate, maturity, "
            "par/cost/fair value and mark per position, plus portfolio-level "
            "totals, structure metrics and `topIndustries`. Money is whole USD; "
            "marks are percent of par. `totalFairValue` is ARBITRATED: read "
            "`fairValueBasis` and `fairValueRefused` first. ABOVE-PAR TRAP: a "
            "mark above 100 is a par-basis artifact until fairValue is checked "
            "against costAmount, NOT a credit premium. A large book serialises "
            "past 100,000 characters: `limit` / `offset` page the `holdings` rows "
            "while every total stays computed over the whole book, and nothing is "
            "dropped to fit. The totals, structure metrics and arbitration are "
            "Oxford Ledge's parse of SEC EDGAR schedule-of-investments filings "
            "(10-Q/10-K), not filer-published figures. `ticker` is required. "
            "Caveats ride the response's tool_notes. [Requires API mode]"
        )
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "BDC ticker symbol (e.g. ARCC, OBDC — see get_bdc_list)"},
                "limit": {"type": "integer", "description": "Max `holdings` rows to return (default 5000 = every row; hard cap 5000, refused above). Pages the row list only.", "minimum": 1, "maximum": 5000},
                "offset": {"type": "integer", "description": "Rows to skip before the page (default 0; max 5000). Past the end returns an empty page with `page.total` intact.", "minimum": 0, "maximum": 5000},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_debt_maturities",
        "description": (
            "Forward debt maturity ladder parsed by Oxford Ledge from the latest "
            "10-K/20-F footnote (the hosted EDGAR-only tool, proxied by name). "
            "Returns {ticker, maturities:[{year, amount}], thereafter, "
            "confidence, confidence_score, source, validation}. AMOUNTS ARE IN "
            "MILLIONS OF USD, not raw dollars -- 400 means $400M. THE LADDER IS "
            "AS OF the filing date, not today: the current-year bucket may "
            "already be repaid or refinanced. Check `validation` (the "
            "balance-sheet cross-check) before quoting a total. confidence / "
            "confidence_score / validation are Oxford Ledge's assessment of its "
            "own parse; the amounts are the filing's. EDGAR only -- no vendor "
            "debt totals and no modelled ladder. For historical "
            "issuance/repayment use get_capital_allocation. Source: SEC EDGAR "
            "10-K note extraction. Plus tier: the refusal is AUTH_REQUIRED naming "
            "the tier -- keyless, it says the client is anonymous and the "
            "operator sets OXFORD_LEDGE_API_KEY; with a valid key on a lower "
            "plan, it says THE KEY IS VALID and the plan is what is missing. "
            "Caveats ride the response's tool_notes. [Requires API mode]"
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
            "Where a company sent its cash, up to 30 annual labels, from SEC "
            "EDGAR XBRL cash-flow tags (the hosted scorecard tool, proxied by "
            "name). Returns {ticker, capitalAllocation:{years, periods, "
            "dividends, netBuybacks, grossRepurchases, netDebtChange, "
            "acquisitions, sharesOut, isDilutive, basis, summary}} as PARALLEL "
            "ARRAYS aligned to `years` (newest first, fiscal labels). netBuybacks "
            "is a NET, DERIVED DILUTION PROXY, not a buyback figure (repurchases "
            "minus issuance, IPO proceeds and SBC); grossRepurchases is the filed "
            "line. An IFRS reporter is REFUSED, never served zeros. The net "
            "series and the summary are Oxford Ledge derivations over the filed "
            "tags (basis hybrid); the inputs are the filing's. Complements "
            "get_fundamentals and get_debt_maturities. Source: SEC EDGAR XBRL "
            "cash-flow tags, 24h cache. Plus tier: the refusal is AUTH_REQUIRED "
            "naming the tier -- keyless, it says the client is anonymous and the "
            "operator sets OXFORD_LEDGE_API_KEY; with a valid key on a lower "
            "plan, it says THE KEY IS VALID and the plan is what is missing. "
            "Caveats ride the response's tool_notes. [Requires API mode]"
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
            "numeric CIK (preferred) or a ticker resolved via SEC's company map "
            "(BLK; BRK-B or BRK.B for Berkshire). A filer NAME is NOT resolved by "
            "this package -- pass the CIK. Returns {cik, fundName, filingDate, "
            "periodOfReport, totalHoldings, totalValue, holdings}; each holding "
            "is {name, title_of_class, value (whole USD), shares, type, "
            "position_type, lots, ticker}. `position_type` is COM|PRN|PUT|CALL: "
            "do NOT sum across types. `holdings` is truncated to max_holdings "
            "(default 50, cap 500) while the totals cover the whole filing. "
            "Source: SEC EDGAR 13F-HR, ~45-day quarterly delay; heavy operation, "
            "max 2 concurrent. Caveats ride the response's tool_notes. [Requires "
            "API mode]"
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
            "A value-investing principle, historical fact or attributed "
            "paraphrase from Oxford Ledge's curated corpus (~2,000 entries about "
            "Buffett, Graham, Munger, Klarman and others). THE WORDING IS NOT "
            "VERIFIED against the primary source: none is a verbatim quotation "
            "unless `verbatim` is true -- so never present the text as the "
            "author's exact words, and credit it with the `attribution` line. "
            "Returns a flat fact: {quote, author, source, source_year, category, "
            "subcategory, era, difficulty, verbatim, attribution}. Cached 24h per "
            "argument set -- vary `category` for a different pick. Caveats ride "
            "the response's tool_notes. [Requires API mode]"
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
            "MOAT / BDC discovery: the private-credit borrowers syndicated across "
            "the MOST BDCs, ranked by ACTIVE lender count (holder_count_active), "
            "then holder_count, then exposure -- the entrypoint for the "
            "BDC/private-credit category. Returns {summary, count, borrowers}; "
            "each row is {borrower, borrower_norm (the key other ol_bdc_* tools "
            "take), holder_count, total_fair_value (whole USD, latest filings), "
            "industry}. Feed a borrower_norm into ol_bdc_borrower_dispersion for "
            "cross-lender pricing. Caps: limit default 25 / hard 100; min_holders "
            "default 2 (max 50). An out-of-range `limit` is REFUSED, never "
            "clamped; the `completeness` block is the runtime truth on "
            "truncation. Source: SEC EDGAR BDC schedules of investments (Oxford "
            "Ledge parse; ol-derived); FREE (no paywall on the hosted channel). "
            "Caveats ride the response's tool_notes. [Requires API mode]"
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
            "MOAT: cross-lender loan-pricing DISPERSION for one private-credit "
            "borrower -- how N different BDCs each price the SAME loan (spread / "
            "mark / fair value); when one BDC marks a borrower S+550 @ 98 and "
            "another S+575 @ 99, the lenders disagree on the credit. Pass the "
            "canonical `borrower_norm` (from ol_bdc_top_borrowers or "
            "search_bdc_borrower). Returns {summary, borrower_norm, count, "
            "lender_count, tranche_count, lenders, ...}: ONE row per BDC lender, "
            "widest spread first, tranches nested. UNITS TRAP: `spread` is the "
            "raw as-filed number and mixes percent and bps across filers -- "
            "compare lenders on `spread_bps` only. Exited positions are excluded "
            "by default (include_stale=true shows them). Default 25 lenders, hard "
            "cap 100. Source: SEC EDGAR BDC schedules of investments (Oxford "
            "Ledge parse; ol-derived); FREE (no paywall on the hosted channel). "
            "Caveats ride the response's tool_notes. [Requires API mode]"
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
                    "description": "Max LENDERS to return (default 25, hard cap 100); each lender's tranches ride nested.",
                    "maximum": 100,
                },
                "include_stale": {
                    "type": "boolean",
                    "description": "Include lenders whose newest filing no longer names this borrower (stale marks). Default false.",
                },
            },
            "required": ["borrower_norm"],
        },
    },
    {
        "name": "ol_bdc_common_borrowers",
        "description": (
            "Borrowers common to a GIVEN SET of BDCs -- the cross-portfolio set "
            "question ('what do ARCC, OBDC and AGTC all lend to?') in ONE call. "
            "Returns per borrower: borrower, borrower_norm, holder_count, "
            "holder_tickers, holders ([{ticker, name}]), total_fair_value and "
            "total_par_amount in USD, and as_of_oldest/as_of_newest. Each BDC is "
            "read at ITS most recent filing, so rows MIX filing dates -- read "
            "as_of_range before treating the marks as contemporaneous. Debt "
            "positions only. Caps: more than 25 bdc_tickers is REFUSED as "
            "INVALID_PARAMS, limit 50/200, min_holders max 50. Feed a "
            "borrower_norm to ol_bdc_borrower_dispersion for cross-lender "
            "pricing. Source: SEC EDGAR BDC schedules of investments (Oxford "
            "Ledge parse -- ol-derived); FREE (no paywall on the hosted channel). "
            "Caveats ride the response's tool_notes. [Requires API mode]"
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
        "description": "Recent SEC Form D private-placement filings from the SEC's QUARTERLY "
                       "Form D data set -- newest first, optionally scoped to an industry "
                       "group and/or a trailing filing-date window. Returns {summary, count, "
                       "days, industry, offerings}. Amounts are whole USD as disclosed; "
                       "total_offering_amount is a ceiling, not money raised. The data set "
                       "lands about one quarter after quarter-end, so a short `days` window "
                       "is EMPTY BY CONSTRUCTION -- not evidence that nothing was filed. "
                       "`limit` default 50, hard cap 200. Source: SEC EDGAR Form D data sets "
                       "(public domain); FREE (no paywall on the hosted channel). Caveats "
                       "ride the response's tool_notes. [Requires API mode]",
        "inputSchema": {
            "type": "object",
            "properties": {
                "industry": {
                    "type": "string",
                    "description": "Industry group filter (optional).",
                },
                "days": {
                    "type": "integer",
                    "description": "Trailing filing-date window in days (optional; 1..1825; omit it for the 365-day default -- a value below 1 is refused as INVALID_PARAMS before any request, never widened to the default). The data set is quarterly with ~1 quarter of posting lag: a window that starts after the envelope's `data_through` is empty by construction, and the empty-window summary says so, naming `data_through`. There is deliberately no schema floor above 1: the lag is a property of the loaded data (days behind on the day a quarter's set lands, months behind just before the next), not a constant a schema could state.",
                    "minimum": 1,
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
        "description": "Recent OPEN-MARKET insider PURCHASES (SEC code 'P') across the "
                       "Oxford Ledge issuer catalog (~5.3k tickers) -- a daily insider "
                       "screen. Returns {summary, since_days, count, buys}, NEWEST FIRST; "
                       "each buy carries ticker, filing and transaction dates, insiderName, "
                       "position, shares, pricePerShare, totalValue (USD), url. since_days "
                       "default 30 (hard cap 180), limit default 25 (hard cap 100). SAMPLING "
                       "TRAP: when the window holds more purchases than `limit`, you get the "
                       "NEWEST N filings, not the whole window -- never total these rows and "
                       "call it the period's insider buying. totalValue and the fallback "
                       "`position` label are Oxford Ledge derivations (basis hybrid). "
                       "Source: SEC EDGAR Form 4 (public domain); FREE (no paywall on the "
                       "hosted channel). Pairs with get_insider_trades (one ticker). Caveats "
                       "ride the response's tool_notes. [Requires API mode]",
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
                "common_only": {
                    "type": "boolean",
                    "description": "Common stock only (default true): drops derivative rows and any security title naming preferred / pfd / warrant / debenture / note; Series-named common classes are kept. false restores every open-market purchase.",
                },
                "min_value": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Only purchases with totalValue >= this many USD (optional); rows with no plausible filed price are dropped when this is set.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_fails_to_deliver",
        "description": "SEC fails-to-deliver history for one ticker -- the "
                       "settlement-failure side of short pressure. Returns {ticker, days, "
                       "history, count, coverage, as_of, summary}; each row is {date "
                       "(settlement date), fails (SHARES, not dollars), price (USD), "
                       "description}, OLDEST-FIRST. `days` (default 180, hard cap 730) is "
                       "anchored to the latest LOADED settlement date (`as_of`), not to "
                       "today. An empty or thin history describes the loaded SEC files, not "
                       "an absence of fails: read `coverage` and `summary` before quoting a "
                       "window as fail-free. Figures are as SEC published: NOT "
                       "split-adjusted. Source: SEC Fails-to-Deliver dataset (published "
                       "twice monthly, ~3-week lag). Caveats ride the response's tool_notes. "
                       "[Requires API mode]",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g. GME)",
                },
                "days": {
                    "type": "integer",
                    "description": "Trailing window in days (default 180, max 730), counted inclusively -- a 90-day window holds 90 settlement dates -- and ending at `as_of` unless end_date is given",
                    "minimum": 1,
                    "maximum": 730,
                },
                "end_date": {
                    "type": "string",
                    "description": "ISO date (YYYY-MM-DD) the window ends on; default = the latest loaded settlement date (`as_of`). Pass today's date to measure against the calendar; a future date is clamped to today.",
                },
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_activist_stakes",
        "description": "Schedule 13D/13G >5% beneficial-owner filings for a ticker -- "
                       "event-driven stake-building, unlike quarterly 13F. Returns {ticker, "
                       "count, filings}, newest first, limit default 50 (hard cap 200); rows "
                       "carry filer_name, filing_date, form_type, shares, percent_of_class, "
                       "accession_number and is_activist (a FORM-TYPE label: true iff the "
                       "form is a 13D, not a judgement). `reports_zero` is the filer's own "
                       "statement that it no longer owns more than 5% -- an exit OR a "
                       "reporting realignment, so cross-check get_holders before reading it "
                       "as a sale. FRESHNESS: keyless callers are served STORED rows and "
                       "never trigger the EDGAR refresh -- read `stale` and `stale_basis`. "
                       "Source: SEC EDGAR. Caveats ride the response's tool_notes. [Requires "
                       "API mode]",
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
        "description": "US Treasury debt composition from the Monthly Statement of the "
                       "Public Debt. Omit BOTH args for the newest month's full class "
                       "breakdown; pass security_type AND security_class together for that "
                       "one class's monthly history (passing only one of them is IGNORED). "
                       "Returns {summary, rows}. AMOUNTS ARE IN MILLIONS OF USD -- a "
                       "28,000,000 value means $28 trillion. The breakdown holds component "
                       "AND Total rows, so summing a column double-counts. `limit` (series "
                       "only) default 120 months, hard cap 360. Sibling of get_yield_curve. "
                       "Source: Treasury.gov MSPD (public domain); FREE (no paywall on the "
                       "hosted channel). Caveats ride the response's tool_notes. [Requires "
                       "API mode]",
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
        "description": "CFTC Commitments-of-Traders positioning for THREE curated markets "
                       "(keys gold, crude_oil, sp500). Pass `market` for its weekly history, "
                       "NEWEST FIRST (names are normalised: 'wti', 'GOLD', 'e-mini s&p' "
                       "resolve), or omit it for the latest report across the three. Returns "
                       "{summary, market, matched_market, rows}. mm_* and open_interest are "
                       "CONTRACT counts, not dollars, and mm_* cover ONE speculative "
                       "category per report family (Managed Money for gold and crude_oil, "
                       "Leveraged Funds for sp500). `limit` (series only) default 52, hard "
                       "cap 156. Source: CFTC.gov (public domain); FREE (no paywall on the "
                       "hosted channel). ATTRIBUTION: every field is CFTC verbatim EXCEPT "
                       "market_key and market_label (Oxford Ledge's curated market catalog), "
                       "matched_market and candidates (Oxford Ledge's resolver over that "
                       "catalog) and mm_net (mm_long minus mm_short, computed by Oxford "
                       "Ledge). Caveats ride the response's tool_notes. [Requires API mode]",
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
        "description": "FDIC-insured banks and thrifts. Pass `query` for a name PREFIX "
                       "search against ACTIVE institutions (largest-asset first), or omit it "
                       "for the largest active institutions. Returns {summary, query?, "
                       "institutions}, each {cert, name, stname, city, bkclass, active, "
                       "asset, dep, estymd, webaddr, ticker, repdte}. UNITS: `asset` and "
                       "`dep` are THOUSANDS of dollars. The store is loaded ACTIVE-ONLY, so "
                       "a bank that merged away or failed is absent by construction -- an "
                       "empty search is a fact about the loaded store, never about the "
                       "world. `limit` default 25, hard cap 100. Source: FDIC.gov (public "
                       "domain); FREE (no paywall on the hosted channel). ATTRIBUTION: every "
                       "field is FDIC BankFind verbatim EXCEPT `ticker`, which is an Oxford "
                       "Ledge-verified CERT-to-ticker mapping, not an FDIC-published field. "
                       "Caveats ride the response's tool_notes. [Requires API mode]",
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
        "description": "Federal-contract obligation history for a ticker, OR the fiscal-year "
                       "leaderboard -- for government-revenue-dependence diligence. TWO "
                       "SHAPES: one of `ticker` or `fiscal_year` is REQUIRED (if both, "
                       "`ticker` wins). With `ticker`: per-fiscal-year obligations (USD, the "
                       "ten largest recipients, dropped_unresolved), NEWEST FY FIRST; with "
                       "fiscal_year only: a leaderboard, largest first. A fiscal year still "
                       "in progress is PARTIAL (period_complete false) and year-to-date -- "
                       "never compare it to a full year. Obligations are federal awards, not "
                       "company-reported revenue. `limit` default 20, hard cap 100. Source: "
                       "USAspending.gov (public domain; OL ticker-crosswalked); FREE (no "
                       "paywall on the hosted channel). Attributing awards to a ticker is an "
                       "Oxford Ledge curated crosswalk. Caveats ride the response's "
                       "tool_notes. [Requires API mode]",
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
        "description": "Recent USPTO patent filings for a ticker (innovation-intensity "
                       "diligence). Returns {summary, ticker, count, filings}, NEWEST FIRST; "
                       "`limit` default 50, hard cap 200, so this is a recent slice, never a "
                       "full portfolio, and `count` is the number RETURNED. TRAP: a "
                       "non-empty patent_number marks a continuation of an already-granted "
                       "PARENT, NOT a grant of this application -- read the status field. "
                       "Filings reflect Oxford Ledge's last on-demand USPTO ingest for the "
                       "ticker, not a schedule. Source: USPTO (public domain); FREE (no "
                       "paywall on the hosted channel). ATTRIBUTION: every filing field is "
                       "USPTO ODP verbatim EXCEPT `ticker`, which is an Oxford Ledge "
                       "applicant-name resolution, not a USPTO field. Caveats ride the "
                       "response's tool_notes. [Requires API mode]",
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
        "description": "MOAT / private credit: the largest quarter-over-quarter MARK moves "
                       "across a SET of BDC portfolios -- 'which borrowers got marked up or "
                       "down the most last quarter, and by whom' in ONE deterministic call. "
                       "Returns {increases, decreases}, each a global ranking; each row is "
                       "{borrower, portfolio, prior_mark, latest_mark, mark_delta, "
                       "prior_filing, latest_filing}. Marks are percent of par, "
                       "fair-value-weighted across the BDC's tranches; mark_delta is in "
                       "points. A borrower enters only when |mark_delta| >= 1.0 point and "
                       "its fair value is >= $500k, so 'no moves' can hide small drifts. "
                       "`coverage` names every BDC that was NOT read and why. bdc_tickers "
                       "capped at 25; limit default 10 / hard 50 per direction. ATTRIBUTION: "
                       "Oxford Ledge's parse of SEC EDGAR BDC schedules of investments "
                       "(ol-derived), not a filer-published series; FREE (no paywall on the "
                       "hosted channel). Caveats ride the response's tool_notes. [Requires "
                       "API mode]",
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
        "description": "BDC non-accrual credit-deterioration signal: the share of debt fair "
                       "value on non-accrual (loans that stopped paying) in the latest "
                       "filing, plus the trailing-quarter trend. Returns {summary, ticker, "
                       "latest, trend}; `trend` is OLDEST-FIRST. flagged_pct is a percentage "
                       "over the DETERMINATE-flag denominator, never total_debt_fv, and it "
                       "is deliberately NULL (withheld, never zero) when determinate "
                       "coverage is under 90% of debt fair value or the flag rate looks like "
                       "a parse misread -- read `coverage_state` before reading flagged_pct. "
                       "`quarters` default 12, hard cap 24. Pairs with "
                       "ol_bdc_borrower_dispersion and ol_bdc_top_borrowers. ATTRIBUTION: "
                       "Oxford Ledge's parse of SEC EDGAR BDC schedules of investments "
                       "(ol-derived), not a filer-published series; FREE (no paywall on the "
                       "hosted channel). Caveats ride the response's tool_notes. [Requires "
                       "API mode]",
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
