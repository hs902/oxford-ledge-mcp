"""oxford_ledge_mcp/fred_tools.py -- the wheel's FRED tool family.

EXTRACTED VERBATIM from server.py on 2026-09-12 (the 3.4.0 publish-vet fix
wave). server.py sat at 1,999 lines against the file-size-budget gate's
2,000-line threshold (tests/test_file_size_budget.py; the pair pin in
tests/test_mcp_server_tools_manifest_contract.py) with six builders about to
add to it. The gate's own instruction is "fix at the ROOT, never rebaseline",
so this is a cut, not a budget entry -- the same discipline as the 2026-09-08
`server_tools.py` cut and the 2026-09-12 T7 `holders_vintage.py` core cut.

WHAT MOVED (one contiguous block, server.py lines 1106-1337 at HEAD 1c4e046e,
in this order): `_YC_HISTORY_LIMIT`, `_YC_LOOKBACK_TOLERANCE_DAYS`,
`_yc_pick_year_ago`, `tool_get_yield_curve` (@mcp_tool get_yield_curve), the
`import re as _re` the carve-out regex uses, `_FRED_THIRDPARTY_NOTE`,
`_FRED_GOV_PREFIXES`, `_fred_thirdparty_cache`, `_scrub_fred_key`,
`_fred_series_is_thirdparty`, `tool_get_fred_data` (@mcp_tool get_fred_data).
The cut itself was a pure move; the B1 wave below (same day) then changed
behaviour in this file only.

WHY THIS FAMILY. It is the only cluster in server.py that is both contiguous
and self-contained: an AST free-name walk over the block (run before the cut,
not assumed) found every unbound name to be stdlib or `oxford_ledge_mcp_core`
-- nothing from server.py's own substrate (`_log`, `_safe`, `_api_get`,
`_NO_ASK_OPERATOR`, the disclosure literals). So this module imports NOTHING
from server.py, at module top or lazily, and there is no cycle to manage.

REGISTRATION BY IMPORT. `@mcp_tool` writes the shared `oxford_ledge_mcp_core`
REGISTRY / TOOL_DISPATCH at function-definition time, so importing this module
IS the registration. server.py imports it at the EXACT source position the
block used to occupy (between get_fundamentals and get_corporate_events), so
TOOL_DISPATCH insertion order and every registry field (cache_ttl / heavy /
min_tier) are identical for all 29 tools -- pinned by
tests/test_mcp_wheel_tool_family_cut_contract.py.

RE-EXPORT RULE. server.py re-exports every name the cut moved, public and
private, so `oxford_ledge_mcp.server.<name>` keeps resolving for every
contract that reaches the family through `S.` (test_mcp_yield_curve_include_
history, test_mcp_oss_twin_parity's `S._fred_series_is_thirdparty` probes). A
test that monkeypatches `S.urllib.request.urlopen` patches the shared urllib
module, which this file reads too -- so those drivers keep working unchanged.
A test that wants to patch one of THESE helpers must patch it HERE (the
re-export in server.py is a second binding the code in this file never
reads). Names ADDED by the B1 wave are reachable as
`oxford_ledge_mcp.fred_tools.<name>` (the same module object).

B1 WAVE (2026-09-12, the 3.4.0 publish vet's FRED findings; the audit record
and its Pattern-K artifact live in the main repository's board audits;
contract tests/test_mcp_fred_guards_contract.py).
Every item below was MEASURED by the vet through the real dispatcher before
it was changed:
  * b02-fred-1  -- `series` reached the observations URL raw (the probe leg
    quoted it, the observations leg did not), so `DGS10&observation_start=
    1900-01-01` rewrote the request and `DGS10#x` dropped the api_key and
    every other parameter from the wire. Now `_parse_fred_series` validates
    against FRED's id charset BEFORE any URL exists and both legs quote.
  * b02-fred-2 / CV-5 -- `MICH` (University of Michigan, the same licensor
    the in-tree Board gate refuses as UMCSENT) sat in the GOV prefix
    fast-path. Removed; 'michigan|survey of consumers' joined the marker
    regex; `_FRED_KNOWN_THIRDPARTY` is a hard deny that never consults
    FRED's notes text.
  * b02-fred-3  -- an HTTP 400 from FRED was 'probe unavailable' whatever
    its body said. `_fred_get_json` now reads a bounded body and tells
    'The series does not exist' (an id typo) from 'api_key is not
    registered' (a credential problem, AUTH_REQUIRED) from transport /
    5xx / 429 (the fail-closed 'unverifiable' path), on BOTH legs.
  * b02-fred-4  -- get_yield_curve swallowed every per-tenor failure and
    shipped a 7-tenor curve as if it were the curve. Per-tenor failures are
    tracked; fewer than 11 tenors adds `completeness` + a string `error`;
    an all-fail run says WHICH failure it was.
  * b02-fred-5  -- an empty observation window shipped as a bare
    `data: []`. It now carries a plain-string `note`.
  * b02-fred-6  -- the probe fetched title/units/frequency and threw them
    away. They ship as `name` / `units` / `frequency`.
  * b02-fred-9/-10/-11 (TRACK, cheap) -- `include_history` parsed strictly
    (the string "false" used to switch history ON); `days` bounded 1..36500
    and validated before the probe; a 200 non-object body is a worded
    DATA_UNAVAILABLE, not a raw traceback.

REDISTRIBUTION ROSTERS (2026-09-22). `get_fred_data` takes a CALLER-SUPPLIED
series id, and until this date the only licensing control on it in this
package was a DENYLIST -- a twelve-id hard deny plus a word match over FRED's
own notes text. A denylist cannot surface the series nobody has looked at, and
that argument bears harder on a package a third party installs than on a
service its author operates. So this file now carries BOTH halves of the main
repository's redistribution decision, copied because the wheel is stdlib-only
and may not import it:
  * `_FRED_KNOWN_THIRDPARTY` -- the hard deny, now equal to that repository's
    refused roster (MORTGAGE30US and AAA joined it: both were named over
    there, neither was on any denylist, and both have a non-government
    copyright holder).
  * `_FRED_RESALE_ALLOWLIST` -- the reviewed public-domain clearance, 40 ids
    each with a named U.S.-federal publisher.
Both copies are pinned against the originals by a contract in the main
repository, in both directions, so a roster that grows on one side and not the
other is a red rather than a silent divergence. What did NOT change: an id on
neither roster is still decided by FRED's metadata, exactly as before.

stdlib + oxford_ledge_mcp_core only; ships in the wheel
(tools/export_mcp_package.py collects it; the manifest contract pins it).
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from oxford_ledge_mcp_core import FUNDAMENTAL, ToolError, mcp_tool
from oxford_ledge_mcp_core.errors import _JSON_TYPE_NAMES
from oxford_ledge_mcp_core.body_limits import (
    FRED_BODY_CAP, BodyTooLarge, read_capped)


# ── shared FRED transport (the ONE urlopen site for the family) ──────────────

#: Bytes read from a FRED error body before it is classified. FRED's error
#: bodies are one short JSON object ({"error_code", "error_message"}); the cap
#: bounds a hostile or misrouted upstream, not FRED.
_FRED_ERROR_BODY_CAP = 2048
#: Characters of upstream text that may ride into a tool message.
_FRED_DETAIL_CAP = 200

#: The sentence server.py's `_NO_ASK_OPERATOR` carries (the C-3 anti-phishing
#: convention: a credential message must never invite the user to paste a key
#: into chat). DUPLICATED, not imported: this module imports nothing from
#: server.py (the family-cut design, pinned by tests/test_mcp_wheel_tool_
#: family_cut_contract.py) and the core package does not define it. The two
#: literals are pinned equal by tests/test_mcp_fred_guards_contract.py, so
#: they cannot drift apart silently.
_FRED_NO_ASK_OPERATOR = (
    " DO NOT ASK THE USER TO PASTE A KEY OR TOKEN INTO THE CONVERSATION -- "
    "it is an environment variable the client's operator sets, and a "
    "credential sent in chat is a security problem, not a fix."
)


class _FredFetchError(Exception):
    """One FRED leg failed, CLASSIFIED. `kind` is one of:

      key_rejected   -- FRED refused the api_key (HTTP 400 whose body names
                        api_key, or 401/403): a credential problem, never a
                        data problem and never a licensing one
      no_such_series -- FRED HTTP 400 'The series does not exist': an id
                        problem, never a licensing or a transport problem
      http           -- any other HTTP error status (429, 5xx, an
                        unrecognised 400): upstream unavailable
      transport      -- URLError / timeout / socket: FRED was not reached
      bad_body       -- HTTP success whose body is not JSON, or is JSON but
                        not an object

    `detail` is bounded and key-scrubbed: safe to put on the wire as-is.
    """

    def __init__(self, kind: str, detail: str, status: int | None = None) -> None:
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail
        self.status = status


def _scrub_fred_key(text: str) -> str:
    """3.2.0 vet C-6 (defense-in-depth): FRED's documented auth rides the
    query string, so a urllib error repr can embed the caller's own key.
    Redact it before any exception text reaches a tool message.

    B1 (2026-09-12): ALSO redacts the configured key VALUE wherever it
    appears, not only behind `api_key=` -- a FRED error body that echoed the
    key would otherwise ride the new AUTH_REQUIRED message verbatim. Read
    from the environment so every message site in this file is covered
    without each caller threading the key through. Keys shorter than 8
    characters are not replaced: a real FRED key is 32 hex characters, and
    replacing a one-letter test key would garble every message."""
    out = re.sub(r"api_key=[^&\s'\"]+", "api_key=REDACTED", text)
    key = os.environ.get("FRED_API_KEY", "")
    if len(key) >= 8:
        out = out.replace(key, "REDACTED")
    return out


def _bounded(text, cap: int = _FRED_DETAIL_CAP) -> str:
    """One line, at most `cap` characters, key-scrubbed."""
    flat = " ".join(str(text if text is not None else "").split())
    if len(flat) > cap:
        flat = flat[:cap] + "..."
    return _scrub_fred_key(flat)


def _json_type_name(value) -> str:
    return _JSON_TYPE_NAMES.get(type(value), type(value).__name__)


def _classify_fred_http_error(e: urllib.error.HTTPError) -> _FredFetchError:
    """Read FRED's error body (bounded) and say which of the three things a
    FRED HTTP error can mean. FRED documents HTTP 400 for BOTH a nonexistent
    series id and an unregistered api_key, so the status alone cannot tell
    an id typo from a credential problem -- the body can."""
    try:
        raw = e.read(_FRED_ERROR_BODY_CAP)
    except Exception:
        raw = b""  # an unreadable error body leaves the status line, the fallback text below
    message = ""
    try:
        body = json.loads(raw.decode("utf-8", "replace")) if raw else None
        if isinstance(body, dict):
            message = str(body.get("error_message") or "")
    except ValueError:
        message = ""
    low = message.lower()
    status = int(getattr(e, "code", 0) or 0)
    detail = _bounded(message or f"HTTP {status} {getattr(e, 'reason', '')}")
    if status in (401, 403) or (status == 400 and "api_key" in low):
        return _FredFetchError("key_rejected", detail, status)
    if status == 400 and "does not exist" in low:
        return _FredFetchError("no_such_series", detail, status)
    return _FredFetchError("http", f"HTTP {status}: {detail}", status)


def _fred_get_json(url: str) -> dict:
    """The one FRED transport: returns the parsed JSON OBJECT on HTTP success;
    raises `_FredFetchError` (classified, bounded, key-scrubbed) on anything
    else. Never lets a raw urllib / json exception -- or any text carrying
    the key -- out."""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            # Bounded since 2026-09-21 (CISO reseat L-1). This was a bare
            # `resp.read()`: the error body has been read bounded since the
            # 3.2.0 vet while the SUCCESS body was not, on a host this client
            # holds, decodes, parses and caches for the tool's TTL. The
            # ceiling is per-host and lives in one place --
            # oxford_ledge_mcp_core.body_limits -- so the transport's 8 MB
            # Oxford Ledge figure is not silently reused for a host whose
            # documents are a different size.
            raw = read_capped(resp, FRED_BODY_CAP, "FRED")
    except BodyTooLarge as e:
        # Classified "transport", not "bad_body": the body may well be valid
        # FRED JSON. What failed is this client's willingness to hold it,
        # which is the same class as a reset or a timeout and is NOT a
        # statement about the series id the caller asked for.
        raise _FredFetchError("transport", _bounded(e)) from None
    except urllib.error.HTTPError as e:
        raise _classify_fred_http_error(e) from None
    except urllib.error.URLError as e:
        raise _FredFetchError("transport", _bounded(getattr(e, "reason", e))) from None
    except Exception as e:  # socket timeouts, resets, a stub's RuntimeError
        raise _FredFetchError("transport", _bounded(e)) from None
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise _FredFetchError(
            "bad_body", f"HTTP success but the body was not JSON ({_bounded(e)})") from None
    if not isinstance(body, dict):
        raise _FredFetchError(
            "bad_body",
            f"HTTP success but the body was a JSON {_json_type_name(body)}, not an object")
    return body


def _fred_key_rejected_error(e: _FredFetchError) -> ToolError:
    """The credential arm, shared by both tools and both legs. AUTH_REQUIRED,
    not DATA_UNAVAILABLE and not a licensing lecture: FRED said the KEY is
    wrong. The key value itself never rides (`_bounded` scrubs it)."""
    return ToolError(
        ToolError.AUTH_REQUIRED,
        f"FRED rejected the FRED_API_KEY this client is configured with "
        f"(HTTP {e.status}: {e.detail}). This is a credential problem, not "
        f"missing data and not a licensing refusal: the client's operator "
        f"should check that FRED_API_KEY is a registered key "
        f"(fred.stlouisfed.org/docs/api/api_key.html) and not revoked."
        + _FRED_NO_ASK_OPERATOR)


def _fred_no_such_series_error(series: str) -> ToolError:
    """The id-typo arm (field-test F8, 2026-09-05), now reachable from FRED's
    real answer -- an HTTP 400 'The series does not exist' -- on either leg,
    not only from a 200 with `seriess: []`."""
    return ToolError(
        ToolError.INVALID_PARAMS,
        f"No FRED series with id '{series}' exists (FRED metadata lookup "
        f"returned no match). Check the series id -- this is an id problem, "
        f"not a licensing refusal.")


# ── argument parsing (before any URL is built) ───────────────────────────────

#: FRED series ids: letters, digits, '_', '.' and '-', 1-40 characters,
#: matched after upper-casing (FRED ids are case-insensitive). Every character
#: the rule admits is RFC 3986-unreserved, so a validated id survives
#: urllib.parse.quote unchanged -- which is why the quote on the observations
#: leg is belt-and-braces and the rule is the control.
_FRED_SERIES_ID_RULE = r"^[A-Za-z0-9_.-]{1,40}$"  # quoted verbatim in the refusal
_FRED_SERIES_ID_RE = re.compile(_FRED_SERIES_ID_RULE)
_FRED_DAYS_DEFAULT = 365
_FRED_DAYS_MIN = 1
#: ~100 years. FRED's oldest daily series start in the 1910s; anything past
#: this is an unbounded full-history pull under a number that looks like a
#: window, and a negative value used to put observation_start in the future.
_FRED_DAYS_MAX = 36500


def _shown(value) -> str:
    """A caller-supplied value, quoted and bounded, for an error message."""
    try:
        text = json.dumps(value, default=str)
    except (TypeError, ValueError):
        text = repr(value)
    return text if len(text) <= 60 else text[:60] + "..."


def _parse_fred_series(args) -> str:
    """`series`, validated against FRED's id charset BEFORE any URL exists.
    A rejected value never reaches the wire, the prefix allowlist or the
    verdict cache. Raises INVALID_PARAMS naming the parameter and the rule."""
    if not isinstance(args, dict) or "series" not in args or args["series"] is None:
        raise ToolError(
            ToolError.INVALID_PARAMS,
            "get_fred_data requires `series`: a FRED series id such as DGS10, "
            "CPIAUCSL or UNRATE.")
    raw = args["series"]
    if not isinstance(raw, str):
        raise ToolError(
            ToolError.INVALID_PARAMS,
            f"`series` must be a string FRED series id, got a JSON "
            f"{_json_type_name(raw)} ({_shown(raw)}).")
    series = raw.strip().upper()
    if not _FRED_SERIES_ID_RE.fullmatch(series):
        raise ToolError(
            ToolError.INVALID_PARAMS,
            f"`series` {_shown(raw)} is not a FRED series id. FRED ids are 1-40 "
            f"characters from A-Z, 0-9, '_', '.' and '-' (rule "
            f"{_FRED_SERIES_ID_RULE}, matched after upper-casing); nothing "
            f"else is sent to FRED.")
    return series


def _parse_fred_days(args) -> int:
    """`days`: an integer 1..36500 (calendar days back from today). Accepts
    an int, an integral float, or a digit string; rejects booleans (a JSON
    `true` is not a day count) and anything outside the bound -- BEFORE the
    metadata probe, so a bad value costs no FRED request."""
    value = args.get("days", _FRED_DAYS_DEFAULT) if isinstance(args, dict) else _FRED_DAYS_DEFAULT
    if value is None:
        value = _FRED_DAYS_DEFAULT
    n = None
    if isinstance(value, bool):
        n = None
    elif isinstance(value, int):
        n = value
    elif isinstance(value, float) and value.is_integer():
        n = int(value)
    elif isinstance(value, str) and re.fullmatch(r"\s*-?\d{1,9}\s*", value):
        n = int(value)
    if n is None or not (_FRED_DAYS_MIN <= n <= _FRED_DAYS_MAX):
        raise ToolError(
            ToolError.INVALID_PARAMS,
            f"`days` must be an integer from {_FRED_DAYS_MIN} to {_FRED_DAYS_MAX} "
            f"(calendar days back from today); got {_shown(value)}.")
    return n


def _parse_fred_bool(value, name: str) -> bool:
    """A boolean argument, parsed STRICTLY. `bool("false")` is True, which is
    how the JSON string "false" switched get_yield_curve's history ON
    (b02-fred-9). Accepts a JSON boolean, 0/1, or the strings
    true/false/1/0 (case-insensitive); anything else is INVALID_PARAMS."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        low = value.strip().lower()
        if low in ("true", "1"):
            return True
        if low in ("false", "0", ""):
            return False
    raise ToolError(
        ToolError.INVALID_PARAMS,
        f"`{name}` must be true or false (a JSON boolean, or the strings "
        f"'true'/'false'/'1'/'0'); got {_shown(value)}.")


