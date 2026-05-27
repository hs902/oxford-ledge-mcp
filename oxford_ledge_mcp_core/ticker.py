"""Ticker-symbol normalization helper for the oxford-ledge-mcp server.

Standalone (stdlib-only) port of the in-tree
`services/ticker_normalization.py:normalize_ticker` so that the pip-
installable package does NOT inherit a `services.*` import (which would
ImportError on every install of the public OSS twin).

Public API:

    from oxford_ledge_mcp_core.ticker import normalize_ticker

    normalize_ticker("brk-b")    -> "BRK-B"
    normalize_ticker("  aapl ")  -> "AAPL"
    normalize_ticker(None)       -> ""
    normalize_ticker("")         -> ""

This helper does pure uppercase + whitespace strip. It deliberately does
NOT perform dash<->dot class-share rewriting (that lives in the in-tree
package under `pg_db.queries.news._dashdot_sibling` and is gated on a
universe check that requires the full hosted dataset; safe behavior for
the standalone OSS twin is to leave class-share variants to the caller).
"""
from __future__ import annotations

from typing import Optional


def normalize_ticker(symbol: Optional[str]) -> str:
    """Canonical form of a stock ticker: uppercase + strip.

    Returns "" for None or empty input. Callers that previously did
    `args["ticker"].upper().strip()` should switch to
    `normalize_ticker(args.get("ticker"))` so the missing-key path
    surfaces as a friendly `ToolError.BAD_INPUT` instead of a raw
    `KeyError`.
    """
    if not symbol:
        return ""
    return str(symbol).strip().upper()
