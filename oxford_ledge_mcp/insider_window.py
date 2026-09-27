"""oxford_ledge_mcp/insider_window.py -- get_insider_trades' row window and
price labels (2026-09-26, MCP audit package MCP-B, B5; ledger
docs/board/audit/2026-09-26_EXTERNAL_mcp_tools_review.md).

A leaf beside server.py, which sits at the file-size gate's 2,000-line
threshold: the handler stays in server.py (its position is pinned by
tests/test_mcp_wheel_tool_family_cut_contract.py) and imports these.
`_FORM4_CODE_LABELS` moved here VERBATIM from server.py to make the room;
server.py re-exports it. Imports nothing from server.py (no cycle).

What B5 adds:
* `limit` (1-100, default 20) and `days` (a filing-date window). The tool had
  neither and always served the route's latest 20 rows, whatever their age.
  The host route honours both since the same change; `rows_in_window` applies
  the window again on the wheel side so a host older than this package cannot
  hand back rows outside it.
* `priceApplicable`. Form 4 filers report a price of 0 on transactions that
  have no price -- awards (A), gifts (G), other (J), will/inheritance (W),
  voting-trust moves (Z). The store keeps the filed 0 verbatim (the
  2026-09-07 form4 price-semantics ruling), so the row now SAYS the 0 means
  "no price", instead of reading as a free trade.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

# 2026-09-05 field-report-#2 F5-d: Form 4 transaction codes shipped as raw
# SEC letters ("P", "F") with no decode ring anywhere in the chain. Labels
# verified against the ingest writer's own code domain
# (tools/fetch_form4_transactions.py TRANSACTION_CODES -- the 18 codes it
# classifies); is_open_market mirrors that map exactly (True only for P/S).
_FORM4_CODE_LABELS = {
    "P": "Open-market purchase",
    "S": "Open-market sale",
    "A": "Award/grant",
    "D": "Disposition to issuer",
    "F": "Tax withholding",
    "M": "Option exercise/conversion",
    "G": "Gift",
    "J": "Other",
    "K": "Equity swap",
    "U": "Tender of shares",
    "W": "Acquisition/disposition by will or inheritance",
    "X": "In-the-money option exercise",
    "Z": "Deposit into/withdrawal from voting trust",
    "C": "Conversion of derivative security",
    "I": "Discretionary transaction",
    "O": "Out-of-the-money option exercise",
    "H": "Expiration of long derivative position",
    "L": "Small acquisition (Rule 16a-6)",
}

#: The route's default window and the caller cap (the host clamps to the same 100).
INSIDER_DEFAULT_LIMIT = 20
INSIDER_LIMIT_CAP = 100

#: Codes whose filed price of 0 means "no price applies" (MCP-B B5).
NO_PRICE_CODES = frozenset({"A", "G", "J", "W", "Z"})


def price_applicable(code: Any, price: Any) -> bool:
    """False ONLY for a no-price code (A/G/J/W/Z) filed at exactly 0; True
    otherwise -- including a null price, which means the price is unknown
    (the ingest gate rejected it or the filing had none), not inapplicable."""
    c = str(code or "").strip().upper()
    if c not in NO_PRICE_CODES or isinstance(price, bool):
        return True
    try:
        return float(price) != 0.0
    except (TypeError, ValueError):
        return True


def rows_in_window(raw: list, limit: int, days: Optional[int],
                   today: Optional[date] = None) -> list:
    """The first `limit` rows (the route's order, newest filing first) whose
    filingDate falls inside the trailing `days` window; a row with no
    filingDate is kept only when no window was asked for."""
    rows = [r for r in (raw or []) if isinstance(r, dict)]
    if days is not None:
        cutoff = ((today or date.today()) - timedelta(days=int(days))).isoformat()
        rows = [r for r in rows if str(r.get("filingDate") or "")[:10] >= cutoff
                and r.get("filingDate")]
    return rows[:int(limit)]


def _window_phrase(limit: int, days: Optional[int]) -> str:
    return (f"the latest {limit} Form 4 rows by filing date"
            + (f" filed in the last {days} days" if days else ""))


def completeness_basis(limit: int, days: Optional[int], default_text: str) -> str:
    """`completeness_basis` for the window actually requested; the default
    call keeps the exact sentence it always had (a shipped wire string)."""
    if limit == INSIDER_DEFAULT_LIMIT and days is None:
        return default_text
    return (f"totalFetched counts the route's window -- {_window_phrase(limit, days)} -- "
            f"not the issuer's full history; complete is null when that window came "
            f"back full ({limit} rows), because more may exist beyond it.")


def empty_scope_note(ticker: str, limit: int, days: Optional[int], default_template: str) -> str:
    """The empty-list scope sentence for the window actually requested."""
    if limit == INSIDER_DEFAULT_LIMIT and days is None:
        return default_template.format(ticker=ticker)
    return (f"No Form 4 rows returned for {ticker}. Scope of this list: Form 4 "
            f"transactions filed for this issuer ticker and its share-class siblings, "
            f"{_window_phrase(limit, days)}. An empty list means none are in that "
            f"window of the store -- not that no insider has ever traded {ticker}.")


def window_may_be_truncated(n_fetched: int, limit: int) -> bool:
    """True when the host's page came back full, so older rows may exist. A
    host older than this package ignores `limit` and always returns at most
    20 rows, so exactly 20 against a larger `limit` is ambiguous and counts
    as full (completeness null) rather than a false `complete: true`."""
    return n_fetched >= limit or (limit > INSIDER_DEFAULT_LIMIT
                                  and n_fetched == INSIDER_DEFAULT_LIMIT)
