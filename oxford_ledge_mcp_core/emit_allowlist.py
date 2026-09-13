"""Per-tool emit ALLOWLISTS for the redistributed pip surface -- the
fail-closed inversion of server.py's carve-out denylist (OWNER MCP
program item 4, 2026-08-10 expansion review).

WHY INVERT. The denylist (_CARVEOUT_ID_KEYS) drops nine KNOWN key names
and fails OPEN: a server-side route that later adds a new
vendor-licensed field under an unlisted name ships through the
passthrough silently -- the 2026-08-10 publish vet's COUNSEL
self-critique named exactly this fragility. The whole point of the pip
package is "everything here is redistributable", so the emit boundary
must fail CLOSED: an unrecognized field is DROPPED, and a tool with no
allowlist at all is REFUSED, never served bare. (That guarantee binds
the tools ROUTED THROUGH this filter -- see Coverage below -- not every
tool on the server; the other passthroughs ship unfiltered as before.)

DESIGN.
* Allowlists are seeded from the PRODUCING helpers' own column lists
  (the canonical source of truth per CLAUDE.md section "Database
  queries"), not from observed payloads: get_corporate_events from
  the producing corporate-events helper's SELECT aliases;
  get_13f_holdings from the producing 13F parser's full response
  (row dict + envelope) plus the serving enrichment's `ticker` --
  and MINUS `cusip`, which is the carve-out the denylist existed for.
* Key comparison is case-insensitive (helpers emit camelCase aliases).
* _ENVELOPE_KEYS carries the shared response-envelope vocabulary so
  every tool's payload frame survives without repeating it per tool.
* The old denylist is retained HERE as a validator, not a runtime
  filter: an import-time check refuses any allowlist that contains a
  carve-out key, so the two mechanisms can never drift apart -- the
  denylist's knowledge is enforced at import, the allowlist enforces at
  emit.

Lives in oxford_ledge_mcp_core so both the pip server and the future
/api/mcp/tool passthrough BRIDGE consume ONE table -- the review's
warning stands: the bridge must ride this filter, or bridging widens
leakage. Coverage today: every one of the 29 wheel tools has an entry
(tests/test_mcp_wheel_tool_family_cut_contract.py pins it), and the hosted
/mcp bridge applies the same table to anonymous callers for every tool that
has one.
"""
from __future__ import annotations

import re
from typing import Any

# Third-party-licensed identifier/rating keys (2026-07-21 compliance
# review): CUSIP is FactSet / CUSIP Global Services IP; agency ratings
# are the agencies' IP. Used at import time to VALIDATE the allowlists
# below; the pip server also keeps its runtime strip as defense-in-depth.
CARVEOUT_ID_KEYS = frozenset({
    "cusip", "moodysrating", "moodys_rating", "sprating", "sp_rating",
    "fitchrating", "fitch_rating", "creditrating", "credit_rating",
})

# The sub-keys of a STRUCTURED error object (CISO re-review, 2026-09-09).
# `error` is an envelope key, so a string error survives the filter -- but a
# DICT error was walked like any other payload node, and `code` / `message` /
# `retry_after` are not field names any tool's allowlist carries, so
# `{"error": {"code": "RATE_LIMITED", "message": "slow down"}}` came out as
# `{"error": {}}`: an error with no code and no message. Latent rather than live
# when found (mcp_server raises ToolError, and the hosted route renders it
# outside this seam) -- but `ToolError.to_dict()` emits exactly that shape, so
# the day any handler RETURNS one instead of raising it, the anonymous channel
# gets an unactionable empty error. An agent can recover from an error; it
# cannot recover from an error that will not say what it is.
_ERROR_DETAIL_KEYS = frozenset({"code", "message", "retry_after"})

# Response-envelope vocabulary shared across tools (lowercase).
_ENVELOPE_KEYS = frozenset({
    "summary", "count", "error", "as_of", "ticker", "cik",
    # Compliance vocabulary (2026-08-24 3.2.0 vet L-2): the fail-closed
    # filter must never silently strip a disclaimer/attribution line a
    # route adds later -- that is the inversion's own failure mode.
    "disclaimer", "attribution", "notice", "license", "period", "quarter",
    # THE RESPONSE FRAME (2026-09-09). Measured by executing the filter over
    # every entry: 6 of 9 filtered tools lost their ENTIRE `completeness`
    # block, and all 9 lost `params_accepted` and `response_size`. Three
    # hand-repeated six of these keys into their own allowlists and got 5 of 6
    # -- nobody listed `rows_key`.
    #
    # `ol_bdc_top_borrowers`'s description tells the agent to read exactly this
    # block ("the `completeness` block in the payload is the runtime truth ...
    # complete=null means exactly-at-cap and genuinely undecidable"), so a
    # consumer of the six stripped tools receives a possibly-truncated list
    # with nothing to say it was truncated -- feedback_count_masks_degenerate_data
    # on the machine channel, which is the hazard COUNSEL made BLOCKING for
    # `coverage`/`determinate_coverage`. Same shape as the C1 `_meta` finding.
    #
    # Global, not per-tool, because that is what this set is FOR ("so every
    # tool's payload frame survives without repeating it per tool") and because
    # repeating it is what produced the 5-of-6. All of it is Oxford Ledge's own
    # response accounting -- our truncation bookkeeping, the caller's arguments
    # echoed back, byte counts. No vendor lineage, no identifier; the carve-out
    # validator still refuses cusip/ratings at import.
    "completeness", "complete", "returned", "limit", "rows_key",
    "completeness_basis", "more_available_hint",
    "params_accepted", "response_size", "chars", "approx_tokens",
    "budget_chars", "over_budget",
    # `hint` (CHAOS P2-1, 2026-09-09): the FOURTEENTH frame key, and the
    # one the first promotion missed. `mcp_response_size.py` writes the
    # other thirteen as dict literals and this one as `block["hint"] = ...`,
    # so a promotion derived by reading dict literals -- or by unioning a
    # captured payload, as mine was -- cannot see it. Measured live:
    # `ol_form_d_raises` with NO arguments returns 31,543 chars against a
    # 32,000 budget, so an agent is 457 characters from keeping
    # `over_budget: true` while losing the only sentence telling it what to
    # do about it.
    "hint",
    # PROVENANCE ENVELOPE (COUNSEL C1, 2026-09-09 — BLOCKING).
    # `attach_provenance` builds a `_meta` block carrying the source, the
    # basis and the terms URL. `_meta` was in no tool allowlist and none of
    # its keys were envelope keys, so the fail-closed filter dropped ALL of
    # it for EVERY filtered tool — verified by execution:
    #   filter_to_allowlist("ol_bdc_top_borrowers", {..., "_meta": {...}})
    #   -> {"summary": "x", "borrowers": [...]}     # _meta gone
    #
    # That defeated the COUNSEL-C2 control on the one surface where it is
    # the ONLY channel: a programmatic MCP caller never sees the terms
    # page, so `_meta` is how an agent learns the source, the basis, and
    # that a redistribution restriction exists at all. The control was
    # written, shipped, and silently stripped —
    # feedback_advertised_but_unwired_substrate, in the file that governs
    # redistribution.
    #
    # `source` / `source_url` become globally admitted key NAMES. They are
    # NOT carve-out keys (that set is cusip + the credit ratings), and
    # mcp_provenance._source() is their only producer with a terminal
    # default of deny — so a tool cannot invent a source string through
    # this door.
    "_meta", "terms_url", "page_url", "source", "source_url",
    "source_key", "basis", "delisted_notice",
    # COUNSEL F-4 ruling (2026-09-12, docs/board/audit/2026-09-12_COUNSEL_f4_
    # basis_and_c4_uspto_odp.md sect-2.2 + sect-3.2 P1): the `hybrid` basis
    # companions and the AI-generated label. COUNSEL PROVED the trap before
    # ruling -- a `_meta` carrying `derived_fields` run through this filter
    # came back with `['basis', 'source_key']`, both new keys silently
    # dropped -- so the keys are admitted in the SAME change that emits them.
    # Key NAMES only, no carve-out; mcp_provenance.attach_provenance is their
    # only producer (from tool identity, never from a payload).
    "derived_fields", "derived_basis", "ai_generated", "ai_generated_note",
})

