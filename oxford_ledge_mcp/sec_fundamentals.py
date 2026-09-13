"""oxford_ledge_mcp/sec_fundamentals.py -- the wheel's get_fundamentals
(SEC EDGAR XBRL companyfacts, standalone -- no Oxford Ledge instance needed).

EXTRACTED VERBATIM from server.py on 2026-09-12 (the 3.4.0 publish-vet fix
wave). server.py sat at 1,999 lines against the file-size-budget gate's
2,000-line threshold (tests/test_file_size_budget.py; the pair pin in
tests/test_mcp_server_tools_manifest_contract.py) with six builders about to
add to it. The gate's own instruction is "fix at the ROOT, never rebaseline",
so this is a cut, not a budget entry -- the same discipline as the 2026-09-08
`server_tools.py` cut and the 2026-09-12 T7 `holders_vintage.py` core cut.

WHAT MOVED: server.py lines 881-1103 at HEAD 1c4e046e -- `tool_get_fundamentals`
(@mcp_tool get_fundamentals, heavy=True) and nothing else. Pure move: the
concept ladder, the duration guard, the NCI eviction, the coverage map and the
#33 split-basis gate are byte-identical to the pre-cut file. Its policy
siblings already lived in core (`fundamentals_policy.py`, `split_basis.py`);
this file is the handler that consumes them.

WHY A SEPARATE MODULE FROM sec_tools.py. get_insider_trades sits between
get_sec_filings and get_fundamentals in server.py, and `@mcp_tool` registers
at definition time, so one SEC module imported at the first block's position
would have moved this tool ahead of get_insider_trades in TOOL_DISPATCH. Two
modules, each imported at its own old position, keep the insertion order
identical for all 29 tools (tests/test_mcp_wheel_tool_family_cut_contract.py).
[As cut, the tool did its own ticker->CIK read against company_tickers.json;
since wave B (below) it imports sec_tools' guard + resolver. sec_tools is
already imported -- and get_sec_filings already registered -- by the time
server.py imports this module, so the dispatch order is unchanged.]

An AST free-name walk over the block (run before the cut) found every unbound
name to be stdlib or `oxford_ledge_mcp_core`; this module imports NOTHING
from server.py, at module top or lazily, so there is no cycle.

RE-EXPORT RULE. server.py re-exports `tool_get_fundamentals`, so
`oxford_ledge_mcp.server.tool_get_fundamentals` keeps resolving for the
subprocess drivers (test_mcp_get_fundamentals_shape_contract,
test_mcp_get_fundamentals_ifrs_refusal_contract). Those drivers set
`pkg_server.urllib.request.urlopen`, which patches the shared urllib module
this file reads too. tools/check_eps_split_basis.py keys this file as the
wheel's split-basis serve path.

stdlib + oxford_ledge_mcp_core only; ships in the wheel
(tools/export_mcp_package.py collects it; the manifest contract pins it).

WAVE B (2026-09-12, the 3.4.0 publish vet, builder B2_sec) -- this file is no
longer a byte-identical move. What changed, each pinned by a contract:
  * the label `TotalDebt` is gone; the series is `LongTermDebt` (us-gaap:
    LongTermDebt with the LongTermDebtNoncurrent fallback), and a top-level
    `concepts` map says which rung served every label/period
    (b01-sec-standalone-4, BLOCK; tests/test_mcp_fundamentals_debt_label_contract.py);
  * ticker guard + CIK resolution are sec_tools' (INVALID_PARAMS before any
    fetch, numeric CIK passthrough, BRK.B) (b01-sec-standalone-5);
  * the split-basis gate is keyed by FULL period end, withholds every
    affected cell at/before the boundary whether or not it was in the
    examined window, and ships withheldValues as {period, value} rows
    (b01-sec-standalone-6; tests/test_eps_split_basis_contract.py wheel legs);
  * `basis.attribution` names the block as Oxford Ledge arithmetic
    (b01-sec-standalone-7); the companyfacts fetch discriminates 404 / 429 /
    timeout / non-object body (b01-sec-standalone-9).
"""

from __future__ import annotations

import datetime as _dt
import json
import urllib.error
import urllib.request

from oxford_ledge_mcp_core import FUNDAMENTAL, ToolError, mcp_tool, normalize_ticker
from oxford_ledge_mcp_core.fundamentals_policy import ANNUAL_FORMS, fundamentals_refusal, taxonomy_blocks
from oxford_ledge_mcp_core.split_basis import (
    apply_basis_gate, basis_gate_report, filed_values_by_year)
