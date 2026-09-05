"""Oxford Ledge MCP Server — financial data tools for Claude Desktop.

Install: pip install oxford-ledge-mcp
Usage:   oxford-ledge-mcp (runs as stdio MCP server)

Two modes:
  1. Standalone: only the keyless public-API tools (2 SEC EDGAR; FRED with a
     free FRED_API_KEY). The other 9 tools raise API_REQUIRED.
  2. API mode:   All 13 tools via an Oxford Ledge instance
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

__version__ = "3.3.0"  # keep in sync with pyproject.toml [project].version