# ── get_yield_curve ──────────────────────────────────────────────────────────

#: Trading days pulled per series when the caller asks for history. ~252 in a
#: year; 400 covers a year plus the slack for holidays and a stale tail without
#: a second request per series.
_YC_HISTORY_LIMIT = 400
#: Rows pulled per series WITHOUT history. Was 1: the newest cell of a DGS
#: series is '.' on a market holiday, so `limit=1` dropped the tenor on any
#: holiday and, on a day every tenor showed '.', reported the whole curve as
#: unfetchable (b02-fred-4). Five rows span a long weekend plus a holiday; the
#: first non-'.' row is served and `as_of` says which date that was.
_YC_LATEST_WINDOW = 5
#: How far a matched "a year ago" observation may sit from the 365-day target
#: before it is refused. A curve is only comparable against a real prior point;
#: silently pairing today against a value 5 months old would answer the
#: steepening question with a number that does not mean what it says.
_YC_LOOKBACK_TOLERANCE_DAYS = 45
#: The eleven tenors the description advertises ("1M through 30Y"), in order.
_YC_SERIES = {
    "1M": "DGS1MO", "3M": "DGS3MO", "6M": "DGS6MO",
    "1Y": "DGS1", "2Y": "DGS2", "3Y": "DGS3", "5Y": "DGS5",
    "7Y": "DGS7", "10Y": "DGS10", "20Y": "DGS20", "30Y": "DGS30",
}
#: Human wording for each per-tenor failure kind (the `_FredFetchError` kinds
#: plus the three the loop itself detects).
_YC_FAILURE_WORDING = {
    "http": "FRED answered an HTTP error",
    "transport": "FRED could not be reached",
    "bad_body": "FRED answered with an unreadable body",
    "no_observations": "FRED returned no observations",
    "latest_suppressed": "every recent observation is suppressed ('.')",
    "malformed": "FRED's value did not parse as a number",
}


