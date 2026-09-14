"""oxford_ledge_mcp_core/split_basis.py -- the split-basis serve gate for the
pip server's `get_fundamentals`.

WHY A SECOND COPY IS ALLOWED HERE. This is a deliberate port of the in-tree
`data/eps_basis_gate.py` (which itself leans on `data/xbrl_restatement.py` for
`nearest_common_ratio`). `mcp_package` is published to PyPI and must not
import in-tree Oxford Ledge code -- `oxford_ledge_mcp_core/__init__.py`'s
standalone-installable invariant -- so a shared import is not available and
the duplication is the sanctioned trade, the same one
`oxford_ledge_mcp_core/ticker.py` and `registry.TIER_RANK` make. Parity with
the in-tree twin is enforced by
`tests/test_eps_split_basis_contract.py::test_core_port_matches_in_tree_twin`,
which runs BOTH implementations over the same committed fixtures and compares
verdicts rather than source text.

Read `data/eps_basis_gate.py` for the full derivation of every constant and
the corpus measurement behind it; that module is the reference and this file
deliberately mirrors its structure so a diff between them stays legible.

THE DEFECT, in one line: `get_fundamentals` takes the latest-filed value for
each period INDEPENDENTLY, which is right per period and wrong for a series,
because a split-year 10-K restates only the comparative years it displays --
so the array straddles two or three share bases with every cell as-filed.
Measured 2026-09-08: NVDA serves 2022 3.85 beside 2023 0.17 (10:1), and
ServiceNow serves 2022 1.60 beside 2023 1.68, which reads as a +5% year when
the honest comparison is +425%.

A FISCAL YEAR IS ITS PERIOD END, NOT ITS CALENDAR LABEL (2026-09-12, 3.4.0
publish vet b01-sec-standalone-6). `filed_values_by_year` keyed the issuer's
refilings by `end[:4]`, and the wheel handler keyed its series the same way.
A 52/53-week filer whose fiscal year ends Jan 1-3 then puts TWO fiscal years
under one key: JNJ's FY2022 (ended 2023-01-01) and FY2023 (ended 2023-12-31)
both read as "2023", so `filed_values_by_year["2023"]` came back
`[6.73, 6.73, 6.73, 13.72, 13.72, 13.72]` -- two different years read as one
year's refiling -- and the gate examined 7 pairs for a 10-row series. Driven
on ServiceNow's real 5:1 with FY2022 re-dated to end 2023-01-01, the first
post-split year was nulled AND absent from `withheldValues` while the note
said the values were there. The keys the gate reasons over are therefore the
FULL period-end string (`2023-01-01`), which identifies exactly one fiscal
period; every comparison here is lexicographic and ISO dates order the same
way four-digit years do, so nothing else in the arithmetic changes. The
in-tree twin was ported the same day (both key by the full period end);
the parity contract compares the two call-for-call.

stdlib only; no I/O; Python 3.9+.
"""

from __future__ import annotations

from datetime import date as _date
from typing import Any, Dict, List, Optional, Sequence, Tuple

ANNUAL_FORMS: Tuple[str, ...] = ("10-K", "20-F", "40-F")

#: Mirrors data/xbrl_restatement.COMMON_SPLIT_RATIOS. Reported, never
#: required -- see `nearest_common_ratio`'s caller in `restatement_evidence`.
COMMON_SPLIT_RATIOS: Tuple[float, ...] = (
    1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0, 15.0, 20.0, 30.0)
NAME_TOLERANCE = 0.08

SPLIT_FLOOR = 1.4
MATCH_TOLERANCE = 1.7
MIN_ABS_EPS = 0.05
QUANTIZATION_STEP = 0.005
MAX_PAIR_QUANTIZATION_ERROR = 0.05
MIN_ABS_AGGREGATE = 1e6

_MIN_ANNUAL_DAYS = 300
_MAX_ANNUAL_DAYS = 400


