"""python -m oxford_ledge_mcp — module-invocation entry point.

2026-08-10 (persona MCP-docs audit 5.4): LLMs predictably suggest
`python -m oxford_ledge_mcp` (the idiomatic guess), and its absence was a
whole failure mode; the console script `oxford-ledge-mcp` remains the
documented entry point.
"""
from oxford_ledge_mcp.server import main

if __name__ == "__main__":
    main()
