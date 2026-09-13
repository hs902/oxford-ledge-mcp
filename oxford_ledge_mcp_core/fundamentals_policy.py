"""get_fundamentals taxonomy policy: what the pip tool admits, and what it
says when it cannot serve.

Extracted 2026-09-07 with the IFRS refusal (external field report 2026-09-04,
DAC/Danaos). `oxford_ledge_mcp/server.py` sits at its file-size budget (2,150;
the TOOLS-manifest cut is the recorded next seam), so the policy lives here --
stdlib + ToolError only, inside the mypy --strict core, unit-testable without
registering a tool.

Two facts this module encodes, both MEASURED on 2026-09-07:

* DAC (CIK 0001369241) reports under US GAAP on Form 20-F: companyfacts keys
  dei/srt/us-gaap, 309 us-gaap concepts, forms 20-F + 6-K, ZERO ifrs-full.
  The old `form == "10-K"` filter dropped every fact and the tool returned
  {"data": {}} at full confidence -- an agent reading that learns "no
  financials". ANNUAL_FORMS admits the three annual forms, exactly as the
  in-tree twin has since it was written (data/edgar_xbrl.py
  _extract_xbrl_annual; '40-F' added there 2026-07-29). Companyfacts tags all
  three fp=FY with fiscal-year durations, so the caller's FY + duration
  filters apply to them unchanged.
* An IFRS reporter (companyfacts carries 'ifrs-full' and no 'us-gaap') used
  to get a "no XBRL data" raise -- loud but taxonomy-blind, and false: the
  financials exist, this tool cannot read them. It now gets a structured
  refusal naming the taxonomy, in the package's ONE error shape.

The ifrs-full LADDER is deliberately not here. It is gated on an OWNER
licensing decision (docs/plans/IFRS_XBRL_EXTRACTION.md; COUNSEL 2026-07-28:
"do not start S1 with code"). Name the taxonomy; never read it.
"""
from __future__ import annotations

import re
from typing import Any

from oxford_ledge_mcp_core.errors import ToolError

#: Annual-report forms admitted into the series: 10-K (domestic), 20-F
#: (foreign private issuer), 40-F (Canadian MJDS).
ANNUAL_FORMS = ("10-K", "20-F", "40-F")

#: A companyfacts unit that is a currency (ISO-4217 code, optionally per
#: share): `CAD`, `CAD/shares`, `USD`. Dimensions (`segment`, `years`,
#: `pure`, `shares`) are not denominations and never name a refusal cause.
_CURRENCY_UNIT = re.compile(r"[A-Z]{3}(?:/shares)?")

#: What IS available for a filer this tool cannot serve. get_sec_filings reads
#: SEC's data.sec.gov/submissions index for the filer (since T10, 2026-09-12;
#: the old browse-edgar feed is gone) and passes filing_type straight through,
#: so '20-F' / '40-F' / '6-K' are legal values. "No package tool reads IFRS
#: XBRL" is a grep fact: companyfacts is read in exactly one place in the
#: package.
FUNDAMENTALS_HINT = (
    "get_sec_filings lists this filer's annual reports on EDGAR (pass "
    "filing_type='20-F' or '40-F' for a foreign private issuer, '6-K' for a "
    "Canadian MJDS filer that furnishes its XBRL there); the statements are "
    "in those filings. No package tool reads IFRS XBRL, and get_fundamentals "
    "serves USD-denominated 10-K/20-F/40-F facts only.")


