"""oxford_ledge_mcp/holders_fold.py -- the 13F superseded-parent fold, as
`get_holders` puts it on the wire.

CUT OUT OF server.py 2026-09-21, for the reason the SEC / FRED / wire /
transport families left it: server.py sits under a 2,000-line budget and the
K-7 / K-8 / K-9 fixes took it to 2,011. The gate's own instruction is "cut it
again rather than buying a budget entry", so this is a cut. Nothing here
registers a tool, so TOOL_DISPATCH insertion order is untouched by
construction, and nothing here imports server.py -- the handler passes in the
two things this module cannot know (the row reshaper and the row cap), which
keeps the dependency pointing one way.

WHAT THE FOLD IS. The hosted producer withholds a stale filer row from
`holders` when its shares reconcile within 1% to same-quarter siblings of its
own fund-name family -- the Vanguard AAPL double count -- and records every
withheld row so the decision is auditable instead of invisible. The wheel's
reshape kept only the SERVED list, so a holders table whose fold had run was
byte-identical to one where nothing was ever withheld; an agent could not tell
a filer that was WITHHELD from one that never filed.

WHAT THIS MODULE GUARANTEES, each of which was a measured defect:

* A withheld row is the SAME SHAPE as a served one (the reshaper is passed in,
  not re-implemented), plus the producer's verdict and its arithmetic.
* `superseded` is NEVER SYNTHESISED. It is the key that carries the verdict,
  so writing `True` over a producer's `false` re-labels a row the producer
  declined to withhold.
* BOTH OPERANDS of the reconciliation ride, never the ratio alone -- an
  inherited ratio hides whose denominator it was.
* A part the producer did not state in a usable form is DROPPED and NAMED in
  `unstated`, never faked. A fabricated number is worse than an absent one,
  and `superseded: true` with nothing behind it is the fail-open shape the
  fold exists to close.
* A row present in BOTH lists is MARKED (`also_in_holders`), because for that
  row the fold did not remove the double count and "do not add these back" is
  inert advice.
* The withheld list is CAPPED and the cut DISCLOSED, like the served one.
* `completeness.complete` is false whenever anything was withheld -- it
  answers "is this every filer", and the fold reduced the list upstream.
* ABSENT, `[]` and "present but unreadable" are THREE different facts and stay
  distinguishable on the wire.

`[]` IS NOT AN ALL-CLEAR, and the qualifier is load-bearing: it means the fold
ran and withheld nothing AMONG THE ROWS IT COULD DATE. A row carrying no
`stale_quarters` was never eligible to be folded and is served in full beside
its current sibling, so an `[]` beside undated rows is a blind pass and the
wire cannot distinguish the two. The key is ABSENT only when the producer sent
no fold at all.

NEVER merged back into `holders` and never counted in `completeness.returned`
-- merging them back is exactly the double count the fold removes.

stdlib only; ships in the wheel (the export tool collects it; the manifest
contract's module roster names it).
"""
from __future__ import annotations

import math

#: Distinguishes "the producer sent no fold at all" (a pre-fold host: the key
#: is genuinely absent) from "the producer sent the key and it was not a
#: list". `data.get(key)` returns None for both, and an explicit `null` is the
#: second case wearing the first's clothes.
NO_FOLD = object()

# The scope note `get_holders` serves on an empty list is FALSE in the fold's
# own headline case. An empty `holders` beside a non-empty
# `superseded_parents` does not mean the scope returned nothing -- it means
# the producer returned rows and the fold withheld all of them, which is a
# different fact and the more interesting one. Serving the scope note there
# sends a reader looking for a coverage problem when the answer is sitting in
# the next key.
EMPTY_AFTER_FOLD_NOTE = (
    "No institutional holders are SERVED for {ticker}, but this is not an "
    "empty result: the producer returned rows and the superseded-parent fold "
    "withheld every one of them as a stale filer reconciling to same-quarter "
    "siblings of its own fund-name family. The withheld rows are in "
    "`superseded_parents`, with the arithmetic behind each verdict. Read this "
    "as 'every filer this scope found was superseded', never as 'nobody holds "
    "{ticker}' and never as a coverage gap -- and do NOT move those rows into "
    "`holders`, which restores the double count the fold removes."
)