# Per-tool emitted-field allowlists (lowercase). A key absent here and
# absent from _ENVELOPE_KEYS does NOT ship. Seed source is named per
# entry; changing a set is a COUNSEL-reviewable act, not a refactor.
TOOL_EMIT_ALLOWLIST: dict[str, frozenset[str]] = {
    # The corporate-events helper's SELECT aliases. No
    # vendor fields exist in this set; 8-K content is public domain.
    # `id` DROPPED 2026-09-12 (3.4.0 vet b04-events-capital-12, CISO
    # concurred): it is the corporate_events SERIAL row id (v19), the same
    # row-id class CISO F1 stripped from get_insider_trades and
    # /api/insider-activity -- measured shipping at row AND top level
    # because this entry admitted it explicitly. No consumer reads it.
    "get_corporate_events": frozenset({
        "events", "eventdate", "eventtype", "headline",
        "description", "amount", "counterparty", "counterpartyticker",
        "status", "sourceurl", "source",
    }),
    # The 13F parser's row keys + the serving
    # ticker enrichment; `cusip` deliberately ABSENT (the carve-out).
    # 2026-08-24 3.2.0 vet L-1: the first seeding took the ROW dict only
    # and silently stripped the response ENVELOPE -- fundName/filingDate/
    # periodOfReport gone means an agent receives a 45-day-lagged 13F with
    # no as-of anchor while the description promises the date. All keys
    # below are SEC 13F-HR-derived (the parser is EDGAR-native end-to-end), no
    # vendor lineage; `cusip` stays deliberately ABSENT everywhere, so the
    # recursive filter drops it from change entries too (the carve-out).
    "get_13f_holdings": frozenset({
        "holdings", "name", "value", "shares", "type", "position_type",
        "ticker", "lots",
        # 2026-09-12 (T8; external field test 2026-09-08 P1): SEC's own
        # <titleOfClass> ('CAP STK CL A' / 'CAP STK CL C'), on holdings rows
        # AND change entries. With `cusip` carved out and the ticker
        # collapsing, it is the ONE surviving key that tells Berkshire's two
        # ALPHABET INC rows apart. 13F-HR-native, no vendor lineage.
        "title_of_class",
        # response envelope (the 13F parser's result dict)
        "fundname", "filingdate", "periodofreport", "totalholdings",
        "totalvalue", "prevfilingdate",
        # quarter-over-quarter changes sub-tree: container, its four
        # buckets, and the entry-only keys (name/shares/value already admitted)
        "changes", "new_positions", "increased", "decreased", "closed",
        "prevshares", "shareschange", "pctchange",
        # 2026-09-12 (3.4.0 vet b03-ownership-14): the route's TRUNCATION
        # DISCLOSURE for the change lists -- data/edgar_13f.py writes
        # `changesTotals` {new_positions, increased, decreased, closed} (the
        # pre-cut counts; the four bucket names are admitted just above) and
        # `changesTruncated` (the boolean a consumer can branch on), "capped
        # WITH DISCLOSURE rather than silently". This fail-closed filter
        # stripped both, so a trimmed `changes` block shipped with nothing
        # saying it was trimmed -- the exact complete-looking incomplete
        # answer the route comment says it exists to prevent. OL response
        # accounting, no vendor lineage.
        "changestotals", "changestruncated",
    }),
    # 2026-09-05 (external field-test F4 remainder): seeded from the
    # producing route's emitted keys (/api/bdc/borrower-mark-history --
    # itself a projection of pg_get_borrower_mark_history's SELECT
    # aliases). SEC-EDGAR-derived Schedule-of-Investments data, public
    # domain; no vendor fields exist in this set.
    "get_bdc_borrower_mark_history": frozenset({
        "borrowernorm", "quarters", "units", "note",
        # per-quarter series entry (the units sub-dict labels these same
        # three mark fields, so its keys are already admitted)
        "quarterkey", "minmark", "maxmark", "parweightedmark",
        "rowcount", "holdercount", "bdcs", "periodend",
        # 2026-09-13 (deep audit f3-bdc-core-7, wave D / D4): per-quarter
        # `aboveParRowCount` and the envelope `markBasis` the route now emits.
        "aboveparrowcount", "markbasis",
    }),
    # 2026-09-05 (same field test): seeded from data/bdc_query.query_by_bdc's
    # response dict + the route's F9 freshness additions. All SEC-EDGAR
    # 10-Q/10-K SOI-derived. DELIBERATELY ABSENT: `byLienPosition` -- its
    # keys are DATA VALUES (lien-name buckets), which the fail-closed
    # key filter would reduce to an empty husk; per-row lienPosition
    # ships instead, so the breakdown is recomputable client-side.
    # 2026-09-08 (COUNSEL F-2). get_bdc_list rode NO filter while emitting
    # the same reconciliation keys as get_bdc_holdings -- so this set was
    # not the redistribution boundary its header claimed, and a refusal
    # here would have suppressed a disclosure on the filtered surface only.
    # Routed through so the claim is true rather than weakened.
    #
    # `bdcs` is the ENVELOPE of this payload and is admitted deliberately:
    # /api/bdc/list returns {"bdcs": [...]}, not a bare list, and `bdcs` is
    # not in _ENVELOPE_KEYS -- so omitting it would fail closed on the WHOLE
    # payload and serve {}. Same SEC-EDGAR lineage throughout; no vendor
    # field (COUNSEL COMPLIANCE_REVIEW_v1 Q1, ~93% confidence, traced to
    # efts./data./www.sec.gov and nothing else).
    # 2026-09-09 (OWNER 2a, after COUNSEL F-2). search_bdc_borrower rode NO
    # filter while emitting our SoI parse plus borrower identity -- the same
    # asymmetry F-2 found on get_bdc_list, on a second tool.
    #
    # Key set DERIVED FROM LIVE PAYLOADS, not from the producer source: the
    # producer mentions 57 quoted names, many of them internal snake_case row
    # keys consumed before emit, so a source-derived list would admit names
    # that never ship and could MISS ones that do. Two reads -- a rich hit
    # (Medline, 27 envelope keys) and a miss (Mozart, 11) -- give the union
    # actually served, including the holder-row and priceHistory keys.
    #
    # BOTH BRANCHES are admitted deliberately: the hit and miss shapes differ,
    # and a filter built from only one would silently amputate the other.
    "search_bdc_borrower": frozenset({
        "age_days", "aggregatesbasis", "ambiguous", "asof",
        "avgmarkedprice", "avgmarkedpricebasis", "avgmarkedpriceunweighted", "bdclatestfiling",
        "bdcname", "bdcticker", "borrowername", "borrowernorm",
        # 3.4.0 vet b05-bdc-core-6 / CV-13 (2026-09-12, B5b): the borrower_
        # descriptions.source column (csv | wellknown | template | research)
        # so a model-written profile is labelled on the wire.
        "description", "descriptionsource", "error", "fairvalue", "filingdate",
        "filingtype", "found", "holdercount", "holdercountbasis",
        "holders", "holderstatus", "holdingrowcount", "industry",
        "industrybasis", "industrytagcount", "interestrate", "lienposition",
        "markedprice", "markedpricerowcount", "match_type", "matches",
        "maturitydate", "maxmarkedprice", "message", "minmarkedprice",
        "nonborrowerrowsexcluded", "paramount", "pricehistory", "query",
        "securitytype", "stale", "stalebasis", "staleholdercount",
        "stalerowcount", "successorticker", "totalfairvalue", "totalfv",
        "totalholders", "totalparamount", "unfundedcommitments", "unfundedfairvaluesum",
        "unfundedrowcount", "units", "zeromarkedpricerowcount",
        # 2026-09-09: `priceHistory` was admitted but its per-quarter row keys
        # were not, so every series arrived as a list of EMPTY dicts once the
        # data-keyed declaration let the tickers through.
        "quarterkey", "periodend",
        # 2026-09-12 T4/T5: sibling-key disclosure on a resolved hit
        # (relatedNorms rows reuse borrowernorm/borrowername/holdercount/
        # holdingrowcount/totalfv, already admitted above) and the
        # all-stale totals refusal sentence. Admitted in the SAME change as
        # the producer -- this filter is fail-closed and drops silently.
        "relatednorms", "relatednormsbasis", "relatednormsnote",
        "aggregatesrefusalreason",
        # 2026-09-13 (deep audit f3-bdc-core-7, wave D / D4): the same above-par
        # triple on the borrower read (Caitec at 145.74 is the measured case).
        "markabovepar", "aboveparrowcount", "markbasis",
    }),
    "get_bdc_list": frozenset({
        "bdcs",
        "ticker", "name", "listed", "filingdate", "lastparsed",
        "holdingcount", "totalfairvalue",
        # the reconciliation triple + the refusal pair, identical in name
        # and meaning to the get_bdc_holdings entry below
        "reportedtotalfairvalue", "fairvaluebasis", "parsedrowsumfairvalue",
        "fairvaluerefused", "fairvaluerefusalreason",
    }),
    "get_bdc_holdings": frozenset({
        # envelope
        "bdcticker", "bdcname", "filingdate", "filingtype", "periodend",
        "totalholdings", "totalparamount", "totalfairvalue",
        "weightedavgprice", "topindustries", "portfoliostructure",
        "holdings", "datasource", "fetchedat", "retired", "successorticker",
        # 2026-09-08 cross-surface FV arbiter. Same SEC-EDGAR lineage as
        # `totalfairvalue` itself (the filing's own XBRL grand total plus our
        # own row sum) — no vendor field, no carve-out key. They are admitted
        # here because the fail-closed filter would otherwise strip exactly
        # the disclosure that lets an agent NOTICE a 46x divergence, which
        # is the defect this batch exists to close: /api/bdc/list has carried
        # this triple since #21 and rides no filter, while get_bdc_holdings
        # rides this one — so an unlisted key here re-creates the asymmetry
        # in the transport rather than in the producer.
        "reportedtotalfairvalue", "fairvaluebasis", "parsedrowsumfairvalue",
        "fairvaluerefused", "fairvaluerefusalreason",
        # holdings rows (query_by_bdc's clean_holdings projection)
        "borrowername", "industry", "securitytype", "lienposition",
        "interestrate", "maturitydate", "paramount", "costamount",
        "fairvalue", "markedprice",
        # portfolioStructure metrics (S21-F risk framing)
        "floatingratepct", "floatingrateofdebtpct", "legacyliborpct",
        "legacyliborofdebtpct", "seniorsecuredpct",
        "seniorsecuredofdebtpct", "equitypct", "pikcount",
        "pikpctofholdings",
        # 2026-09-09 (external re-review #2): the refusal now reaches the
        # row-derived aggregates, and this flag marks the BREAKDOWN itself.
        # A consumer reading only `fairValueRefused` gets the scalar story;
        # one iterating rows needs the flag on the block it is iterating.
        "holdingsreconciled",
        # 2026-09-12 (T6, MCP field-test re-review): the row list's
        # COMPLETENESS disclosure. query_by_bdc drops non-identity borrower
        # cells at the read path while `totalholdings` stays the registry
        # count and every aggregate is computed over the unfiltered rows --
        # PHEN served 1 row under a 12-count header with nothing a consumer
        # could reconcile against. Three scalars, same SEC-EDGAR lineage as
        # the rows they count; no vendor field, no carve-out. Admitted here
        # for the same reason as the arbiter triple above: an unlisted key
        # re-creates the silence in the transport. `bylienposition` stays
        # DELIBERATELY ABSENT (see the entry header): admitting it bare ships
        # `{}` under the key filter, and declaring it data-keyed would take
        # TOOL_DATA_KEYED_CONTAINERS past the cap `test_the_hatch_stays_small`
        # holds at 4 -- the 1-row-vs-12 mismatch is now detectable from these
        # scalars without it.
        "holdingsreturned", "nonborrowerrowsexcluded",
        "excludedrowsfairvalue",
        # THE ABOVE-PAR BASIS + THE FROZEN FILER (2026-09-13 deep audit f3-bdc-core-7 /
        # f4-bdc-derived-17, wave D / D4). Per row `markAbovePar` (markedPrice > 100),
        # envelope `aboveParRowCount` + `markBasis` (the MARK_ABOVE_PAR_BASIS sentence:
        # FV / filed principal, where par may exclude PIK/OID accretion), and
        # `filerStatus` beside the `successorTicker` already admitted (BKCC -> TCPC).
        # Measured DROPPED by this filter before this edit. Our own disclosure.
        "markabovepar", "aboveparrowcount", "markbasis", "filerstatus",
    }),
    # 2026-09-05 moat-promotion vet L-2 (docs/board/audit/
    # 2026-09-05_CISO_COUNSEL_CHAOS_moat_promotion_vet.md): the three
    # name-proxied ol_bdc_* tools MUST register here and ride the filter --
    # hosted-side filtering is CONTENT hygiene (nonborrower/industry-label
    # artifacts), not a redistribution boundary; the pip boundary must not
    # depend on the server never adding a licensed field later. All three
    # seeded from the COMPOSED hosted emit builders (mcp_tools/moat_reads.py
    # -- the dispersion envelope + lender rows, the top-borrowers envelope +
    # rows + industry_basis, the common-borrowers envelope + rows), including
    # every nested sub-tree: _as_of block keys, _completeness block keys,
    # holders {ticker,name} entries, industry_basis sub-keys (verified
    # scalar-valued: by_fair_value is an industry LABEL string per
    # pg_get_borrower_industry_vote, never a data-keyed dict). All data is
    # the OL first-party parse of SEC EDGAR 10-K/10-Q Schedules of
    # Investments (public domain); no vendor field exists in any of these
    # emits (vet L-1, checked builder-by-builder). summary/count/as_of/
    # attribution/disclaimer ride _ENVELOPE_KEYS.
    "ol_bdc_borrower_dispersion": frozenset({
        # envelope (moat_reads.py dispersion return dict)
        "borrower_norm", "completeness", "spread_unit", "fair_value_unit",
        "marked_price_unit", "filing_date_range", "lenders",
        # lender rows
        "bdc_ticker", "filing_date", "security_type", "lien_position",
        "spread", "spread_bps", "marked_price", "fair_value",
        "bdc_latest_filing", "is_stale_vs_bdc_latest", "bdc_name",
        # YTM v1 yield view (2026-09-05, OWNER D1-D7): per-row measures +
        # machine-readable suppressions + the payload base-rate/disclosure
        "rate_type", "maturity_date", "mark_as_of", "non_accrual",
        "current_yield_pct", "spread_to_maturity_bps",
        "all_in_simple_yield_pct", "yield_basis", "pik_leg_excluded",
        "yield_suppressed", "margin_suppressed_reason",
        "base_rate", "yield_disclosure", "series", "rate_pct", "as_of", "source",
        # _as_of block
        "filing_dates", "mixes_filings", "stale_rows", "scope", "note",
        # _completeness block
        "returned", "limit", "total_available", "complete",
        "completeness_basis", "more_available_hint",
        # 2026-09-12 T12: above-par mark disclosure. Per-row flag + basis
        # sentence, and the envelope count. Admitted in the SAME change as
        # the producer (mcp_tools/moat_reads.py dispersion handler) -- this
        # filter is fail-closed and would drop them silently otherwise.
        "mark_above_par", "mark_above_par_basis", "rows_above_par",
        # 2026-09-12 (3.4.0 vet b07-bdc-moat-1; the 2026-09-05 field-report
        # F3 filer-status axis): the producer writes `filer_status`
        # (active|inactive|null) and `successor_ticker` on EVERY lender row
        # (moat_reads.py, beside bdc_name) and the summary tells the agent
        # to read them ("see filer_status/successor_ticker") -- while this
        # entry admitted neither, so nothing on the wire identified which
        # row was the wound-down filer. The sibling top_borrowers entry
        # admits the same pair as status/successor. OL roster labels, no
        # vendor lineage. Pinned by tests/test_mcp_dispersion_lender_row_
        # keys_survive_filter_contract.py, which runs the in-tree handler's
        # output through this filter and asserts no lender-row key is lost.
        "filer_status", "successor_ticker",
    }),
    "ol_bdc_top_borrowers": frozenset({
        # envelope
        "completeness", "units", "holder_count_basis", "fair_value_basis",
        "borrowers",
        # borrower rows
        "borrower", "borrower_norm", "holder_count",
        "cross_holder_sum_fair_value", "total_fair_value", "industry",
        "holder_tickers", "holders", "name", "holder_count_matches_tickers",
        # industry_basis sub-tree (#32 vote disclosure; values are scalar
        # industry labels, safe for the recursive KEY filter)
        "industry_basis", "stored_label_chosen_by", "by_fair_value",
        "fair_value_agreement", "distinct_industries", "contested",
        # _as_of block
        "filing_dates", "mixes_filings", "stale_rows", "scope", "note",
        # _completeness block
        "returned", "limit", "total_available", "complete",
        "completeness_basis", "more_available_hint",
        # 2026-09-09: the per-BDC holder-status map, and the two keys INSIDE
        # it. `holder_ticker_status` is data-keyed (a BDC ticker per entry, see
        # TOOL_DATA_KEYED_CONTAINERS), so the container needs admitting here
        # AND declaring there -- admitting it alone leaves the tickers dropped,
        # declaring it alone leaves the container dropped before the
        # declaration is read. The import-time validator now refuses the
        # second half-configuration; this comment is the first.
        "holder_ticker_status", "status", "successor",
        # 2026-09-12 (X2): the filter-STATE block. The borrower filters fail
        # open in both halves (moat_reads._borrower_filters) and the reachable
        # leg -- an empty industry vocabulary cached for its TTL -- left no
        # trace on the payload while the description promised "clean
        # borrowers only". Four fixed key names, all scalar-valued, all OL's
        # own accounting (a state word, a vocabulary size, a drop count).
        "borrower_filters", "nonborrower", "industry_label",
        "industry_vocab_size", "rows_removed",
        # 2026-09-13 (deep audit f3-bdc-core-2, wave D / D4): the borrower
        # directory's holder count beside the per-call `holder_count`, so a
        # directory/roster disagreement is visible rather than silently the larger.
        "directory_holder_count",
    }),
    "ol_bdc_common_borrowers": frozenset({
        # envelope
        "bdc_tickers", "min_holders", "completeness", "units",
        "fair_value_basis", "as_of_range", "borrowers",
        # 2026-09-12 (X2): filter-STATE block, same shape and reason as the
        # sibling entry above (one helper, two callers -- the vet's own rule).
        "borrower_filters", "nonborrower", "industry_label",
        "industry_vocab_size", "rows_removed",
        # borrower rows
        "borrower", "borrower_norm", "holder_count", "holder_tickers",
        "holders", "name", "total_fair_value", "total_par_amount",
        "as_of_oldest", "as_of_newest",
        # 3.4.0 vet b07-bdc-moat-13 (2026-09-12, B5b): the SAME filer-status
        # map the sibling row carries (one helper, two callers); declared
        # data-keyed below -- the same container NAME, not a new hole.
        "holder_ticker_status", "status", "successor",
        # _as_of block
        "filing_dates", "mixes_filings", "stale_rows", "scope", "note",
        # _completeness block
        "returned", "limit", "total_available", "complete",
        "completeness_basis", "more_available_hint",
        # 2026-09-13 (deep audit f4-bdc-derived-6, wave D / D4): the ticker gate --
        # a requested BDC that resolves to nothing is named under `unresolved_tickers`
        # [{ticker, reason}] instead of silently narrowing the intersection.
        # `ticker` rides the envelope.
        "unresolved_tickers", "reason",
    }),
    # ── The eleven, 2026-09-09 ────────────────────────────────────────────
    # COUNSEL COMPLIANCE_REVIEW_v1: ADMIT-WITH-CONDITIONS on all eleven, zero
    # refusals, lineage traced handler -> helper SELECT -> ingest per tool. This
    # clears the LICENSING leg only; `feedback_public_repo_persona_vet` needs
    # CISO + COUNSEL + CHAOS + OWNER for the publish itself.
    #
    # Every set below is the UNION of keys observed in LIVE payloads across each
    # tool's branches (labelled per entry), never a SELECT list -- COUNSEL's own
    # self-critique was that it read SELECT lists, not responses, and
    # `search_bdc_borrower` measured the cost: 27 vs 11 top-level keys between
    # its hit and miss branches, so either alone silently amputates the other.
    #
    # Six of these tools 500'd on their data path when first called (Decimal /
    # date / datetime never reached the wire); the render fix that unblocked
    # them is a separate commit, and these keys were captured after it deployed.

    # SEC quarterly Form D ZIP end-to-end (`data/edgar_formd.py:8-10`).
    # `offering_indefinite` + `total_amount_sold` are C3 MUST-ADMIT: without
    # them the "ceiling is not money raised" trap the description names becomes
    # invisible, and a reader takes total_offering_amount for a raise.
    "ol_form_d_raises": frozenset({
        "accession", "date_of_first_sale", "days", "entity_type",
        "federal_exemptions", "filing_date", "first_sale_yet_to_occur",
        "industry", "industry_group", "investment_fund_type",
        "investors_count", "is_debt", "is_equity", "issuer_cik",
        "issuer_name", "offering_indefinite", "offerings", "state",
        "submission_type", "total_amount_sold", "total_offering_amount",
        "total_remaining",
        # 3.4.0 vet b08-vi-formd-insiders-1 (2026-09-12, B5b): the loaded-
        # vintage freshness markers -- the SEC posts the Form D data sets
        # QUARTERLY, so a trailing window is empty by construction inside the
        # lag; without these two names the filter strips the marker the
        # finding was filed for.
        "data_through", "newest_quarter_loaded",
    }),

    # `form4_transactions` -- the same substrate the wheel's `get_insider_trades`
    # already ships. C3 STRIP `id`: a monotonic internal surrogate PK discloses
    # corpus size and ingest ordering, and terms.html §5.5 prohibits systematic
    # corpus reconstruction. Dropped from the manifest description too.
    "ol_insider_recent_buys": frozenset({
        "buys", "filingdate", "insidername", "isderivative", "position",
        "pricepershare", "securitytitle", "shares", "sharesowned",
        "since_days", "title", "totalvalue", "transactiondate",
        "transtype", "url",
    }),

    # `sec_ftd`. COUNSEL flagged that the STORE holds CUSIP
    # (`tools/fetch_sec_ftd.py:5`) while `pg_get_ftd_history` does not SELECT it
    # (`pg_db/queries/ftd.py:36-46`) -- so the absence is structural here, not
    # decorative, and the import-time carve-out validator pins it.
    # `description` is C3 MUST-ADMIT (the security's own name).
    # THIS TOOL WAS PULLED FROM THE BATCH AND PUT BACK: it returned count=0 for
    # every ticker over 730 days because `sec_ftd` was EMPTY -- the ingest cron
    # had never been created. It exists now and the keys below are from a
    # populated window, not an empty one.
    "get_fails_to_deliver": frozenset({
        "date", "days", "description", "fails", "history", "price",
        # 2026-09-13 (deep audit f5-gov-feeds-2, wave D / D5): the coverage floor.
        # An empty history is normal ONLY inside the loaded window, so the payload
        # names it: `coverage` {earliest_settlement_date, latest_settlement_date,
        # files_loaded, window_start, window_predates_coverage,
        # window_postdates_coverage}. Our own store accounting; `as_of` / `summary`
        # ride the envelope.
        "coverage", "earliest_settlement_date", "latest_settlement_date", "files_loaded", "window_start", "window_predates_coverage", "window_postdates_coverage",
    }),

    # EDGAR 13D/G, clean. `updated_at` is admitted deliberately: it is OUR CACHE
    # stamp, not a filing date, and the description must say so -- withholding
    # freshness is worse than the naming hazard. See C5 on the write-on-read.
    # `purpose` DROPPED 2026-09-12 (3.4.0 vet b09-gov-a-2): no writer in the
    # tree populates it. fetch_13d_filings (data/edgar_13d.py) builds rows
    # without a `purpose` key; pg_upsert_activist_stakes writes
    # `f.get("purpose")` -> NULL and `purpose = EXCLUDED.purpose` on
    # conflict, so every refresh re-nulls it; parse_13d_details (the only
    # thing that ever sets a purpose) feeds the /details read route, never
    # the store. A promised key that is always null is dropped, not
    # described. Pinned by tests/test_mcp_activist_stakes_purpose_never_
    # written_contract.py, which drives the writer with EDGAR stubbed.
    "get_activist_stakes": frozenset({
        "accession_number", "filer_name", "filing_date", "filings",
        "form_type", "is_activist", "percent_of_class",
        "shares", "updated_at",
        # 2026-09-09 (CISO F2): the staleness disclosure that replaces the
        # unconditional refresh for anonymous callers. Admitted in the SAME
        # change that emits them -- a new payload key with no allowlist entry
        # is silently dropped, which is the defect this file spent the day on.
        "age_seconds", "stale", "refreshed",
        # 2026-09-13 (deep audit f5-gov-feeds-1 BLOCK, wave D / D5): the writer was
        # blind to EDGAR's Nov-2024 'SCHEDULE 13D/G' relabel. `stale` is now derived
        # from newest_filing_seen (EDGAR's index watermark) vs newest_filing_stored
        # (the newest row on file); `fetched_rows` is what the refresh returned.
        # Measured DROPPED by this filter before this edit.
        "newest_filing_stored", "newest_filing_seen", "fetched_rows",
    }),

    # Treasury MSPD verbatim (`pg_db/queries/treasury_mspd.py:174-181`).
    "ol_treasury_debt": frozenset({
        "debt_held_public_mil_amt", "intragov_hold_mil_amt", "record_date",
        "rows", "security_class", "security_class_desc", "security_type",
        "security_type_desc", "src_line_nbr", "total_mil_amt",
    }),

    # CFTC Socrata. C3 STRIP `positions` -- the raw Socrata field-name blob; not
    # SELECTed today, pinned out so a future helper change cannot ship it.
    # `market_label` is an OL-authored string embedding CME/S&P marks
    # (`data/cftc_cot.py:53`) -- descriptive/nominative use, never endorsement.
    "ol_cftc_cot": frozenset({
        "market", "market_key", "market_label", "mm_long", "mm_net",
        "mm_short", "open_interest", "report_date", "report_type", "rows",
        # SECOND BRANCH, added after the first cut of this set missed it. My
        # capture called this tool ONCE, with no `market` argument, so it only
        # ever saw the all-market snapshot -- and `contract_code` +
        # `source_dataset` are emitted only by the per-market SERIES branch.
        # That is precisely the `search_bdc_borrower` lesson (27 vs 11 keys
        # between branches) committed by the script whose own docstring cites
        # it. Caught by the description-vs-allowlist contract, not by review.
        "contract_code", "source_dataset",
    }),

    # FDIC BankFind verbatim EXCEPT `ticker`, which is NOT an FDIC field --
    # `tools/ingest_fdic_institutions.py:109` omits it and :10-12 says it comes
    # from our own verified CERT<->ticker map. A hybrid: the description carries
    # the sentence saying so, because `_meta.source` would otherwise be false
    # for that one field. (`ticker` is an envelope key, hence not listed here.)
    "ol_fdic_bank": frozenset({
        "active", "asset", "bkclass", "cert", "city", "dep", "estymd",
        "institutions", "name", "query", "repdte", "stname", "webaddr",
    }),

    # USAspending amounts + UEIs are government; the TICKER attribution is our
    # hand-curated crosswalk (`data/usaspending_crosswalk.py:6-14`). Second
    # hybrid, same treatment. `dropped_unresolved` is C3 MUST-ADMIT -- it is the
    # crosswalk's own coverage admission, and without it a partial mapping reads
    # as complete. C3 STRIP `id`.
    "ol_federal_contracts": frozenset({
        "amount", "dropped_unresolved", "end_date", "entity_count",
        "fetched_at", "fiscal_year", "hint", "leaderboard", "name",
        "obligations", "recipient_id", "recipients", "start_date",
        "total_obligations_usd", "uei", "ueis",
        # 2026-09-13 (deep audit f5-gov-feeds-6, wave D / D5): same sibling disclosure.
        "requested_ticker",
    }),

    # The emitted `applicant_name` is USPTO's own `firstApplicantName`
    # (`data/uspto_patents.py:83`), NOT the `company_profiles` name -- that one
    # is only the QUERY and never reaches the payload, which is what kept this
    # clear of the `cfa.source` pattern. C3 STRIP `id` + `ingested_at` (internal
    # write stamp; `filing_date` is the honest date). C4: read the ODP ToU.
    "ol_patents": frozenset({
        "applicant_name", "application_number", "application_type",
        "filing_date", "filings", "patent_number", "publication_number",
        "status", "title",
        # 2026-09-13 (deep audit f5-gov-feeds-6, wave D / D5): rows served under a
        # share-class sibling (GOOG -> GOOGL) name the class asked for.
        "requested_ticker",
    }),

    # OL PARSE -- `pg_get_bdc_qoq_diff_rows` reads `bdc_holdings` only
    # (`pg_db/queries/bdc.py:833-849`), so OL attribution is mandatory and the
    # basis must say ol-derived, not primary. `coverage` and its WHOLE subtree
    # are C3 MUST-ADMIT: without them a partial sweep reads as complete, which
    # is a §6.4 misrepresentation on the machine channel and the
    # `feedback_count_masks_degenerate_data` shape.
    "ol_bdc_mark_changes": frozenset({
        "bdc_tickers", "borrower", "coverage", "covered", "covered_detail",
        "decreases", "decreases_completeness", "filing_dates",
        "grain_basis", "increases", "increases_completeness",
        "latest_filing", "latest_mark", "mark_delta", "mark_moves_found",
        "mixes_filings", "not_covered", "not_covered_detail", "note",
        "portfolio", "prior_filing", "prior_mark", "requested",
        "requested_tickers", "scope", "stale_rows", "units",
        # 3.4.0 vet b06-bdc-marks-9 (2026-09-12, B5b): the inclusion
        # thresholds surfaced as a payload block instead of prose.
        "filters", "min_abs_mark_delta_pts", "min_borrower_fv_usd",
        # The REFUSAL branch. COUNSEL named the coverage subtree as
        # `covered_detail`, `not_covered_detail`, `reason` AND `detail`; my
        # first capture called this tool only with real BDC tickers, so the
        # last two -- which appear when a requested ticker resolves to nothing
        # -- were never observed and were dropped. Without them the refusal
        # arrives with no stated reason, which is the same "hedge becomes a
        # confident answer" failure the rest of this subtree guards against.
        "detail", "reason",
        # 2026-09-13 (deep audit f4-bdc-derived-17, wave D / D4): an INACTIVE filer's
        # frozen final filing is labelled, with its successor where one exists.
        "filer_status", "successor_ticker",
    }),

    # OL PARSE -- `pg_get_bdc_non_accrual_share` reads `bdc_holdings` only
    # (`pg_db/queries/bdc.py:1519-1533`); OL attribution mandatory.
    # `determinate_coverage` is C3 MUST-ADMIT: without it `flagged_pct: null`
    # ("withheld, coverage <90%") is indistinguishable from "no data".
    "ol_bdc_credit_quality": frozenset({
        "determinate_coverage", "determinate_fv", "filing_date",
        "flagged_fv", "flagged_pct", "latest", "quarter_key", "quarters",
        "total_debt_fv", "trend",
        # 2026-09-13 (deep audit f4-bdc-derived-17 / -18, wave D / D4): the
        # denominator sentence on the `latest` block (flagged_fv / DETERMINATE fv,
        # never total_debt_fv) and the inactive-filer label.
        "flagged_pct_basis", "filer_status", "successor_ticker",
    }),

    # ── CISO F5, 2026-09-12: the nine wheel tools that rode no emit filter ──
    # 20 of the 29 wheel tools were filtered; these 9 shipped whatever their
    # handler returned. Every set is the UNION of keys observed across the
    # sources named per entry (hosted anonymous /mcp capture; the wheel's own
    # literal keys where it talks to FRED/SEC directly or reshapes a route; a
    # local handler run and the route's response_model for the two plus-gated
    # tools nothing anonymous can see), lowercased, minus _ENVELOPE_KEYS, minus
    # CARVEOUT_ID_KEYS, minus `id` / `created_at`. The wheel now applies this
    # table CENTRALLY in its dispatcher, and a contract pins that every
    # PIP_TOOLS member has an entry -- a wheel tool with no allowlist is a CI
    # red, not a runtime 500 and not a silent passthrough.

    # A: hosted anonymous /mcp, hit (AAPL: 74 distinct keys) + miss ("Ticker not
    # found in CIK map"). B: the wheel's OWN companyfacts reader -- its concept
    # vocabulary (Revenue, NetIncome, EPS, DilutedShares, TotalAssets, ...,
    # lowercased) plus data/period/value/withheld/yearsAvailable/coverage/
    # coverageNote. Two shapes under one name; the union is what keeps both
    # whole. `metrics.*` and `balanceSheet.*` are LISTS aligned with `years`,
    # so no hatch is needed there. `basis.withheldValues.<metric>` is a
    # YEAR-keyed dict on BOTH channels (hosted: epsDiluted/sharesOut; wheel:
    # EPS/DilutedShares) and rides the year-SHAPE rule in `_walk` (see
    # DATA_KEY_SHAPES) -- not a per-tool declaration, which is what emptied the
    # wheel's copy (T2, 2026-09-12).
    "get_fundamentals": frozenset({
        "affectedmetrics", "balancesheet", "basisboundaries",
        "basischecked", "basisconsistent", "capex", "cashandshortterm",
        "coverage", "coveragenote", "currentassets", "currentliabilities",
        "currentratio", "da", "data", "debttoassets", "dilutedshares",
        "earliest", "ebit", "ebitmarginpct", "enddate", "eps", "epsdiluted",
        "evidence", "fcf", "firstcomparableyear", "fundamentals",
        "goodwill", "grossmarginpct", "grossprofit", "intangibleassets",
        "latest", "metrics", "nearestsplitratio", "netincome", "note",
        "observedjump", "opcf", "operatingcashflow", "quarterly",
        "quickratio", "revenue", "sharesout", "source_period",
        "stockholdersequity", "totalassets", "totaldebt",
        "totalliabilities", "value", "withheld", "withheldthrough",
        "withheldvalues", "yearpairsexamined", "years", "yearsavailable",
        # THE DEBT LABEL (3.4.0 vet b01-sec-standalone-4, BLOCK, 2026-09-12).
        # The wheel's series called `TotalDebt` was us-gaap:LongTermDebt with
        # an unlabeled LongTermDebtNoncurrent fallback; it is now emitted as
        # `LongTermDebt` and the key TotalDebt is gone from the WHEEL. The
        # `totaldebt` name above STAYS: it is the HOSTED channel's
        # `fundamentals.metrics.totalDebt` / `balanceSheet.totalDebt` (the
        # matrix fixture carries both paths) -- this set is the union of
        # two shapes, and dropping it would amputate the hosted one. Beside
        # the label: `concepts` {label: [{period, concept}]} names the
        # us-gaap rung that served every cell (a list of rows, because a
        # period end is data, not a name, and the year-shape hatch below
        # is deliberately scoped to four-digit years), `concept` is its row
        # key, and `conceptsNote` says how to read it. Our own metadata
        # about the filer's own tags; no vendor field, no identifier.
        "longtermdebt", "concepts", "concept", "conceptsnote",
        # THE GATE'S ADVISORY TIER (T1 residual b, 2026-09-12). The #33
        # split-basis gate has three outcomes the flag pair cannot carry on
        # its own, and the F5 seeding -- a capture of ONE issuer whose gate
        # withheld -- never observed any of them: `basisAdvisory` (an
        # implied-share jump with NO issuer refiling: disclosed, not
        # withheld -- 8 issuers in the module's own docstring),
        # `residualBreaksAfterCut` (a break the cut left behind -- the gate
        # reporting success while still serving a mixed-basis array), and
        # `basisNote` (the UNEXAMINED branch's sentence: "NOT a clean result
        # -- the check did not run"). Measured through this filter before the
        # fix: all three stripped, on both channels, while `basisConsistent`
        # survived -- so `null` read as "no data" and `true` read as "clean"
        # with the caveat gone. The row keys are the SAME on both channels
        # (`basis_jumps` in data/eps_basis_gate.py and the split_basis port):
        # from_year / to_year / jump / implied, plus `basis` (envelope) on
        # the advisory rows. All of it is our own arithmetic over SEC
        # companyfacts; no vendor field, no identifier.
        "basisadvisory", "residualbreaksaftercut", "basisnote",
        "from_year", "to_year", "jump", "implied",
        # THE INSTANT BOUNDARY (T1 residual a, 2026-09-12). The hosted
        # `sharesOut` rung is CommonStockSharesOutstanding, a balance-sheet
        # INSTANT restated on a two-year comparative while EPS is restated on
        # three -- so the EPS cut left one pre-split share-count cell inside
        # the window (served AAPL 2018 = 4.75bn beside 2019 = 17.77bn).
        # `apply_instant_boundary` (data/eps_basis_gate.py) withholds that
        # cell into withheldValues.sharesOut (year-shape hatch, already
        # admitted) and names the share count's own edge with these four
        # keys. Hosted-only in practice: the wheel's DilutedShares is a
        # duration fact and never lags. Our own arithmetic; no identifier.
        "instantmetrics", "instantwithheldthrough", "instantobservedjump",
        "instantnote",
        # THE EQUITY RUNG + THE TAGGING HOLE (2026-09-13 deep audit,
        # f1-sec-fundamentals-4 / -5, both FIX-BEFORE-PUBLISH). `equityNote`
        # says which rule admitted the consolidated equity rung for an NCI
        # filer (JNJ tags its 10-K equity ONLY there); `equityWithheldNci`
        # rows {period, value, nci} carry the periods refused because the NCI
        # instant is non-zero (the `withheld: 'nci_consolidated'` cells).
        # `coverage[label].contiguous` says whether the served periods skip a
        # fiscal year; `gapBreaks` {label: {olderPeriod, newerPeriod,
        # observedJump, withheldThrough}} + `gapNote` disclose a >= 5x step
        # across such a hole (DAC's 1-for-14 inside its 2012-2016 hole) whose
        # older side is withheld as `basis_unverified`. All of it is our own
        # arithmetic over SEC companyfacts; no vendor field, no identifier.
        "equitynote", "equitywithheldnci", "nci", "contiguous",
        "gapbreaks", "gapnote", "olderperiod", "newerperiod",
        # THE FISCAL-YEAR AXIS (2026-09-13 deep audit f1-sec-fundamentals-1 BLOCK,
        # wave D / D1). `periods` is the ISO period-end list aligned with `years`
        # (JNJ's FY2022, ended 2023-01-01, is served again); the five splitRatio*
        # keys name the filer's OWN tagged split (StockholdersEquityNoteStockSplit
        # ConversionRatio1) that withheld pre-split share counts; `noAnnualFacts`
        # {usGaapConceptCount, formsSeen, unitsSeen, sentence} is what a filer with
        # NO annual us-gaap fact does carry (CNI: 457 concepts, all on 6-K in CAD),
        # and `taxonomy` / formsSeen / unitsSeen ride the hosted refusal that
        # quotes it. Our own reading of SEC companyfacts; no vendor, no identifier.
        "periods", "splitratiometrics", "splitratiowithheldthrough", "splitratiodate", "splitratio", "splitrationote", "noannualfacts", "usgaapconceptcount", "formsseen", "unitsseen", "sentence", "taxonomy",
    }),

    # A: hosted anonymous /mcp, include_history false (22 keys) + true (31).
    # The eleven tenors are a fixed vocabulary, so they are NAMES, not a hatch.
    # B: the wheel calls FRED directly with the operator's own key and emits
    # yield_curve / yield_curve_1y_ago / history_coverage / lookback_tolerance_
    # days / maturities_total / maturities_with_prior. `_source` is the row's
    # attribution ("treasury.gov" / "fred") and rides through.
    # B1 (2026-09-12, b02-fred-4): a partial curve (fewer than eleven tenors)
    # now carries `completeness` {maturities_total, maturities_missing,
    # reason}. `completeness` already rides _ENVELOPE_KEYS and is repeated
    # here so this entry names every key the tool emits; `maturities_missing`
    # (tenor labels) and `reason` (our own sentence) are new NAMES. Measured
    # before this edit: the filter kept `maturities_total` and dropped the
    # other two -- the same fail-closed strip the b02-6 finding warned of.
    "get_yield_curve": frozenset({
        "10y", "1m", "1y", "20y", "2y", "30y", "3m", "3y", "5y", "6m", "7y",
        "_source", "completeness", "current", "data", "date", "dates",
        "history_coverage", "include_history", "lookback_tolerance_days",
        "maturities", "maturities_missing", "maturities_total",
        "maturities_with_prior", "name", "oneyearago", "reason", "series",
        "threemonthsago", "value", "yield_curve", "yield_curve_1y_ago",
        "ytdchange",
    }),

    # The hosted tool is KEY-ONLY (anonymous -> "not available to anonymous
    # callers"), so A is the in-tree handler's literals (mcp_tools/macro_reads.py:
    # series/data/observation/note/available/available_count + the latest-value
    # row shape {series,name,value,date,ytdChange,_source}). B: the wheel's own
    # FRED reader (count/data/date/series/value). Only the wheel filter bites
    # today; the entry exists so the F1 seam is ready if the tool ever opens.
    # B1 (2026-09-12, b02-fred-6 / -5): the wheel now emits the probe's
    # title/units/frequency as `name` / `units` / `frequency` and a plain-
    # string `note` on an empty window. `name` and `note` were already here;
    # `units` and `frequency` are new NAMES (FRED's own metadata words, no
    # vendor lineage). Measured before this edit: both were silently dropped.
    "get_fred_data": frozenset({
        "_source", "available", "available_count", "data", "date",
        "frequency", "name", "note", "observation", "series", "units",
        "value", "ytdchange",
    }),

    # A: hosted anonymous /mcp, random (26 keys) + category (5). B: REST
    # /api/value-investing/random, the route the wheel proxies. `id` and
    # `created_at` STRIPPED: a facts-corpus row id and its insert stamp are
    # ours, no parameter round-trips them (params are category/query), and
    # the C3 rationale for `id` is the same one word over. `total_facts` and
    # `available_categories` are the coverage statements and stay.
    "get_value_investing_fact": frozenset({
        "author", "available_categories", "category", "difficulty", "era",
        "fact", "quote", "source_year", "subcategory", "total_facts",
        # 2026-09-13 (deep audit d3-hosted-catalog-3 / f7-reference-search-8, wave D /
        # D7 blocker B7): the QUERY path returns {facts, count, total_facts} and
        # `facts` was never admitted, so an anonymous category query came back as
        # {count, total_facts} with the rows stripped. The row keys (quote, author,
        # source_year, category, subcategory, era, difficulty; `source` is an
        # envelope key) were already here. Oxford Ledge-authored corpus.
        "facts",
    }),

    # PLUS-GATED. RE-SEEDED 2026-09-12 (3.4.0 vet b04-events-capital-1/-2/
    # -3): the wheel is now a NAME-PROXY of the hosted get_debt_maturities,
    # so this entry is the HOSTED shape and nothing else -- captured by
    # EXECUTING the in-tree handler through mcp_server._execute_tool_with_
    # limits(caller_kind="http") with fetch_debt_maturities stubbed to the
    # writer's own hit / warned / miss shapes (data/edgar_debt_maturities.py
    # fetch_debt_maturities: result dict + the two convenience flags), the
    # capture pinned by tests/test_mcp_debt_capital_name_proxy_contract.py.
    # The former entry was a UNION of the in-tree shape and the REST route's
    # (schedule[]{year, amount}, totalDebt); the route half is dead now the
    # route is not proxied, and `data` / `fetched_at` never were emitted
    # (they are the in-memory cache wrapper's keys). Pruned, per the vet:
    # "prune whichever half is dead in the same change and re-seed from an
    # executed capture, not the response_model". All SEC-EDGAR-derived
    # (10-K/20-F note parse cross-checked against XBRL), no vendor lineage.
    # ticker / source / _meta.* ride _ENVELOPE_KEYS.
    "get_debt_maturities": frozenset({
        # envelope
        "maturities", "thereafter", "confidence", "confidence_score",
        "validation", "filing_date", "report_date",
        # maturities[] rows
        "year", "amount",
        # validation block
        "valid", "maturity_total", "bs_total", "diff_pct", "warning",
        # the two convenience flags (hit-with-validation / hit-with-warning)
        "cross_validated", "validation_warning",
    }),

    # PLUS-GATED. RE-SEEDED 2026-09-12 (3.4.0 vet b04-events-capital-8/-7):
    # the wheel is now a NAME-PROXY of the hosted get_capital_allocation --
    # the 10-year capital ALLOCATION scorecard (data/edgar_xbrl._fetch_
    # capital_allocation, SEC XBRL cash-flow tags) the description was
    # always written for. Captured the same way as the sibling above
    # (in-tree handler executed with the fetcher stubbed to the writer's
    # result dict). The capital-STRUCTURE keys the REST proxy used to emit
    # (layers / layer / amount / percentage, Finnhub-fed, under a middleware
    # `_meta` citing SEC EDGAR) are GONE from this entry: the wheel cannot
    # emit them any more and admitting them would let a Finnhub payload
    # through a GOV_PUBLIC tool the day someone re-pointed the proxy.
    # `summary` and `error` ride _ENVELOPE_KEYS (the error branch is
    # {"error": <str>} alone).
    "get_capital_allocation": frozenset({
        "capitalallocation",
        # the parallel arrays, newest-first, aligned to `years`
        "years", "dividends", "netbuybacks", "netdebtchange",
        "acquisitions", "sharesout", "isdilutive",
        # summary block
        "sharecountchange10yr", "dilutiveyears", "totaldividends",
        "totalnetbuybacks", "totalnetdebt", "totalacquisitions",
        # THE SCORECARD'S BASIS (2026-09-13 deep audit f1-sec-fundamentals-1 /
        # d3-hosted-catalog-2 BLOCK, wave D / D1). The tool now serves `periods`
        # beside `years`, a `basis` block with the SAME vocabulary get_fundamentals
        # admits above (the split gate that stops DAC's 1-for-14 reading as an -83%
        # buyback), and summary sentences (`windowYears`, `yearsJudged`,
        # `shareCountNote`, `dilutionNote`, `dividendsNote`) that say what every
        # summary figure was computed over. `taxonomy` / usGaapConceptCount /
        # formsSeen / unitsSeen ride the refusal specimen (TSM). Our own arithmetic
        # over SEC companyfacts; no vendor field, no identifier.
        "periods", "basis", "windowyears", "sharecountnote", "yearsjudged", "dilutionnote", "dividendsnote", "taxonomy", "usgaapconceptcount", "formsseen", "unitsseen", "basisconsistent", "basischecked", "yearpairsexamined", "withheldthrough", "firstcomparableyear", "observedjump", "nearestsplitratio", "basisboundaries", "affectedmetrics", "withheldvalues", "evidence", "note", "period", "value", "basisadvisory", "residualbreaksaftercut", "basisnote", "from_year", "to_year", "jump", "implied", "instantmetrics", "instantwithheldthrough", "instantobservedjump", "instantnote", "splitratiometrics", "splitratiowithheldthrough", "splitratiodate", "splitratio", "splitrationote",
    }),

    # PIP-ONLY. The wheel reshapes /api/institutional-holders into holders[]
    # {holder, shares, value, type, quarter, filingDate} + totalHolders/asOf/
    # totalFetched (B, the wheel's literals). T7 (2026-09-12): the per-row
    # vintage (quarter + filingDate, the get_13f_holdings key style) and the
    # honest top-level disclosure -- `vintages` (a LIST of {quarter, count}
    # rows, deliberately not a quarter-keyed dict) + `rankingBasis` -- plus the
    # route's own `coverage` block passed through verbatim (shares_13f /
    # fund_count / shares_outstanding / pct / quarter / basis / overstated:
    # all SEC-13F-derived counts, no vendor lineage). `quarter`, `count` and
    # `basis` already ride _ENVELOPE_KEYS; they are repeated here so this
    # entry names every key the tool emits, not just the ones the frame does
    # not happen to cover.
    "get_holders": frozenset({
        "asof", "holder", "holders", "shares", "totalfetched",
        "totalholders", "type", "value",
        "quarter", "filingdate", "vintages", "count", "rankingbasis",
        "coverage", "shares_13f", "fund_count", "shares_outstanding", "pct",
        "basis", "overstated",
        # 2026-09-12 (3.4.0 vet b03-ownership-2): the empty-branch SCOPE
        # note. `note` is NOT an _ENVELOPE_KEYS member (`notice` is), and the
        # first cut of this change measured the sentence stripped by this very
        # filter -- admitted per tool, the way the dispersion entry does.
        # `error` / `_meta` ride _ENVELOPE_KEYS.
        "note",
    }),

    # PIP-ONLY. The wheel reshapes /api/insider-activity into trades[] with
    # explicit keys, and that reshape already drops the route's `id` -- which
    # the route DOES emit anonymously (measured 2026-09-12: transactions[].id
    # 1,643,421..., the same form4_transactions row-id class as CISO F1). This
    # entry makes the strip a declared boundary instead of an accident of the
    # reshaper: if someone ever spreads the row, `id` still does not ship.
    "get_insider_trades": frozenset({
        "date", "datebasis", "filingdate", "insider", "is_open_market",
        "position", "pricepershare", "shares", "sharesowned",
        "totalfetched", "trades", "transactiondate", "transtypelabel",
        "type", "url", "value",
        # 2026-09-12 (3.4.0 vet b03-ownership-8): the route's derivative-
        # table labels (pg_get_insider_activity `securityTitle` /
        # `isDerivative`, on every row; same pair ol_insider_recent_buys
        # already admits). Without them an RSU award or an option-exercise
        # leg read as ordinary shares. Admitted in the SAME change as the
        # reshape that now carries them. `completeness_basis` / `error` /
        # `_meta` ride _ENVELOPE_KEYS; `note` (b03-ownership-11, the
        # empty-branch scope sentence) does NOT -- measured stripped on the
        # first cut -- so it is admitted here.
        "securitytitle", "isderivative", "note",
    }),

    # PIP-ONLY. The wheel builds this from SEC's submissions API itself:
    # filings[]{form, title, url, date} plus a `completeness` block
    # {returned, cap, windowRows, windowFrom}. 3.4.0 vet b01-sec-standalone-1
    # (2026-09-12): the unfiltered default is the 10 newest submissions of
    # ANY form with the form fused into `title` and the cap undisclosed, so
    # a model asking for "recent filings" got Form 4s and Rule 144 notices
    # and could not tell ten from all. `form` is the row's own form type;
    # `cap` is the row cap (10); `windowRows` is how many submissions SEC's
    # `filings.recent` index held (~1000, the only window this tool reads);
    # `windowFrom` is that window's oldest filingDate. `completeness` and
    # `returned` ride _ENVELOPE_KEYS. All from the wheel's literals; SEC's
    # own index, no vendor field, no identifier.
    "get_sec_filings": frozenset({
        "date", "filings", "title", "url",
        "form", "cap", "windowrows", "windowfrom",
    }),

}