# b01-sec-standalone-5: the SAME guard + resolver get_sec_filings uses, so a
# ticker the wheel resolves in one tool cannot be "not found" in the other.
# sec_tools registers get_sec_filings on import, and server.py imports it
# BEFORE this module, so this import is a cached-module read that moves no
# registration (tests/test_mcp_wheel_tool_family_cut_contract.py pins order).
from oxford_ledge_mcp.sec_tools import (
    _SEC_UA, _reject_bad_sec_ticker, _resolve_ticker_to_cik_via_sec,
    _sec_body_mismatch, _sec_rate_limited, _sec_transport_failure)

#: b01-sec-standalone-7: the `basis` block is OUR arithmetic over the filer's
#: refilings, and the wheel carried only the generic top-level attribution
#: sentence with nothing naming which values it covered. Fixed sentence on
#: every basis block, all three outcomes; `attribution` rides the envelope
#: allowlist. Same "ATTRIBUTION: ... (ol-derived)" register the eleven
#: hosted-hybrid descriptions use.
_BASIS_ATTRIBUTION = (
    "ATTRIBUTION: this `basis` block is Oxford Ledge's split-basis check "
    "(ol-derived), computed over the filer's own SEC companyfacts refilings: "
    "the observed jump, nearest split ratio, boundaries, advisory rows and the "
    "decision to withhold are Oxford Ledge arithmetic, not filer-published "
    "values, and must be attributed to Oxford Ledge (oxfordledge.com) when "
    "restated. The withheld values themselves are the filer's as-filed figures.")

#: b01-sec-standalone-4: the per-period concept map beside `data`.
_CONCEPTS_NOTE = (
    "concepts mirrors data: for every label and period, the us-gaap concept "
    "that served the value. A label whose ladder has a fallback rung can "
    "switch concept across periods (LongTermDebt -> LongTermDebtNoncurrent "
    "when the filer tags no LongTermDebt for a year; the Noncurrent rung "
    "EXCLUDES the current portion). Read it before comparing two years of "
    "one label as like-for-like.")

#: The split-affected labels. NetIncome, Revenue and the balance sheet are
#: split-invariant and must never be withheld by the gate.
_SPLIT_AFFECTED = ("EPS", "DilutedShares")

# ── f1-sec-fundamentals-4 (2026-09-13 deep audit, FIX-BEFORE-PUBLISH): the
# equity rung for a filer that publishes NCI concept NAMES. The G1 eviction
# narrowed the ladder to the parent rung whenever ANY non-controlling-interest
# concept existed -- and for JNJ that dropped the WHOLE label: JNJ tags its
# 10-K equity ONLY under ...IncludingPortionAttributableToNoncontrollingInterest
# (68 FY facts; the parent rung's 20 facts are all 10-Q), and carries
# MinorityInterest (0 at 2023-01-01, 1.26B for two Kenvue quarters), so an
# $81.5B-equity mega-cap served no StockholdersEquity, no coverage row and no
# note. The eviction was a false positive: at every FY end where both rungs
# have a fact they are EQUAL (NCI is zero there). AGL is the second specimen:
# its FY2025 equity sits on the Including rung only (MinorityInterest 0 at
# 2024-12-31, no NCI instant at 2025-12-31), so the newest served row was
# FY2024 beside FY2025 total assets.
#
# The rule now: the ladder still narrows to the parent rung (G1 stands), and
# then the Including rung is ADMITTED per period end P where the parent rung
# has no annual fact, iff the NCI at P is demonstrably immaterial -- no
# non-zero NCI INSTANT (`_NCI_INSTANT_CONCEPTS`) is tagged at P, or a
# same-instant parent StockholdersEquity fact of ANY form equals the
# Including value. A period whose NCI instant is non-zero and whose parent is
# absent is REFUSED, and the refusal is on the wire: {period, value: null,
# withheld: "nci_consolidated"} plus `equityNote` naming the NCI amount --
# never a silent blank. `concepts` names the Including rung wherever it
# served, so a mixed series is visible cell by cell.
_EQUITY_LABEL = "StockholdersEquity"
_EQUITY_PARENT = "StockholdersEquity"
_EQUITY_INCLUDING = "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"
#: Balance-sheet INSTANT concepts that carry the NCI amount itself.
_NCI_INSTANT_CONCEPTS = (
    "MinorityInterest",
    "RedeemableNoncontrollingInterestEquityCarryingAmount",
    "RedeemableNoncontrollingInterestEquityCommonCarryingAmount",
    "RedeemableNoncontrollingInterestEquityPreferredCarryingAmount",
    "RedeemableNoncontrollingInterestEquityOtherCarryingAmount",
)
_EQUITY_NOTE = (
    "StockholdersEquity for this filer: the parent-only rung "
    "(us-gaap:StockholdersEquity) is preferred; where the filer tags no "
    "annual parent figure for a period, the consolidated rung "
    "(...IncludingPortionAttributableToNoncontrollingInterest) is served "
    "ONLY when its non-controlling interest is demonstrably zero at that "
    "period end (no non-zero NCI instant tagged, or a same-instant parent "
    "figure equal to it) -- `concepts` names the rung per period. A period "
    "with a non-zero NCI instant and no parent figure is withheld as "
    "{value: null, withheld: 'nci_consolidated'} rather than served under a "
    "parent-attributable label; the NCI amounts are in `equityWithheldNci`.")

