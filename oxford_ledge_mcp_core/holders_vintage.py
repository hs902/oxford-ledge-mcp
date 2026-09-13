"""oxford_ledge_mcp_core/holders_vintage.py -- per-row 13F vintage and the
honest as-of disclosure for the pip server's `get_holders` (T7, 2026-09-12).

THE DEFECT. /api/institutional-holders serves a per-fund-LATEST set
(pg_db/queries/institutional_holdings.py: DISTINCT ON fund_cik under a
6-quarter floor) ranked by value_usd struck at each filer's OWN period-end.
Measured 2026-09-12 on AAPL (anonymous REST read, http 200, 100 rows): the
quarters were 2026-Q1 x87 / 2026-Q2 x12 / 2025-Q4 x1; the wheel's [:10] cut
was 2026-Q1 x5 / 2026-Q2 x4 / 2025-Q4 x1. Geode (368.6M sh, 2026-Q1 at an
implied $253.12 = $93.3bn) ranked BELOW FMR (325.3M sh, 2026-Q2 at $289.36 =
$94.1bn) -- fewer dollars on more shares, a pure vintage artefact.
`tool_get_holders` reshaped each row to {holder, shares, value, type},
DROPPING the route's `quarter` and `filing_date`, and then emitted ONE
top-level `asOf` = the route's `as_of_quarter`, which is the MODE quarter of
its full row set -- false for 5 of the 10 rows the wheel labelled with it.
`get_13f_holdings` had already learned this (3.2.0 vet L-1: filingDate /
periodOfReport admitted after "a 45-day-lagged 13F with no as-of anchor");
the lesson was not carried to get_holders.

THE RULE.
  * `row_vintage` copies `quarter` + `filingDate` (the get_13f_holdings key
    style) from a route row -- only what the row carries; a legacy row with
    no date gets no key, never a null one.
  * `holders_disclosure` keeps a single `asOf` ONLY when every returned row
    carries the same quarter -- and it is the ROWS' quarter, because the rows
    are what the payload holds. Otherwise it emits `vintages`, a LIST of
    {quarter, count} rows (a quarter-keyed dict is data-keyed at the emit
    boundary and would need a container declaration) that sums to the
    returned count, plus a `rankingBasis` note. Rows that carry no quarter
    at all (the pre-T7 producer shape) fall back to the route's label, so
    that shape is byte-identical to before. The route's `coverage` block --
    whose `quarter` is the B5a partial-ingest-guarded single-quarter pick,
    the anchor an agent needs when `vintages` says the rows disagree --
    passes through verbatim when present and is never synthesised.

WHY A CORE MODULE. server.py sits one comment block under the 2,000-line
file-size threshold; the disclosure lives here the way `split_basis.py`
holds get_fundamentals' gate, so the handler stays a reshape + two calls.

Deliberately NOT here: the REST ORDER BY (it feeds the web 13F panel and
InstitutionalHoldersResponse) and the superseded-parent fold (queue P1-13f
fix #2 -- Vanguard's five 2026-Q1 subsidiaries reconcile to the stale
2025-Q4 parent at 1.0002; that is a backend detection, not an emit fix).

stdlib only; no I/O; Python 3.9+.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

RANKING_BASIS = ("value_usd as reported at each filer's own period-end; "
                 "not price-normalised")


def row_vintage(row: Mapping[str, Any]) -> Dict[str, str]:
    """The per-row vintage keys the route sent, in get_13f_holdings' style."""
    out: Dict[str, str] = {}
    quarter = row.get("quarter") or row.get("periodOfReport")
    if quarter:
        out["quarter"] = str(quarter)
    filed = row.get("filing_date") or row.get("filingDate")
    if filed:
        out["filingDate"] = str(filed)
    return out


def vintage_histogram(holders: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """{quarter, count} rows over the RETURNED holders, newest quarter first
    ("YYYY-Qn" sorts lexically); rows with no quarter are counted under null
    and listed last, so the counts always sum to len(holders)."""
    counts: Dict[Optional[str], int] = {}
    for h in holders:
        q = h.get("quarter")
        key = str(q) if q else None
        counts[key] = counts.get(key, 0) + 1
    named = sorted((q for q in counts if q is not None), reverse=True)
    rows: List[Dict[str, Any]] = [{"quarter": q, "count": counts[q]} for q in named]
    if None in counts:
        rows.append({"quarter": None, "count": counts[None]})
    return rows


def holders_disclosure(holders: Sequence[Mapping[str, Any]],
                       route_body: Mapping[str, Any]) -> Dict[str, Any]:
    """Top-level keys to merge into the get_holders payload: exactly one of
    `asOf` / (`vintages` + `rankingBasis`) per the module rule, plus the
    route's `coverage` block when it sent one."""
    out: Dict[str, Any] = {}
    present = [h["quarter"] for h in holders if h.get("quarter")]
    if present and len(present) == len(holders) and len(set(present)) == 1:
        out["asOf"] = present[0]
    elif present:
        out["vintages"] = vintage_histogram(holders)
        out["rankingBasis"] = RANKING_BASIS
    elif route_body.get("as_of_quarter"):
        # legacy rows carry no quarter: emit what EXISTS, never invent a date
        out["asOf"] = route_body.get("as_of_quarter")
    coverage = route_body.get("coverage")
    if isinstance(coverage, dict) and coverage:
        out["coverage"] = coverage
    return out