def _yc_pick_year_ago(observations, latest_date):
    """The observation closest to one year before ``latest_date``, or None.

    ``observations`` is FRED's newest-first list. Returns None rather than the
    nearest available point when nothing lands within the tolerance -- a
    comparison against whatever happens to be oldest is worse than no
    comparison, because the caller cannot see how far off it is.
    """
    import datetime as _dt

    try:
        anchor = _dt.date.fromisoformat(latest_date) - _dt.timedelta(days=365)
    except (TypeError, ValueError):
        return None
    best, best_gap = None, None
    for o in observations:
        if not isinstance(o, dict) or o.get("value") in (None, ".", ""):
            continue
        try:
            d = _dt.date.fromisoformat(o.get("date", ""))
        except (TypeError, ValueError):
            continue
        gap = abs((d - anchor).days)
        if best_gap is None or gap < best_gap:
            best, best_gap = o, gap
    if best is None or best_gap > _YC_LOOKBACK_TOLERANCE_DAYS:
        return None
    return best


def _yc_failure_sentence(failed: dict) -> str:
    """One sentence grouping the missing tenors by WHY, e.g.
    '1M, 3M, 20Y, 30Y: FRED answered an HTTP error (HTTP 500: Internal
    Server Error)'. `failed` is {label: (kind, detail, status)}."""
    groups: dict[str, list] = {}
    for label, (kind, detail, _status) in failed.items():
        groups.setdefault((kind, detail), []).append(label)
    parts = []
    for (kind, detail), labels in groups.items():
        wording = _YC_FAILURE_WORDING.get(kind, kind)
        parts.append(f"{', '.join(labels)}: {wording}" + (f" ({detail})" if detail else ""))
    return "; ".join(parts)