# ── f1-sec-fundamentals-5 (same audit, FIX-BEFORE-PUBLISH): a basis break
# ACROSS A TAGGING HOLE. Danaos' 1-for-14 reverse split (2019) sits inside a
# 2012-2016 hole in its weighted-share / EPS tagging, so the 10-newest window
# paired FY2011 = 109,045,468 (as-filed, pre-split) beside FY2017 = 7,844,595
# (restated post-split) with `basisConsistent: true`: the gate examines
# CONSECUTIVE examined pairs (EPS-and-NetIncome window, 2017-2025) and no pair
# spans the hole, so nothing was withheld and the payload read as a 93%
# share-count collapse under a green flag. The gate itself is a port pinned
# call-for-call to the in-tree twin (tests/test_eps_split_basis_contract.py),
# so this is a WHEEL-SIDE step AFTER it: over the served cells of each
# split-affected label, a consecutive served pair more than one fiscal year
# apart (the hole) whose values differ by >= _GAP_RATIO_FLOOR either way is a
# basis break the gate could not examine; the older side, and everything
# older, is withheld as {value: null, withheld: "basis_unverified"} with the
# values in withheldValues and `basis.gapNote` naming the hole. Never a
# rescale: the pre-hole cell is the filer's figure and the factor is not
# recoverable across untagged years.
_GAP_RATIO_FLOOR = 5.0
#: Consecutive fiscal-year ends are <= ~371 days apart (52/53-week filers);
#: a larger step means at least one fiscal year is untagged in between.
_CONTIGUOUS_MAX_DAYS = 400


def _days_between(a, b):
    try:
        return abs((_dt.date.fromisoformat(a) - _dt.date.fromisoformat(b)).days)
    except (ValueError, TypeError):
        return None


def _annual_rows(us_gaap, concepts, unit_key, duration):
    """{period end: latest-filed annual fact} + {period end: concept} over a
    ladder, earlier-listed concept winning a tie -- the per-label extraction
    the handler's main loop applies to every label."""
    by_end, concept_by_end = {}, {}
    for concept in reversed(concepts):
        if concept not in us_gaap:
            continue
        entries = (us_gaap[concept].get("units") or {}).get(unit_key, [])
        annual = [e for e in entries
                  if e.get("form") in ANNUAL_FORMS and e.get("fp") == "FY"
                  and (not duration or 330 <= _span_days(e) <= 400)]
        per_concept = {}
        for e in annual:
            k = e.get("end", "")
            prev = per_concept.get(k)
            if prev is None or e.get("filed", "") > prev.get("filed", ""):
                per_concept[k] = e
        by_end.update(per_concept)
        for k in per_concept:
            concept_by_end[k] = concept
    return by_end, concept_by_end


def _span_days(e):
    try:
        s = _dt.date.fromisoformat(e.get("start", ""))
        t = _dt.date.fromisoformat(e.get("end", ""))
        return (t - s).days
    except ValueError:
        return -1


def _nci_instants(us_gaap):
    """{period end: max |NCI| tagged at that instant} over the NCI instant
    concepts, every form -- an instant fact has no `start`."""
    out = {}
    for concept in _NCI_INSTANT_CONCEPTS:
        block = us_gaap.get(concept)
        if not isinstance(block, dict):
            continue
        for e in (block.get("units") or {}).get("USD", []):
            if e.get("start"):
                continue
            v = e.get("val")
            if not isinstance(v, (int, float)):
                continue
            k = e.get("end", "")
            out[k] = max(out.get(k, 0), abs(v))
    return out


