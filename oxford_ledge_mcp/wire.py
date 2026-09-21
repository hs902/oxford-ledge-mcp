"""The wire: one serializer and the JSON-RPC / MCP result shapes both
transports write (2026-09-12, 3.4.0 publish vet, wave B3).

Cut out of server.py in the same wave that added them, for the same reason
the SEC + FRED families left it: server.py sits under a 2,000-line budget
with a sibling builder adding handler guards to it. Nothing here registers a
tool or imports the server; every name is re-exported from server.py so
`oxford_ledge_mcp.server._wire_dumps` keeps resolving.

* `_coerce_for_wire` / `_wire_dumps` -- K-5: NaN / Infinity never reach the
  wire (a strict client rejects the bare tokens), a Decimal / date dict KEY
  becomes str / ISO. Mirrors the hosted `_McpJSONResponse._coerce`;
  `allow_nan=False` is the backstop.

  **This is LOAD-BEARING, not latent.** It said "latent today -- no wheel
  path produces NaN or Decimal", and that was wrong about the input side:
  `json.loads` accepts the bare `NaN` / `Infinity` / `-Infinity` tokens by
  default, so any HOST can put a non-finite float into a decoded body and a
  proxying handler will carry it straight through. `_coerce_for_wire` turns
  it into an explicit `null` before it can reach a strict client, which is
  the honest option available here -- the value is not a number and this
  client must not invent one -- and readers that need to tell "the producer
  said nothing" from "the producer said something unusable" say so at the
  handler (`get_holders`' `unstated` list is the worked example). Decimal
  remains a wheel-side non-producer; the NaN half is reachable today.
  Corrected 2026-09-21 (delta vet K-11): a comment that calls a live guard
  latent is how the guard gets deleted as dead code in the next cut.
* `_TransportToolError` -- critic-1: raised from the mcp-SDK `call_tool` so
  EVERY mcp 1.x flags the result isError:true; the SDK renders `str(e)` as
  the content text, so `str()` is the same JSON envelope the built-in loop
  writes. (Returning a `CallToolResult` is accepted only by newer 1.x
  releases; the `except Exception` arm has been there since 1.0.0.)
* `_tool_content` / `_rpc_error` -- the two response shapes the built-in
  JSON-RPC loop writes (K-4: a malformed request gets `_rpc_error`, never an
  unanswered id).
"""
from __future__ import annotations

import datetime as _datetime
import decimal as _decimal
import json
from typing import Any


def _coerce_for_wire(o: Any) -> Any:
    if isinstance(o, dict):
        out = {}
        for k, v in o.items():
            if isinstance(k, _decimal.Decimal):
                k = str(k)
            elif isinstance(k, (_datetime.datetime, _datetime.date)):
                k = k.isoformat()
            out[k] = _coerce_for_wire(v)
        return out
    if isinstance(o, (list, tuple)):
        return [_coerce_for_wire(v) for v in o]
    if isinstance(o, float):
        return None if (o != o or o in (float("inf"), float("-inf"))) else o
    if isinstance(o, _decimal.Decimal) and (o.is_nan() or o.is_infinite()):
        return None
    return o


def _wire_fallback(o: Any) -> str:
    """`default=` for the values json.dumps cannot encode: date / datetime
    -> ISO 8601 (str() would give "2026-01-01 00:00:00"), everything else
    -> str, the fallback the wheel has always used (Decimal -> "1.50")."""
    if isinstance(o, (_datetime.datetime, _datetime.date)):
        return o.isoformat()
    return str(o)


def _wire_dumps(obj: Any, indent: int | None = None) -> str:
    """The ONE serializer for tool content on both transports."""
    return json.dumps(_coerce_for_wire(obj), indent=indent,
                      default=_wire_fallback, allow_nan=False)


def _tool_content(text: str, is_error: bool) -> dict[str, Any]:
    """The MCP tools/call result body the built-in loop writes."""
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def _rpc_error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


class _TransportToolError(Exception):
    """See the module docstring: the SDK-transport spelling of isError:true."""

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.text = text

    def __str__(self) -> str:
        return self.text
