"""Wheel-side `_meta` for the four STANDALONE tools (2026-09-12, 3.4.0 publish
vet COUNSEL CV-2 / F-1, CHAOS K-11, sect-4.2.4 wheel half).

WHY THIS TABLE EXISTS. The 14 name-proxied tools receive their provenance
block from the hosted dispatch seam (`mcp_provenance.attach_provenance`,
which does NOT ship in the wheel), so their wire carries `_meta.source` /
`source_url` / `terms_url` / `basis`. The four tools that talk to SEC EDGAR
and FRED DIRECTLY -- get_sec_filings, get_fundamentals, get_yield_curve,
get_fred_data -- cross no hosted seam, so they carried no `_meta` at all
while the README said "every tool response carries a `_meta` block". The
dispatcher attaches the entry below iff the result carries no `_meta`.

WHY IT IS SMALL AND WHY IT IS KEYED BY TOOL NAME. The critic (vet sect-7
item 5) named the trap: a wheel-side table is a hand-maintained twin of the
hosted classification, and two catalogs drift into two truths. So this
table carries ONLY the four tools that have no other source of `_meta`
(the REST-proxied tools get theirs from `middleware/route_provenance.py`,
B5a's half, one source of truth on the host), and a parity contract
(`tests/test_mcp_dispatch_seam_contract.py`) asserts against the in-tree
`mcp_provenance` module that (a) every `basis` here is in its vocabulary,
(b) for the three tools it classifies the `basis` / `source` / `source_url`
here EQUAL what `attach_provenance` would emit for the same arguments, and
(c) no REST-proxied or name-proxied tool appears here. get_sec_filings is
PIP_ONLY (absent from the hosted classification), so its row is the one
this table is the sole authority for -- and it is a primary read of the
same SEC EDGAR submissions API the hosted `_SEC_EDGAR_TOOLS` cite.

`basis: "primary"` for all four: the payload's substantive values are the
cited primary source's, verbatim (the B4 vocabulary; a split-basis
withholding or a FRED third-party carve-out REMOVES values, it does not
derive new ones). The hosted twin classifies ITS get_yield_curve `hybrid`
for `data[].ytdChange` -- a path the wheel's shape does not carry (CV-7:
hosted derived paths name the hosted shape), so the parity contract is
shape-aware: `primary` here is legal exactly while none of the hosted
derived paths resolves on the wheel's driven result, and the day one does
this row must become `hybrid` with those `derived_fields`.

Nothing here is imported by the hosted server; nothing here imports the
hosted server. stdlib only.
"""
from __future__ import annotations

from typing import Any

# The same literal `mcp_provenance.TERMS_URL` resolves to (BASE + "/terms").
TERMS_URL = "https://www.oxfordledge.com/terms"

_SEC_EDGAR = "SEC EDGAR (public)"
_SEC_SEARCH = "https://www.sec.gov/edgar/search/"
_SEC_BROWSE = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
               "&ticker={ticker}&type=10-K")
_FRED = "FRED (Federal Reserve Bank of St. Louis)"
_FRED_ROOT = "https://fred.stlouisfed.org/"
_FRED_SERIES = "https://fred.stlouisfed.org/series/{series}"
# COUNSEL-C3 (/mcp vet): the DATA is US-Treasury constant-maturity yields,
# DELIVERED via FRED's DGS series -- name both, credit neither as author.
_TREASURY_VIA_FRED = "U.S. Treasury constant-maturity yields (via FRED DGS series)"
_TREASURY_VIA_FRED_URL = "https://fred.stlouisfed.org/graph/?id=DGS10"

#: tool -> (source, basis). `source_url` is argument-shaped (a ticker'd
#: EDGAR browse page, a series page), so it is built by `standalone_meta`.
STANDALONE_TOOLS: dict[str, tuple[str, str]] = {
    "get_sec_filings": (_SEC_EDGAR, "primary"),
    "get_fundamentals": (_SEC_EDGAR, "primary"),
    "get_yield_curve": (_TREASURY_VIA_FRED, "primary"),
    "get_fred_data": (_FRED, "primary"),
}


def _clean(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _source_url(tool_name: str, args: dict[str, Any]) -> str:
    """The primary-source URL for this call, mirroring `mcp_provenance._source`:
    a SINGULAR ticker gets the issuer's EDGAR filing list; a FRED series
    gets its series page; anything else the source's search/root page."""
    if tool_name == "get_yield_curve":
        return _TREASURY_VIA_FRED_URL
    if tool_name == "get_fred_data":
        s = _clean(args.get("series"))
        return _FRED_SERIES.format(series=s) if s else _FRED_ROOT
    t = _clean(args.get("ticker"))
    # Same rule as the hosted `_source`, no cleverer: any non-blank ticker
    # string gets the issuer's browse page (upper-cased), else the search
    # entry. Parity is the property; the contract compares the two outputs.
    if t:
        return _SEC_BROWSE.format(ticker=t.upper())
    return _SEC_SEARCH


def standalone_meta(tool_name: str, args: dict[str, Any] | None) -> dict[str, Any] | None:
    """The `_meta` block for a standalone tool, or None for every other tool.

    Keys, deliberately the minimal set the vet asked for: `source`,
    `source_url`, `terms_url`, `basis`. The wheel's short attribution /
    not-advice literals ride the top level (L-3); they are not repeated here.
    """
    entry = STANDALONE_TOOLS.get(tool_name)
    if entry is None:
        return None
    source, basis = entry
    return {
        "source": source,
        "source_url": _source_url(tool_name, args if isinstance(args, dict) else {}),
        "terms_url": TERMS_URL,
        "basis": basis,
    }