def _parent_equity_any_form(us_gaap):
    """{period end: set of parent StockholdersEquity values, any form}."""
    out = {}
    block = us_gaap.get(_EQUITY_PARENT)
    if isinstance(block, dict):
        for e in (block.get("units") or {}).get("USD", []):
            if isinstance(e.get("val"), (int, float)):
                out.setdefault(e.get("end", ""), set()).add(e.get("val"))
    return out


def _admit_including_rung(us_gaap, parent_by_end):
    """(admitted {end: fact}, refused {end: {value, nci}}) over the Including
    rung's annual facts at period ends the parent rung does not serve."""
    incl_by_end, _ = _annual_rows(us_gaap, [_EQUITY_INCLUDING], "USD", False)
    nci = _nci_instants(us_gaap)
    parent_any = _parent_equity_any_form(us_gaap)
    admitted, refused = {}, {}
    for end, fact in incl_by_end.items():
        if end in parent_by_end:
            continue
        val = fact.get("val")
        nci_here = nci.get(end, 0)
        same_instant_parent_equal = val in parent_any.get(end, set())
        if nci_here == 0 or same_instant_parent_equal:
            admitted[end] = fact
        else:
            refused[end] = {"value": val, "nci": nci_here}
    return admitted, refused


def _gap_breaks(rows):
    """The newest basis break across a tagging hole in a newest-first
    [{period, value}] series: (older_period, newer_period, ratio) or None.
    Consecutive SERVED cells only (a withheld/null cell ends the walk on
    that side); a hole is a step > _CONTIGUOUS_MAX_DAYS; a break is a ratio
    >= _GAP_RATIO_FLOOR either way between two same-sign non-zero values."""
    prev = None
    for row in rows:
        v = row.get("value")
        if not isinstance(v, (int, float)) or isinstance(v, bool) or v == 0:
            prev = None
            continue
        if prev is not None:
            days = _days_between(prev["period"], row["period"])
            if days is not None and days > _CONTIGUOUS_MAX_DAYS:
                a, b = abs(prev["value"]), abs(v)
                ratio = max(a, b) / min(a, b)
                if ratio >= _GAP_RATIO_FLOOR and (prev["value"] > 0) == (v > 0):
                    return row["period"], prev["period"], round(ratio, 4)
        prev = row
    return None


def _series_contiguous(rows):
    """True when every consecutive served period is one fiscal year apart."""
    ends = [r.get("period") for r in rows if r.get("period")]
    for a, b in zip(ends, ends[1:]):
        d = _days_between(a, b)
        if d is not None and d > _CONTIGUOUS_MAX_DAYS:
            return False
    return True


