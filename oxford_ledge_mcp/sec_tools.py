"""oxford_ledge_mcp/sec_tools.py -- the wheel's standalone SEC EDGAR tools
that need no Oxford Ledge instance: get_sec_filings and the shared
ticker/CIK helpers.

EXTRACTED VERBATIM from server.py on 2026-09-12 (the 3.4.0 publish-vet fix
wave). server.py sat at 1,999 lines against the file-size-budget gate's
2,000-line threshold (tests/test_file_size_budget.py; the pair pin in
tests/test_mcp_server_tools_manifest_contract.py) with six builders about to
add to it. The gate's own instruction is "fix at the ROOT, never rebaseline",
so this is a cut, not a budget entry -- the same discipline as the 2026-09-08
`server_tools.py` cut and the 2026-09-12 T7 `holders_vintage.py` core cut.

WHAT MOVED (two blocks of server.py at HEAD 1c4e046e, in this order):
  * lines 705-788: `_SEC_TICKER_RE`, `_reject_bad_sec_ticker`, `_SEC_ARCHIVE`,
    `tool_get_sec_filings` (@mcp_tool get_sec_filings);
  * lines 1567-1598: `_resolve_ticker_to_cik_via_sec` -- SHARED with
    `tool_get_13f_holdings`, which STAYS in server.py and reaches it through
    the re-export below.
Pure move: tool names, argument handling, response shapes, error messages and
cache classes are byte-identical to the pre-cut file. `_cents` and
`_FORM4_CODE_LABELS` belong to get_insider_trades and stayed.

WHY get_fundamentals IS NOT HERE. The brief's SEC family is NOT contiguous in
server.py: get_insider_trades (lines 823-878) sits between get_sec_filings and
get_fundamentals, and a module registers everything it defines on FIRST
import. One module holding both handlers, imported where get_sec_filings
stood, would register get_fundamentals ahead of get_insider_trades and change
TOOL_DISPATCH insertion order -- the invariant the position rule exists to
keep. So the XBRL tool lives in the sibling `sec_fundamentals.py`, imported
at ITS old position; the order is identical for all 29 tools.

An AST free-name walk over both blocks (run before the cut) found every
unbound name to be stdlib or `oxford_ledge_mcp_core`; this module imports
NOTHING from server.py, at module top or lazily, so there is no cycle.

REGISTRATION BY IMPORT. `@mcp_tool` writes the shared `oxford_ledge_mcp_core`
REGISTRY / TOOL_DISPATCH at function-definition time, so importing this module
IS the registration. server.py imports it at the EXACT source position the
first block occupied (between get_holders and get_insider_trades) -- pinned by
tests/test_mcp_wheel_tool_family_cut_contract.py.

RE-EXPORT RULE. server.py re-exports every name above, public and private, so
`oxford_ledge_mcp.server.<name>` keeps resolving for every contract that
reaches the family through `S.` (`S.tool_get_sec_filings`,
`S._reject_bad_sec_ticker`, `S._resolve_ticker_to_cik_via_sec`). A driver
that sets `S.urllib.request.urlopen` patches the shared urllib module, which
this file reads too. A test that wants to patch one of THESE helpers must
patch it HERE -- the re-export in server.py is a second binding the code in
this file never reads.

stdlib + oxford_ledge_mcp_core only; ships in the wheel
(tools/export_mcp_package.py collects it; the manifest contract pins it).

WAVE B (2026-09-12, the 3.4.0 publish vet, builder B2_sec) -- this file is
no longer a byte-identical move. What changed, each pinned by
tests/test_mcp_sec_filings_submissions_api_contract.py:
  * get_sec_filings emits `form` per row and a top-level `completeness`
    {returned, cap: 10, windowRows, windowFrom} (b01-sec-standalone-1);
  * SEC 429 -> RATE_LIMITED with retry_after from the header; an HTTP-success
    body that is not the documented object -> the client/server contract
    mismatch sentence, not "availability; retry later"; a 404 reached via a
    ticker names the ticker (b01-sec-standalone-2);
  * the shared resolver keeps SEC's ~800KB company map for 24h at module
    level, guards a non-object map body, and is now ALSO the resolver
    get_fundamentals uses (b01-sec-standalone-5 / -12).
The cut narrative above is history and is kept as written.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

from oxford_ledge_mcp_core import FUNDAMENTAL, ToolError, mcp_tool, normalize_ticker

#: One declared UA for every sec.gov read the wheel makes (SEC's fair-access
#: policy wants a contact address; the two tools and the 13F resolver share it).
_SEC_UA = "OxfordLedge contact@oxfordledge.com"


# 2026-09-05 field-report-#2 F7-SSRF: normalize_ticker is strip+upper ONLY,
# and the value was interpolated straight into the browse-edgar URL -- so
# "AAPL&count=999" or "X&owner=only" rewrote the outbound query string.
# The in-tree ssrf_guard cannot be imported here (this package is
# stdlib-standalone by design); the portable fix is the SEC-F1 charset-reject
# pattern. Digits are deliberately ADMITTED (an all-digit value IS the CIK and
# skips the ticker->CIK resolve; that worked before this guard and must keep working);
# the pattern's job is blocking URL metacharacters, not policing ticker shape.
_SEC_TICKER_RE = re.compile(r"^[A-Z0-9.\-]{1,10}$")


def _reject_bad_sec_ticker(ticker):
    """Raise INVALID_PARAMS unless *ticker* (already normalized) is charset-safe
    for URL interpolation. Returns the ticker unchanged when it passes -- the
    ALLOW path is a real code path, exercised by the behavioral-parity contract."""
    if not _SEC_TICKER_RE.match(ticker or ""):
        raise ToolError(
            ToolError.INVALID_PARAMS,
            f"Invalid ticker {str(ticker)[:40]!r}: expected 1-10 characters "
            f"from A-Z, 0-9, '.', '-' (e.g. AAPL, BRK.B, 0000320193).")
    return ticker


def _sec_retry_after(e):
    """Seconds from an HTTPError's Retry-After header, or None. SEC sends a
    plain integer; an HTTP-date or a missing header is None (not 0)."""
    try:
        v = int(str(e.headers.get("Retry-After") or "").strip() or 0)
    except Exception:
        return None
    return v or None


def _sec_rate_limited(api, cik, e):
    """3.4.0 vet b01-sec-standalone-2: SEC's 429 used to be coded
    DATA_UNAVAILABLE ('an upstream availability problem ... retry later') with
    no retry_after -- the dispatcher's own '429'->RATE_LIMITED map never ran
    because the handler raised first. Build the RATE_LIMITED error here so
    every sec.gov read in the wheel says the same thing."""
    wait = _sec_retry_after(e)
    return ToolError(
        ToolError.RATE_LIMITED,
        f"SEC EDGAR's {api} rate-limited this client (HTTP 429) for CIK "
        f"{int(cik)} -- not a ticker problem; SEC's fair-access limit is 10 "
        f"requests/second per client. Retry after {wait or 'a few'} seconds.",
        retry_after=wait)


def _sec_body_mismatch(api, cik, exc):
    """The 'HTTP success, wrong shape' sentence -- mirrors errors.non_object_
    response's wording (a client/server contract mismatch), NOT 'availability;
    retry later': a body that parsed to an array or lacks the documented keys
    will parse the same way on the retry."""
    return ToolError(
        ToolError.DATA_UNAVAILABLE,
        f"SEC EDGAR's {api} answered HTTP success for CIK {int(cik)}, but the "
        f"body was not the documented object (upstream: {type(exc).__name__}) "
        f"-- an oxford-ledge-mcp client/server contract mismatch, not a ticker "
        f"problem and not an availability problem: retrying will hit the same "
        f"shape. Upgrade oxford-ledge-mcp or report the response shape.")


def _sec_transport_failure(api, cik, exc):
    timed_out = isinstance(exc, TimeoutError) or isinstance(getattr(exc, "reason", None), TimeoutError)
    return ToolError(
        ToolError.TIMEOUT if timed_out else ToolError.DATA_UNAVAILABLE,
        f"SEC EDGAR's {api} failed for CIK {int(cik)} (upstream: "
        f"{type(exc).__name__}) -- an availability problem, not a ticker problem; retry later.")


# 2026-09-12 (T10): the legacy cgi-bin/browse-edgar atom feed fails server-side
# (~10s 503 for every ticker, for a numeric CIK, and with a 30s client timeout)
# while data.sec.gov/submissions answers in ~0.2s; in-tree doctrine has been
# "code callers use data.sec.gov" since the 2026-05-18 F11 sweep, which missed
# this caller. (1) ticker->CIK resolves FIRST, so a miss is detected before any
# fetch and "check the ticker" is exact where used; (2) transport/HTTP failures
# RAISE -- a raised ToolError bypasses _cache_set, whereas the returned envelope
# was cached FUNDAMENTAL=3600s and replayed one transient failure as a ticker
# error for an hour; (3) exact form match (+ "/A"), not browse-edgar's prefix.
_SEC_ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"

#: The row cap. 3.4.0 vet b01-sec-standalone-1: it was `if len(filings) >= 10:
#: break` with nothing on the wire saying 10 was a cap, so a model asking for
#: "recent filings" could not tell ten rows from all rows. It is now disclosed
#: in `completeness.cap` beside what was actually read.
_SEC_FILINGS_CAP = 10


@mcp_tool(name="get_sec_filings", cache=FUNDAMENTAL)
def tool_get_sec_filings(args):
    # F7-SSRF (2026-09-05): charset-validate BEFORE any URL interpolation.
    ticker = _reject_bad_sec_ticker(normalize_ticker(args.get("ticker")))
    # 2026-08-10 field test #2: absent filing_type means ALL forms -- never a
    # silent 10-K default while the manifest advertises four form types.
    filing_type = (args.get("filing_type") or "").strip().upper()
    cik = ticker if ticker.isdigit() else _resolve_ticker_to_cik_via_sec(ticker)
    if not cik:
        return {"ticker": ticker, "filings": [],
                "error": f"No SEC filer matches ticker '{ticker}' -- check the "
                         f"ticker symbol, or pass the numeric CIK instead."}
    api = "submissions API"
    cik_url = f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json"
    req = urllib.request.Request(cik_url, headers={"User-Agent": _SEC_UA})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            # b01-sec-standalone-2: a 404 reached through a TICKER said
            # "check the CIK" -- the caller never typed one. Name the path.
            via = (f" (resolved from ticker '{ticker}' via SEC's company map "
                   f"-- the two SEC indexes disagree; retry later or pass "
                   f"the numeric CIK directly)"
                   if not ticker.isdigit() else " -- check the CIK.")
            return {"ticker": ticker, "filings": [],
                    "error": f"SEC EDGAR has no filer record for CIK {int(cik)}{via}"}
        if e.code == 429:
            raise _sec_rate_limited(api, cik, e)
        raise ToolError(ToolError.DATA_UNAVAILABLE,
                        f"SEC EDGAR's {api} returned HTTP {e.code} for CIK {int(cik)} "
                        f"-- an upstream availability problem, not a ticker problem; retry later.")
    except Exception as e:
        raise _sec_transport_failure(api, cik, e)
    # HTTP success: the SHAPE is a contract, not an availability question.
    # A body that is not the documented submissions object (an array, a
    # string, HTML, a dict without filings.recent, a `recent` whose columns
    # are not equal-length lists) raises the mismatch sentence; it used to be
    # wrapped as '(upstream: TypeError) -- an availability problem; retry
    # later', which is wrong in both halves.
    try:
        recent = json.loads(raw.decode("utf-8"))["filings"]["recent"]
        forms = recent["form"]
        dates = recent["filingDate"]
        accs = recent["accessionNumber"]
        if not (isinstance(forms, list) and isinstance(dates, list)
                and isinstance(accs, list)
                and len(dates) == len(forms) == len(accs)):
            raise TypeError("filings.recent columns are not equal-length lists")
    except (ValueError, TypeError, KeyError, AttributeError) as e:
        raise _sec_body_mismatch(api, cik, e)

    def _col(key):  # the two document columns may be short/absent: pad, do not truncate
        vals = recent.get(key)
        vals = vals if isinstance(vals, list) else []
        return vals + [""] * (len(forms) - len(vals))
    # b01-sec-standalone-1: what was READ, beside what was returned. SEC's
    # `filings.recent` is the filer's ~1000 newest submissions; older ones
    # live in paged files this tool does not read. `windowFrom` is the
    # oldest filingDate in that window, so a consumer can tell "no 10-K in
    # the last N rows" from "no 10-K ever".
    completeness = {"returned": 0, "cap": _SEC_FILINGS_CAP,
                    "windowRows": len(forms),
                    "windowFrom": min((d for d in dates if d), default=None)}
    filings = []
    for form, date, acc, doc, desc in zip(forms, dates, accs,
                                          _col("primaryDocument"), _col("primaryDocDescription")):
        form = str(form or "")
        if filing_type and form.upper() not in (filing_type, filing_type + "/A"):
            continue
        url = _SEC_ARCHIVE.format(cik=int(cik), acc=str(acc).replace("-", ""), doc=doc) if acc else ""
        title = f"{form} - {desc}" if desc and desc.upper() != form.upper() else form
        # `form` rides beside `title` (which fuses form + description):
        # nine of ten unfiltered NVDA rows were Form 4 / 144 / N-PX and a
        # consumer had to parse the title to find that out.
        filings.append({"form": form, "title": title, "url": url, "date": date})
        if len(filings) >= _SEC_FILINGS_CAP:
            break
    completeness["returned"] = len(filings)
    if not filings:
        # filings.recent is SEC's ~1000-row window; older paged files are not read.
        return {"ticker": ticker, "filings": [], "completeness": completeness,
                "error": f"No {filing_type or 'recent'} filings among the filer's {len(forms)} most "
                         f"recent EDGAR submissions (older filings are outside this tool's window)."}
    return {"ticker": ticker, "filings": filings, "completeness": completeness}


#: b01-sec-standalone-12: SEC's company_tickers.json (~800KB) was re-downloaded
#: on EVERY result-cache miss, per ticker, per tool -- the only cache was the
#: tool RESULT. One parsed copy, module-wide, shared by both standalone tools
#: and the 13F resolver; refreshed after 24h (the map changes with listings,
#: not intraday). A fetch failure never writes the cache.
_TICKER_MAP_TTL = 86400
_ticker_map_cache = {"at": 0.0, "map": None}


def _clear_ticker_map_cache():  # zero-caller-ok: the callers are the three subprocess test drivers (tests/test_mcp_sec_filings_submissions_api_contract.py, tests/test_mcp_fundamentals_debt_label_contract.py, tests/test_eps_split_basis_wheel_period_keying_contract.py), which call `T._clear_ticker_map_cache()` from INSIDE their child source strings -- the wheel is only ever imported in a subprocess, so no in-process reference can exist for the walk to see
    _ticker_map_cache.update(at=0.0, map=None)


def _resolve_ticker_to_cik_via_sec(ticker):
    """Resolve a ticker (BRK.B or BRK-B) to a CIK via SEC's public company map.

    Stdlib-only stand-in for the in-tree cik_map resolve path (SEC-F1 guard
    port, 2026-09-05). Returns the CIK as a bare string, or None on a miss.
    Raises DATA_UNAVAILABLE only when the map itself cannot be fetched --
    a resolution MISS is the caller's argument problem, not availability.
    """
    tickers_data = _ticker_map_cache["map"]
    if tickers_data is None or time.time() - _ticker_map_cache["at"] > _TICKER_MAP_TTL:
        try:
            req = urllib.request.Request(
                "https://www.sec.gov/files/company_tickers.json",
                headers={"User-Agent": _SEC_UA})
            with urllib.request.urlopen(req, timeout=10) as resp:
                tickers_data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            raise ToolError(
                ToolError.DATA_UNAVAILABLE,
                f"Could not reach SEC's ticker map to resolve '{ticker}' -- "
                f"provide a numeric CIK directly (e.g. 1067983). "
                f"(upstream: {type(e).__name__})")
        if not isinstance(tickers_data, dict):
            # b01-sec-standalone-9: a non-object map leaked as
            # "'list' object has no attribute 'values'" through get_fundamentals.
            raise ToolError(
                ToolError.DATA_UNAVAILABLE,
                f"SEC's ticker map answered HTTP success, but the body was a JSON "
                f"{type(tickers_data).__name__}, not the documented object -- an "
                f"oxford-ledge-mcp client/server contract mismatch; pass the "
                f"numeric CIK directly (e.g. 1067983) or upgrade oxford-ledge-mcp.")
        _ticker_map_cache.update(at=time.time(), map=tickers_data)
    # SEC's map is dash-form (BRK-B, 543 entries) with one dot-form ticker;
    # callers write BRK.B. Exact match wins; the other separator is the fallback
    # (shared.py _CikMap.get precedent) so a real filer is never reported missing.
    alt = ticker.replace(".", "-") if "." in ticker else ticker.replace("-", ".")
    fallback = None
    for entry in tickers_data.values():
        if not isinstance(entry, dict):
            continue
        t = str(entry.get("ticker", "")).upper()
        if t == ticker:
            return str(entry["cik_str"])
        if t == alt and fallback is None:
            fallback = str(entry["cik_str"])
    return fallback