def _yc_all_failed_error(failed: dict) -> ToolError:
    """No tenor could be read. Say WHICH failure it was (b02-fred-4): a
    rejected key never reaches here (it raises on the first tenor); the
    rest are told apart so an agent does not retry a holiday as if it were
    an outage, or report an outage as if the curve were gone."""
    total = len(_YC_SERIES)
    kinds = {kind for kind, _d, _s in failed.values()}
    statuses = {s for _k, _d, s in failed.values()}
    first_detail = next((d for _k, d, _s in failed.values() if d), "")
    if kinds == {"latest_suppressed"}:
        return ToolError(
            ToolError.DATA_UNAVAILABLE,
            f"FRED returned observations for all {total} tenors, but the newest "
            f"{_YC_LATEST_WINDOW} cells of every tenor are suppressed ('.'): the "
            f"latest observation window is unpublished (a market holiday or a "
            f"release gap), not a transport failure and not a statement that "
            f"the curve is gone. Retry after the next FRED release.")
    if kinds == {"transport"}:
        return ToolError(
            ToolError.DATA_UNAVAILABLE,
            f"Could not reach FRED for any of the {total} tenors (transport "
            f"failure: {first_detail}). Not a statement about the data; retry "
            f"later.")
    if kinds == {"http"} and statuses == {429}:
        return ToolError(
            ToolError.RATE_LIMITED,
            f"FRED rate-limited every one of the {total} tenor requests "
            f"(HTTP 429). Retry shortly.", retry_after=60)
    if kinds == {"http"}:
        return ToolError(
            ToolError.DATA_UNAVAILABLE,
            f"FRED answered an HTTP error for all {total} tenors "
            f"({first_detail}). Upstream unavailable, not a statement about "
            f"the data; retry later.")
    if kinds == {"no_observations"}:
        return ToolError(
            ToolError.DATA_UNAVAILABLE,
            f"FRED returned zero observations for all {total} tenors -- a "
            f"response-shape or window problem on FRED's side, not a "
            f"statement that the curve is gone.")
    if kinds == {"bad_body"}:
        return ToolError(
            ToolError.DATA_UNAVAILABLE,
            f"FRED answered every one of the {total} tenor requests with a body "
            f"that is not a JSON object ({first_detail}) -- a FRED response-"
            f"shape mismatch, not missing data.")
    return ToolError(
        ToolError.DATA_UNAVAILABLE,
        f"No tenor of the yield curve could be read from FRED -- "
        f"{_yc_failure_sentence(failed)}. Not a statement about the data.")