# Import-time invariant: no allowlist may admit a carve-out key. This is
# the denylist's knowledge promoted to a structural check -- the two
# lists cannot drift apart silently.
# CASING IS LOAD-BEARING (CHAOS P3-2, 2026-09-09). Membership is tested as
# `k.lower() in merged`, so an entry carrying an uppercase letter is
# PERMANENTLY INERT -- it silently drops the very key it was added to admit,
# and reads as present to anyone grepping the set. The convention is already
# doing real work (`ol_insider_recent_buys` lowercases a camelCase
# producer's filingDate / insiderName / pricePerShare), so it is asserted
# here rather than trusted, in the loop that already walks every entry.
#: Containers whose CHILD KEYS ARE DATA, not field names (2026-09-09).
#:
#: The allowlist is a set of key NAMES. A payload that maps a ticker to a value
#: — `priceHistory: {"ARCC": [...], "MSDL": [...]}` — has keys the allowlist can
#: never hold, so `_walk` dropped every entry and the whole block arrived empty.
#: Measured live before extending the filter to the hosted channel:
#: `search_bdc_borrower` lost `priceHistory` for AGTC/ARCC/MSDL/PSBD, and
#: `ol_bdc_top_borrowers` lost `holder_ticker_status` for twelve tickers. Both
#: tools already ride this filter in the published wheel, so this was live data
#: loss, not a hypothetical.
#:
#: Declaring a container here passes its IMMEDIATE child keys through and keeps
#: filtering everything beneath them — the boundary still holds one level down,
#: which is where the field names live. Fail-closed by default: a container
#: nobody declares behaves exactly as before.
#:
#: Keep this set SMALL and per-tool. It is an escape hatch from a fail-closed
#: filter, and every entry is a place where key names stop being checked.
TOOL_DATA_KEYED_CONTAINERS: dict[str, frozenset[str]] = {
    # borrower -> per-BDC quarterly mark series
    "search_bdc_borrower": frozenset({"pricehistory"}),
    # borrower row -> per-BDC {status, successor} for delisted/renamed holders
    "ol_bdc_top_borrowers": frozenset({"holder_ticker_status"}),
    # 2026-09-12 (3.4.0 vet b07-bdc-moat-13, B5b): the sibling tool now carries
    # the SAME map from the SAME helper. The cap contract counts DISTINCT
    # container names (a hole is a shape, not a call site): still two.
    "ol_bdc_common_borrowers": frozenset({"holder_ticker_status"}),
    # `get_fundamentals` WAS here (CISO F5, 2026-09-12: {"epsdiluted",
    # "sharesout"}, the fourth and cap-reaching entry) and is not any more.
    # The entry named the HOSTED metric labels, and the wheel's own
    # companyfacts reader labels the same withheld series `EPS` /
    # `DilutedShares` (server.py passes those to apply_basis_gate) -- so the
    # wheel's `withheldValues` came out `{"EPS": {}, "DilutedShares": {}}`
    # while its note still said the values were there. A name-based hatch
    # cannot cover a container whose NAME differs per channel without listing
    # every label, and the labels are a call argument, not a literal, so no
    # AST walk sees them. The year-keyed dict is data by SHAPE; see
    # DATA_KEY_SHAPES below, which is what replaced this entry (T2).
}

