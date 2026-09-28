"""Per-tool caveat notes the pip package attaches to every response.

MCP-E (external MCP audit E1, 2026-09-26; OWNER R-MCP-AWARE ruling 3 -- the
3.8.0 content). The wheel's 29 tool descriptions measured 70,912 characters
at 43ea7312 (the audit's read of the published wheel: 68,511; the longest,
search_bdc_borrower, 4,767 here), paid by every connected session before its
first call. They were cut to about 1,200 characters each -- what the tool
returns, its key arguments, its source or basis, and the ONE caveat
a caller must know before calling -- and every other caveat MOVED HERE, to be
read WITH the data it qualifies. The dispatch seam
(server._execute_tool_with_limits) puts the tool's tuple on the response
under the envelope key `tool_notes`, after the emit allowlist and before the
cache write, so a replay carries the same notes.

`tool_notes` rather than `notes`: `notes` is a data field name elsewhere
(FRED series metadata, borrower profiles), and the fail-closed allowlist
admits envelope keys at every depth of a payload.

These are the WHEEL's own notes and they REPLACE any `tool_notes` a hosted
answer carried through a name-proxied call: the wheel's description is what
this package's caller read, so the notes that complete it are this table's.

COUNSEL condition (BOARD 2026-09-26): licence, terms, basis, "not verified"
and refusal notices reach the caller in the response, never silence. FRED's
licence refusal roster stayed in its description verbatim.
"""
from __future__ import annotations

import json
from typing import Any

NOTES_KEY = "tool_notes"


def place_notes(result: dict, notes: list) -> dict:
    """A COPY of `result` with `notes` under `tool_notes`, placed right after
    `summary` (or FIRST when there is no `summary`), never at the tail.

    CHAOS 2026-09-26 FIX-1 / TRACK-1: appended at the tail, the notes landed
    AFTER `attribution` / `disclaimer`, which the dispatch seam pins as the
    last two keys, and a cache replay (`mark_served_from_cache` re-tails the
    disclosure) then serialized in a different order from the first call. At
    the head they are also what a client that truncates a long result keeps.
    Any `tool_notes` already present (the hosted copy a name-proxied answer
    carried) is dropped and re-placed, never nested or duplicated.
    """
    out: dict = {}
    if "summary" not in result:
        out[NOTES_KEY] = notes
    for k, v in result.items():
        if k == NOTES_KEY:
            continue
        out[k] = v
        if k == "summary":
            out[NOTES_KEY] = notes
    return out


def notes_chars(result: Any) -> int:
    """Serialized chars the `tool_notes` entry adds to `result` (0 if none):
    the length of `{"tool_notes": [...]}` -- the entry plus one `, `."""
    if not isinstance(result, dict) or NOTES_KEY not in result:
        return 0
    try:
        return len(json.dumps({NOTES_KEY: result[NOTES_KEY]}, default=str))
    except (TypeError, ValueError):
        return 0


def attach_tool_notes(tool_name: str, result: Any) -> Any:
    """Return `result` with the tool's notes under `tool_notes` (a copy),
    placed near the head (see `place_notes`). A non-dict result and a tool
    with no notes are returned unchanged. The input dict is never mutated.

    CHAOS 2026-09-26 TRACK-3: a name-proxied answer arrives with the HOST's
    `_meta.response_size`, measured over the host's own notes. When this swap
    replaces a hosted copy, the block's `chars` / `approx_tokens` move by the
    exact difference, so the block still describes what ships (`over_budget`
    judges the data without the notes on both surfaces, so it does not move).
    A payload that carried no hosted copy keeps the host's block untouched.
    """
    notes = TOOL_NOTES.get(tool_name)
    if not notes or not isinstance(result, dict):
        return result
    before = notes_chars(result)
    out = place_notes(result, list(notes))
    meta = out.get("_meta")
    size = meta.get("response_size") if isinstance(meta, dict) else None
    if before and isinstance(size, dict) and type(size.get("chars")) is int:
        size = dict(size)
        size["chars"] += notes_chars(out) - before
        size["approx_tokens"] = size["chars"] // 4
        out["_meta"] = {**meta, "response_size": size}
    return out