@mcp_tool(name="get_yield_curve", cache=FUNDAMENTAL)
def tool_get_yield_curve(args):
    """Get Treasury yield curve from FRED.

    include_history=true adds the same curve as of ~1 year ago, for
    steepening/inversion work.

    2026-08-11 (#30): this handler did not read `args` AT ALL, while its
    inputSchema declared `include_history`. The dispatcher's own contract
    (`_echo_params_accepted`, mcp_server.py) is deliberately named
    params_ACCEPTED rather than honored because a downstream hop can drop a
    value it validated -- and this was a live instance of exactly that gap: a
    caller passed include_history, saw it echoed as accepted, and got the
    current curve regardless. Closing it per-tool is what that docstring
    prescribes.

    History costs no extra REQUESTS. The same one-call-per-series loop asks for
    a wider window and reads both ends out of it, so the difference is response
    size rather than round trips.

    B1 (2026-09-12, b02-fred-4): per-tenor failures are TRACKED, not
    swallowed. Fewer than eleven tenors adds a `completeness` block
    ({maturities_total, maturities_missing, reason}) and a string `error`
    (so the dispatcher seam does not cache a partial curve for an hour); an
    all-fail run says which failure it was; a rejected key raises
    AUTH_REQUIRED on the first tenor instead of ten more identical requests.
    """
    fred_key = os.environ.get("FRED_API_KEY", "")
    if not fred_key:
        raise ToolError(ToolError.API_REQUIRED, "Set FRED_API_KEY environment variable for yield curve data")
    include_history = _parse_fred_bool(args.get("include_history", False), "include_history")
    limit = _YC_HISTORY_LIMIT if include_history else _YC_LATEST_WINDOW
    curve, year_ago, as_of = {}, {}, {}
    failed: dict = {}  # label -> (kind, detail, status)
    for label, sid in _YC_SERIES.items():
        url = (
            f"https://api.stlouisfed.org/fred/series/observations"
            f"?series_id={urllib.parse.quote(sid)}&api_key={fred_key}&file_type=json"
            f"&sort_order=desc&limit={limit}"
        )
        try:
            data = _fred_get_json(url)
        except _FredFetchError as e:
            if e.kind == "key_rejected":
                # Every tenor shares the key; the other ten would say the same.
                raise _fred_key_rejected_error(e)
            failed[label] = (e.kind, e.detail, e.status)
            continue
        obs = data.get("observations")
        if not isinstance(obs, list) or not obs:
            failed[label] = ("no_observations", "", None)
            continue
        # The newest USABLE row within the latest window (a holiday cell is
        # '.'); history is read from the rows below it.
        latest_idx = None
        for i, o in enumerate(obs[:_YC_LATEST_WINDOW]):
            if isinstance(o, dict) and o.get("value") not in (None, ".", ""):
                latest_idx = i
                break
        if latest_idx is None:
            failed[label] = ("latest_suppressed", "", None)
            continue
        latest = obs[latest_idx]
        try:
            curve[label] = float(latest["value"])
        except (TypeError, ValueError, KeyError):
            failed[label] = ("malformed", _bounded(latest.get("value")), None)
            continue
        as_of[label] = latest.get("date")
        if include_history:
            prior = _yc_pick_year_ago(obs[latest_idx + 1:], latest.get("date"))
            if prior:
                try:
                    year_ago[label] = float(prior["value"])
                except (TypeError, ValueError, KeyError):
                    pass  # ok-swallow: a malformed PRIOR cell leaves the tenor without a year-ago point, which history_coverage already counts; the current value is unaffected
    if not curve:
        raise _yc_all_failed_error(failed)
    out = {"yield_curve": curve, "as_of": as_of, "source": "FRED"}
    if include_history:
        # Emitted even when EMPTY, and that is deliberate: the caller asked for
        # history, so the key must be present to say it was applied. Omitting
        # it on a miss is indistinguishable from ignoring the parameter, which
        # is the bug being fixed.
        out["yield_curve_1y_ago"] = year_ago
        out["history_coverage"] = {
            "maturities_with_prior": len(year_ago),
            "maturities_total": len(curve),
            "lookback_tolerance_days": _YC_LOOKBACK_TOLERANCE_DAYS,
        }
    if len(curve) < len(_YC_SERIES):
        missing = [label for label in _YC_SERIES if label not in curve]
        out["completeness"] = {
            "maturities_total": len(_YC_SERIES),
            "maturities_missing": missing,
            "reason": (
                f"{len(missing)} of {len(_YC_SERIES)} tenors returned no usable "
                f"latest observation -- {_yc_failure_sentence(failed)}. The "
                f"curve is partial; a missing tenor is not a statement that "
                f"Treasury stopped publishing it."),
        }
        out["error"] = (
            f"partial yield curve: {len(missing)} of {len(_YC_SERIES)} tenors "
            f"missing ({', '.join(missing)}); see completeness.reason.")
    return out


# ── get_fred_data ────────────────────────────────────────────────────────────

# Third-party / copyrighted FRED-series carve-out (3.1.0; hardened FAIL-CLOSED per the
# 2026-07-21 CHAOS/DATA_CZAR/COUNSEL compliance review). FRED aggregates 800k+ series;
# U.S.-government series (BLS / BEA / Census / Federal Reserve / Treasury) are public
# domain and free to redistribute, but series from private commercial providers (S&P
# Dow Jones, ICE BofA, Moody's, CBOE, Nasdaq, FTSE Russell, University of Michigan,
# ...) are non-commercial-only and may not be redistributed commercially. This
# gov-public-data-only package refuses them. FAIL-CLOSED design:
#   * Hard deny FIRST (B1, CV-5): an id in `_FRED_KNOWN_THIRDPARTY` is refused
#     without a probe, so the eight ids the in-tree Board gate names never depend
#     on FRED's notes text carrying a licensor word.
#   * Primary: fetch /fred/series metadata; if `notes`/`title` shows any copyright or
#     named-licensor marker, REFUSE.
#   * If the metadata probe is UNAVAILABLE (network/quota), DO NOT guess-serve — serve
#     ONLY a series matching the known U.S.-gov source allowlist, else REFUSE.
#   * Cache ONLY authoritative metadata verdicts (never a probe-failure fallback), so a
#     transient blip can't poison-cache a carve-out series as clean; recovery self-heals.
import re as _re

