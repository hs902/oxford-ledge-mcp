"""Tool-partition declaration — the tool surface of oxford-ledge-mcp.

Three sets describe how this server's tools relate to the hosted
Oxford Ledge service:

  - SHARED_TOOLS — tools this server provides over HTTP that the
    hosted Oxford Ledge service also provides.
  - IN_TREE_ONLY_TOOLS — tools available only from the hosted Oxford
    Ledge service; this distribution does not implement them.
  - PIP_ONLY_TOOLS — standalone tools this server provides that do
    not require an Oxford Ledge API endpoint (`OXFORD_LEDGE_URL`).

This file is a REGRESSION GATE: the test suite imports these sets and
compares them against the live tool registry. Adding a tool without
updating this file fails the test loudly. If a tool legitimately
moves between sets, update this file in the same commit as the
server change.
"""
from __future__ import annotations

# Tools also provided by the hosted Oxford Ledge service.
SHARED_TOOLS: frozenset[str] = frozenset({
    "calculate_intrinsic_value",
    "get_13f_holdings",
    "get_anomaly_flags",
    "get_bdc_list",
    "get_bond_data",
    "get_capital_allocation",
    "get_company_data",
    "get_company_profile",
    "get_corporate_events",
    "get_debt_maturities",
    "get_economic_calendar",
    "get_fred_data",
    "get_fundamentals",
    "get_market_indicators",
    "get_news",
    "get_options_chain",
    "get_peer_comparison",
    "get_price_history",
    "get_short_interest",
    "get_valuation_history",
    "get_value_investing_fact",
    "get_yield_curve",
    "search_bdc_borrower",
    "search_bonds",
    "search_company",
})

# Tools available only from the hosted Oxford Ledge service; this
# distribution does not implement them. See module docstring.
IN_TREE_ONLY_TOOLS: frozenset[str] = frozenset({
    "batch_get_ticker_data",
    "bulk_get_fundamentals",
    "get_ai_question",
    "get_analyst_estimates",
    "get_calendar",
    "get_estimate_revisions",
    "get_index_movers",
    "get_insider_activity",
    "get_portfolio_analytics",
    "get_portfolio_positions",
    "get_sector_breakdown",
    "run_screener",
    "search_news_archive",
})

# Standalone tools this server provides; they work without an
# Oxford Ledge API endpoint (OXFORD_LEDGE_URL unset).
PIP_ONLY_TOOLS: frozenset[str] = frozenset({
    "compare_stocks",
    "get_analyst_recommendations",
    "get_balance_sheet",
    "get_cash_flow",
    "get_company_info",
    "get_financials",
    "get_holders",
    "get_insider_trades",
    "get_sec_filings",
    "get_stock_quote",
    "screen_stocks",
})


# Convenience views for consumers.
IN_TREE_TOOLS: frozenset[str] = SHARED_TOOLS | IN_TREE_ONLY_TOOLS
PIP_TOOLS: frozenset[str] = SHARED_TOOLS | PIP_ONLY_TOOLS


def summary() -> dict[str, int]:
    """Return a summary dict for logging / diagnostics."""
    return {
        "shared": len(SHARED_TOOLS),
        "in_tree_only": len(IN_TREE_ONLY_TOOLS),
        "pip_only": len(PIP_ONLY_TOOLS),
        "in_tree_total": len(IN_TREE_TOOLS),
        "pip_total": len(PIP_TOOLS),
    }