TOOL_NOTES: dict[str, tuple[str, ...]] = {
    "get_holders": (
        (
            "Each row is {holder, fund_cik (the filer's SEC CIK, when the "
            "filing carries one -- it is what `superseded_by` names), shares, "
            "value (whole USD, as reported at the filer's own period-end), "
            "type, quarter, filingDate}."
        ),
        (
            "Because rows are each filer's latest filing, one call can mix "
            "quarters: `asOf` is present only when every returned row shares "
            "one quarter; otherwise `vintages` lists {quarter, count} over the "
            "returned rows and `rankingBasis` says the ranking is not "
            "price-normalised."
        ),
        (
            "`coverage` (when present) is the single-quarter 13F snapshot: its "
            "`quarter` is the honest as-of anchor. Each row's `stale_quarters` "
            "is its distance from that anchor (0 = current; the key is ABSENT, "
            "never 0, when the row could not be dated); a row struck NEWER than "
            "the anchor keeps `stale_quarters` 0 and adds `ahead_quarters` (>= "
            "1, absent otherwise), the only thing separating it from a row AT "
            "the anchor."
        ),
        (
            "A stale filer whose shares reconcile to same-quarter siblings of "
            "its own fund-name family is WITHHELD from `holders` and recorded "
            "in `superseded_parents`: the same row shape plus `superseded: "
            "true`, `superseded_by` (the `fund_cik`s of the rows that supersede "
            "it; each served row carries `fund_cik`, so the reference resolves "
            "inside this same payload whenever the superseding row survived the "
            "top-10 cut) and BOTH operands of the reconciliation -- the row's "
            "own `shares`, `superseded_by_shares` (the sibling sum) and "
            "`reconciled_pct` (their distance apart AS A PERCENTAGE OF THE "
            "WITHHELD ROW'S OWN `shares`)."
        ),
        (
            "When the producer did not state one of those parts in a usable "
            "form, that key is ABSENT and the row carries `unstated` naming it "
            "-- read such a row as a withholding whose arithmetic or "
            "attribution is missing, never as a reconciled one."
        ),
        (
            "A withheld row that is ALSO present in `holders` carries "
            "`also_in_holders: true`: the two lists are built independently, so "
            "for that row the fold did NOT remove the double count, and "
            "counting the withheld copy as well doubles it again."
        ),
        (
            "If the whole key `superseded_parents` is missing while the top "
            "level carries `unstated: [\"superseded_parents\"]`, the producer "
            "sent the key in a shape this client could not read: treat the fold "
            "as NOT RUN rather than as having withheld nothing."
        ),
        (
            "`superseded_parents` is capped at 10 like `holders`; "
            "`completeness.supersededReturned` / "
            "`completeness.supersededWithheldTotal` disclose that cut. `[]` "
            "means the fold ran and withheld nothing AMONG THE ROWS IT COULD "
            "DATE: a row carrying no `stale_quarters` was never eligible to be "
            "folded, so an `[]` beside undated rows is not a finding that no "
            "double count exists -- the wire cannot distinguish the two cases."
        ),
        (
            "Do NOT add withheld rows back into `holders` or into any total: "
            "that restores the double count the fold removes."
        ),
        (
            "`vintages`, `rankingBasis`, `coverage`, `stale_quarters`, "
            "`ahead_quarters` and the `superseded_parents` fold are Oxford "
            "Ledge computations over the 13F rows; the rows themselves are the "
            "filings' figures."
        ),
        (
            "The `completeness` block discloses the top-10 cut against the "
            "total holder count; `completeness.complete` is false whenever "
            "anything was withheld -- it answers 'is this every filer'."
        ),
        (
            "An EMPTY `holders` list comes with a `note` naming the scope "
            "(13F-HR COM positions, last 6 quarters; the ticker must be in the "
            "13F universe) -- a scoped statement, not proof that nobody owns "
            "the stock. When the fold withheld every row the producer returned, "
            "the `note` says THAT instead and the withheld rows are in "
            "`superseded_parents`."
        ),
        (
            "If the API answers with an error body, its `error` string is "
            "passed through and `completeness.complete` is null: read `error` "
            "before reading `holders`."
        ),
    ),
    "get_sec_filings": (
        (
            "`completeness` is {returned, cap: 10, windowRows, windowFrom}: the "
            "read covers only SEC's most-recent-1000 submissions index for the "
            "filer (`windowRows` rows, back to `windowFrom`), so a filtered "
            "read can return fewer than 10 rows and nothing older than "
            "`windowFrom` is visible through this tool."
        ),
        (
            "An empty `filings` list carries an `error` string naming the "
            "window."
        ),
    ),
    "get_insider_trades": (
        (
            "Each trade is {insider, position, shares, pricePerShare, "
            "priceApplicable, value, sharesOwned, type, transTypeLabel, "
            "is_open_market, securityTitle, isDerivative, transactionDate, "
            "filingDate, dateBasis, date, url}."
        ),
        (
            "`priceApplicable` is false when the filing reports a price of 0 on "
            "a code that has no price (A award, G gift, J other, W will or "
            "inheritance, Z voting trust): that 0, and the 0 `value` built from "
            "it, mean no price, not a free trade; it is true on every other "
            "row, including a null price (unknown)."
        ),
        (
            "`date` is the filing date when the filing carries one, and "
            "`dateBasis` names the date actually served ('filing' when `date` "
            "is filingDate, 'transaction' only when no filing date exists) -- "
            "read `transactionDate` for when the trade happened."
        ),
        (
            "`type` is the raw SEC code, `transTypeLabel` its decode, "
            "`is_open_market` is true only for codes P and S."
        ),
        (
            "`shares` is SIGNED (negative on dispositions); `pricePerShare` is "
            "the filed price unrounded (4 dp); `value` = |shares| x price, "
            "computed by Oxford Ledge at ingest from the filing's own figures; "
            "both are null when the filed price failed the ingest plausibility "
            "gate or the filing carried none."
        ),
        (
            "`position` is the filer's reported title, or Officer / Director / "
            "10% Owner / Insider when the filing left it blank."
        ),
        (
            "Rows with `isDerivative` true (RSU awards, option legs, notes; "
            "`securityTitle` names the instrument) carry derivative-security "
            "counts and exercise prices, not common-stock trades -- do not add "
            "them to share counts."
        ),
        (
            "`url` is the EDGAR filing document for current rows and the "
            "issuer's Form 4 index for legacy rows."
        ),
        (
            "`completeness` is {returned, totalFetched, complete}: "
            "`totalFetched` is the route's window (`limit` rows), not the "
            "issuer's total, and `complete` is null when the window was full "
            "(older filings may exist beyond it)."
        ),
        (
            "An empty `trades` list carries a `note` naming the scope; an API "
            "error body passes through as `error` with `completeness.complete` "
            "null."
        ),
        (
            "Each row also carries formType (the Form 4 type as filed, '4' or "
            "'4/A'), accessionNumber (the filing), isAmendment (true for a 4/A; "
            "null when the store holds no form type), and supersedesAccession: "
            "a Form 4 and its 4/A that report the SAME line (identical filer, "
            "date, code, shares, price, shares-owned-after, security title and "
            "derivative flag) are served ONCE, as the amendment, with "
            "supersedesAccession naming the folded original -- so summing "
            "shares or value over the list no longer double-counts an amended "
            "filing. A 4/A that CORRECTED a value is a different line and is "
            "served beside its original; isAmendment says which is which."
        ),
        (
            "Each row also carries issuerSelfFiled: true when the Form 4 was "
            "filed under the company's own SEC ID (the reporting-owner CIK "
            "equals the issuer's CIK), so the reporting-owner field names the "
            "company rather than a person -- the filing's footnotes may still "
            "name the officer. Oxford Ledge lists these rows but never counts "
            "them in its own buy/sell summaries, net figures or insider "
            "clusters; leave them out when you total the list. false whenever "
            "either CIK is missing (never a guess). The key is ABSENT (not "
            "false) when the Oxford Ledge server that answered does not send it "
            "(a host older than this package): read that as unknown."
        ),
    ),
    "get_fundamentals": (
        (
            "An IFRS reporter gets a structured DATA_UNAVAILABLE refusal naming "
            "`taxonomy`, and a Canadian MJDS filer whose XBRL is furnished on "
            "Form 6-K in CAD (CNI) is refused with `annualFormsSeen` / "
            "`unitsSeen` naming why."
        ),
        (
            "`data` maps each label to up to 10 annual points {period (the "
            "fiscal-period END date), value}, newest first. UNITS: whole USD; "
            "EPS is USD per share; DilutedShares is a share count."
        ),
        (
            "`LongTermDebt` is us-gaap:LongTermDebt with a "
            "LongTermDebtNoncurrent fallback -- it is NOT total debt "
            "(commercial paper, short-term borrowings and, in fallback years, "
            "the current portion are excluded); the pre-3.4.0 label `TotalDebt` "
            "was this same series under a false name."
        ),
        (
            "`StockholdersEquity` is the parent-only rung; for a filer that "
            "tags non-controlling interests, the consolidated rung "
            "(...IncludingPortionAttributableToNoncontrollingInterest) fills a "
            "period only when its NCI is demonstrably zero there (JNJ tags its "
            "10-K equity ONLY on that rung), `equityNote` says so, and a period "
            "with a non-zero NCI and no parent figure is withheld as {value: "
            "null, withheld: 'nci_consolidated'} with the NCI in "
            "`equityWithheldNci`."
        ),
        (
            "`concepts` mirrors `data`: for EVERY served label, a list "
            "[{period, concept}] index-aligned with data[label], naming the "
            "us-gaap concept that served each cell, so a series that mixes "
            "concepts across years is visible (`conceptsNote` explains the "
            "fallback rung)."
        ),
        (
            "`coverage` discloses per label {yearsAvailable (per-concept XBRL "
            "depth, counted before any withholding), contiguous} -- "
            "contiguous=false means the served periods skip at least one fiscal "
            "year (a tagging hole), so neighbouring rows are not "
            "year-over-year."
        ),
        (
            "`basis` is Oxford Ledge's split-basis check: an EPS or "
            "DilutedShares series that spans a stock split is withheld on the "
            "pre-split side ({value: null, withheld: 'split_basis'}) with the "
            "withheld values, the observed jump and the reasoning in `basis` "
            "(basisConsistent true = examined, one basis; false = a "
            "corroborated break, cells withheld; null = unexamined, OR an "
            "implied-share jump with no issuer refiling listed in basisAdvisory "
            "-- nothing withheld, nothing certified, basisNote says which)."
        ),
        (
            "A >= 5x step across a tagging hole that no examined year pair "
            "spans (DAC's 1-for-14 inside its 2012-2016 hole) withholds the "
            "older side as {value: null, withheld: 'basis_unverified'} with "
            "`basis.gapBreaks` / `gapNote`; `basis.attribution` names that "
            "block as Oxford Ledge's derivation over the filed facts -- every "
            "other value is the filing's, verbatim."
        ),
        (
            "For investment companies (BDCs, closed-end funds), "
            "OperatingCashFlow is routinely NEGATIVE because portfolio "
            "purchases run through operating activities under ASC 946 -- it is "
            "not a distress signal there."
        ),
    ),
    "get_yield_curve": (
        (
            "include_history=true adds `yield_curve_1y_ago` (the FRED "
            "observation nearest one year before each tenor's as_of, within a "
            "45-day tolerance; empty when none qualifies) and "
            "`history_coverage` {maturities_with_prior, maturities_total, "
            "lookback_tolerance_days}."
        ),
        (
            "When fewer than 11 tenors could be read, a `completeness` block "
            "{maturities_total: 11, maturities_missing, reason} says which are "
            "missing and why; a curve with no readable tenor raises "
            "DATA_UNAVAILABLE naming the cause."
        ),
    ),
    "get_fred_data": (
        (
            "`count` is len(data), and `name` / `units` / `frequency` come from "
            "FRED's series metadata -- units vary BY SERIES (GDP is billions of "
            "dollars, UNRATE is percent), so read `units` before comparing "
            "anything."
        ),
        (
            "An empty window carries a `note` saying the window returned no "
            "observations (a quarterly series with a short `days`, or "
            "all-suppressed newest cells) -- not that the series has no data."
        ),
        (
            "Series ids must match FRED's id charset (^[A-Z0-9_.-]{1,40}$); "
            "anything else is refused with INVALID_PARAMS before any request is "
            "made."
        ),
        (
            "The CLEARED roster of 40 reviewed federal series covers BLS, BEA, "
            "Census, ETA, the Board of Governors' H.15/H.4.1/H.6/H.10/G.17 "
            "releases, the St. Louis and New York Fed."
        ),
        (
            "Anything else is decided by FRED's own series metadata -- a "
            "third-party copyright notice or a named licensor (S&P Dow Jones, "
            "ICE BofA, Moody's, CBOE, University of Michigan ...) is refused, "
            "while a BLS/BEA series whose title merely contains such a word "
            "(MIUR, 'Unemployment Rate in Michigan') is served. An id FRED does "
            "not know is refused as unknown."
        ),
        (
            "When FRED's metadata is unreachable, only a cleared or "
            "known-government-prefixed id serves and the rest are refused as "
            "unverifiable."
        ),
    ),
    "get_corporate_events": (
        (
            "`coverage` = {rows_stored, oldest_event_date, newest_event_date} "
            "is what the store holds for the ticker regardless of the filter, "
            "and `summary` says why a result is empty (nothing indexed for the "
            "ticker vs the filter matched none of the N stored)."
        ),
        (
            "`eventType` is Oxford Ledge's 8-K item-to-category map (the one "
            "derived field; e.g. Item 1.01 -> material_agreement, Item 2.02 -> "
            "earnings, Item 5.02 -> executive_change); `headline` is the SEC "
            "item title; `description` is an excerpt of the filing text (an "
            "earnings row, once filled, leads with its press release's headline "
            "when one was found); `sourceUrl` is the EDGAR filing."
        ),
        (
            "An empty (or null) `description` is a filing whose text has not "
            "been read yet (not fetched, or it could not be extracted), never "
            "a filing that says nothing: open `sourceUrl` to read it."
        ),
        (
            "`counterparty` is the other party Oxford Ledge's M&A interpreter "
            "read from an acquisition_disposition filing (served only at 0.5 "
            "confidence or above), else null; `counterpartyTicker` is always "
            "null (no writer fills it). No row id ships."
        ),
        (
            "`event_type` filters on the stored category; dividend / split / "
            "merger are accepted for compatibility but no 8-K writer emits them "
            "(for M&A use acquisition_disposition)."
        ),
        (
            "An unreachable store REFUSES (the route answers 503 with an error "
            "body, passed through) rather than serving events=[]."
        ),
    ),
    "search_bdc_borrower": (
        (
            "Oxford Ledge derivations: canonical-name pick, borrower "
            "normalisation, group merge, current-holder aggregates."
        ),
        (
            "Envelope: borrowerName, borrowerNorm, description, "
            "descriptionSource, industry, totalHolders, totalParAmount, "
            "totalFairValue, avgMarkedPrice/min/max, match_type, units, and "
            "`holders` -- one row per TRANCHE (bdcTicker, bdcName, filingDate, "
            "securityType, lienPosition, interestRate as filed, maturityDate, "
            "parAmount, fairValue, markedPrice, stale, staleBasis, "
            "holderStatus, successorTicker). `units` says it: USD; markedPrice "
            "is percent of par."
        ),
        (
            "ABOVE-PAR TRAP: markedPrice (and the avgMarkedPrice / min / max "
            "aggregates over it) is fair value over the FILED principal, and "
            "filers differ on what principal tracks -- par may exclude "
            "capitalised PIK/OID accretion, or the filer's principal field may "
            "equal cost -- so a row marked above 100 (Caitec at 145.74 is the "
            "measured case) is a par-basis artifact until fairValue is checked "
            "against cost, NOT a credit premium."
        ),
        (
            "`description` is a company profile, NOT filing text -- "
            "`descriptionSource` names its writer. Five values: only `csv` (a "
            "lender's SEC-filed business description) and `template` (a line "
            "Oxford Ledge builds from the filed sector) are not model-written, "
            "and for those `_meta` carries NO `ai_generated` flag; anything "
            "else -- the research-seed tag, `wellknown` (an uncited "
            "model-written blurb), `manual` (the store's DEFAULT when a writer "
            "was not stated, so NOT an attestation of a human author), or an "
            "ABSENT source -- is served with `_meta.ai_generated: true`: "
            "written from public web sources, not checked for copying. Read "
            "that flag as WRITER NOT ESTABLISHED, not as proof the text is "
            "model-written: over-labelling a one-line profile is the cheap "
            "error, under-labelling model prose is not, so the flag is "
            "deliberately conservative and `_meta.ai_generated_note` says which "
            "entries are known to be model-written."
        ),
        (
            "A caller with no account may get `description` null with "
            "`descriptionWithheld` for those rows; `descriptionSources`, when "
            "present, lists the pages the model cited."
        ),
        (
            "`priceHistory` holds ONE quarter per BDC -- not a time series; use "
            "get_bdc_borrower_mark_history."
        ),
        (
            "AGGREGATES count CURRENT holders only (aggregatesBasis "
            "'current_holders_only'): a row filed before that BDC's latest "
            "filing (staleBasis 'exited_position') or by a wound-down filer "
            "(staleBasis 'inactive_filer') stays in holders with stale=true but "
            "is excluded, so `holders` can have more rows than totalHolders; "
            "staleRowCount/staleHolderCount count them. All rows stale -> "
            "totalParAmount/totalFairValue null (not 0) with "
            "aggregatesRefusalReason; marks stay in holders[].fairValue."
        ),
        (
            "RELATED KEYS: a hit is ONE borrower_norm key, not necessarily the "
            "whole obligor; relatedNorms lists other keys sharing its prefix "
            "with current holders ({borrowerNorm, borrowerName, holderCount, "
            "holdingRowCount, totalFv}; relatedNormsBasis "
            "'prefix_of_resolved_key'; [] when none). relatedNormsStale lists "
            "prefix siblings with ZERO current holders (every row exited or "
            "filed by an inactive filer): holderCount 0, totalFv null (not "
            "measured on the current basis), holdingRowCount as stored; [] when "
            "none. Discovery is on key existence -- a fully-exited obligor "
            "still shows the other keys it is filed under."
        ),
        (
            "In the ambiguous `matches[]` list every candidate carries "
            "totalFvBasis 'current_holders_only', and a candidate with stored "
            "rows but no current holder carries totalFv null with "
            "totalFvRefusalReason -- never 0."
        ),
        (
            "A brand and its 'X Acquisition, LLC' vehicle can be separate keys: "
            "check it before reading totalHolders as the lender count, and "
            "query ol_bdc_borrower_dispersion per key."
        ),
        (
            "A MISS returns {found: false, match_type: null, message} -- a "
            "search miss, not a finding of no BDC exposure; ambiguous: {found: "
            "false, ambiguous: true, matches: [...], holders: []} -- re-call "
            "with a specific name (matches[].holderCount/totalFv are "
            "latest-filing-only). A hit carries match_type and no `found` key. "
            "Debt and equity included."
        ),
        (
            "PAGING (additive): `limit` / `offset` page the `holders` rows only "
            "-- every aggregate, holdingRowCount, priceHistory and relatedNorms "
            "stay computed over ALL rows; a call declaring either gets `page` "
            "{limit, offset, returned, total, hasMore} and a `completeness` "
            "block with total_available; an offset past the end is an empty "
            "page with total intact; out-of-range values are REFUSED, never "
            "clamped; a call declaring neither is unchanged (every row, up to "
            "the store's 5000-row backstop)."
        ),
    ),
    "get_bdc_list": (
        (
            "The reconciliation triple: reportedTotalFairValue (the filing's "
            "OWN stated grand total), fairValueBasis ('parsed-rows' or "
            "'filing-reported') and parsedRowSumFairValue; the refusal pair "
            "fairValueRefused / fairValueRefusalReason; the gap label "
            "fairValueGap / fairValueGapNote."
        ),
        (
            "When a parse over-counts, totalFairValue is swapped to the "
            "filing-reported figure and the raw row sum is preserved in "
            "parsedRowSumFairValue, so the two disagreeing numbers are both "
            "visible rather than silently reconciled (a parse recovering under "
            "half the filed total is swapped the same way); when it "
            "UNDER-counts by more than 5% but recovers at least half, "
            "totalFairValue stays the parsed-row sum -- every dollar of it a "
            "served row -- and UNDERSTATES the book, which only fairValueGap "
            "says."
        ),
        (
            "fairValueGap is null (the two agree within 5%, or cannot be "
            "compared) | 'rows_under_reported' | 'rows_over_reported' | "
            "'funded_basis_presentation' (a measured funded-basis filer, today "
            "FSK: its schedule reports FUNDED amounts above a headline net of "
            "unfunded commitments -- a presentation difference, not an "
            "over-count), and fairValueGapNote states the measured ratio in one "
            "sentence."
        ),
        (
            "reportedTotalFairValue is null, never 0, in TWO cases: the filing "
            "tags no usable grand total, or Oxford Ledge's stored reference "
            "describes a DIFFERENT filing than the book served, so it cannot "
            "reconcile -- a null reference carries no swap, no gap label and no "
            "refusal."
        ),
        (
            "lastParsed is the date Oxford Ledge last wrote this BDC's registry "
            "row (a repair counts), not the filing date; null when that read "
            "failed."
        ),
        (
            "When the store does not answer, holdingCount is null (never a "
            "measured 0) and a top-level `notice` says the counts were not "
            "measured."
        ),
        (
            "holdingCount, totalFairValue and the arbitration are Oxford "
            "Ledge's parse, not filer-published figures; ticker / name / listed "
            "are the registry."
        ),
    ),
    "get_bdc_borrower_mark_history": (
        (
            "ABOVE-PAR TRAP: the marks are fair value over the FILED principal "
            "and filers differ on what principal tracks (par may exclude "
            "capitalised PIK/OID accretion, or the principal field may equal "
            "cost), so a minMark / maxMark / parWeightedMark above 100 is a "
            "par-basis artifact until fair value is checked against cost on the "
            "holding rows (get_bdc_holdings), NOT a credit premium."
        ),
        (
            "Each quarter is {quarterKey, periodEnd, minMark, maxMark, "
            "parWeightedMark, rowCount, holderCount, bdcs}. `rowCount` is a "
            "HOLDING-ROW count (one row per BDC position, so a tranche co-held "
            "by N BDCs counts N times), not a tranche count; `holderCount` is "
            "distinct BDCs."
        ),
        (
            "Rows are priced, funded, non-equity debt positions only (unpriced, "
            "unfunded and equity rows are outside both counts)."
        ),
        (
            "An unknown key returns an empty series with a `note`, not an error "
            "(an unreachable store returns the same note today, so pair an "
            "empty series with a second read before concluding the key is "
            "unknown)."
        ),
    ),
    "get_bdc_holdings": (
        (
            "UNITS: parAmount / costAmount / fairValue and every total are "
            "whole USD; markedPrice and weightedAvgPrice are percent of par; "
            "portfolioStructure values are percentages (0-100). `topIndustries` "
            "is [industry, positionCount] pairs, top 10; structure metrics are "
            "floating-rate %, senior-secured %, equity % and PIK count."
        ),
        (
            "ABOVE-PAR TRAP: markedPrice is fair value over the FILED principal "
            "and filers differ on what principal tracks (par may exclude "
            "capitalised PIK/OID accretion, or the principal field may equal "
            "cost), so a row above 100 -- and a weightedAvgPrice above 100 "
            "(RAND's registry 111.49 is the measured case) -- is a par-basis "
            "artifact until fairValue is checked against costAmount, NOT a "
            "credit premium."
        ),
        (
            "`totalFairValue` is ARBITRATED: read `fairValueBasis` "
            "('parsed-rows' | 'filing-reported') and `fairValueRefused` first "
            "-- when the parse over-counts against the filing's own total, "
            "totalFairValue is the filing-reported figure, "
            "`reportedTotalFairValue` is that figure, `parsedRowSumFairValue` "
            "is the raw row sum, `fairValueRefusalReason` says why, and every "
            "row-derived aggregate (totalParAmount, weightedAvgPrice, "
            "topIndustries, portfolioStructure) is null with "
            "`holdingsReconciled: false`."
        ),
        (
            "`fairValueGap` / `fairValueGapNote` carry the gap label "
            "get_bdc_list serves (null | 'rows_under_reported': the parsed-row "
            "total UNDERSTATES the book, use reportedTotalFairValue for its "
            "size | 'rows_over_reported' | 'funded_basis_presentation', FSK's "
            "funded-amount schedule, not an over-count) with the measured ratio "
            "in one sentence."
        ),
        (
            "`reportedTotalFairValue` is null, never 0, when the filing tags no "
            "usable grand total OR when Oxford Ledge's stored reference "
            "describes a DIFFERENT filing than the book served (cannot "
            "reconcile: no swap, no gap label, no refusal)."
        ),
        (
            "`totalHoldings` is the REGISTRY count of parsed positions (the "
            "population the totals and percentages cover) -- except that when "
            "the stored registry row describes a different filing than the "
            "newest book whose rows are served, filingType, periodEnd and "
            "totalHoldings are RECOMPUTED from the served rows, so the header "
            "always describes the rows beneath it."
        ),
        (
            "The served `holdings` list may be SHORTER than totalHoldings "
            "because rows whose borrower cell carries no issuer identity are "
            "dropped at read -- `holdingsReturned`, `nonBorrowerRowsExcluded` "
            "and `excludedRowsFairValue` disclose the gap so you can reconcile "
            "served rows against the header."
        ),
        (
            "parseQuality 'ok' | 'suspect' (suspect when >= 50% of the filing's "
            "parsed rows carry no borrower identity -- a parse failure of that "
            "schedule, not a portfolio -- OR when fairValueRefused is true, "
            "with the parsed/reported ratio in the note; parseQualityNote says "
            "so and names what is unverified)."
        ),
        (
            "portfolioStructureBasis 'all_parsed_rows': portfolioStructure, "
            "byLienPosition and topIndustries are computed over EVERY parsed "
            "row including nonBorrowerRowsExcluded, not over holdings[]."
        ),
        "An unknown or retired ticker returns `error` beside an empty list.",
        (
            "PAGING (additive): `limit` / `offset` page the `holdings` rows "
            "only -- totalHoldings, holdingsReturned, nonBorrowerRowsExcluded, "
            "excludedRowsFairValue, totalFairValue and its arbitration, "
            "weightedAvgPrice, byLienPosition, topIndustries and "
            "portfolioStructure all stay computed over ALL rows; a call "
            "declaring either gets `page` {limit, offset, returned, total, "
            "hasMore} and a `completeness` block with total_available; an "
            "offset past the end is an empty page with total intact; "
            "out-of-range values are REFUSED, never clamped; a call declaring "
            "neither is unchanged (every row, up to the store's 5000-row "
            "backstop). `page.total` is the served row count (== "
            "holdingsReturned), so a page never restates the filing."
        ),
        (
            "A large book is the reason paging exists: a ~325-row portfolio "
            "serialises past 100,000 characters, over most clients' tool-result "
            "ceiling. Nothing is ever dropped to fit -- read "
            "`_meta.response_size` and re-request with a smaller `limit` if it "
            "crowds your context."
        ),
    ),
    "get_debt_maturities": (
        (
            "`maturities` is a LIST of year/amount pairs (not a year-keyed "
            "map), normally the next ~5 years, with everything beyond the table "
            "in `thereafter`."
        ),
        (
            "`confidence` is high|medium|low|none and `source` names the reader "
            "that produced the ladder: 'xbrl' (the filer's own XBRL facts, "
            "tried first), 'table' (the footnote's HTML table), 'regex' (the "
            "footnote text), or null when nothing parsed; a ladder the "
            "balance-sheet cross-check rejected is served as 'xbrl_rejected' / "
            "'table_rejected' / 'regex_rejected' beside maturities=[] and "
            "confidence 'none', and a filer whose XBRL debt is not in USD as "
            "'<source>_non_usd' -- all describe PARSER certainty, not filer "
            "accuracy."
        ),
        (
            "`validation` carries {valid, maturity_total, bs_total, diff_pct, "
            "warning} cross-checking the ladder against the balance sheet, so "
            "check it before quoting a total. `cross_validated` is present "
            "(true) ONLY when the ladder total matched the balance sheet and "
            "absent otherwise -- read validation.valid for the negative, not "
            "the key's absence."
        ),
        (
            "`filing_date` is the annual report's filing date and `report_date` "
            "its period end: THE LADDER IS AS OF filing_date, not today -- a "
            "bucket labelled with the current year has partly elapsed by the "
            "time you read it, and amounts in it may already have been repaid "
            "or refinanced; `summary` names the elapsed bucket(s) when there "
            "are any, and the reader that produced the ladder."
        ),
        "An unparseable filer returns maturities=[] with confidence 'none'.",
    ),
    "get_capital_allocation": (
        (
            "`years` is newest-first and the rest are PARALLEL ARRAYS aligned "
            "to it by index; `periods` is the ISO period-end list beside it and "
            "each label is the filer's FISCAL year (the same axis as "
            "get_fundamentals -- JNJ FY2022, ended 2023-01-01, is served as "
            "2022)."
        ),
        (
            "These are NET, DERIVED series, not raw cash-flow lines: "
            "netBuybacks = repurchases minus equity issuance minus IPO proceeds "
            "minus share-based comp (NEGATIVE when a company is a net issuer, "
            "which isDilutive[i] mirrors as a boolean), netDebtChange = "
            "repayments minus issuance (positive means net paydown)."
        ),
        (
            "netBuybacks is computed from issuance and SBC even when no "
            "repurchase fact exists, so an IPO year (RDDT) reads isDilutive "
            "true; a year with none of the four facts is null (isDilutive null, "
            "never false)."
        ),
        (
            "IPO proceeds count only as the filer's OWN IPO: the first non-zero "
            "ProceedsFromIssuanceInitialPublicOffering in the filer's series "
            "with no non-zero PaymentsForRepurchaseOfCommonStock in any earlier "
            "year (a subsidiary's IPO tagged by a repurchasing parent -- Kenvue "
            "in JNJ's FY2023 -- is excluded; summary.dilutionNote states the "
            "rule and names what it admitted or excluded)."
        ),
        (
            "`dividends` reads PaymentsOfDividendsCommonStock / "
            "PaymentsOfDividends / PaymentsOfOrdinaryDividends (earlier rung "
            "wins; a subsidiary's minority-interest payout is never read)."
        ),
        (
            "netBuybacks is a DILUTION PROXY, not a buyback figure: it "
            "subtracts non-cash SBC and can count dilution twice (issuance "
            "proceeds include option-exercise cash), so AAPL FY2012 reads "
            "negative with no repurchase at all."
        ),
        (
            "grossRepurchases is the filed PaymentsForRepurchaseOfCommonStock "
            "line per year (null when the year is untagged; a 0 is the filer's "
            "own tagged zero, as AAPL filed for FY2012). Gross issuance, gross "
            "repayment and SBC are NOT emitted separately."
        ),
        (
            "`sharesOut` reads CommonStockSharesOutstanding, then the diluted "
            "weighted average for a dual-class filer with no non-dimensional "
            "instant (RDDT)."
        ),
        (
            "`basis` is the same split-basis gate get_fundamentals serves: "
            "shareCountChange10yr is split-basis-gated (a reverse-split issuer "
            "such as DAC is served null or split-adjusted, never a phantom "
            "buyback) -- pre-split share-count cells are withheld into "
            "basis.withheldValues.sharesOut and summary.shareCountNote states "
            "the comparable-basis move."
        ),
        (
            "`summary` carries windowYears (the number of newest fiscal years "
            "EVERY summary figure is computed over, 10 or fewer), "
            "shareCountChange10yr (percent, newest vs oldest cell in that "
            "window), shareCountNote, dilutiveYears (fiscal years in the window "
            "judged dilutive; null when none could be judged), yearsJudged, "
            "dilutionNote, totalDividends (null, not 0, when no dividend rung "
            "is tagged in the window), dividendsNote, totalNetBuybacks, "
            "totalGrossRepurchases (null when no year in the window is tagged), "
            "totalNetDebt, totalAcquisitions."
        ),
        (
            "All money is whole USD; sharesOut is a share count. Untagged years "
            "are null."
        ),
        (
            "A filer with no annual us-gaap cash-flow fact (an IFRS reporter "
            "such as TSM) is REFUSED with {error, taxonomy, usGaapConceptCount, "
            "formsSeen, unitsSeen}, never served years=[] with zeros."
        ),
    ),
    "get_13f_holdings": (
        (
            "A ticker is letters with at most one class suffix (BLK; BRK-B or "
            "BRK.B for Berkshire, which SEC lists as BRK-A / BRK-B, never bare "
            "BRK)."
        ),
        (
            "A filer NAME ('Berkshire Hathaway', 'Baupost') is NOT resolved by "
            "this package: its handler proxies the CIK-keyed route and refuses "
            "any other shape as INVALID_PARAMS -- pass the CIK. The hosted "
            "server's own get_13f_holdings does resolve a name (since "
            "2026-09-13: 3-80 characters; ONE name-prefix match in the curated "
            "13F filer universe becomes its CIK and the payload carries "
            "`resolved_from` {query, cik, name}; zero or several matches is an "
            "INVALID_PARAMS error listing up to three candidates and pointing "
            "at its hosted-only filer-search tool -- the first of an ambiguous "
            "list is never picked), so `resolved_from` is a hosted-channel key "
            "that never appears on this package's wire."
        ),
        (
            "`value` is whole USD (13F values are dollars despite the form's "
            "'x$1000' wording); `position_type` is COM|PRN|PUT|CALL and "
            "options/notes are kept separate -- `shares` on a PUT/CALL row is "
            "the option's underlying and on a PRN row the note principal, so do "
            "NOT sum across types."
        ),
        (
            "`ticker` is an Oxford Ledge security-identifier-to-ticker "
            "crosswalk, ABSENT on unmapped rows (the licensed identifiers "
            "themselves are stripped): share classes of one issuer may map to "
            "distinct tickers (Alphabet A -> GOOGL, C -> GOOG; Lennar A/B) or, "
            "where the crosswalk is still class-blind, to one ticker -- "
            "`title_of_class` is the authoritative class discriminator, read it "
            "before adding rows of one issuer; `lots` is Oxford Ledge's count "
            "of infotable rows merged into the position."
        ),
        (
            "`totalValue` and `totalHoldings` cover the WHOLE filing while "
            "`holdings` is truncated to max_holdings (default 50, cap 500), "
            "value-ranked."
        ),
        (
            "When a prior filing exists the response also carries "
            "prevFilingDate and changes:{new_positions, increased, decreased, "
            "closed} (rows with prevShares / sharesChange / pctChange), plus "
            "`changesTotals` (the full per-bucket counts) and "
            "`changesTruncated` when a bucket was cut; the `changes` key is "
            "ABSENT when only one filing was found."
        ),
        (
            "An empty `holdings` list carries `error` saying either that no "
            "13F-HR is on file for the CIK or that the latest filing could not "
            "be parsed -- never a bare totalValue 0."
        ),
    ),
    "get_value_investing_fact": (
        (
            "Most entries paraphrase or summarise the named author's ideas, "
            "some may repeat the author's own words, and none is a verbatim "
            "quotation unless `verbatim` is true -- so never present the text "
            "as the author's exact words."
        ),
        (
            "The text is in the `quote` key (a field name, not a claim that the "
            "words are the author's), `author` is whose ideas it concerns, "
            "`source` is the book, letter or speech, `verbatim` is true only "
            "for an entry verified against its primary source (false for every "
            "entry today), and `attribution` is the credit line to use when you "
            "repeat the text (it names the author, the source and the year and "
            "says the text is not a verbatim quotation; a historical-record "
            "entry is credited as an Oxford Ledge summary of its source)."
        ),
        (
            "The corpus, its selection and its classification are Oxford "
            "Ledge's (basis ol-authored); the ideas, and any words that are the "
            "author's own, belong to the named author, credited through "
            "`attribution`."
        ),
    ),
    "ol_bdc_top_borrowers": (
        (
            "A wound-down filer and its successor holding one book no longer "
            "rank a borrower as two lenders (when the filer roster cannot be "
            "read, the ranking falls back to holder_count)."
        ),
        (
            "holder_count is distinct BDC lenders; a wound-down filer's frozen "
            "last filing still counts -- read holder_count_active / "
            "holder_count_ever, summed over holder_ticker_status, for the "
            "present-tense split. total_fair_value is null when unpriced."
        ),
        (
            "A row whose industry label was checked also carries "
            "`industry_basis` {stored_label_chosen_by ('row_count', or "
            "'rollup_differs_from_row_count' when the stored label no longer "
            "matches the fresh row-count vote -- it may be stale), "
            "by_fair_value, fair_value_agreement, distinct_industries, "
            "contested (true when the lenders' row-count and fair-value votes "
            "disagree, OR when the served `industry` disagrees with either -- a "
            "stale stored label is contested even when the lenders agree)}."
        ),
        (
            "Parser mis-ingests (subtotals, maturity-date and "
            "instrument-descriptor rows, bare industry-taxonomy labels) are "
            "filtered out when the filter is available; the `borrower_filters` "
            "block says whether each half ran (nonborrower / industry_label, "
            "with industry_vocab_size) and `rows_removed` how many rows it took "
            "out. Cell-bleed names ('Acme, LLC, Diversified Financial "
            "Services') are deliberately NOT filtered."
        ),
        (
            "TRUNCATION: the `completeness` block in the payload is the runtime "
            "truth -- complete=true means under-cap (this IS everything), "
            "complete=null means exactly-at-cap and genuinely undecidable (read "
            "`more_available_hint`). An out-of-range `limit` is REFUSED as "
            "INVALID_PARAMS naming the bound (nothing is clamped), so the "
            "schema maximum is the rule and `completeness` is the check."
        ),
    ),
    "ol_bdc_borrower_dispersion": (
        (
            "Envelope: {summary, borrower_norm, count, lender_count, "
            "tranche_count, lenders, include_stale, stale_lenders_excluded, "
            "spread_unit, base_rate, yield_disclosure, rows_above_par, "
            "rows_commitment_basis, as_of, completeness}."
        ),
        (
            "`lenders` is ONE row per BDC lender (count == lender_count), "
            "ranked by the lender's par-weighted spread_bps, widest first, with "
            "its funded debt tranches nested under `tranches` (tranche_count "
            "counts them all); a multi-tranche lender row sums fair_value and "
            "par_amount, par-weights spread_bps and marked_price, and nulls any "
            "per-tranche field that differs (lender_row_basis says so)."
        ),
        (
            "Each tranche, and a single-tranche lender row, is {bdc_ticker, "
            "bdc_name, filing_date, bdc_latest_filing, is_stale_vs_bdc_latest, "
            "filer_status, successor_ticker, security_type, lien_position, "
            "rate_type, maturity_date, spread, spread_bps, marked_price, "
            "mark_as_of, mark_above_par, mark_above_par_basis, fair_value, "
            "non_accrual, current_yield_pct, spread_to_maturity_bps, "
            "all_in_simple_yield_pct, yield_basis, yield_suppressed, "
            "pik_leg_excluded, par_amount, cost_amount, mark_basis, "
            "mark_basis_note}."
        ),
        (
            "UNITS TRAP: `spread` is the RAW AS-FILED number and is MIXED-UNIT "
            "across filers -- one BDC files 5.75 (percent) for what another "
            "files as 575 (bps) -- so never average or diff `spread` blind; "
            "compare lenders on `spread_bps` (normalised basis points, the "
            "ranking key; `spread_unit` says so). marked_price is out of 100; "
            "fair_value is whole USD."
        ),
        (
            "STALENESS: `filing_date` is the filing the row came from and "
            "`bdc_latest_filing` that BDC's newest filing; "
            "`is_stale_vs_bdc_latest` true means the BDC has filed since "
            "without this borrower (an exited position) -- such lenders are "
            "EXCLUDED by default, in the query before `limit` "
            "(stale_lenders_excluded counts them; include_stale=true shows "
            "them) -- and `filer_status` 'inactive' with `successor_ticker` "
            "marks a wound-down lender whose frozen final filing still appears."
        ),
        (
            "YIELDS: current_yield_pct / spread_to_maturity_bps / "
            "all_in_simple_yield_pct are serve-time Oxford Ledge computations "
            "(SOFR read at serve time from `base_rate`, never stored); "
            "`yield_suppressed` names why a yield is null (non-accrual, pure "
            "PIK, unpriced floor) and `yield_disclosure` states the method; "
            "rows with mark_above_par, or with mark_basis 'commitment_basis' "
            "(the mark per 100 of par sits more than 5 points below the mark "
            "per 100 of cost on a loan marked at 90 or more of its cost: a "
            "partly funded commitment), carry no serve-time yields at all."
        ),
        (
            "ABOVE-PAR TRAP: marked_price is fair value over FILED principal, "
            "and filers differ on what principal tracks -- a row above 100 "
            "carries mark_above_par=true plus a mark_above_par_basis sentence "
            "(par may exclude capitalised PIK/OID accretion, or the filer's "
            "principal field may equal cost; FV/par and FV/cost differ) and "
            "rows_above_par counts them, so do NOT read such a row as a credit "
            "premium without checking fair_value against cost."
        ),
        (
            "Debt tranches only (equity excluded). Rows are each BDC's most "
            "recent filing THAT HOLDS this borrower, so vintages can differ "
            "across lenders. A single lender comes back as ONE row (count=1); "
            "an empty result means the key is not in the corpus as a funded "
            "debt position (equity-only, unfunded-only, or an unknown key)."
        ),
        (
            "maturity_date_precision ('day' | 'month' | 'year' | null) is the "
            "precision the filer's SOI printed; a month-precision maturity "
            "cannot anchor the day-count, so spread_to_maturity_bps is null "
            "with margin_suppressed_reason 'no_maturity' and "
            "margin_suppressed_note saying the maturity is partial, not missing "
            "(likewise when the served date is already past)."
        ),
        (
            "TRUNCATION: the `completeness` block in the payload is the runtime "
            "truth -- complete=true means under-cap, complete=null means "
            "exactly-at-cap and undecidable (read `more_available_hint`); an "
            "out-of-range `limit` is REFUSED as INVALID_PARAMS, never clamped."
        ),
    ),
    "ol_bdc_common_borrowers": (
        (
            "Every other BDC tool runs borrower -> lenders; this one runs "
            "lenders -> shared borrowers."
        ),
        (
            "`holder_tickers` are the bare BDC symbols; in `holders` a name is "
            "null when the registry has no row, never a guessed name."
        ),
        (
            "Debt positions only (equity stakes are not lending relationships). "
            "Ordered most-widely-held first."
        ),
        (
            "More than 25 bdc_tickers is REFUSED as INVALID_PARAMS before any "
            "request (the schema's maxItems; nothing is truncated); a "
            "min_holders above the number of BDCs supplied is rejected rather "
            "than returning a misleading empty list."
        ),
        (
            "TRUNCATION: the `completeness` block in the payload is the runtime "
            "truth -- complete=true means under-cap, complete=null means "
            "exactly-at-cap and undecidable (read `more_available_hint`); an "
            "out-of-range `limit` is REFUSED as INVALID_PARAMS, never clamped."
        ),
        (
            "Oxford Ledge parse: normalised borrower keys, cross-BDC sums, "
            "artifact filters (ol-derived)."
        ),
    ),
    "ol_form_d_raises": (
        (
            "Each offering is {accession, submission_type, filing_date, "
            "issuer_cik, issuer_name, entity_type, state, industry_group, "
            "investment_fund_type, is_equity, is_debt, total_offering_amount, "
            "offering_indefinite, total_amount_sold, total_remaining, "
            "investors_count, date_of_first_sale, first_sale_yet_to_occur, "
            "federal_exemptions, quarter}, NEWEST FIRST."
        ),
        (
            "Amounts are whole USD AS DISCLOSED -- total_offering_amount is a "
            "ceiling, not money raised (use total_amount_sold), and "
            "offering_indefinite means no cap was stated."
        ),
        (
            "CADENCE: the source is the SEC quarterly Form D data set, posted "
            "about one quarter after quarter-end; `quarter` on each row is the "
            "DATA-SET VINTAGE it came from, not a filing quarter, and the "
            "envelope's `data_through` (newest filing_date loaded) and "
            "`newest_quarter_loaded` say how far the store reaches."
        ),
        (
            "A trailing `days` window shorter than that lag is EMPTY BY "
            "CONSTRUCTION -- it is not evidence that nothing was filed -- and "
            "the empty-window summary says so; there is no 'filed this week' "
            "read on this data set. WITHOUT `days` the read is a top-N over the "
            "whole table."
        ),
        "`industry` must match the stored industry_group label exactly.",
    ),
    "ol_insider_recent_buys": (
        (
            "Each buy is {ticker, filingDate, transactionDate, insiderName, "
            "position, title, transType, shares, pricePerShare, totalValue, "
            "sharesOwned, securityTitle, isDerivative, url (SEC filing)}, "
            "NEWEST FIRST."
        ),
        (
            "Open-market purchases only (SEC transaction_code 'P'); option "
            "exercises, grants and sales are excluded, as are issuers filing on "
            "themselves."
        ),
        (
            "`totalValue` is USD (dollars, with cents) = |shares| x price, "
            "computed by Oxford Ledge at ingest and null when the filed price "
            "failed the plausibility gate; `position` is the filer's reported "
            "title, or an Oxford Ledge fallback label (Officer / Director / 10% "
            "Owner / Insider) when the filing left it blank -- both are Oxford "
            "Ledge derivations (basis hybrid); every other field is the Form "
            "4's."
        ),
        "Multi-buyer cluster detection is hosted-only.",
        (
            "Each row also carries formType (the Form 4 type as filed, '4' or "
            "'4/A'), accessionNumber (the filing), isAmendment (true for a 4/A; "
            "null when the store holds no form type), and supersedesAccession: "
            "a Form 4 and its 4/A that report the SAME line (identical filer, "
            "date, code, shares, price, shares-owned-after, security title and "
            "derivative flag) are served ONCE, as the amendment, with "
            "supersedesAccession naming the folded original -- so summing "
            "shares or value over the list no longer double-counts an amended "
            "filing. A 4/A that CORRECTED a value is a different line and is "
            "served beside its original; isAmendment says which is which."
        ),
        (
            "Each row also carries issuerSelfFiled (Oxford Ledge's comparison "
            "of the filer's and the issuer's SEC IDs, not a Form 4 field); "
            "expect false here, because purchases filed under the issuer's own "
            "SEC ID are excluded from this screen -- a true row is one that "
            "exclusion missed, so leave it out of any total."
        ),
    ),
    "get_fails_to_deliver": (
        (
            "Each row is {date (the SETTLEMENT date, as ISO text -- the field "
            "is `date`, not settlement_date), fails (SHARES failed, not "
            "dollars), price (closing price that day, USD), description (issue "
            "name)}, OLDEST-FIRST so it charts left to right."
        ),
        (
            "`days` is a trailing window, default 180, hard cap 730, ANCHORED "
            "TO THE LATEST LOADED SETTLEMENT DATE (`as_of`), not to today: each "
            "SEC half-month file lands ~3 weeks after the period ends, so a "
            "window measured back from today was empty for every ticker on most "
            "days of the month; the served span ends at `as_of` and "
            "`coverage.window_start` / `coverage.window_end` say where it ran."
        ),
        (
            "Coverage is sparse by nature: SEC publishes a row only on days a "
            "ticker actually had fails, so gaps between rows are normal -- but "
            "the STORE holds only the SEC half-month files Oxford Ledge has "
            "loaded, so an empty or thin `history` is a statement about the "
            "loaded settlement-date range, not evidence of no fails: a `days` "
            "window that reaches before the earliest loaded file is empty by "
            "construction."
        ),
        (
            "THE COVERAGE FLOOR rides every payload: `coverage` = "
            "{earliest_settlement_date, latest_settlement_date, files_loaded, "
            "files_expected, files_missing (the SEC half-month file labels "
            "absent INSIDE the loaded range, e.g. 202608b -- a gap there is a "
            "missing file, not a fail-free stretch; null if the store could not "
            "list its periods), window_start, window_end, days_covered, "
            "days_before_earliest, days_after_latest, window_predates_coverage, "
            "window_postdates_coverage (true when the window starts after the "
            "newest loaded date OR at least one whole half-month after it lies "
            "inside the window)}, `as_of` (the latest settlement date loaded) "
            "and a `summary` that states how many of the requested days fall "
            "inside the loaded data and names the head, the tail and the "
            "missing files as NOT LOADED rather than fail-free -- when none of "
            "the window is loaded it says so instead of \"0 fails\" -- read them "
            "before quoting a window as fail-free."
        ),
        (
            "Figures are as SEC published for that settlement date: NOT "
            "split-adjusted, and a renamed ticker's earlier rows sit under the "
            "old symbol; one row per ticker and settlement date -- where SEC "
            "lists more than one CUSIP under a symbol on a date (a CUSIP change "
            "with both securities failing), `fails` is the SUM across those "
            "CUSIPs and `price` / `description` follow the CUSIP with the "
            "larger fails; class shares use SEC's concatenated symbol (BRKB), "
            "which BRK.B / BRK-B also match."
        ),
        "The short-interest half of that picture is hosted-only.",
    ),
    "get_activist_stakes": (
        (
            "Each filing: ticker, filer_name, filing_date, form_type, shares, "
            "percent_of_class (a percent number), accession_number (build the "
            "EDGAR document URL from it), updated_at, plus a derived "
            "is_activist that is true IFF form_type contains '13D' -- i.e. it "
            "is a FORM-TYPE label, not a judgement: 13D signals active intent "
            "(proxy fight, takeover), 13G a passive index/institutional holder."
        ),
        (
            "Each filing also carries `reports_zero` (the cover page states 0 "
            "shares / 0% -- the filer's own statement that it no longer "
            "beneficially owns more than 5% of the class; an exit OR a "
            "reporting realignment such as Vanguard's 2026-01-12 disaggregation "
            "under SEC Release 34-39538, so cross-check get_holders before "
            "reading it as a sale)."
        ),
        (
            "Each filing also carries `unparsed` (shares and percent are null "
            "because the cover page could not be read: unknown, not zero); "
            "`summary` spells out both `reports_zero` and `unparsed`."
        ),
        (
            "FRESHNESS: keyless (anonymous) callers are served STORED rows and "
            "never trigger the EDGAR refresh -- read `stale` (null = the store "
            "was touched within 24h by some caller but THIS call did not "
            "compare it against EDGAR's index -- keyless callers never refresh "
            "-- so freshness is not certified; `stale_basis` names the "
            "evidence: 'age', 'edgar_index' or 'no_refresh_evidence'; true = "
            "the stored rows are older than 24h, or nothing is on file, OR "
            "EDGAR's index lists a newer Schedule 13D/13G than the newest "
            "stored row -- `newest_filing_seen` > `newest_filing_stored` -- or "
            "a family label this writer does not ingest; `notice` says which, "
            "and `fetched_rows` is the last refresh's admitted row count, null "
            "when no refresh ran), `age_seconds` (null = no rows have ever been "
            "fetched for this ticker, and none will be without an API key) and "
            "`refreshed` (whether this call refreshed)."
        ),
        (
            "Keyed callers refresh from EDGAR when the store is older than 24h; "
            "that refresh is bounded to 20s and falls back to the stored rows "
            "on timeout, and it is SKIPPED for up to an hour after any caller's "
            "result for the same arguments was cached (the hosted tool-level "
            "cache; this package caches its own copy for an hour as well), so "
            "`refreshed` can be false on a keyed call."
        ),
        (
            "`updated_at` is OUR CACHE stamp for the row, not a filing date -- "
            "read `filing_date` for when the filer filed."
        ),
        "The 13D Item 4 purpose text is not served (nothing populates it).",
        "The institutional-consensus cross-check is hosted-only.",
    ),
    "ol_treasury_debt": (
        (
            "Omit BOTH args for the newest month's full class breakdown (one "
            "row per security class, in statement order); pass security_type "
            "AND security_class together for that one class's monthly history "
            "-- passing only one of them is IGNORED and you get the "
            "latest-month breakdown."
        ),
        (
            "Rows are {record_date, security_type_desc, security_class_desc, "
            "debt_held_public_mil_amt, intragov_hold_mil_amt, total_mil_amt} "
            "(the latest-month shape also carries src_line_nbr)."
        ),
        (
            "Because the breakdown contains both component and Total rows, "
            "summing a column double-counts; filter by security_class_desc "
            "first."
        ),
        "Monthly, published a few business days after month-end.",
    ),
    "ol_cftc_cot": (
        (
            "Pass a `market` for that market's weekly history (NEWEST FIRST), "
            "or omit it for the latest report across the three markets (one row "
            "per market)."
        ),
        (
            "MARKET NAMES ARE NORMALISED, not matched by exact key: the value "
            "is case-folded and stripped of punctuation, then matched through a "
            "desk-alias table (CL / WTI / crude / 'Crude Oil, Light Sweet' -> "
            "crude_oil; ES / SPX / S&P / 'E-mini S&P 500' -> sp500; GC / XAU / "
            "gold -> gold) and as a substring of the stored keys and labels, so "
            "'GOLD', 'wti' and 'e-mini s&p' all resolve; `matched_market` names "
            "the key that answered (null on the all-market snapshot)."
        ),
        (
            "A name that resolves to NOTHING stored returns {error, "
            "matched_market: null, candidates (up to five nearest stored "
            "names), rows: []} -- and a name matching SEVERAL stored markets is "
            "that same miss, never the first of an ambiguous list. Every "
            "payload carries `markets_available` naming the three keys."
        ),
        (
            "A series row is {report_date, market_key, market_label, "
            "report_type, contract_code, mm_long, mm_short, mm_net, "
            "open_interest, source_dataset} (the all-market snapshot omits "
            "contract_code and source_dataset)."
        ),
        (
            "mm_* and open_interest are CONTRACT counts, not dollars, and mm_* "
            "cover ONE speculative category per report family -- commercials, "
            "swap dealers and other reportables are not returned: report_type "
            "`disaggregated` rows (gold, crude_oil) are the CFTC Managed Money "
            "category; report_type `tff` rows (sp500) are the CFTC Leveraged "
            "Funds category -- the closest speculative analogue, since the "
            "Traders-in-Financial-Futures report has no Managed Money column."
        ),
        (
            "An unresolvable name returns rows=[] with `candidates` (the store "
            "answered); an unreachable store is REFUSED (DATA_UNAVAILABLE), "
            "never served as rows=[]."
        ),
        "Weekly, published Friday for Tuesday positions.",
    ),
    "ol_fdic_bank": (
        (
            "Pass `query` for a name PREFIX search against ACTIVE institutions "
            "(largest-asset first; a leading 'The ' on the legal name is "
            "ignored, so 'Huntington' finds 'The Huntington National Bank'), or "
            "omit it for the largest active institutions."
        ),
        (
            "Every payload carries `coverage` {institutions_loaded, "
            "active_loaded, inactive_loaded, newest_repdte, last_loaded_at, "
            "ingest_scope} and `as_of` (= newest_repdte): the store is loaded "
            "ACTIVE-ONLY from the live FDIC API, so a bank that merged away or "
            "failed before a load (e.g. Comerica Bank, cert 983, acquired Feb "
            "2026) is absent by construction -- an empty search is a fact about "
            "the loaded store, never about the world."
        ),
        (
            "Each institution is {cert (FDIC certificate number, the "
            "identifier), name, stname, city, bkclass, active, asset, dep, "
            "estymd, webaddr, ticker (non-null only for the ~34 CERTs on Oxford "
            "Ledge's verified CERT-to-ticker map -- blank does NOT mean the "
            "bank is unlisted), repdte (the report date the figures are as "
            "of)}."
        ),
        (
            "UNITS: `asset` and `dep` are raw FDIC units, i.e. THOUSANDS of "
            "dollars -- 3,200,000 means $3.2 billion, not $3.2 million."
        ),
        (
            "`limit` default 25, hard cap 100, so the prefix search returns at "
            "most 25 matches unless you raise it."
        ),
        "Call reports only: no branch, CRA or enforcement data.",
    ),
    "ol_federal_contracts": (
        (
            "TWO SHAPES, and one of `ticker` or `fiscal_year` is REQUIRED "
            "(neither raises INVALID_PARAMS; if both are given, `ticker` wins "
            "and `fiscal_year` is ignored)."
        ),
        (
            "With `ticker`: {summary, ticker, as_of, obligations} where each "
            "row is {ticker, fiscal_year, total_obligations_usd (USD with cents "
            "-- units of dollars, not thousands), entity_count, recipients "
            "(each {name, uei, recipient_id, amount}; the TEN largest by amount "
            "-- when the year had more, `recipients_truncated: true` and "
            "`recipients_total` say so, and `entity_count` is always the full "
            "count), dropped_unresolved (how many awardee search hits the "
            "crosswalk did NOT attribute to this ticker -- read it before "
            "treating the total as complete), start_date, end_date, fetched_at, "
            "period_complete, days_elapsed, days_in_period}, NEWEST FY FIRST; "
            "`as_of` is the date USAspending was last read."
        ),
        (
            "A fiscal year whose end_date lies after `as_of` is PARTIAL "
            "(period_complete false, days_elapsed < days_in_period) and its "
            "total is year-to-date -- never compare it to a full year. `ueis` "
            "is no longer emitted (it duplicated recipients[].uei)."
        ),
        (
            "With `fiscal_year` only: {summary, fiscal_year, leaderboard} of "
            "{ticker, fiscal_year, total_obligations_usd, entity_count, "
            "fetched_at}, largest first (the envelope carries period_complete / "
            "days_elapsed / days_in_period for the requested year)."
        ),
        (
            "Obligations are federal awards, not company-reported revenue. "
            "Obligations are the ISSUER's while the crosswalk keys one share "
            "class: a ticker with no rows whose share-class sibling has them is "
            "served the sibling's rows under the sibling's `ticker`, with "
            "`requested_ticker` carrying the symbol you asked for and the "
            "summary saying so."
        ),
        (
            "ATTRIBUTION: the per-recipient amounts and UEIs are USAspending "
            "verbatim; attributing them to a TICKER is an Oxford Ledge curated "
            "crosswalk, the per-ticker total and entity_count are Oxford Ledge "
            "sums over the rows the crosswalk kept, and `dropped_unresolved` is "
            "an UPPER BOUND on that crosswalk's coverage gap -- it also counts "
            "unrelated name matches (a 'Lockheed ...' credit union), so it "
            "never says how many related entities were missed."
        ),
        "A ticker off the crosswalk honestly returns [].",
    ),
    "ol_patents": (
        (
            "Each filing is {applicant_name, application_number, "
            "publication_number, patent_number, title, filing_date, status, "
            "application_type}, NEWEST FIRST."
        ),
        (
            "`limit` default 50, hard cap 200 -- so this is a recent slice, "
            "never a full portfolio, and `count` is the number RETURNED, not "
            "the company's total patent estate."
        ),
        (
            "Filings reflect Oxford Ledge's last on-demand USPTO ingest for "
            "this ticker, not a schedule: the newest `filing_date` is the "
            "recency bound, and a stale ingest, a company that stopped filing, "
            "and an alias this ingest never keyed all look the same here."
        ),
        (
            "OL alias-resolves the applicant (GOOGL spans Alphabet + Google LLC "
            "+ DeepMind + Waymo)."
        ),
        (
            "Patents are the ISSUER's while the store is keyed by one share "
            "class: a ticker with no rows whose share-class sibling has them "
            "(GOOG -> GOOGL) is served the sibling's rows under the sibling's "
            "`ticker`, with `requested_ticker` carrying the symbol you asked "
            "for and the summary saying so."
        ),
        (
            "TRAP: a non-empty patent_number means this application is a "
            "continuation of an already-granted PARENT, NOT that this "
            "application itself was granted -- read `status` for that; each row "
            "repeats it as `parent_patent_number`."
        ),
        (
            "`last_ingested_at` is when the newest served row was ingested "
            "(null when none)."
        ),
    ),
    "ol_bdc_mark_changes": (
        (
            "Built because the alternative is stitching it by hand: a model "
            "asked this question fanned out per-BDC calls, worked from "
            "portfolio AVERAGES (the wrong grain), hit a rate limit, and "
            "fabricated a row by copying another BDC's numbers."
        ),
        (
            "`portfolio` is the BDC ticker holding the borrower. Marks are "
            "PERCENT OF PAR, fair-value-weighted across all tranches the BDC "
            "holds of that borrower; mark_delta is in percentage points."
        ),
        (
            "INCLUSION THRESHOLDS: a borrower enters a ranking only when "
            "|mark_delta| >= 1.0 point and its fair value is >= $500k, so 'no "
            "moves' can hide sub-point drifts and tiny positions."
        ),
        (
            "Grain is BORROWER, not position: security_type is deliberately NOT "
            "returned, because rolling up across tranches is what stops a "
            "continuously-held borrower reading as both entered and exited when "
            "its tranche mix is re-parsed."
        ),
        (
            "Each BDC is read at ITS two most recent filings and BDCs file on "
            "different calendars, so rows MIX vintages -- read `as_of` before "
            "treating the moves as contemporaneous."
        ),
        (
            "`coverage` names every BDC that was and was NOT read, with a "
            "reason per exclusion (no_prior_quarter / no_parsed_holdings / "
            "query_failed / over_ticker_cap / fair_value_refused -- the last "
            "when that BDC's latest book is refused against a reference "
            "coherent with it, the same fairValueRefused get_bdc_list carries, "
            "so its marks are not ranked), so a partial sweep can never read as "
            "a complete one."
        ),
        (
            "Caps: bdc_tickers truncated at 25 (the excess is listed in "
            "coverage, not dropped silently), limit default 10 / hard 50 per "
            "direction."
        ),
    ),
    "ol_bdc_credit_quality": (
        (
            "`latest` = {filing_date, flagged_fv, determinate_fv, "
            "total_debt_fv, flagged_pct, flagged_pct_basis (the denominator "
            "sentence), determinate_coverage}; the envelope also carries "
            "`filer_status` ('active'|'inactive') and `successor_ticker` -- an "
            "INACTIVE filer's frozen final filing is labelled in `summary` "
            "(BKCC -> TCPC); `trend` is per-quarter OLDEST-FIRST with the same "
            "fields plus quarter_key."
        ),
        (
            "UNITS: the *_fv figures are whole USD of fair value, flagged_pct "
            "is a percentage number, determinate_coverage is a 0-1 fraction."
        ),
        (
            "DENOMINATOR: flagged_pct = flagged_fv / determinate_fv x 100 -- "
            "the DETERMINATE-flag denominator (the rows whose non-accrual "
            "status the parse could read), never total_debt_fv; multiply it by "
            "determinate_coverage for the share of the whole debt book, which "
            "is up to 10% lower relative at the 90% gate."
        ),
        (
            "`flagged_pct` is deliberately NULL whenever determinate coverage "
            "is under 90% of debt fair value -- a partially-determinate quarter "
            "never reports a rate computed over a fraction of the book, so "
            "treat null as 'withheld', never as zero."
        ),
        "Unparsed or non-BDC tickers return latest=null, trend=[].",
        (
            "`latest.coverage_state` and every trend row's `coverage_state` is "
            "one of `none_parsed` (0% determinate: no non-accrual flag was "
            "parsed from the filing -- a parser gap, not a withholding and not "
            "a 0% rate), `partial` (0-90% determinate: the rate is withheld and "
            "the sentence carries the coverage number), `covered` (>= 90%: the "
            "rate is stated), `unusually_high` (coverage passed and the rate IS "
            "stated, but more than 25% of determinate debt fair value carries a "
            "non-accrual flag WITHOUT the misread signature below -- the "
            "flagged loans marked under 85 per 100 of par, or no mark on file "
            "to test -- unusually high, check the filing before relying on it) "
            "or `implausible` (coverage passed, more than 25% is flagged AND "
            "the flagged loans are marked near par -- their aggregate mark is "
            "at or above 85 per 100 of par, while a loan a lender has stopped "
            "accruing on is marked down -- a sign our parse misread the "
            "schedule, so the rate is withheld and the raw flagged_fv / "
            "determinate_fv sums stay on the row for inspection; `summary` "
            "states the mark). Read the state before reading flagged_pct."
        ),
        (
            "`latest` and every trend row also carry `withheld` "
            "('implausible_flag_rate' when that misread test is what nulled the "
            "rate, else null -- the coverage gate keeps its own expression, "
            "determinate_coverage below 0.9) and `parser_dialect_version` (the "
            "OLDEST parser-generation stamp among the filing's rows, null for "
            "unstamped history: a quarter stamped below the trend's newest "
            "version has not been re-read by the newer parser, and `summary` "
            "names the span when the trend mixes versions)."
        ),
    ),
}
