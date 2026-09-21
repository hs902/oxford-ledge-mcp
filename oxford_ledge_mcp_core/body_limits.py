"""Per-host ceilings on an HTTP SUCCESS body, and the one bounded read.

## Why this exists separately from the Oxford Ledge transport

The wheel talks to two KINDS of host. `transport.py` owns the three legs that
reach an operator-configurable `OXFORD_LEDGE_URL`, and it has capped a success
body at 8 MB since the 3.4.0 vet. The standalone SEC + FRED tools talk to two
HARDCODED public hosts over TLS and had no ceiling at all: four bare
`resp.read()` calls that would hold, decode and parse whatever arrived.

That asymmetry was defensible and was NOT what the record said. The transport
constant's comment, the changelog line and the vet artifact all read as
class-extinction ("a success body larger than 8 MB is refused"), while a third
of the package's success reads were unbounded. This module closes the gap and,
more importantly, makes the ceiling a NAMED per-host number instead of one
global figure that is either too small for SEC or too large for everyone else.

## Why a single 8 MB number could not be reused

`data.sec.gov`'s XBRL companyfacts document for a large filer legitimately
exceeds 8 MB. Measured 2026-09-21 with `curl -H 'Accept-Encoding: identity'`
(the wheel sends no `Accept-Encoding`, so urllib is served identity too), bytes
on the wire for `https://data.sec.gov/api/xbrl/companyfacts/CIK<cik>.json`:

    Citigroup      CIK 0000831001   8,785,882   <-- over the transport ceiling
    JPMorgan       CIK 0000019617   7,947,875
    Bank of Am.    CIK 0000070858   6,865,004
    General Elec.  CIK 0000040545   6,101,059
    Wells Fargo    CIK 0000072971   7,808,460
    Pfizer         CIK 0000078003   5,032,767
    Johnson & J.   CIK 0000200406   4,168,526
    Apple          CIK 0000320193   3,789,099
    Berkshire      CIK 0001067983   2,797,863

So reusing the transport's 8 MB would have REFUSED a correct answer for the
largest filers -- a ceiling that turns into a data outage is worse than no
ceiling, and it would have been found by a user, not by a test. The companyfacts
ceiling is set at ~3.6x the observed maximum instead.

The sibling documents are much smaller and get their own, tighter numbers
(same command, same day):

    submissions   CIK 0000019617   4,640,698   (largest of three sampled)
    submissions   CIK 0000831001   2,363,382
    submissions   CIK 0000320193     164,231
    company_tickers.json               799,073

FRED is the one host NOT measured here: `api.stlouisfed.org` requires a
registered key, and this pass drove no keyed request. Its ceiling is reasoned
from the document shape rather than measured, and is labelled as such below --
a FRED observations document is a flat list of ~100-byte observation objects,
so even a daily series carried back to 1919 is a few MB.

## What a ceiling does and does not buy

It bounds resident memory and the parse that follows, on a host this client
does not control at runtime. It is NOT an integrity control: these hosts are
reached over TLS and the ceiling says nothing about what they return. The
refusal is fail-closed (nothing is parsed, served or cached) and names the
ceiling, so an operator who hits one can tell it from an outage.
"""
from __future__ import annotations

from typing import Any

#: SEC XBRL companyfacts (`data.sec.gov/api/xbrl/companyfacts/CIK*.json`).
#: 32 MB = ~3.6x the 8,785,882-byte maximum measured 2026-09-21 (see module
#: docstring). These documents grow by one fact-period per filing, so the
#: headroom is deliberate: a ceiling that has to be raised every few quarters
#: gets raised in an incident instead of in a review.
SEC_COMPANYFACTS_BODY_CAP = 32 * 1024 * 1024

#: SEC submissions (`data.sec.gov/submissions/CIK*.json`). 16 MB = ~3.4x the
#: 4,640,698-byte maximum measured the same day.
SEC_SUBMISSIONS_BODY_CAP = 16 * 1024 * 1024

#: SEC's public ticker->CIK map (`www.sec.gov/files/company_tickers.json`),
#: one document for the whole registry. 8 MB = ~10x the 799,073 bytes
#: measured; it grows with the number of listed filers, not with any caller's
#: argument, so the multiple is generous on purpose.
SEC_TICKER_MAP_BODY_CAP = 8 * 1024 * 1024

#: FRED (`api.stlouisfed.org`). NOT MEASURED -- see the module docstring; a
#: keyed request was out of scope for the pass that set these. Reasoned from
#: the document shape: observations are ~100-byte objects, so the longest
#: daily series FRED carries is single-digit MB. 16 MB is the ceiling; if a
#: real FRED response is ever refused here, RAISE it against a measurement
#: rather than removing it.
FRED_BODY_CAP = 16 * 1024 * 1024


class BodyTooLarge(Exception):
    """An HTTP success body over the ceiling for its host.

    Carries the sentence the caller should relay. Each call site maps this to
    its OWN refusal type (the SEC tools raise `ToolError`, the FRED tools
    raise their classified `_FredFetchError`), because the two families
    already differ in how they report an upstream problem and a shared
    exception type here must not decide that for them.
    """

    def __init__(self, where: str, cap: int) -> None:
        self.where = where
        self.cap = cap
        super().__init__(
            f"{where} answered with a body over the {cap}-byte ceiling this "
            f"client will read. Nothing was parsed, served or cached -- an "
            f"upstream/transport problem, not your arguments. Retry later "
            f"rather than changing arguments."
        )


def read_capped(resp: Any, cap: int, where: str) -> bytes:
    """Read a success body, or raise `BodyTooLarge`.

    Reads one byte PAST the cap, so "exactly at the ceiling" stays servable
    and is distinguishable from "over it" -- the same construction
    `transport._read_capped` uses for the Oxford Ledge legs. `resp` is any
    object with a `read(amt)`; the amount is what makes the bound real, so a
    driver that ignores the argument is not exercising this function.
    """
    raw: bytes = resp.read(cap + 1)
    if len(raw) > cap:
        raise BodyTooLarge(where, cap)
    return raw
