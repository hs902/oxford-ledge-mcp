"""Oxford Ledge MCP Server — financial data tools for Claude Desktop.

Install: pip install oxford-ledge-mcp
Usage:   oxford-ledge-mcp (runs as stdio MCP server)

Two modes:
  1. Standalone: only the keyless public-API tools (2 SEC EDGAR; FRED with a
     free FRED_API_KEY). The other 25 tools need OXFORD_LEDGE_URL.
  2. API mode:   All 29 tools via an Oxford Ledge instance
     Set OXFORD_LEDGE_URL=https://www.oxfordledge.com

Claude Desktop config (claude_desktop_config.json):
{
  "mcpServers": {
    "oxford-ledge": {
      "command": "oxford-ledge-mcp"
    }
  }
}
"""

from __future__ import annotations

__version__ = "3.7.1"  # keep in sync with pyproject.toml [project].version