def nearest_common_ratio(factor: float) -> Tuple[Optional[float], float]:
    """(ratio, relative_distance) for the closest COMMON_SPLIT_RATIOS entry,
    or (None, distance) when nothing is within NAME_TOLERANCE."""
    if not factor or factor <= 0:
        return None, float("inf")
    probe = factor if factor >= 1 else 1.0 / factor
    best: Optional[float] = None
    best_d = float("inf")
    for r in COMMON_SPLIT_RATIOS:
        d = abs(probe - r) / r
        if d < best_d:
            best, best_d = r, d
    return (best if best_d <= NAME_TOLERANCE else None), best_d


def _span_days(start: str, end: str) -> Optional[int]:
    try:
        return (_date.fromisoformat(end) - _date.fromisoformat(start)).days
    except (ValueError, TypeError):
        return None


def filed_values_by_year(concept_block: Any, unit: str) -> Dict[str, List[float]]:
    """{fiscal year: [every filed value for that year, OLDEST FILING FIRST]},
    where a fiscal year is identified by its FULL period-end string
    (`2023-01-01`), never by `end[:4]`.

    The values under one key are the issuer's own refilings of ONE fiscal
    period -- that is what `restatement_evidence` measures a split from. Two
    different fiscal years that happen to share a calendar label (a Jan-1-3
    FYE beside the following Dec-31 FYE) are not refilings of each other, and
    bucketing them together read as a 2x "restatement" of a year that was
    never restated. The name is kept: the key IS the fiscal year, and the
    wiring checker (tools/check_eps_split_basis.py) pins this call by name."""
    if not isinstance(concept_block, dict):
        return {}
    per_end: Dict[str, List[Tuple[str, float]]] = {}
    units = concept_block.get("units") or {}
    for e in units.get(unit) or []:
        if e.get("form") not in ANNUAL_FORMS:
            continue
        end = e.get("end") or ""
        if len(end) < 4:
            continue
        start = e.get("start")
        if start:
            span = _span_days(start, end)
            if span is not None and not (_MIN_ANNUAL_DAYS <= span <= _MAX_ANNUAL_DAYS):
                continue
        val = e.get("val")
        if not isinstance(val, (int, float)) or val == 0:
            continue
        per_end.setdefault(end, []).append((str(e.get("filed") or ""), float(val)))
    return {end: [v for _f, v in sorted(pairs)] for end, pairs in per_end.items()}


def _factor(vals: Sequence[float]) -> Optional[float]:
    clean = [v for v in vals if v]
    if not clean:
        return None
    if len(set(clean)) < 2:
        return 1.0
    if not clean[-1]:
        return None
    return abs(clean[0] / clean[-1])


def net_restatement_factor(per_share_vals: Sequence[float],
                           agg_vals: Sequence[float]) -> Optional[float]:
    """How far the PER-SHARE figure moved RELATIVE to the aggregate across the
    issuer's own refiling of the same period. A split moves only the
    per-share leg, so the ratio IS the split factor; an accounting
    restatement moves both and the ratio collapses to ~1."""
    ps = _factor(per_share_vals)
    ag = _factor(agg_vals)
    if ps is None or ag is None or not ag:
        return None
    return ps / ag


def restatement_evidence(per_share_filed: Dict[str, List[float]],
                         aggregate_filed: Dict[str, List[float]],
                         window: Sequence[str]) -> Dict[str, Dict[str, Any]]:
    found: Dict[str, Dict[str, Any]] = {}
    for year in window:
        vals = per_share_filed.get(year) or []
        if len(set(vals)) < 2 or not vals[-1]:
            continue
        factor = net_restatement_factor(vals, aggregate_filed.get(year) or [])
        if factor is None:
            continue
        if not (factor >= SPLIT_FLOOR or factor <= 1.0 / SPLIT_FLOOR):
            continue
        name, dist = nearest_common_ratio(factor)
        found[year] = {"factor": round(factor, 4), "nearest_ratio": name,
                       "distance_from_nearest": round(dist, 4)}
    return found


def implied_shares(per_share: Dict[str, Any], aggregate: Dict[str, Any],
                   window: Sequence[str],
                   require_positive: bool = False) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for y in window:
        ps = per_share.get(y)
        ag = aggregate.get(y)
        if not isinstance(ps, (int, float)) or not isinstance(ag, (int, float)):
            continue
        if require_positive and (ps <= 0 or ag <= 0):
            continue
        if abs(ps) < MIN_ABS_EPS or abs(ag) < MIN_ABS_AGGREGATE:
            continue
        out[y] = abs(float(ag) / float(ps))
    return out