#: Containers whose KEYS ARE DATA BY SHAPE (T2, 2026-09-12) -- the third
#: universal hatch beside `error` and `params_accepted`, written as a declared
#: table rather than a `k.lower() ==` branch so `test_the_universal_hatches_
#: stay_countable` can COUNT it instead of staying blind to it.
#:
#: A non-empty dict whose keys ALL match one of these patterns has its keys
#: passed through and its VALUES filtered normally one level down -- exactly
#: the per-tool hatch's semantics, keyed by what the keys look like instead
#: of by what their parent is called. A MIXED dict (one year key beside one
#: field-name key) matches nothing and stays fail-closed: every key is then
#: tested by name, the years are not names, and the block empties. That is
#: deliberate -- a shape rule that fired on "mostly years" would be a hole
#: with fuzzy edges.
#:
#: Why this is the fix and not a wider per-tool table: the wheel's split-basis
#: disclosure keys its withheld series by the wheel's OWN metric labels
#: (`EPS`, `DilutedShares`), the hosted channel by its own (`epsDiluted`,
#: `sharesOut`), and both bucket by four-digit year underneath. The old
#: per-tool entry listed one channel's labels and silently emptied the
#: other's. `test_the_hatch_stays_small`'s own message says the fix for a
#: growing name table is upstream, in the shape; this rule reads the shape
#: that is already there, and the per-tool table is back to two.
#:
#: SCOPE, stated so the next re-measure does not widen it by accident: a
#: four-digit year `(19|20)\d\d`, full-match, string keys only. NOT a
#: quarter (`2017Q3`), NOT a date (`2017-09-30`), NOT a ticker -- those stay
#: per-tool declarations. No CARVEOUT_ID_KEYS member is a four-digit year
#: (asserted at import below), so nothing this rule passes is a licensed
#: identifier.
DATA_KEY_SHAPES: dict[str, re.Pattern[str]] = {
    "four_digit_year": re.compile(r"(19|20)[0-9]{2}"),
}


