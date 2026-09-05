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
leakage. Coverage today: the two raw-passthrough tools the denylist
defended. Expanding coverage tool-by-tool is the bridge work's job.
"""
from __future__ import annotations

from typing import Any

# Third-party-licensed identifier/rating keys (2026-07-21 compliance
# review): CUSIP is FactSet / CUSIP Global Services IP; agency ratings
# are the agencies' IP. Used at import time to VALIDATE the allowlists
# below; the pip server also keeps its runtime strip as defense-in-depth.
CARVEOUT_ID_KEYS = frozenset({
    "cusip", "moodysrating", "moodys_rating", "sprating", "sp_rating",
    "fitchrating", "fitch_rating", "creditrating", "credit_rating",
})

# Response-envelope vocabulary shared across tools (lowercase).
_ENVELOPE_KEYS = frozenset({
    "summary", "count", "error", "as_of", "ticker", "cik",
    # Compliance vocabulary (2026-08-24 3.2.0 vet L-2): the fail-closed
    # filter must never silently strip a disclaimer/attribution line a
    # route adds later -- that is the inversion's own failure mode.
    "disclaimer", "attribution", "notice", "license", "period", "quarter",
})

# Per-tool emitted-field allowlists (lowercase). A key absent here and
# absent from _ENVELOPE_KEYS does NOT ship. Seed source is named per
# entry; changing a set is a COUNSEL-reviewable act, not a refactor.
TOOL_EMIT_ALLOWLIST: dict[str, frozenset[str]] = {
    # The corporate-events helper's SELECT aliases. No
    # vendor fields exist in this set; 8-K content is public domain.
    "get_corporate_events": frozenset({
        "events", "id", "eventdate", "eventtype", "headline",
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
        # response envelope (the 13F parser's result dict)
        "fundname", "filingdate", "periodofreport", "totalholdings",
        "totalvalue", "prevfilingdate",
        # quarter-over-quarter changes sub-tree: container, its four
        # buckets, and the entry-only keys (name/shares/value already admitted)
        "changes", "new_positions", "increased", "decreased", "closed",
        "prevshares", "shareschange", "pctchange",
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
    }),
    # 2026-09-05 (same field test): seeded from data/bdc_query.query_by_bdc's
    # response dict + the route's F9 freshness additions. All SEC-EDGAR
    # 10-Q/10-K SOI-derived. DELIBERATELY ABSENT: `byLienPosition` -- its
    # keys are DATA VALUES (lien-name buckets), which the fail-closed
    # key filter would reduce to an empty husk; per-row lienPosition
    # ships instead, so the breakdown is recomputable client-side.
    "get_bdc_holdings": frozenset({
        # envelope
        "bdcticker", "bdcname", "filingdate", "filingtype", "periodend",
        "totalholdings", "totalparamount", "totalfairvalue",
        "weightedavgprice", "topindustries", "portfoliostructure",
        "holdings", "datasource", "fetchedat", "retired", "successorticker",
        # holdings rows (query_by_bdc's clean_holdings projection)
        "borrowername", "industry", "securitytype", "lienposition",
        "interestrate", "maturitydate", "paramount", "costamount",
        "fairvalue", "markedprice",
        # portfolioStructure metrics (S21-F risk framing)
        "floatingratepct", "floatingrateofdebtpct", "legacyliborpct",
        "legacyliborofdebtpct", "seniorsecuredpct",
        "seniorsecuredofdebtpct", "equitypct", "pikcount",
        "pikpctofholdings",
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
        # _as_of block
        "filing_dates", "mixes_filings", "stale_rows", "scope", "note",
        # _completeness block
        "returned", "limit", "total_available", "complete",
        "completeness_basis", "more_available_hint",
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
    }),
    "ol_bdc_common_borrowers": frozenset({
        # envelope
        "bdc_tickers", "min_holders", "completeness", "units",
        "fair_value_basis", "as_of_range", "borrowers",
        # borrower rows
        "borrower", "borrower_norm", "holder_count", "holder_tickers",
        "holders", "name", "total_fair_value", "total_par_amount",
        "as_of_oldest", "as_of_newest",
        # _as_of block
        "filing_dates", "mixes_filings", "stale_rows", "scope", "note",
        # _completeness block
        "returned", "limit", "total_available", "complete",
        "completeness_basis", "more_available_hint",
    }),
}

# Import-time invariant: no allowlist may admit a carve-out key. This is
# the denylist's knowledge promoted to a structural check -- the two
# lists cannot drift apart silently.
for _tool, _allowed in TOOL_EMIT_ALLOWLIST.items():
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

    def _walk(o: Any) -> Any:
        if isinstance(o, dict):
            return {k: _walk(v) for k, v in o.items()
                    if isinstance(k, str) and k.lower() in merged}
        if isinstance(o, list):
            return [_walk(x) for x in o]
        return o

    return _walk(obj)