def basis_jumps(implied: Dict[str, float], window: Sequence[str],
                per_share: Optional[Dict[str, Any]] = None,
                ) -> List[Dict[str, Any]]:
    ys = [y for y in window if y in implied]
    out: List[Dict[str, Any]] = []
    for a, b in zip(ys, ys[1:]):
        if implied[a] <= 0:
            continue
        jump = implied[b] / implied[a]
        if not (jump >= SPLIT_FLOOR or jump <= 1.0 / SPLIT_FLOOR):
            continue
        if per_share is not None:
            pa = per_share.get(a)
            pb = per_share.get(b)
            if isinstance(pa, (int, float)) and isinstance(pb, (int, float)) \
                    and pa and pb:
                err = (QUANTIZATION_STEP / abs(pa)) + (QUANTIZATION_STEP / abs(pb))
                if err > MAX_PAIR_QUANTIZATION_ERROR:
                    continue
        out.append({"from_year": a, "to_year": b, "jump": round(jump, 4),
                    "implied": [round(implied[a]), round(implied[b])]})
    return out


def _matches(jump: float, factor: float) -> bool:
    a, b = abs(jump), abs(factor)
    if a < 1:
        a = 1.0 / a
    if b < 1:
        b = 1.0 / b
    if not a or not b:
        return False
    r = a / b
    return (1.0 / MATCH_TOLERANCE) <= r <= MATCH_TOLERANCE


def verify_single_basis(per_share: Dict[str, Any], aggregate: Dict[str, Any],
                        window: Sequence[str]) -> List[Dict[str, Any]]:
    """Re-test a (possibly already cut) window. The gate calls this on its own
    output: a cut that leaves a break behind is a gate reporting success while
    still serving a mixed-basis array."""
    return basis_jumps(implied_shares(per_share, aggregate, window), window,
                       per_share)


def basis_gate_report(per_share: Dict[str, Any], aggregate: Dict[str, Any],
                      per_share_filed: Dict[str, List[float]],
                      aggregate_filed: Dict[str, List[float]],
                      window: Sequence[str]) -> Dict[str, Any]:
    evidence = restatement_evidence(per_share_filed, aggregate_filed, window)
    implied = implied_shares(per_share, aggregate, window)
    jumps = basis_jumps(implied, window, per_share)
    conservative = {
        (j["from_year"], j["to_year"]) for j in basis_jumps(
            implied_shares(per_share, aggregate, window, require_positive=True),
            window, per_share)}

    corroborated: List[Dict[str, Any]] = []
    advisory: List[Dict[str, Any]] = []
    for j in jumps:
        hit: Optional[Dict[str, Any]] = None
        for year in sorted(evidence):
            ev = evidence[year]
            if year > j["from_year"] and _matches(j["jump"], ev["factor"]):
                hit = dict(ev)
                hit["restated_year"] = year
                break
        if hit:
            entry = dict(j)
            entry["corroboration"] = hit
            corroborated.append(entry)
        elif (j["from_year"], j["to_year"]) in conservative:
            entry = dict(j)
            entry["basis"] = "jump_without_issuer_refiling_NOT_withheld"
            advisory.append(entry)

    withhold: Optional[Dict[str, Any]] = None
    if corroborated:
        newest = max(corroborated, key=lambda c: str(c["from_year"]))
        corr = newest["corroboration"]
        withhold = {
            "boundary_year": newest["from_year"],
            "first_comparable_year": newest["to_year"],
            "observed_jump": newest["jump"],
            "nearest_split_ratio": corr["nearest_ratio"],
            "refiled_factor": corr["factor"],
            "restated_year": corr["restated_year"],
            "all_boundaries": [c["from_year"] for c in corroborated],
            "withheld_years": [y for y in window if y <= newest["from_year"]],
            "evidence": "implied_share_jump_plus_issuer_refiling_relative_to_aggregate",
        }
        survivors = [y for y in window if y > newest["from_year"]]
        residual = verify_single_basis(per_share, aggregate, survivors)
        if residual:
            withhold["residual_breaks_after_cut"] = residual
    return {"withhold": withhold, "advisory": advisory,
            "evidence_years": sorted(evidence),
            "examined": {"years": len(implied),
                         "year_pairs": max(0, len(implied) - 1)}}


