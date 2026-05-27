"""Oxford Ledge MCP Server — financial data tools for Claude Desktop.

Install: pip install oxford-ledge-mcp
Usage:   oxford-ledge-mcp (runs as stdio MCP server)

Two modes:
  1. Standalone: 18 tools via yfinance + free APIs (no setup needed)
  2. API mode:   All 36 tools via Oxford Ledge instance
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

__version__ = "2.0.4"
