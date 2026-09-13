"""oxford_ledge_mcp/transport.py -- the wheel's HTTP transport: the REST
proxy (`_api_get`), the hosted name-proxy bridge (`_api_tool_call` and its
keyed / keyless legs), the K-2 error translation, and the disclosure
literals every success carries.

EXTRACTED VERBATIM from server.py on 2026-09-12 (the 3.4.0 publish-vet fix
wave, wave C). server.py sat at 2,159 lines against the file-size-budget
gate's 2,000-line threshold (the file-size gate and the wheel's pair pin,
both in the main repo) after the wave-B seam
builder added ~650 lines to the dispatcher and this block. The gate's own
instruction is "fix at the ROOT, never rebaseline", so this is a cut, not a
budget entry -- the same discipline as the 2026-09-08 `server_tools.py` cut
and the same-day FRED / SEC family cuts (fred_tools.py, sec_tools.py,
sec_fundamentals.py).

WHAT MOVED (one contiguous block, server.py lines 297-866 at HEAD e547ecc5,
in this order): `_UPSTREAM_TEXT_CAP`, `_excerpt`, `_is_loopback_host`,
`_authenticated_request`, `_parse_json_body`, `_api_get`,
`_api_error_sentence`, the hosted name-proxy banner, `_OL_ATTRIBUTION`,
`_OL_DISCLAIMER`, `_NO_ASK_OPERATOR`, `_HOSTED_TOOL_ERROR_CODES`,
`_VERSION_SKEW_MSG`, `_hosted_error_to_tool_error`, `_read_http_error_body`,
`_http_retry_after`, `_nonblank`, `_attach_disclosure`, `_api_tool_call`,
`_api_tool_call_keyed`, `_api_tool_call_keyless`. No `@mcp_tool` lives in
the block, so TOOL_DISPATCH insertion order is untouched by construction
(the family-cut contract in the main repo still pins it). Error
text, status ladders, header handling and the disclosure literals are
byte-identical to the pre-cut file.

THE ONE THING THAT IS NOT VERBATIM, stated so nobody re-derives it. An AST
free-name walk over the block (run before the cut, not assumed) found
exactly two names from server.py's own substrate: the env-derived
`_API_URL` and `_API_KEY`. Those STAY in server.py, because every driver
contract sets them on the server module after import
(`S._API_KEY = "KEY"`, `S._API_URL = url` -- the dispatch-seam, moat-
promotion, 404-semantics and empty-list-envelope drivers in the main
repo) and
expects the transport to see the new value. So the five functions that
read them (`_authenticated_request`, `_api_get`, `_api_tool_call`,
`_api_tool_call_keyed`, `_api_tool_call_keyless`) each open with
`from oxford_ledge_mcp import server as _S` and read `_S._API_URL` /
`_S._API_KEY` at CALL time -- twelve identifier sites, never bound at
import, so a value set on `S` after import is the value the wire sees
(proved by execution in the family-cut contract, not assumed). The other
free names are stdlib (`json`, `urllib`), `oxford_ledge_mcp_core`
(`ToolError`, `non_object_tool_error`) and the `oxford_ledge.mcp` logger,
which `logging.getLogger` hands back as the same object server.py holds.

That lazy import is the one place a wheel module reaches back into
server.py. It runs inside a function body only, after server.py has
finished importing this module, so there is no import cycle; the
family-cut contract's "never imports the server" rule applies to the three
HANDLER modules and deliberately not to this one, and pins the lazy shape
here instead (a module-top `from oxford_ledge_mcp import server` is a red).

RE-EXPORT RULE. server.py re-exports every name above, public and private,
at the EXACT source position the block occupied, so
`oxford_ledge_mcp.server.<name>` keeps resolving and -- the load-bearing
half -- every @mcp_tool handler that stayed in server.py still calls
`_api_get` / `_api_tool_call` through server.py's own globals. That is what
keeps `S._api_get = lambda ...` in the existing drivers LIVE for the
handlers. What it does NOT cover: a call made INSIDE this module
(`_api_tool_call` -> `_api_tool_call_keyed`, `_api_get` ->
`_authenticated_request`, either leg -> `_hosted_error_to_tool_error` /
`_attach_disclosure`) resolves in THIS module's globals. A test that wants
to intercept one of those internal hops must patch
`oxford_ledge_mcp.transport.<name>`; the re-export in server.py is a
second binding the code here never reads. (Measured at the cut: no
existing contract patched an internal hop on `S`; they patch `_api_get`
itself, or `urllib.request.urlopen`, which is the shared module this file
reads too.)

stdlib + oxford_ledge_mcp_core (+ the call-time server read above); ships
in the wheel (the publish exporter collects it; the manifest contract's
file-size pair pin names it).
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request

from oxford_ledge_mcp_core import ToolError
from oxford_ledge_mcp_core.errors import non_object_tool_error

# The same logger object server.py holds (`logging.getLogger` is keyed by
# name); the one debug line in `_read_http_error_body` reads it.
_logger = logging.getLogger("oxford_ledge.mcp")


# ── API proxy helper ──────────────────────────────────────────────────────────

# CISO-6 (3.4.0 vet): ONE cap for every interpolation of UPSTREAM text into a
# ToolError message (it was 500 / 64KB / unbounded depending on the branch,
# so a hostile OXFORD_LEDGE_URL could put a 30KB instruction in a sentence
# the model reads). Every branch below goes through `_excerpt`.
_UPSTREAM_TEXT_CAP = 500


def _excerpt(text):
    """Bound upstream text (characters) before it enters an error message."""
    s = text if isinstance(text, str) else ("" if text is None else str(text))
    return s[:_UPSTREAM_TEXT_CAP]


def _is_loopback_host(url):
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return host in ("localhost", "::1") or host.startswith("127.")


def _authenticated_request(url, data=None, headers=None):
    """The urllib Request for a call that carries the operator's key.

    CISO-3 (3.4.0 vet, measured): `HTTPRedirectHandler.redirect_request`
    copies every REGULAR header onto the redirected request, so a 3xx from
    the configured host to any other host forwarded `x-api-key` there.
    `add_unredirected_header` is the urllib API that keeps it off a redirect
    (`requests` strips Authorization on a host change; urllib strips
    nothing). The key also never travels over plain `http://` to a
    non-loopback host: sending it would be cleartext, sending WITHOUT it
    would silently downgrade a paying operator to anonymous (MONETIZE-2), so
    the call is refused loudly. http://localhost:10000 (README) stays fine.
    """
    from oxford_ledge_mcp import server as _S  # call-time read: tests set S._API_URL / S._API_KEY
    hdrs = {"User-Agent": "OxfordLedgeMCP/1.0"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs)
    if _S._API_KEY:
        if urllib.parse.urlsplit(url).scheme == "http" and not _is_loopback_host(url):
            raise ToolError(
                ToolError.API_REQUIRED,
                "OXFORD_LEDGE_URL is a plain http:// address that is not "
                "loopback, and OXFORD_LEDGE_API_KEY is set: the key would "
                "travel in the clear, so this call is refused. The client's "
                "operator should point OXFORD_LEDGE_URL at https:// (or a "
                "localhost instance) or unset the key." + _NO_ASK_OPERATOR)
        # Authenticates + meters the call against the key's account (#120/#121).
        req.add_unredirected_header("x-api-key", _S._API_KEY)
    return req


def _parse_json_body(raw, where):
    """Decode + parse an HTTP-success body, or raise DATA_UNAVAILABLE.

    b08-7 / b10-5 (3.4.0 vet): JSONDecodeError is a ValueError, it escaped
    the HTTPError/URLError handlers on all three legs, and the dispatcher
    relabelled it INVALID_PARAMS "Expecting value: line 1 column 1" -- the
    model was told its ARGUMENTS were wrong when an HTML challenge page was.
    """
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ToolError(
            ToolError.DATA_UNAVAILABLE,
            f"{where} answered HTTP 200 with a body that is not JSON "
            f"({len(raw)} bytes) -- a transport/edge problem (a proxy or "
            f"challenge page), not your arguments. Retry later rather than "
            f"changing arguments.")


def _api_get(path, params=None, timeout=15):
    """Make a GET request to the Oxford Ledge API."""
    from oxford_ledge_mcp import server as _S  # call-time read: tests set S._API_URL / S._API_KEY
    if not _S._API_URL:
        raise ToolError(
            ToolError.API_REQUIRED,
            "This tool requires a running Oxford Ledge instance. "
            "Set the OXFORD_LEDGE_URL environment variable "
            "(e.g. OXFORD_LEDGE_URL=https://www.oxfordledge.com)."
        )
    url = f"{_S._API_URL}{path}"
    if params:
        qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items() if v is not None)
        if qs:
            url += f"?{qs}"
    req = _authenticated_request(url)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        body = ""
        raw_body = ""
        try:
            # 3.2.0 vet K-7: parse-before-truncate. The 404 discriminator
            # below json-parses this; truncating FIRST made any envelope
            # over 500 bytes unparseable and mislabelled a data-level 404
            # as a version mismatch (the exact bug the discriminator
            # fixed, resurfacing on large bodies). Read bounded (64KB),
            # parse the full read, truncate only what gets DISPLAYED.
            raw_body = e.read(65536).decode("utf-8", "replace")
            body = _excerpt(raw_body)
        except Exception:
            pass
        # MONETIZE-2 (#121): give the AGENT an error it can act on. Every failure
        # here used to read DATA_UNAVAILABLE — so a 402 (this account's tier does
        # not include the tool) and a 401 (no/!valid key) both told the model "the
        # data isn't available", which is false and un-actionable: the model
        # retried, or told the user the filing didn't exist. Payment and auth are
        # not data problems.
        # 2026-08-11: every credential message below names the OPERATOR as the
        # source and forbids soliciting one in chat. These read as instructions
        # to the caller, and the caller is a MODEL -- on the hosted twin an
        # agent hit the sibling of this message and asked its human to paste "an
        # X-API-Key or an OAuth bearer credential" into the conversation. That
        # is phishing-shaped even when the error is honest, and it trains users
        # to put secrets in a chat box. Credentials here are env vars set once
        # in the client's own config; the end user is never the right source.
        _NO_ASK = (" DO NOT ASK THE USER TO PASTE A KEY OR TOKEN INTO THE "
                   "CONVERSATION -- it is an environment variable the client's "
                   "operator sets, and a credential sent in chat is a security "
                   "problem, not a fix.")
        if e.code == 402:
            raise ToolError(
                ToolError.AUTH_REQUIRED,
                "This tool requires a paid Oxford Ledge tier. "
                + ("Your API key's plan does not include it — see "
                   "https://www.oxfordledge.com/pricing."
                   if _S._API_KEY else
                   # SF-MCP-CONNECT-HOWTO T7 / C-12 (2026-09-13): /account does
                   # not exist; the key lives at /?view=settings under YOUR API
                   # KEYS -- the same sentence the hosted anon-tool refusal
                   # carries (routes_mcp_public_fastapi.py).
                   "The client's operator sets OXFORD_LEDGE_API_KEY (keys are "
                   "created at https://www.oxfordledge.com/?view=settings under "
                   "YOUR API KEYS; there is no /account page) — without "
                   "one this client is anonymous and only the free public-data "
                   "tools work.")
                + _NO_ASK,
            )
        if e.code in (401, 403):
            raise ToolError(
                ToolError.AUTH_REQUIRED,
                "Oxford Ledge rejected the credentials for this tool "
                f"({e.code}). The client's operator should check "
                "OXFORD_LEDGE_API_KEY is set and not revoked." + _NO_ASK,
            )
        if e.code == 429:
            retry_after = None
            try:
                retry_after = int(e.headers.get("Retry-After") or 0) or None
            except Exception:
                pass
            raise ToolError(
                ToolError.RATE_LIMITED,
                "Oxford Ledge rate limit reached for this key.",
                retry_after=retry_after,
            )
        if e.code == 404:
            # Same reasoning that earned 402 its own code: a 404 on a path is
            # a client/server version mismatch (developer bug), not "the data
            # doesn't exist" — never launder it as DATA_UNAVAILABLE.
            #
            # 2026-08-11: but the server uses 404 for BOTH. A route answers
            # 404 through the unified error envelope when a FILTER matched
            # nothing (the envelope helper REWRITES unmatched messages to a
            # status-code default, so the agent sees generic no-data text,
            # not the route's literal -- 3.2.0 vet K-7 corrected the account
            # here that claimed otherwise), so a
            # perfectly-routed call with an unknown `category` was reported to
            # the agent as "this endpoint does not exist" — and the directive
            # below ("report it rather than retrying") steered it AWAY from the
            # one correct recovery, which was to try another category. Two
            # individually-defensible decisions producing a confident lie.
            #
            # Discriminate on the BODY, which is unambiguous: our own handlers
            # emit the unified envelope {error, message, status, request_id}
            # (the server's shared error-envelope helper), whereas an unrouted path
            # gets FastAPI's default {"detail": "Not Found"}. A data-level 404
            # therefore carries `error` + `status`; a routing 404 does not.
            _envelope = None
            try:
                _parsed = json.loads(raw_body)
                if isinstance(_parsed, dict) and "error" in _parsed \
                        and "status" in _parsed:
                    _envelope = _parsed
            except Exception:
                _envelope = None
            if _envelope is not None:
                # Routed fine; the FILTER matched nothing. Actionable by
                # changing arguments, so it must not read as a broken build.
                raise ToolError(
                    ToolError.DATA_UNAVAILABLE,
                    f"No data matched this request: "
                    f"{_excerpt(_envelope.get('message') or _envelope.get('error'))} "
                    f"(the endpoint exists and responded — adjust the "
                    f"arguments, e.g. a different category/filter value, "
                    f"rather than reporting a version mismatch).",
                )
            raise ToolError(
                ToolError.NOT_FOUND,
                f"HTTP 404 for {path} — this endpoint does not exist on the "
                "server. Likely a package/API version mismatch, not missing "
                "data; report it rather than retrying other tickers.",
            )
        if e.code in (400, 422):
            # 3.4.0 publish vet b03-3 / b03-18: a 400 ("No ticker provided")
            # or a pydantic 422 (max_holdings above the route's cap) is the
            # CALLER's arguments being refused -- INVALID_PARAMS, so the
            # model changes them instead of reporting the data missing. The
            # route's own sentence rides along, bounded.
            raise ToolError(
                ToolError.INVALID_PARAMS,
                f"Oxford Ledge rejected the arguments (HTTP {e.code}): "
                f"{_excerpt(_api_error_sentence(raw_body) or body)}")
        if e.code == 503:
            # The pool-exhausted refusal (api_errors PgPoolExhausted) sets
            # Retry-After; it is a transient capacity condition, not a data
            # one, and the header is the one actionable thing about it.
            raise ToolError(
                ToolError.DATA_UNAVAILABLE,
                f"Oxford Ledge is temporarily unavailable (HTTP 503): "
                f"{_excerpt(_api_error_sentence(raw_body) or body)}",
                retry_after=_http_retry_after(e))
        raise ToolError(ToolError.DATA_UNAVAILABLE, f"API returned {e.code}: {body}")
    except urllib.error.URLError as e:
        raise ToolError(ToolError.DATA_UNAVAILABLE, f"Cannot reach Oxford Ledge API at {_S._API_URL}: {_excerpt(e.reason)}")
    return _parse_json_body(raw, f"GET {path}")


def _api_error_sentence(raw_body):
    """The route's own `message` / `error` string from a unified error
    envelope, or "" when the body is not one (a pydantic 422 `detail` list
    is rendered as its first message)."""
    try:
        parsed = json.loads(raw_body)
    except Exception:
        return ""
    if not isinstance(parsed, dict):
        return ""
    for k in ("message", "error"):
        v = parsed.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    detail = parsed.get("detail")
    if isinstance(detail, list) and detail and isinstance(detail[0], dict):
        loc = ".".join(str(x) for x in (detail[0].get("loc") or []) if x != "query")
        msg = detail[0].get("msg")
        if isinstance(msg, str):
            return f"{loc}: {msg}" if loc else msg
    if isinstance(detail, str):
        return detail.strip()
    return ""


# ── Hosted-MCP name-proxy helper (2026-09-05 moat promotion) ─────────────────
# The 2026-09-05 moat-promotion vet (in the main repository's board audits)
# is the spec for everything in this block. The three promoted ol_bdc_* tools are
# THIN NAME-PROXIES: the pip handler POSTs {"tool": <hardcoded literal>,
# "arguments": ...} to the hosted MCP dispatch and returns the unwrapped,
# emit-allowlisted result. The hosted gate chain (cleancore boundary, tier
# gate, rate limit, artifact filters) is inherited by construction.

# L-3 disclosure parity: the same two literals the hosted /mcp transport
# attaches in _meta on every success (routes_a2a_fastapi A2A_ATTRIBUTION /
# A2A_DISCLAIMER — the CLEANCORE vet 2026-08-12 blocking condition 2). The
# keyless leg PASSES the hosted _meta through; the keyed REST envelope
# carries neither, so the package attaches the same literals itself.
# _ENVELOPE_KEYS admits both, so the fail-closed filter cannot strip them.
_OL_ATTRIBUTION = (
    "Values derived by Oxford Ledge must be attributed to Oxford Ledge "
    "(oxfordledge.com) when restated to an end user."
)
_OL_DISCLAIMER = "Educational information only. Not investment advice."

# C-3: the _NO_ASK anti-phishing convention (see _api_get) applies to any
# new credential-flavored message on this path too.
_NO_ASK_OPERATOR = (
    " DO NOT ASK THE USER TO PASTE A KEY OR TOKEN INTO THE CONVERSATION -- "
    "it is an environment variable the client's operator sets, and a "
    "credential sent in chat is a security problem, not a fix."
)

# K-2: the hosted /api/mcp/tool refusal codes that are SAME-NAMED in this
# package's ToolError taxonomy (routes_admin_fastapi/mcp.py
# _TOOL_ERROR_STATUS keys). Translation is keyed on the BODY's `code`
# field, message verbatim (single wrap) — deliberately NOT _api_get's
# HTTPError discriminator ladder, which mislabels the unknown-tool 404
# as DATA_UNAVAILABLE-adjust-your-arguments (the vet's K-2 evidence).
_HOSTED_TOOL_ERROR_CODES = frozenset({
    ToolError.AUTH_REQUIRED, ToolError.INVALID_PARAMS, ToolError.RATE_LIMITED,
    ToolError.DATA_UNAVAILABLE, ToolError.TIMEOUT, ToolError.CACHE_MISS,
})

_VERSION_SKEW_MSG = (
    "The hosted catalog does not know this tool -- likely a package/server "
    "version skew, not missing data. Update the oxford-ledge-mcp package "
    "(or report the mismatch) rather than retrying other arguments."
)


#: The host's `error` field is sometimes a bare CODE TOKEN (`tier_required`
#: from routes/api_errors.py's TierGateException handler) with the human
#: sentence in `message`. A token is a word for machines; the sentence is
#: what a model may read out (f8-transport-errors-1).
_BARE_CODE_TOKEN = re.compile(r"^[a-z][a-z0-9_]*$")

#: Where plans are sold; the host's `upgrade_url` is a path on this origin
#: (routes/api_errors.py: "/pricing"). Same literal the REST leg's 402 branch
#: has used since MONETIZE-2.
_OL_PUBLIC_ORIGIN = "https://www.oxfordledge.com"
_OL_KEYS_URL = _OL_PUBLIC_ORIGIN + "/?view=settings"


_TIER_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,39}")
_UPGRADE_PATH_RE = re.compile(r"/[A-Za-z0-9_\-.?=&/]{0,80}")


def _tier_token(value, default="a higher"):
    """A tier name the host sent, or the generic phrase: a short plain token
    only, never a sentence (DELTA re-vet CISO-5)."""
    s = str(value or "").strip()
    return s if s and _TIER_TOKEN_RE.fullmatch(s) else default


def _tier_refusal_message(body, keyed):
    """The sentence for a hosted TIER refusal (f8-transport-errors-1 /
    d2-wheel-prose-5, 2026-09-13 deep audit).

    Before this, the keyed leg served the code word `tier_required` followed
    by the anti-phishing "DO NOT ASK THE USER TO PASTE A KEY" text -- the
    tier name, the host's sentence and the upgrade URL were all dropped, and
    the remedy the message implied (check the key) was wrong: the key is
    VALID, the plan behind it is what is missing. The keyless leg said
    "This tool requires the plus tier. Upgrade at oxfordledge.com/pricing."
    and never mentioned that a paying subscriber gets exactly this refusal
    until the operator sets OXFORD_LEDGE_API_KEY. Both legs now build the
    sentence from what the host sent (`requiredTier`, `currentTier`,
    `upgrade_url`, `message`) and say which of the two things -- key or plan
    -- is missing. `keyed` is passed by the leg; this function never reads
    the key (vet C-3: the translator is credential-free)."""
    # 2026-09-13 (DELTA re-vet CISO-5): the host's `upgrade_url` used to be
    # rendered VERBATIM when it started with "http", and the tier strings
    # unbounded -- a compromised or misdirected host (OXFORD_LEDGE_URL
    # pointed elsewhere) could put a foreign URL or an instruction sentence
    # into the model's context through a 402. The upgrade destination is
    # now always a PATH on Oxford Ledge's own origin, and a tier name is a
    # short plain token or the generic phrase.
    tier = _tier_token(body.get("requiredTier"))
    current = _tier_token(body.get("currentTier"), default="")
    path = str(body.get("upgrade_url") or "/pricing").strip()
    if "//" in path or not _UPGRADE_PATH_RE.fullmatch(path):
        path = "/pricing"   # a protocol-relative or foreign URL never renders
    upgrade = _OL_PUBLIC_ORIGIN + path
    host_sentence = body.get("message") if isinstance(body.get("message"), str) else ""
    host_sentence = _excerpt(host_sentence.strip())
    if keyed:
        return (
            f"This tool requires the {tier} tier. The API key this client "
            f"sent was accepted -- THE KEY IS VALID -- but the Oxford Ledge "
            f"plan behind it"
            + (f" ({current} tier)" if current else "")
            + f" does not include this tool, so the plan, not the key, is "
            f"what is missing. Upgrade the plan at {upgrade}."
            + (f" Host: {host_sentence}" if host_sentence else ""))
    if keyed is False:
        return (
            f"This tool requires the {tier} tier, and this client is "
            f"ANONYMOUS (no OXFORD_LEDGE_API_KEY is configured), so the host "
            f"refused it as a free-tier caller. If the client's operator has "
            f"an Oxford Ledge plan that includes the {tier} tier, the fix is "
            f"to set OXFORD_LEDGE_API_KEY in the client config (keys are "
            f"created at {_OL_KEYS_URL} under YOUR API KEYS); otherwise "
            f"upgrade at {upgrade}."
            + (f" Host: {host_sentence}" if host_sentence else "")
            + _NO_ASK_OPERATOR)
    # Leg unknown (a direct caller of the translator): the tier and the URL,
    # nothing asserted about the key either way.
    return (
        f"This tool requires the {tier} tier on the caller's Oxford Ledge "
        f"plan. Upgrade at {upgrade}."
        + (f" Host: {host_sentence}" if host_sentence else ""))


def _hosted_error_to_tool_error(parsed, http_status=None, retry_after=None,
                                raw_text="", keyed=None):
    """Translate a hosted MCP-dispatch refusal into the pip ToolError (K-2).

    `parsed` is the hosted refusal body: on the keyed REST leg the JSON
    error envelope {"status": "error", "error": ..., "code": ...}; on the
    keyless /mcp leg the `_meta` dict of an isError result (which carries
    the REST payload verbatim, routes_mcp_public_fastapi.py:603-607).
    Returns (never raises) so contract tests can feed synthetic bodies
    straight through and assert the resulting codes.

    Mapping (vet K-2, verbatim requirements):
      * body `code` in the shared taxonomy -> SAME-NAMED ToolError with the
        hosted `error` message verbatim (single wrap -- a hosted
        DATA_UNAVAILABLE must not be re-wrapped into a second envelope);
      * unknown-tool 404 body ({"status":"error","error":"Unknown tool: X"},
        no `code`) -> NOT_FOUND with the version-skew directive, NEVER
        DATA_UNAVAILABLE;
      * FastAPI's unrouted {"detail": "Not Found"} -> NOT_FOUND likewise;
      * a TIER refusal (`requiredTier` on either leg) -> AUTH_REQUIRED with
        the sentence `_tier_refusal_message` builds for the leg `keyed`
        names: on the keyed leg the key is valid and the plan is missing (no
        anti-phishing text -- there is no key to ask for); on the keyless
        leg the client is anonymous and the operator sets the key
        (f8-transport-errors-1 / d2-wheel-prose-5);
      * codeless 401/403 (or the /mcp `authentication_required` shape) ->
        AUTH_REQUIRED with the credential sentence;
      * codeless 429 -> RATE_LIMITED, honoring Retry-After;
      * anything else -> DATA_UNAVAILABLE with the hosted message.
    When the host's `error` is a bare code token (`tier_required`) and a
    `message` sentence exists, the sentence is the message -- a token is not
    a thing to read to a user. The API key is NEVER interpolated into any
    message here (C-3). Every hosted string is bounded by `_excerpt`
    (CISO-6), and `http_status` None -- a refusal carried IN a 200 body --
    is named as such, never rendered as the Python literal "(None)"
    (b07-8 / b09-a-13).
    """
    body = parsed if isinstance(parsed, dict) else {}
    err_field = body.get("error")
    msg_field = body.get("message")
    if (isinstance(err_field, str) and _BARE_CODE_TOKEN.match(err_field.strip())
            and isinstance(msg_field, str) and msg_field.strip()):
        primary = msg_field
    else:
        primary = err_field or msg_field
    msg = _excerpt(str(primary or raw_text or "").strip())
    status_label = f"HTTP {http_status}" if http_status else "malformed 200 body"

    code = body.get("code")
    if code in _HOSTED_TOOL_ERROR_CODES:
        if code == ToolError.RATE_LIMITED:
            return ToolError(
                code, msg or "Oxford Ledge rate limit reached for this caller.",
                retry_after=retry_after)
        return ToolError(
            code, msg or f"Hosted MCP dispatch refused this call ({status_label}).")

    # Unknown tool / unrouted path: version skew, never a data condition.
    if (msg.startswith("Unknown tool")
            or http_status == 404
            or body.get("detail") == "Not Found"):
        return ToolError(ToolError.NOT_FOUND, _VERSION_SKEW_MSG)

    # A tier refusal on either leg: the host says which tier. The keyed 402
    # envelope (routes/api_errors.py tier_gate_exception_handler) and the
    # keyless /mcp `_meta` (routes_mcp_public_fastapi.py TierGateException
    # arm) both carry `requiredTier`.
    if body.get("requiredTier") or (
            http_status == 402 and str(err_field or "").strip() == "tier_required"):
        return ToolError(ToolError.AUTH_REQUIRED, _tier_refusal_message(body, keyed))

    # /mcp anonymous-premium refusal shape or codeless HTTP auth statuses.
    if code == "authentication_required" or http_status in (401, 402, 403):
        return ToolError(
            ToolError.AUTH_REQUIRED,
            (msg or "Oxford Ledge rejected the credentials for this call. "
                    "The client's operator should check OXFORD_LEDGE_API_KEY "
                    "is set and not revoked.") + _NO_ASK_OPERATOR)

    if http_status == 429:
        return ToolError(
            ToolError.RATE_LIMITED,
            msg or "Oxford Ledge rate limit reached for this caller.",
            retry_after=retry_after)

    if msg and not http_status:
        # An in-band refusal (isError text / a 200 `status: error` envelope)
        # that says what went wrong: the host's own sentence, verbatim
        # (bounded), with no status to append.
        return ToolError(ToolError.DATA_UNAVAILABLE,
                         f"Hosted MCP dispatch failed: {msg}")
    return ToolError(
        ToolError.DATA_UNAVAILABLE,
        f"Hosted MCP dispatch failed ({status_label}): {msg}"
        if msg else f"Hosted MCP dispatch failed ({status_label}).")


def _read_http_error_body(e):
    """(parsed_json_or_None, raw_text) from an HTTPError — parse-before-
    truncate (the 3.2.0 vet K-7 lesson: truncating first makes any envelope
    over the cut unparseable and mislabels the refusal)."""
    raw = ""
    try:
        raw = e.read(65536).decode("utf-8", "replace")
    except Exception as read_err:
        # Not silent: an unreadable refusal body downgrades the K-2
        # translation to status-only mapping, which is worth a trace.
        _logger.debug("could not read hosted error body: %s", read_err)
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = None
    return parsed, raw


def _http_retry_after(e):
    try:
        return int(e.headers.get("Retry-After") or 0) or None
    except Exception:
        return None


def _nonblank(value):
    """A disclosure value counts only if it is a non-empty string."""
    return isinstance(value, str) and bool(value.strip())


def _attach_disclosure(result, meta=None):
    """L-3: attribution + not-investment-advice travel on every success.
    Hosted /mcp _meta values pass through when present; otherwise the
    package attaches its own copies of the same literals. Called from both
    _api_tool_call legs (keyless carries hosted _meta) AND the dispatch seam.

    K-8 (3.4.0 publish vet): this was `setdefault`, so a payload carrying
    `disclaimer: ""` (or a hosted `_meta.disclaimer` of "") WON over the
    literal and the wheel shipped an empty not-advice line. A blank is
    treated as absent: the hosted text still wins when it says something,
    the literal fills in when nothing does, and the two keys are appended
    LAST either way (the wire order the seam contract pins)."""
    if isinstance(result, dict):
        m = meta if isinstance(meta, dict) else {}
        for key, literal in (("attribution", _OL_ATTRIBUTION),
                             ("disclaimer", _OL_DISCLAIMER)):
            if _nonblank(result.get(key)):
                continue
            result.pop(key, None)
            hosted = m.get(key)
            result[key] = hosted if _nonblank(hosted) else literal
    return result


def _api_tool_call(tool, arguments, timeout=30):
    """POST one hosted MCP tool call and return the unwrapped result.

    C-1 transport split (the vet's blocking condition, both directions
    load-bearing):
      * keyed (OXFORD_LEDGE_API_KEY set) -> POST /api/mcp/tool. The
        validated-key path bypasses the browser-CSRF Origin check AND is
        correctly METERED against the key's account. Keyed traffic must
        NOT move to /mcp — the metering gap there (V4) is still open.
      * keyless -> POST /mcp as JSON-RPC tools/call, the transport
        DESIGNED for absent-Origin anonymous agents; it enforces the
        identical cleancore + tier + rate chain through the shared front.
    NEVER fabricates an Origin header — a keyless caller that spoofed
    `Origin: https://www.oxfordledge.com` at /api/mcp/tool would turn the
    cookie-CSRF gate into decoration (the vet's named forbidden fix).

    C-3: the API key rides ONLY in the `x-api-key` header on the keyed
    leg — never the URL, never the JSON body, never a log line or error
    message.
    """
    from oxford_ledge_mcp import server as _S  # call-time read: tests set S._API_URL / S._API_KEY
    if not _S._API_URL:
        raise ToolError(
            ToolError.API_REQUIRED,
            "This tool requires a running Oxford Ledge instance. "
            "Set the OXFORD_LEDGE_URL environment variable "
            "(e.g. OXFORD_LEDGE_URL=https://www.oxfordledge.com)."
        )
    args = arguments if isinstance(arguments, dict) else {}
    if _S._API_KEY:
        return _api_tool_call_keyed(tool, args, timeout)
    return _api_tool_call_keyless(tool, args, timeout)


def _api_tool_call_keyed(tool, arguments, timeout):
    """Keyed leg: POST /api/mcp/tool (metered, key-authenticated).

    C-3: header-only, never a query string, never the body, never echoed
    anywhere below. The key is attached by `_authenticated_request` as an
    UNREDIRECTED header (CISO-3: a cross-host 3xx cannot carry it)."""
    from oxford_ledge_mcp import server as _S  # call-time read: tests set S._API_URL / S._API_KEY
    data = json.dumps({"tool": tool, "arguments": arguments}).encode("utf-8")
    req = _authenticated_request(
        f"{_S._API_URL}/api/mcp/tool",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        parsed, raw_err = _read_http_error_body(e)
        raise _hosted_error_to_tool_error(
            parsed, http_status=e.code, retry_after=_http_retry_after(e),
            raw_text=_excerpt(raw_err), keyed=True)
    except urllib.error.URLError as e:
        raise ToolError(
            ToolError.DATA_UNAVAILABLE,
            f"Cannot reach Oxford Ledge API at {_S._API_URL}: {_excerpt(e.reason)}")
    payload = _parse_json_body(raw, "POST /api/mcp/tool")
    if not isinstance(payload, dict) or payload.get("status") != "ok":
        raise _hosted_error_to_tool_error(
            payload if isinstance(payload, dict) else {}, keyed=True)
    # C-5: return the unwrapped `result`, never the hosted envelope.
    result = payload.get("result")
    if not isinstance(result, dict):
        # b07-8 (skeptic): a well-formed envelope whose `result` is a list,
        # a string, a number or null was served -- and cached -- as success.
        raise non_object_tool_error(tool, result)
    return _attach_disclosure(result)


def _api_tool_call_keyless(tool, arguments, timeout):
    """Keyless leg: POST /mcp tools/call (anonymous-by-design transport)."""
    from oxford_ledge_mcp import server as _S  # call-time read: tests set S._API_URL / S._API_KEY
    data = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": tool, "arguments": arguments},
    }).encode("utf-8")
    # No Origin header (absent-Origin is ALLOWED there by design — V1),
    # and no credential: this leg only runs when no key is configured.
    req = urllib.request.Request(
        f"{_S._API_URL}/mcp",
        data=data,
        headers={
            "User-Agent": "OxfordLedgeMCP/1.0",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        parsed, raw_err = _read_http_error_body(e)
        raise _hosted_error_to_tool_error(
            parsed, http_status=e.code, retry_after=_http_retry_after(e),
            raw_text=_excerpt(raw_err), keyed=False)
    except urllib.error.URLError as e:
        raise ToolError(
            ToolError.DATA_UNAVAILABLE,
            f"Cannot reach Oxford Ledge API at {_S._API_URL}: {_excerpt(e.reason)}")
    payload = _parse_json_body(raw, "POST /mcp")
    if not isinstance(payload, dict):
        raise ToolError(ToolError.DATA_UNAVAILABLE,
                        "Malformed /mcp response (not a JSON object).")
    if payload.get("error"):
        _err = payload["error"] if isinstance(payload["error"], dict) else {}
        raise ToolError(
            ToolError.DATA_UNAVAILABLE,
            f"/mcp transport error: {_excerpt(_err.get('message') or payload['error'])}")
    res = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    text = ""
    for c in (res.get("content") or []):
        if isinstance(c, dict) and c.get("type") == "text":
            text = c.get("text") or ""
            break
    meta = res.get("_meta") if isinstance(res.get("_meta"), dict) else {}
    if res.get("isError"):
        # _meta carries the REST refusal payload verbatim (incl. `code`).
        # b09-a-13: a BARE handler result {"error": "..."} arrives with a
        # _meta of only attribution/disclaimer, so the sentence lives in the
        # content text -- read it as the body (the _meta keys still win),
        # rather than rendering the raw JSON blob into the message.
        body = dict(meta)
        retry = None
        try:
            in_band = json.loads(text)
        except Exception:
            in_band = None
        if isinstance(in_band, dict):
            err = in_band.get("error")
            if isinstance(err, dict):
                # ToolError.to_dict() shape {"error": {code, message, ...}}
                in_band = {**in_band, "error": err.get("message"),
                           "code": in_band.get("code") or err.get("code")}
                retry = err.get("retry_after")
            body = {**in_band, **meta}
        raise _hosted_error_to_tool_error(
            body, retry_after=retry if isinstance(retry, int) else None,
            raw_text=_excerpt(text), keyed=False)
    try:
        result = json.loads(text)
    except Exception:
        raise ToolError(ToolError.DATA_UNAVAILABLE,
                        "Malformed /mcp tool result (non-JSON content).")
    if not isinstance(result, dict):
        # b07-8 / b09-a-6 / b08-13: `[1, 2, 3]`, `"nope"`, `null` in the
        # content text were served as success and cached for an hour.
        raise non_object_tool_error(tool, result)
    return _attach_disclosure(result, meta)