@mcp_tool(name="get_fundamentals", cache=FUNDAMENTAL, heavy=True)
def tool_get_fundamentals(args):
    """Get XBRL fundamentals from SEC EDGAR directly."""
    # Step 1: guard, then resolve ticker -> CIK, BEFORE any fetch. INVALID_
    # PARAMS on an empty / metachar ticker; an all-digit value IS the CIK;
    # BRK.B resolves through the dash-form fallback (it was refused with a
    # false "Could not find CIK" while get_sec_filings resolved it).
    ticker = _reject_bad_sec_ticker(normalize_ticker(args.get("ticker")))
    cik = ticker if ticker.isdigit() else _resolve_ticker_to_cik_via_sec(ticker)
    if not cik:
        raise ToolError(
            ToolError.DATA_UNAVAILABLE,
            f"No SEC filer matches ticker '{ticker}' -- check the ticker "
            f"symbol, or pass the numeric CIK instead (e.g. 0000320193).")
    cik = cik.zfill(10)

    # Step 2: company facts from XBRL, with the same discrimination
    # get_sec_filings has: 404 = SEC has no XBRL for this filer (named, with
    # the ticker it was resolved from), 429 = RATE_LIMITED with retry_after,
    # timeout = TIMEOUT, other HTTP = availability, and an HTTP-success body
    # that is not an object = the client/server contract mismatch sentence.
    # Before wave B every one of these was 'EDGAR XBRL lookup failed for X:
    # <exc>' (b01-sec-standalone-9). Inline, not a helper: the urlopen
    # ratchet (tools/check_no_new_urlopen.py) keys its unpaced-SEC set by
    # function, and this handler is the baselined one.
    api = "XBRL companyfacts API"
    facts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    req = urllib.request.Request(facts_url, headers={"User-Agent": _SEC_UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            via = (f" (resolved from ticker '{ticker}')" if not ticker.isdigit() else "")
            raise ToolError(
                ToolError.DATA_UNAVAILABLE,
                f"SEC has no XBRL companyfacts for CIK {int(cik)}{via} -- the "
                f"filer may exist in EDGAR's index without machine-readable "
                f"financial statements (funds, trusts, pre-2009 filers). "
                f"get_sec_filings still lists its documents.")
        if e.code == 429:
            raise _sec_rate_limited(api, cik, e)
        raise ToolError(
            ToolError.DATA_UNAVAILABLE,
            f"SEC EDGAR's {api} returned HTTP {e.code} for CIK {int(cik)} -- an "
            f"upstream availability problem, not a ticker problem; retry later.")
    except Exception as e:
        raise _sec_transport_failure(api, cik, e)
    try:
        facts = json.loads(raw.decode("utf-8"))
    except ValueError as e:
        raise _sec_body_mismatch(api, cik, e)
    if not isinstance(facts, dict):
        # An array / string / null body is not "no taxonomy"; the taxonomy
        # refusal asserts a fact about the FILER and must not fire here.
        raise _sec_body_mismatch(api, cik, TypeError(f"JSON {type(facts).__name__} body"))
    try:
        # 2026-09-07 taxonomy-aware (DAC field report). The policy -- which
        # annual forms are admitted, what an IFRS/no-taxonomy filer is told,
        # and why the ifrs-full ladder is NOT here -- lives in
        # oxford_ledge_mcp_core.fundamentals_policy; read it before editing.
        facts_block, us_gaap = taxonomy_blocks(facts)
        if not us_gaap:
            raise fundamentals_refusal(
                ticker, cik, "ifrs-full" if "ifrs-full" in facts_block else None)

        # Extract key line items
        line_items = {
            "Revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
                        # investment companies (BDCs) tag revenue as gross
                        # investment income. 3.2.0 vet K-6 execution removed
                        # the sibling rung InvestmentIncomeOperating here:
                        # SEC frames CY2015+CY2023 report ZERO filers for it
                        # and both flagship BDC companyconcepts 404 -- a
                        # never-matching rung (the OCF defect class), while
                        # this one shows 182 filers in CY2023.
                        "GrossInvestmentIncomeOperating"],
            "NetIncome": ["NetIncomeLoss"],
            "EPS": ["EarningsPerShareDiluted", "EarningsPerShareBasic"],
            # 2026-09-08 (#33): the EPS DENOMINATOR. Its absence was not a
            # cosmetic gap -- EPS was the only split-affected series in the
            # payload and nothing beside it moved when the basis changed, so
            # a consumer had no way to see a 4:1 or 10:1 step for what it
            # was. Coverage measured over a 244-ticker live sample: 240
            # filers tag it (98.4%), exactly the same 240 that tag
            # EarningsPerShareDiluted, always in the `shares` unit.
            "DilutedShares": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
            "TotalAssets": ["Assets"],
            "TotalLiabilities": ["Liabilities"],
            "StockholdersEquity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
            # 2026-08-24 MCP audit: the old sole rung named a NON-EXISTENT
            # us-gaap concept (SEC companyconcept 404-verified) -- the same
            # never-matching-rung class as the in-tree sharesOut fix. The
            # real concept, plus the continuing-operations variant some
            # filers use.
            "OperatingCashFlow": ["NetCashProvidedByUsedInOperatingActivities",
                                  "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
            # 2026-09-12 (3.4.0 vet b01-sec-standalone-4, BLOCK): this label
            # was `TotalDebt`. It is us-gaap:LongTermDebt -- current +
            # noncurrent TERM debt, no commercial paper, no short-term
            # borrowings -- with an unlabeled fallback to the NONCURRENT
            # portion alone. Measured on AAPL: FY2025 served 90,678M under
            # "total debt" against 98,657M of borrowings (CP 7,979M
            # excluded); FY2021 served 109,106M = noncurrent only (current
            # 9,613M + CP 6,000M excluded, -12.5%); and the 2021->2022 step
            # read +0.9% while like-for-like noncurrent fell 9.3%, because
            # the series switched concept at that boundary with nothing on
            # the wire. The label now says what the series IS; the key
            # `TotalDebt` is REMOVED, not aliased, so a consumer sees the
            # change; `concepts` names the rung per period. A real total
            # (current + noncurrent + CP + short-term borrowings) is a
            # separate feature -- summing rungs risks double counting
            # across DebtCurrent / LongTermDebtCurrent / CommercialPaper.
            "LongTermDebt": ["LongTermDebt", "LongTermDebtNoncurrent"],
        }

        # Flow (duration) concepts: a 10-K's companyfacts entries ALSO carry
        # quarterly duration facts tagged form=10-K/fp=FY, so form+fp alone
        # mixes Q rows into the annual series (2026-08-10 field test).
        # DilutedShares is a duration fact too -- it is a WEIGHTED AVERAGE
        # over the year, not an instant count, so it needs the same 330-400d
        # guard that keeps a 10-K's quarterly rows out of the annual series.
        duration_labels = {"Revenue", "NetIncome", "EPS", "OperatingCashFlow",
                           "DilutedShares"}

        # G1 (2026-09-04, in-tree F4 doctrine in miniature): the
        # Including... equity rung is parent + NCI. For a filer that
        # tags ANY non-controlling-interest concept, letting it fill
        # parent-missing years seats a CONSOLIDATED figure under a
        # parent-attributable label (the +281% class the in-tree
        # extractor evicted). Name-matched, with the two families the
        # in-tree predicate excludes (consolidated totals themselves +
        # the two pretax ordering-only lines). A no-NCI filer (the
        # AAON class) keeps the rung -- for them it is arithmetically
        # the parent figure. False positive costs an honest blank;
        # false negative is the defect. When in doubt, match.
        _NCI_EXCL = (
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxes"
            "ExtraordinaryItemsNoncontrollingInterest",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxes"
            "MinorityInterestAndIncomeLossFromEquityMethodInvestments",
        )
        _has_nci = any(
            ("Noncontrolling" in c or "MinorityInterest" in c)
            and c not in _NCI_EXCL and "IncludingPortion" not in c
            for c in us_gaap)
        if _has_nci:
            line_items["StockholdersEquity"] = ["StockholdersEquity"]
            # f1-sec-fundamentals-4: the per-period admission of the
            # Including rung runs AFTER the main loop (below), against the
            # parent rows that loop served -- the ladder rewrite stands.

        result = {"ticker": ticker, "data": {}}
        # b01-sec-standalone-4: which rung served each cell, per label and
        # period, index-aligned with data[label]. A list of rows rather
        # than a {period: concept} dict because the emit filter admits
        # keys by NAME and a period end is data, not a name (the T2 shape
        # hatch is deliberately scoped to four-digit years); the row shape
        # is the one data[label] already uses.
        concepts_served = {}
        # Period-keyed raws for the split-basis gate below -- FULL period
        # end, never period[:4] (b01-sec-standalone-6: a Jan-1-3 FYE and
        # the following Dec-31 FYE share a calendar label and collided).
        by_period_raw = {}
        equity_refused = {}
        for label, concepts in line_items.items():
            # Filers SWITCH concepts over a decade (AAPL: Revenues ->
            # RevenueFromContractWithCustomer... at FY2019), so first-hit
            # concept selection truncates history. Merge all listed
            # concepts per period end; earlier-listed concept wins a tie.
            # Each fiscal year re-appears as a comparative in later 10-Ks;
            # `_annual_rows` keeps ONE row per period end -- the latest-filed
            # within a concept (restatements win), then lets the higher-
            # priority concept override cross-concept. (Try USD first, then
            # USD/shares for EPS.)
            unit_key = ("USD/shares" if label == "EPS"
                        else "shares" if label == "DilutedShares"
                        else "USD")
            by_end, concept_by_end = _annual_rows(
                us_gaap, concepts, unit_key, label in duration_labels)
            if label == _EQUITY_LABEL and _has_nci:
                # f1-sec-fundamentals-4: admit the Including rung per period
                # the parent rung does not serve, when NCI is demonstrably
                # zero there; refuse -- on the wire -- when it is not.
                admitted, equity_refused = _admit_including_rung(us_gaap, by_end)
                for end, fact in admitted.items():
                    by_end[end] = fact
                    concept_by_end[end] = _EQUITY_INCLUDING
                for end in equity_refused:
                    by_end[end] = {"end": end, "val": None, "_refused": True}
                    concept_by_end[end] = _EQUITY_INCLUDING
            if not by_end:
                continue
            newest_first = sorted(by_end.values(),
                                  key=lambda x: x.get("end", ""),
                                  reverse=True)[:10]
            result["data"][label] = [
                ({"period": e.get("end", ""), "value": None,
                  "withheld": "nci_consolidated"} if e.get("_refused")
                 else {"period": e.get("end", ""), "value": e.get("val")})
                for e in newest_first
            ]
            concepts_served[label] = [
                {"period": e.get("end", ""),
                 "concept": "us-gaap:" + concept_by_end[e.get("end", "")]}
                for e in newest_first
            ]
            by_period_raw[label] = {
                e.get("end", ""): e.get("val") for e in newest_first
                if not e.get("_refused")}
            # Keep the refused set to what the window actually shows.
            if label == _EQUITY_LABEL:
                shown = {e.get("end", "") for e in newest_first}
                equity_refused = {k: v for k, v in equity_refused.items()
                                  if k in shown}
        if not result["data"]:  # backstop: never {"data": {}} at full confidence
            raise fundamentals_refusal(
                ticker, cik, "ifrs-full" if "ifrs-full" in facts_block else "us-gaap",
                observed=_observed_facts(us_gaap))
        result["concepts"] = concepts_served
        result["conceptsNote"] = _CONCEPTS_NOTE
        if _has_nci and any(
                c.get("concept", "").endswith(_EQUITY_INCLUDING)
                for c in concepts_served.get(_EQUITY_LABEL, [])):
            # The Including rung served (or was refused for) at least one
            # period of an NCI filer: say which rule decided it.
            result["equityNote"] = _EQUITY_NOTE
            if equity_refused:
                result["equityWithheldNci"] = [
                    {"period": p, "value": v["value"], "nci": v["nci"]}
                    for p, v in sorted(equity_refused.items(), reverse=True)]
        # 2026-09-05 field-report-#2 F7-fundamentals: series depth is per-
        # concept fact availability in companyfacts (capped at 10y), so one
        # label can carry 6 annual points beside a sibling's 10 with nothing
        # disclosing the ragged depth. Coverage discloses it; the DATA is
        # unchanged. `contiguous` (f1-sec-fundamentals-5): false when the
        # served periods skip at least one fiscal year -- the old note said
        # "not missing rows", which was false for DAC's 2011 + 2017-2025.
        result["coverage"] = {
            label: {"yearsAvailable": len(series),
                    "contiguous": _series_contiguous(series)}
            for label, series in result["data"].items()
        }
        result["coverageNote"] = (
            "yearsAvailable per label = annual facts SEC companyfacts carries "
            "for that concept, capped at 10. Labels can differ; a shorter "
            "series means the filer's XBRL history is shorter for that "
            "concept. contiguous=false means the served periods are NOT "
            "consecutive fiscal years (the filer's companyfacts has a "
            "tagging hole for that concept) -- read the period of every "
            "row before treating neighbours as year-over-year.")

        # ── #33 split-basis gate ────────────────────────────────────────
        # The per-period dedup above ("keep ONE row per period end -- the
        # latest-filed within a concept") is right for a period and wrong
        # for a SERIES: a split-year 10-K restates only the comparative
        # years it displays, so this array can straddle two or three share
        # bases with every cell as-filed and individually plausible. The
        # gate re-reads the UN-deduped facts to find the issuer's own
        # restatement and withholds the cells older than the newest
        # boundary. Policy + evidence rules live in
        # oxford_ledge_mcp_core.split_basis; read it before editing.
        #
        # KEYED BY FULL PERIOD END (b01-sec-standalone-6). Consecutive
        # period ends are the year pairs; a 52/53-week filer whose FY ends
        # Jan 1-3 no longer collides two fiscal years into one key.
        eps_by_period = by_period_raw.get("EPS") or {}
        ni_by_period = by_period_raw.get("NetIncome") or {}
        window = sorted(set(eps_by_period) & set(ni_by_period))
        eps_concept = next((c for c in ("EarningsPerShareDiluted",
                                        "EarningsPerShareBasic")
                            if c in us_gaap), None)
        basis_report = basis_gate_report(
            eps_by_period, ni_by_period,
            filed_values_by_year(us_gaap.get(eps_concept), "USD/shares"),
            filed_values_by_year(us_gaap.get("NetIncomeLoss"), "USD"),
            window)
        # The payload's series are newest-first lists of {period, value};
        # rebuild them as period-aligned arrays over EVERY period an
        # affected label serves -- not just the EPS-and-NetIncome window the
        # report examined -- so a pre-boundary cell outside the window (NOW
        # FY2013: EPS filed, no NetIncomeLoss fact) is withheld too instead
        # of being served on the pre-split basis beside the note that says
        # it was withheld.
        gated_periods = sorted(
            {p for lbl in _SPLIT_AFFECTED for p in (by_period_raw.get(lbl) or {})},
            reverse=True)
        gated = {lbl: [(by_period_raw.get(lbl) or {}).get(p) for p in gated_periods]
                 for lbl in _SPLIT_AFFECTED}
        disclosure = apply_basis_gate(
            gated_periods, gated, basis_report, _SPLIT_AFFECTED)
        if disclosure.get("basisConsistent") is False:
            # Write the nulled cells back by PERIOD, from the disclosure's
            # own withheld map -- so withheldValues covers every nulled cell
            # by construction, and a cell the label never had (an absent
            # DilutedShares year) is not tagged as withheld.
            withheld = disclosure.get("withheldValues") or {}
            for label, per_period in withheld.items():
                for row in result["data"].get(label) or []:
                    if row.get("period") in per_period:
                        row["value"] = None
                        row["withheld"] = "split_basis"
            # The withheld cells travel as rows ({period, value}, newest
            # first), the shape data[label] uses. A {period: value} dict
            # would be emptied at the emit boundary: the filter admits
            # keys by name, the T2 year-shape hatch matches four-digit
            # years only, and a full period end is neither.
            disclosure["withheldValues"] = {
                label: [{"period": p, "value": v} for p, v in per_period.items()]
                for label, per_period in withheld.items()}
        # f1-sec-fundamentals-5: a basis break ACROSS A TAGGING HOLE, which
        # the gate above cannot examine (no consecutive pair spans it). Runs
        # over the cells the gate left served, per affected label; withholds
        # the older side of the hole and everything older.
        gap_hits = {}
        for label in _SPLIT_AFFECTED:
            rows = result["data"].get(label) or []
            hit = _gap_breaks(rows)
            if not hit:
                continue
            older, newer, ratio = hit
            withheld_rows = []
            for row in rows:
                if row.get("period", "") <= older and row.get("value") is not None:
                    withheld_rows.append({"period": row["period"], "value": row["value"]})
                    row["value"] = None
                    row["withheld"] = "basis_unverified"
            gap_hits[label] = {"olderPeriod": older, "newerPeriod": newer,
                               "observedJump": ratio,
                               "withheldThrough": older}
            wv = disclosure.setdefault("withheldValues", {})
            wv[label] = (wv.get(label) or []) + withheld_rows
        if gap_hits:
            disclosure["basisConsistent"] = False
            disclosure["basisChecked"] = True
            disclosure["gapBreaks"] = gap_hits
            disclosure["gapNote"] = (
                "A split-affected series steps by >= {floor:g}x across a hole "
                "in the filer's XBRL tagging ({gaps}): the fiscal years "
                "between are untagged in SEC companyfacts, so no examined "
                "year pair spans the step and the split-basis check could "
                "not verify it. The older side of each hole, and every "
                "older cell, is withheld as {{value: null, withheld: "
                "'basis_unverified'}} -- the values are in withheldValues, "
                "as filed, not rescaled. A reverse split inside the hole "
                "(Danaos, 1-for-14 in 2019, hole 2012-2016) is the "
                "measured case."
            ).format(floor=_GAP_RATIO_FLOOR, gaps="; ".join(
                f"{lbl}: {h['olderPeriod']} -> {h['newerPeriod']}, "
                f"{h['observedJump']:g}x" for lbl, h in gap_hits.items()))
        disclosure["attribution"] = _BASIS_ATTRIBUTION
        result["basis"] = disclosure
        return result
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(ToolError.DATA_UNAVAILABLE, f"EDGAR XBRL lookup failed for '{ticker}': {e}")


def _observed_facts(us_gaap):
    """What the filer's us-gaap block DOES carry, for the refusal sentence
    (f1-sec-fundamentals-10): the forms its fp=FY facts are furnished on and
    the currency units seen. Canadian National (CNI) carries every fact on
    Form 6-K in CAD -- a US-GAAP 40-F filer this tool cannot serve, and the
    old refusal blamed the ladder and hinted at IFRS."""
    forms, units = set(), set()
    for block in us_gaap.values():
        if not isinstance(block, dict):
            continue
        for unit, entries in (block.get("units") or {}).items():
            for e in entries:
                if e.get("fp") == "FY" and e.get("form"):
                    forms.add(str(e["form"]))
                    units.add(str(unit))
    return {"annualFormsSeen": sorted(forms), "unitsSeen": sorted(units)}