def _keys_are_data_by_shape(o: dict[Any, Any]) -> bool:
    """True iff *o* is non-empty and EVERY key is a str full-matching one
    declared shape. Mixed dicts return False and stay fail-closed."""
    if not o:
        return False
    return all(
        isinstance(k, str) and any(p.fullmatch(k) for p in DATA_KEY_SHAPES.values())
        for k in o)


for _shape_name, _shape in DATA_KEY_SHAPES.items():
    _hit = sorted(k for k in CARVEOUT_ID_KEYS if _shape.fullmatch(k))
    if _hit:
        raise AssertionError(
            f"DATA_KEY_SHAPES[{_shape_name!r}] matches carve-out key(s) {_hit}"
            " -- a shape rule that passes a licensed identifier is the leak"
            " the allowlist inversion exists to prevent")


# Every data-keyed container must belong to a tool that HAS an allowlist, and
# must itself be admitted — otherwise the declaration is inert (the container key
# is dropped before `_walk` ever looks inside it), which is the silent-no-op
# shape this file keeps finding in itself.
for _t, _containers in TOOL_DATA_KEYED_CONTAINERS.items():
    if _t not in TOOL_EMIT_ALLOWLIST:
        raise AssertionError(
            f"{_t} declares data-keyed containers but has no emit allowlist")
    _missing = sorted(c for c in _containers
                      if c not in (TOOL_EMIT_ALLOWLIST[_t] | _ENVELOPE_KEYS))
    if _missing:
        raise AssertionError(
            f"{_t} declares data-keyed container(s) {_missing} that its own "
            "allowlist does not admit -- the container is dropped before the "
            "declaration is ever consulted, so it would silently do nothing")