# Copyright / third-party markers in the FRED notes/title (ASCII word, the (c) glyph,
# or a named commercial licensor) — catches reworded / empty-"copyright" attributions.
# 'michigan|surveys? of consumers' added 2026-09-12 (b02-fred-2): the University
# of Michigan Surveys of Consumers is the licensor the in-tree gate refuses as
# UMCSENT (the program's name is plural; FRED's notes have been seen singular).
#
# ANCHORED 2026-09-13 (deep audit f6-macro-events-8, FIX-BEFORE-PUBLISH): the
# bare words `michigan`, `russell` and `moody` refused PUBLIC-DOMAIN BLS series
# whose TITLE merely contains the word -- MIUR ("Unemployment Rate in
# Michigan"), KSRUSS0URN ("Unemployment Rate in Russell County, KS"), and any
# Moody County, SD series -- with a message asserting third-party copyright,
# a same-day regression of the b02-fred-2 remedy. The licensor markers are the
# LICENSOR'S NAME now: "University of Michigan" / "Survey(s) of Consumers",
# "FTSE Russell" / "Russell <index number>", "Moody's" (always possessive for
# the agency). The hard-deny roster (UMCSENT, MICH, ...) never depended on
# this regex and is unchanged. tests/test_mcp_fred_bls_title_not_licensor_
# contract.py drives MIUR / KSRUSS0URN through the verdict (served) beside
# UMCSENT and a Moody's-noted AAA (refused).
_FRED_THIRDPARTY_NOTE = _re.compile(
    "copyright|©|all rights reserved|s&p|dow jones|standard & poor|case-shiller|"
    "ice data|ice bofa|bofa merrill|moody['’]?s\\b|cboe|nasdaq omx|ftse|"
    "russell \\d|msci|bloomberg|"
    "university of michigan|surveys? of consumers",
    _re.IGNORECASE)
# Known U.S.-government / public-domain source prefixes — the allowlist used ONLY when
# the metadata probe is unavailable (everything else fails closed / refused).
# `MICH` REMOVED 2026-09-12 (b02-fred-2): it is University of Michigan Inflation
# Expectation -- the same non-government licensor as UMCSENT -- and sat here under
# "public-domain" from 3.1.0, so on a probe failure MICH and any MICH* id served
# while UMCSENT was refused. tests/test_mcp_fred_guards_contract.py pins the tuple
# disjoint from `_FRED_KNOWN_THIRDPARTY` so the two lists cannot disagree again.
_FRED_GOV_PREFIXES = (
    "DGS", "DFF", "FEDFUNDS", "SOFR", "GDP", "CPIAUCSL", "CPILFESL", "PCEPI", "UNRATE",
    "PAYEMS", "T10Y", "T5Y", "DTB", "TB3MS", "DFEDTAR", "DEXUS", "DEXJP", "DEXCH",
    "M1SL", "M2SL", "HOUST", "RSAFS", "INDPRO", "PPIACO", "RRPONTSYD", "WALCL")