def taxonomy_blocks(facts: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """(facts_block, us_gaap) from a companyfacts payload, guarded for a
    missing or non-dict `facts`. Both are {} when absent: the caller refuses
    on an empty us_gaap and consults facts_block for what the filer DOES
    carry ("ifrs-full" in facts_block)."""
    facts_block = facts.get("facts") if isinstance(facts, dict) else None
    if not isinstance(facts_block, dict):
        facts_block = {}
    us_gaap = facts_block.get("us-gaap") or {}
    return facts_block, us_gaap


def fundamentals_refusal(ticker: str, cik: str, taxonomy: str | None,
                         observed: dict[str, Any] | None = None) -> ToolError:
    """The structured refusal get_fundamentals raises instead of serving an
    empty series -- never {"data": {}} at full confidence.

    `taxonomy` names what SEC companyfacts DOES carry for the filer:
      'ifrs-full' -- an IFRS reporter. The financials exist; this tool reads
                     us-gaap concepts only.
      'us-gaap'   -- the block is present but no annual fact matched the
                     ladder.
      None        -- neither block, or no facts at all.
    `observed` (f1-sec-fundamentals-10, 2026-09-13 deep audit) is what the
    us-gaap block DOES carry -- {annualFormsSeen, unitsSeen} -- so the
    'us-gaap' refusal names the REAL cause instead of blaming the ladder:
    Canadian National (CNI) has 457 us-gaap concepts with 24 fp=FY Revenues
    facts, every one furnished on Form 6-K in CAD; ANNUAL_FORMS admits none
    and the CAD units would be skipped if it did. The old sentence said "none
    of its annual facts matched the ladder" and the hint talked about IFRS.
    One error shape for the whole package: ToolError.to_dict(), with these
    fields merged into its `error` object.
    """
    if taxonomy == "ifrs-full":
        message = (
            f"{ticker} (CIK {cik}) reports under IFRS: SEC companyfacts "
            "carries an 'ifrs-full' block and no usable 'us-gaap' annual "
            "facts. get_fundamentals reads us-gaap concepts only, so this "
            "filer's financial statements are not available through this "
            "tool. The financials exist -- this is a taxonomy limit, not a "
            "package-version, connectivity, or data-absence problem.")
    elif taxonomy == "us-gaap":
        forms = list((observed or {}).get("annualFormsSeen") or [])
        units = list((observed or {}).get("unitsSeen") or [])
        off_form = [f for f in forms if f not in ANNUAL_FORMS]
        # Currency units only (ISO-4217 code, optionally per share): a
        # `segment` or `years` unit is a dimension, not a denomination.
        non_usd = [u for u in units
                   if _CURRENCY_UNIT.fullmatch(u) and not u.startswith("USD")]
        if forms and not any(f in ANNUAL_FORMS for f in forms):
            cause = (
                f"its fiscal-year (fp=FY) facts are furnished on "
                f"{', '.join(off_form)} rather than on a 10-K/20-F/40-F"
                + (f", and in {', '.join(non_usd)}" if non_usd else "")
                + " -- get_fundamentals serves USD-denominated annual facts "
                "from 10-K/20-F/40-F filings only (a Canadian MJDS filer "
                "whose XBRL rides its 6-K furnishings, like CNI, is this "
                "class)")
        elif non_usd and not any(u.startswith("USD") for u in units):
            cause = (
                f"its annual facts are denominated in {', '.join(non_usd)} "
                "and get_fundamentals serves USD facts only")
        else:
            cause = (
                "none of its annual (10-K/20-F/40-F, fp=FY) facts matched "
                "get_fundamentals' line-item ladder")
        message = (
            f"{ticker} (CIK {cik}) has a 'us-gaap' block in SEC companyfacts, "
            f"but {cause}, so no financials are available through this "
            "tool. This is not an absence of filings.")
    else:
        message = (
            f"SEC companyfacts for {ticker} (CIK {cik}) carries neither a "
            "'us-gaap' nor an 'ifrs-full' block, so no XBRL financial "
            "statements are available through get_fundamentals.")
    details: dict[str, Any] = {"taxonomy": taxonomy, "ticker": ticker,
                               "cik": cik, "hint": FUNDAMENTALS_HINT}
    if observed:
        details["annualFormsSeen"] = list(observed.get("annualFormsSeen") or [])
        details["unitsSeen"] = list(observed.get("unitsSeen") or [])
    return ToolError(ToolError.DATA_UNAVAILABLE, message, details=details)