def apply_basis_gate(years: Sequence[str], series: Dict[str, List[Any]],
                     report: Dict[str, Any],
                     metrics: Sequence[str]) -> Dict[str, Any]:
    """Null the split-affected cells at/before the boundary, IN PLACE, and
    return the disclosure block. Array shape is preserved; withheld values
    travel into the disclosure rather than being destroyed."""
    examined = report.get("examined") or {}
    pairs = int(examined.get("year_pairs", 0))
    b = report.get("withhold")
    if not b:
        if pairs < 1:
            return {
                "basisConsistent": None,
                "basisChecked": False,
                "yearPairsExamined": pairs,
                "basisNote": (
                    "Not enough usable year pairs to check whether this "
                    "per-share series sits on one share basis. This is NOT "
                    "a clean result -- the check did not run."),
            }
        out: Dict[str, Any] = {"basisConsistent": True, "basisChecked": True,
                               "yearPairsExamined": pairs}
        if report.get("advisory"):
            # 2026-09-13 (external 3.4.0 review, finding 1): an advised break
            # is NOT withheld and NOT certified -- null, the unexamined
            # branch's value, for the same reason. True beside a populated
            # basisAdvisory read as "consistent" on a series with a measured
            # 3.8x discontinuity. Twin of data/eps_basis_gate.py.
            out["basisConsistent"] = None
            out["basisAdvisory"] = report["advisory"]
            out["basisNote"] = (
                "An implied-share jump with NO issuer refiling to corroborate it "
                "was found (see basisAdvisory). Nothing was withheld and this "
                "series is NOT certified single-basis: basisConsistent is null, "
                "not true. Treat the years on either side of each advised break "
                "as possibly non-comparable until the issuer's own restated "
                "figures say otherwise.")
        return out
    cut = b["boundary_year"]
    withheld: Dict[str, Dict[str, Any]] = {}
    for i, y in enumerate(years):
        if y > cut:
            continue
        for m in metrics:
            vals = series.get(m)
            if not vals or i >= len(vals) or vals[i] is None:
                continue
            withheld.setdefault(m, {})[y] = vals[i]
            vals[i] = None
    disclosure: Dict[str, Any] = {
        "basisConsistent": False,
        "basisChecked": True,
        "yearPairsExamined": pairs,
        "withheldThrough": cut,
        "firstComparableYear": b["first_comparable_year"],
        "observedJump": b["observed_jump"],
        "nearestSplitRatio": b["nearest_split_ratio"],
        "basisBoundaries": b["all_boundaries"],
        "affectedMetrics": list(metrics),
        "withheldValues": withheld,
        "evidence": b["evidence"],
        # `cut` / `ry` are fiscal-period identifiers: the wheel passes the
        # FULL period end (2023-01-01), so the sentence names the period
        # end; it reads the same way for a bare calendar year.
        "note": (
            "Per-share figures for fiscal years ending {cut} and earlier are "
            "quoted on a pre-split basis and are NOT comparable with the "
            "years after them. The issuer refiled the fiscal year ending "
            "{ry} on a new basis (~{nr}:1) that "
            "moved the per-share figure relative to net income, which is a "
            "stock split rather than a restatement. "
            "Those cells are withheld rather than "
            "rescaled -- each is a value the filer actually reported, and "
            "the exact factor is not recoverable because buybacks move the "
            "share count in the same year. The withheld values are in "
            "withheldValues. Net income, revenue and balance-sheet lines "
            "are split-invariant and are unaffected."
        ).format(cut=cut, ry=b["restated_year"], nr=b["nearest_split_ratio"]),
    }
    if b.get("residual_breaks_after_cut"):
        disclosure["residualBreaksAfterCut"] = b["residual_breaks_after_cut"]
    if report.get("advisory"):
        disclosure["basisAdvisory"] = report["advisory"]
    return disclosure