# HARD DENY (B1 2026-09-12, COUNSEL CV-5 / F-6). The in-tree Board roster
# `data/market_data.py::_THIRD_PARTY_FRED_SERIES` (2026-07-21: six ICE BofA OAS
# series, VIXCLS, UMCSENT), COPIED here because the wheel is stdlib-only and may
# not import the monorepo; tests/test_mcp_fred_guards_contract.py reads the
# in-tree literal off the AST and pins this set as its superset. Plus the ids
# the 3.4.0 vet drove whose refusal otherwise depends on FRED's title/notes text
# carrying a licensor word. An id here is refused BEFORE any probe -- no
# request, nothing cached, the marker regex never consulted.
_FRED_KNOWN_THIRDPARTY = frozenset({
    "BAMLH0A0HYM2", "BAMLC0A0CM", "BAMLC0A1CAAA",   # ICE Data Indices, LLC (OAS)
    "BAMLH0A1HYBB", "BAMLH0A2HYB", "BAMLH0A3HYC",   # ICE Data Indices, LLC (OAS)
    "VIXCLS",                                        # CBOE (VIX index level)
    "UMCSENT",                                       # University of Michigan (Consumer Sentiment)
    # -- wheel-side additions, each measured in the 2026-09-12 vet --
    "MICH",       # University of Michigan: Inflation Expectation (b02-fred-2's misclassified id)
    "SP500",      # S&P Dow Jones Indices LLC (refused on title today; the title is not ours)
    "DJIA",       # S&P Dow Jones Indices LLC
    "NASDAQCOM",  # Nasdaq OMX Group (CV-5: served when the notes carry no copyright line)
    # -- 2026-09-22: the two ids the main repository's `FRED_RESALE_REFUSED`
    #    roster records that this file did not. Both are NAMED in that
    #    repository, neither was on any denylist, and both have a
    #    non-government copyright holder -- the exact state a publisher
    #    denylist over a caller-supplied id cannot surface. Refusing them here
    #    costs one frozenset entry and removes the dependence on FRED's notes
    #    text happening to carry a licensor word.
    "MORTGAGE30US",  # Freddie Mac (Primary Mortgage Market Survey) -- a GSE, not
                     # a U.S. Government work under 17 USC 105
    "AAA",           # Moody's (Seasoned Aaa Corporate Bond Yield)
})
#: CLEARED FOR REDISTRIBUTION -- the reviewed public-domain roster, COPIED from
#: the main repository's `FRED_RESALE_SERIES_ALLOWLIST` (2026-09-22) because the
#: wheel is stdlib-only and may not import it. Every id below carries a named
#: U.S.-federal publisher and a recorded public-domain rationale over there; the
#: publishers are the comment headings here. The main repository's wheel-roster
#: contract AST-reads that literal and pins this set against it in BOTH
#: directions, so the two copies cannot drift the way this file's deny roster
#: and the in-tree Board roster once did.
#:
#: WHAT IT DOES, precisely, and what it deliberately does NOT do:
#:   * it CLEARS. An id here serves when the metadata probe is unavailable (the
#:     `_FRED_GOV_PREFIXES` fallback is a prefix heuristic and misses eight of
#:     these: JTSJOL, PCE, PSAVERT, TOTALSA, PERMIT, DGORDER, ICSA, DTWEXBGS),
#:     and the marker regex cannot refuse it -- a reviewed entry naming a
#:     federal statistical program outranks a word match over FRED's free text,
#:     which is the same false-positive class the 2026-09-13 anchoring fix
#:     closed for MIUR / KSRUSS0URN.
#:   * it does NOT become the only way to serve. An id that is neither here nor
#:     on the hard-deny roster is still decided by the probe, exactly as before.
#:     Enumerating every public-domain FRED series is not possible -- FRED
#:     carries 800k+ -- so a fail-closed-to-this-roster `get_fred_data` would
#:     refuse most of the U.S. statistical system to save the tail this probe
#:     already covers. The residual is named in the changelog rather than
#:     hidden: for an id outside both rosters this package still runs a
#:     denylist over FRED's own notes.
_FRED_RESALE_ALLOWLIST = frozenset({
    # -- U.S. Bureau of Labor Statistics --
    "CPIAUCSL", "CPILFESL", "UNRATE", "PAYEMS", "JTSJOL", "PPIACO",
    # -- U.S. Bureau of Economic Analysis --
    "GDP", "GDPC1", "PCE", "PCEPILFE", "PSAVERT", "TOTALSA",
    # -- U.S. Census Bureau --
    "HOUST", "PERMIT", "DGORDER", "RSAFS",
    # -- U.S. Employment and Training Administration --
    "ICSA",
    # -- Board of Governors of the Federal Reserve System --
    "DGS1MO", "DGS3MO", "DGS6MO", "DGS1", "DGS2", "DGS3", "DGS5", "DGS7",
    "DGS10", "DGS20", "DGS30", "FEDFUNDS", "DFF", "INDPRO", "M2SL", "WALCL",
    "DTWEXBGS",
    # -- Federal Reserve Bank of St. Louis (arithmetic on the H.15 / TIPS legs) --
    "T10Y2Y", "T10Y3M", "T5YIE", "T10YIE", "T5YIFR",
    # -- Federal Reserve Bank of New York --
    "SOFR",
})
_fred_thirdparty_cache: dict[str, str] = {}
#: Series metadata kept from a successful probe, keyed by id:
#: {"name": title, "units", "frequency"}. Emitted by get_fred_data (b02-fred-6).
_fred_series_meta_cache: dict[str, dict] = {}


def _fred_series_is_thirdparty(series: str, key: str) -> str:
    """Fail-closed verdict: "thirdparty" (confirmed copyright, or a hard-deny
    roster id -- no probe), "unknown" (FRED's own metadata endpoint
    authoritatively says no such series -- an id typo, NOT a licensing
    case), "unverifiable" (probe down; only known-gov prefixes serve), or ""
    (clear to serve). Only authoritative FRED-metadata verdicts are cached.
    2026-09-05 (field-test F8): a typo'd id used to receive the third-party
    licensing refusal -- confusing and wrong; the split never weakens
    fail-closed (unknown requires FRED itself confirming nonexistence).

    B1 (2026-09-12, b02-fred-3): FRED confirms nonexistence with an HTTP 400
    'The series does not exist' -- the branch a 200 `seriess: []` was
    written for is one FRED most likely never takes -- and answers an
    unregistered key with the SAME status. Both used to be 'probe
    unavailable'. Now the body decides: nonexistence -> "unknown" (cached);
    a rejected key RAISES AUTH_REQUIRED (a credential problem is not a
    licensing verdict); transport / 5xx / 429 stay on the fail-closed path.

    2026-09-22: `_FRED_RESALE_ALLOWLIST` (the reviewed public-domain roster)
    is consulted AFTER the hard deny and BEFORE anything FRED says. Order is
    the whole design: deny beats clearance, clearance beats the notes-text
    heuristic, and the heuristic still decides everything on neither roster.
    The probe still RUNS for a cleared id -- `name` / `units` / `frequency`
    come from it -- it just cannot produce a licensing refusal for one.
    """
    s = (series or "").upper()
    if s in _FRED_KNOWN_THIRDPARTY:
        return "thirdparty"
    if s in _fred_thirdparty_cache:
        return _fred_thirdparty_cache[s]
    url = (f"https://api.stlouisfed.org/fred/series"
           f"?series_id={urllib.parse.quote(s)}&api_key={key}&file_type=json")
    rows = None  # probe unavailable until FRED answers authoritatively
    try:
        body = _fred_get_json(url)
    except _FredFetchError as e:
        if e.kind == "key_rejected":
            raise _fred_key_rejected_error(e)
        if e.kind == "no_such_series":
            rows = []  # FRED itself says the series does not exist
    else:
        seriess = body.get("seriess")
        if isinstance(seriess, list):
            rows = seriess
    if rows is not None:
        # Authoritative FRED answer -> cache it.
        if rows:
            row = rows[0] if isinstance(rows[0], dict) else {}
            meta = (row.get("notes") or "") + " " + (row.get("title") or "")
            # A CLEARED id is not refusable by a word match over FRED's free
            # text: the roster entry was reviewed against the publisher, the
            # regex is a heuristic over prose we do not write, and the
            # heuristic's false positives are a measured class (MIUR,
            # KSRUSS0URN -- public-domain BLS series whose TITLE carries a
            # licensor's word). The hard deny above still outranks both.
            verdict = ("thirdparty"
                       if (_FRED_THIRDPARTY_NOTE.search(meta)
                           and s not in _FRED_RESALE_ALLOWLIST)
                       else "")
            _fred_series_meta_cache[s] = {
                "name": row.get("title"),
                "units": row.get("units"),
                "frequency": row.get("frequency"),
            }
        else:
            verdict = "unknown"  # FRED itself says the series does not exist
        _fred_thirdparty_cache[s] = verdict
        return verdict
    # Probe unavailable: FAIL CLOSED. Serve ONLY a series this package has
    # already cleared -- a reviewed roster entry, or the known U.S.-gov prefix
    # heuristic -- and refuse the rest. The roster is the exact half: it admits
    # the eight cleared ids no prefix covers (JTSJOL, PCE, PSAVERT, TOTALSA,
    # PERMIT, DGORDER, ICSA, DTWEXBGS), which used to read "unverifiable" on a
    # FRED outage. Do NOT cache (so a recovered probe re-decides
    # authoritatively next time).
    if s in _FRED_RESALE_ALLOWLIST or s.startswith(_FRED_GOV_PREFIXES):
        return ""
    return "unverifiable"


