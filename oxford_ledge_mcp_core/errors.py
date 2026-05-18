"""Structured error class for MCP tool handlers.

Raised by all tool handlers so consumers (Claude Desktop) see
consistent, structured error codes.
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