for _tool, _allowed in TOOL_EMIT_ALLOWLIST.items():
    _upper = sorted(k for k in _allowed if k != k.lower())
    if _upper:
        raise AssertionError(
            f"emit allowlist for {_tool} has non-lowercase key(s) {_upper}"
            " -- membership is tested lowercased, so these are inert and"
            " would silently drop the fields they were added to admit")
    _bad = _allowed & CARVEOUT_ID_KEYS
    if _bad:
        raise AssertionError(
            f"emit allowlist for {_tool} admits carve-out key(s) {sorted(_bad)}"
            f" -- third-party-licensed identifiers must never be allowlisted")


class EmitAllowlistMissing(KeyError):
    """Raised when a tool asks to emit through the filter but has no
    allowlist -- fail-closed: refusing to serve beats serving bare."""


def filter_to_allowlist(tool: str, obj: Any) -> Any:
    """Recursively keep only allowlisted (or envelope) keys for *tool*.

    Fail-closed on both axes: an unknown TOOL raises (never serves
    unfiltered); an unknown KEY is dropped (never ships). Lists recurse;
    scalars pass through -- values are the tool's business, KEYS are the
    redistribution boundary.
    """
    allowed = TOOL_EMIT_ALLOWLIST.get(tool)
    if allowed is None:
        raise EmitAllowlistMissing(
            f"{tool} has no emit allowlist -- refusing to serve an "
            f"unfiltered payload through the redistribution boundary")
    merged = allowed | _ENVELOPE_KEYS
    data_keyed = TOOL_DATA_KEYED_CONTAINERS.get(tool, frozenset())

    def _walk(o: Any, in_data_keyed: bool = False) -> Any:
        if isinstance(o, dict):
            # Inside a declared data-keyed container the KEYS are values —
            # a ticker, a quarter — so they pass through and their contents
            # are filtered normally one level down.
            if in_data_keyed:
                return {k: _walk(v) for k, v in o.items()
                        if isinstance(k, str)}
            # A dict keyed ENTIRELY by a declared data SHAPE (today: four-
            # digit years) is data by shape, whatever its parent is called.
            # Same semantics as the per-tool hatch -- keys pass, values are
            # filtered normally one level down -- so `{"2017": {"cusip": ..}}`
            # still loses the cusip. The THIRD universal hatch; counted by
            # DATA_KEY_SHAPES, not by a `k.lower() ==` branch. See the table.
            if _keys_are_data_by_shape(o):
                return {k: _walk(v) for k, v in o.items()}
            out = {}
            for k, v in o.items():
                if not isinstance(k, str) or k.lower() not in merged:
                    continue
                # A STRUCTURED error keeps its code/message/retry_after. Still
                # fail-closed -- three declared keys, filtered by name like
                # everything else, and anything deeper is walked normally.
                if k.lower() == "error" and isinstance(v, dict):
                    out[k] = {ek: _walk(ev) for ek, ev in v.items()
                              if isinstance(ek, str)
                              and ek.lower() in _ERROR_DETAIL_KEYS}
                # `params_accepted` is keyed by PARAMETER NAME (CHAOS P2-2).
                # Second instance of the data-keyed-container class, but a
                # UNIVERSAL one rather than a per-tool declaration: its keys are
                # the caller's own arguments for whatever tool this is, so no
                # entry in TOOL_DATA_KEYED_CONTAINERS could ever cover it.
                #
                # Measured before the fix, echoing each tool's OWN declared
                # inputSchema: 3 of 17 filtered tools lost at least one
                # parameter, and `get_13f_holdings` lost BOTH of its --
                # `fund` and `max_holdings`. The other 14 survived by
                # COINCIDENCE: their parameters are called `ticker`, `limit`,
                # `cik`, `quarter`, which happen to be envelope vocabulary. An
                # echo that works where the names happen to collide is not a
                # control. And `max_holdings` is the exact parameter the echo
                # was written for -- the 2026-08-11 defect was an agent sending
                # `max_holdings: 3`, having it ignored, and NOTHING saying so.
                # So the fix for that defect was disabled, on the anonymous
                # channel, for the one tool that motivated it.
                #
                # CARVE-OUTS ARE STILL STRIPPED. `get_bond_data` declares a
                # `cusip` parameter, so a bare passthrough would put a CUSIP
                # back in an anonymous payload -- the single key this whole
                # boundary exists to keep out -- and it would arrive as a
                # side effect of fixing a disclosure bug. That it is the
                # caller's own input does not matter: the COUNSEL C3 condition
                # is about what WE emit.
                elif k.lower() == "params_accepted" and isinstance(v, dict):
                    out[k] = {pk: _walk(pv) for pk, pv in v.items()
                              if isinstance(pk, str)
                              and pk.lower() not in CARVEOUT_ID_KEYS}
                else:
                    out[k] = _walk(v, k.lower() in data_keyed)
            return out
        # TUPLES TOO (CHAOS P3-2). `_walk` handled dict and list; a tuple
        # fell through to `return o` and shipped its contents UNFILTERED --
        # including `cusip`, the one key the import-time validator exists to
        # keep out -- and `json.dumps` renders it as an array, so the leak is
        # indistinguishable from a filtered list on the wire. Unreachable
        # through the wheel today (payloads arrive via `json.loads`, which
        # never produces tuples), but this table is committed to the in-process
        # `/api/mcp/tool` passthrough bridge, where a handler can return one.
        # In a filter whose docstring says "fail-closed on both axes", this was
        # the axis that was not.
        if isinstance(o, (list, tuple)):
            return [_walk(x) for x in o]
        return o

    return _walk(obj)