def _withheld_row(row, reshape_row, served_ciks, served_named):
    """One withheld row in the served rows' own key names, plus its verdict."""
    parent = reshape_row(row)
    # NEVER synthesised: see the module docstring.
    if isinstance(row.get("superseded"), bool):
        parent["superseded"] = row["superseded"]
    by = [str(c) for c in (row.get("superseded_by") or []) if c]
    if by:
        parent["superseded_by"] = by
    unstated = []
    for key in ("superseded_by_shares", "reconciled_pct"):
        val = row.get(key)
        if (isinstance(val, (int, float)) and not isinstance(val, bool)
                and math.isfinite(val)):
            parent[key] = val
        elif val is not None:
            # A string operand, or a NaN/Infinity one -- `json.loads` accepts
            # the bare tokens from a host, so both are reachable.
            unstated.append(key)
    if parent.get("superseded") is True and not by:
        unstated.append("superseded_by")
    if unstated:
        parent["unstated"] = unstated
    # Identity for the both-lists check is the filer's CIK when both rows
    # carry one (the only join the payload guarantees) and the
    # (holder, quarter) pair otherwise; a blank name never matches.
    if ((parent.get("fund_cik") and parent["fund_cik"] in served_ciks)
            or (parent.get("holder")
                and (parent.get("holder"), parent.get("quarter"))
                in served_named)):
        parent["also_in_holders"] = True
    return parent


def apply_fold(out, data, holders, ticker, fault, reshape_row, row_cap):
    """Attach the fold to `out` in place. Returns `out`.

    `out` already carries `holders` + `completeness`; this adds
    `superseded_parents`, the two withheld-list completeness operands, and the
    corrections to `complete` / `note` that a non-empty withheld list makes
    necessary. A producer that sent no fold leaves `out` untouched.
    """
    folded = data.get("superseded_parents", NO_FOLD)
    if not isinstance(folded, list):
        if folded is not NO_FOLD:
            # The producer sent the key and it was not a list (a dict, a
            # string, an explicit null). Dropping it to key-absent renders
            # this host identical to one that never folded at all, which is
            # the one thing a reader must be able to tell. Same `unstated`
            # vocabulary the withheld rows use, at the level where the
            # failure happened.
            out["unstated"] = ["superseded_parents"]
        return out
    withheld_rows = [row for row in folded if isinstance(row, dict)]
    served_ciks = {h["fund_cik"] for h in holders if h.get("fund_cik")}
    served_named = {(h.get("holder"), h.get("quarter")) for h in holders
                    if h.get("holder")}
    out["superseded_parents"] = [
        _withheld_row(row, reshape_row, served_ciks, served_named)
        for row in withheld_rows[:row_cap]]
    # The same returned/withheld-total discipline `completeness` already
    # applies to `holders`. Without it the top-level block reported
    # "returned: 1" over a 5,000-row withheld list, and the cut was silent --
    # an agent could not tell 10 withheld rows from 10 of 5,000.
    out["completeness"]["supersededReturned"] = len(out["superseded_parents"])
    out["completeness"]["supersededWithheldTotal"] = len(withheld_rows)
    if withheld_rows and not fault:
        # `complete` answered "was every FETCHED row returned", and the rows
        # the fold withheld never reach the fetch -- so it read `true` over a
        # list the producer had already reduced. A reader asking "is this all
        # the filers?" got yes.
        out["completeness"]["complete"] = False
        if not holders:
            out["note"] = EMPTY_AFTER_FOLD_NOTE.format(ticker=ticker)
    return out