@mcp_tool(name="get_fred_data", cache=FUNDAMENTAL)
def tool_get_fred_data(args):
    """Get FRED economic data series (U.S.-government / public-domain series only).

    Returns {series, name, units, frequency, data[{date, value}] newest-first,
    count[, note]}. `name` / `units` / `frequency` come from FRED's series
    metadata and are null when the metadata probe was unavailable. An empty
    window carries a plain-string `note` saying so (never a bare `data: []`).
    """
    fred_key = os.environ.get("FRED_API_KEY", "")
    if not fred_key:
        raise ToolError(ToolError.API_REQUIRED, "Set FRED_API_KEY environment variable for FRED data")
    # Arguments first, BEFORE any URL is built or any FRED request is spent
    # (b02-fred-1, -8, -10): a rejected value never reaches the wire.
    series = _parse_fred_series(args)
    days = _parse_fred_days(args)
    _verdict = _fred_series_is_thirdparty(series, fred_key)
    if _verdict == "unknown":
        raise _fred_no_such_series_error(series)
    if _verdict == "unverifiable":
        raise ToolError(
            ToolError.INVALID_PARAMS,
            f"FRED series '{series}' could not be verified against FRED metadata "
            f"(probe unavailable) and is not a known U.S.-government series. This "
            f"package fails closed on licensing: only confirmed public-domain "
            f"series serve. Retry later, or use a known gov series (DGS10, "
            f"CPIAUCSL, UNRATE, ...).")
    if _verdict:
        raise ToolError(
            ToolError.INVALID_PARAMS,
            f"FRED series '{series}' carries third-party (non-U.S.-government) copyright "
            f"(e.g. S&P Dow Jones Indices, ICE BofA, Moody's, CBOE, University of "
            f"Michigan) and is licensed for non-commercial use only. This "
            f"gov-public-data package does not serve it. Use a U.S.-government series "
            f"(BLS / BEA / Census / Federal Reserve / Treasury), or license the data "
            f"directly from the copyright holder.")
    from datetime import datetime, timedelta
    now = datetime.now()
    start_date = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = now.strftime("%Y-%m-%d")
    url = (
        f"https://api.stlouisfed.org/fred/series/observations"
        f"?series_id={urllib.parse.quote(series)}&api_key={fred_key}&file_type=json"
        f"&observation_start={start_date}&sort_order=desc"
    )
    try:
        data = _fred_get_json(url)
    except _FredFetchError as e:
        # The same discrimination as the probe leg (b02-fred-3), mirrored.
        if e.kind == "key_rejected":
            raise _fred_key_rejected_error(e)
        if e.kind == "no_such_series":
            raise _fred_no_such_series_error(series)
        if e.kind == "transport":
            raise ToolError(
                ToolError.DATA_UNAVAILABLE,
                f"Could not reach FRED for '{series}' (transport failure: "
                f"{e.detail}). Not a statement about the series; retry later.")
        if e.kind == "bad_body":
            raise ToolError(
                ToolError.DATA_UNAVAILABLE,
                f"FRED answered for '{series}' with {e.detail} -- no observations "
                f"could be read from it, and that is not a statement that the "
                f"series has no data.")
        if e.status == 429:
            raise ToolError(
                ToolError.RATE_LIMITED,
                f"FRED rate-limited the request for '{series}' (HTTP 429). Retry shortly.",
                retry_after=60)
        raise ToolError(
            ToolError.DATA_UNAVAILABLE,
            f"FRED data fetch failed for '{series}': {e.detail}. Upstream "
            f"unavailable, not a statement about the series; retry later.")
    try:
        obs = data.get("observations")
        if not isinstance(obs, list):
            raise ToolError(
                ToolError.DATA_UNAVAILABLE,
                f"FRED answered for '{series}' with an object carrying no "
                f"`observations` list (got a JSON {_json_type_name(obs)}) -- a "
                f"FRED response-shape mismatch, not a statement that the series "
                f"has no data.")
        points = []
        suppressed = 0
        for o in obs:
            if not isinstance(o, dict):
                continue
            value = o.get("value")
            if value in (None, ".", ""):
                suppressed += 1
                continue
            try:
                points.append({"date": o.get("date"), "value": float(value)})
            except (TypeError, ValueError):
                suppressed += 1
        meta = _fred_series_meta_cache.get(series) or {}
        out = {
            "series": series,
            "name": meta.get("name"),
            "units": meta.get("units"),
            "frequency": meta.get("frequency"),
            "data": points,
            "count": len(points),
        }
        if not points:
            frequency = meta.get("frequency")
            if suppressed:
                out["note"] = (
                    f"FRED returned {suppressed} observation(s) for {series} between "
                    f"{start_date} and {end_date} but every value is suppressed "
                    f"('.'); not a statement that the series has no data -- widen "
                    f"`days`.")
            else:
                out["note"] = (
                    f"no observations for {series} between {start_date} and "
                    f"{end_date}; not a statement that the series has no data"
                    + (f" (FRED lists the series frequency as '{frequency}'; a "
                       f"window shorter than one period is empty by construction)"
                       if frequency else "")
                    + " -- widen `days`.")
        return out
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(ToolError.DATA_UNAVAILABLE, f"FRED data fetch failed for '{series}': {_scrub_fred_key(str(e))}")
