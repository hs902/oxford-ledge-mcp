"""Structured error class for MCP tool handlers.

Extracted 2026-04-24 from `mcp_server.py` as part of the M1 twin-
dedup sprint. Both the in-tree and pip MCP servers raise this same
class; consumers (Claude Desktop) see consistent error codes
regardless of which server they're talking to.
"""
from __future__ import annotations

from typing import Any


class ToolError(Exception):
    """Structured MCP tool error with code, message, and optional retry_after."""

    RATE_LIMITED = "RATE_LIMITED"
    INVALID_PARAMS = "INVALID_PARAMS"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    CACHE_MISS = "CACHE_MISS"
    API_REQUIRED = "API_REQUIRED"  # pip standalone mode: tool needs OXFORD_LEDGE_URL
    # 2026-08-10 field test #2: a 404 on a nonexistent PATH is a developer
    # bug (client/server version skew), not missing data. Laundering it as
    # DATA_UNAVAILABLE told the agent "the filing doesn't exist" and kept
    # three dead endpoint strings invisible for months.
    NOT_FOUND = "NOT_FOUND"

    def __init__(self, code: str, message: str,
                 retry_after: int | None = None) -> None:
        self.code = code
        self.message = message
        self.retry_after = retry_after
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"error": {"code": self.code, "message": self.message}}
        if self.retry_after:
            d["error"]["retry_after"] = self.retry_after
        return d
