"""Tool-partition declaration — which MCP tools live in which server.

M1 Phase 2 (2026-04-24). The two MCP servers (in-tree `mcp_server.py`
+ pip `mcp_package/oxford_ledge_mcp/server.py`) have overlapping but
not identical tool surfaces. Phase 0 of the M1 sprint documented the
split as intentional:

  - **Shared (25 tools)** — implemented by both servers. In-tree uses
    direct-Python calls into data_providers / pg_db / oxford_ledge_db /
    edgar / market_data / fmp_api. Pip uses HTTP calls against
    `OXFORD_LEDGE_URL` in API mode.
  - **In-tree only (13 tools)** — call Oxford Ledge-specific internals
    (portfolio, screener, ai_question, etc.) that would require pip
    to replicate significant service-layer logic over HTTP. Not
    cost-effective; pip users who need these can run the in-tree
    server from a local OL checkout.
  - **Pip only (11 tools)** — yfinance-backed standalone tools that
    work without `OXFORD_LEDGE_URL`. In-tree doesn't implement them
    because it has always had richer data via the data_providers
    layer; duplicating the yfinance path would be dead code.

This file is the REGRESSION GATE: `tests/test_mcp_tool_partition.py`
imports these sets and compares against the live `REGISTRY` from
each server. If someone adds a tool to one side without updating
this file, the test fails loudly.

If a legitimate change moves a tool (e.g. M1 Phase 3 wires Tradier
and `get_options_chain` graduates from pip-only to shared), update
this file IN THE SAME COMMIT that changes the server code.
"""
from __future__ import annotations

# Tools present in BOTH servers.
# 2026-07-21 FMP-removal (OWNER-directed fully-distributable catalog): dropped
# calculate_intrinsic_value, get_company_data, get_company_profile,
# get_market_indicators, get_peer_comparison, get_price_history,
# get_valuation_history from the in-tree server (vendor-fed, no distributable source).
# 2026-07-21 3B keyless-public cut (OWNER call): the pip package is now
# gov-public-data-only (SEC EDGAR / FRED / Treasury / FINRA-TRACE / OL-original).
# get_anomaly_flags, get_economic_calendar, get_news, get_options_chain,
# search_company were removed from the PIP server (vendor/blended/aggregated
# lineage) but KEPT in the in-tree hosted server, so they moved SHARED -> IN_TREE_ONLY.
SHARED_TOOLS: frozenset[str] = frozenset({
    "get_13f_holdings",
    "get_bdc_list",
    "get_capital_allocation",
    "get_corporate_events",
    "get_debt_maturities",
    "get_fred_data",
    "get_fundamentals",
    "get_value_investing_fact",
    "get_yield_curve",
    "search_bdc_borrower",
})

# Tools present ONLY in the in-tree server (mcp_server.py).
# These call OL-codebase internals that the pip package doesn't
# vendor. See module docstring for rationale.
IN_TREE_ONLY_TOOLS: frozenset[str] = frozenset({
    # 2026-07-21 FMP-removal: dropped batch_get_ticker_data, bulk_get_fundamentals,
    # get_analyst_estimates, get_calendar, get_earnings_transcript,
    # get_estimate_revisions, get_portfolio_analytics, run_screener (vendor-fed).
    # 2026-07-21 3B keyless-public cut: moved here from SHARED (removed from the
    # PIP server as vendor/blended/aggregated lineage; kept in the in-tree hosted
    # server). get_options_chain is also an env-gated stub (below).
    "get_anomaly_flags",
    "get_economic_calendar",
    "get_news",
    "get_options_chain",
    "search_company",
    # 2026-07-21 CUSIP carve-out: search_bonds/get_bond_data disseminate CUSIPs
    # (FactSet / CUSIP Global Services IP — a third-party carve-out within FINRA
    # data that needs a direct license for commercial redistribution). Removed from
    # the gov-public-data-only PIP server; kept in the in-tree hosted server.
    "search_bonds",
    "get_bond_data",
    # 2026-07-21 compliance review (CHAOS/DATA_CZAR/COUNSEL): get_short_interest is an
    # advertised not_implemented stub with an unresolved float-lineage + FINRA-attribution
    # question — removed from the pip surface until it's real (OWNER #23). Env-gated stub
    # in-tree (also in IN_TREE_ENV_GATED_STUBS below).
    "get_short_interest",
    "get_activist_stakes",        # MCP B.3 (#239) — new in-tree wrapper
    "get_ai_question",
    "get_fails_to_deliver",       # MCP B.3 (#239) — new in-tree wrapper
    "get_insider_activity",
    "get_institutional_consensus",  # institutional rename #235/#240
    "get_institutional_holders",    # institutional rename #235/#240
    "get_portfolio_positions",
    "get_sector_breakdown",
    "search_news_archive",
    # SF-MCP-SDK-EXPANSION Wave-2 (2026-07-21, BOARD-ratified): SEC/gov-derived
    # distributable tools. IN_TREE_ONLY until the OWNER publish vet promotes them.
    "ol_bdc_credit_quality",
    "ol_bdc_fee_load",
    "ol_13f_filer_analytics",
    "ol_ownership_changes",
    "ol_federal_contracts",
    "ol_patents",
    "ol_form_d_raises",
    "ol_insider_recent_buys",
    "ol_short_interest_trend",
    "ol_bdc_loan_pricing_trend",
    "ol_cftc_cot",
    "ol_treasury_debt",
    "ol_fdic_bank",
    # FMP-removal Stage-3 (2026-07-21): clean SEC-XBRL valuation rebuild tools that
    # replace the removed FMP/Finnhub valuation surface (get_value_score et al.).
    # Same IN_TREE_ONLY publish gate as the rest of the wave.
    "ol_intrinsic_value",
    "ol_peer_fundamentals",
    "ol_fundamentals_screen",
    # SF-MCP Wave-1 moat tools (2026-06-13, OWNER-ratified). Built IN-TREE
    # only — the public PyPI publish is OWNER-owned behind the
    # CISO+COUNSEL+CHAOS vet (feedback_public_repo_persona_vet), so these
    # stay in IN_TREE_ONLY until that vet + a version bump promote the
    # vetted batch into the pip twin (then they move to SHARED_TOOLS in the
    # SAME commit, per the module docstring). 4 FREE + 1 PAID (filing_search,
    # metered via the existing AI-usage quota gate).
    "ol_insider_cluster_scan",
    "ol_bdc_borrower_dispersion",
    "ol_bdc_top_borrowers",
    "ol_filing_search",
    "ol_bdc_borrower_news_today",
    # MCP Phase-1 read tools (2026-07-07). Same IN_TREE_ONLY gate as Wave-1
    # until the OWNER-owned CISO+COUNSEL+CHAOS publish vet promotes the batch
    # into the pip twin. All FREE, all READ. Postures: mcp_redistribution.py.
    # (get_value_score REMOVED 2026-07-21 FMP-removal — Finnhub/FMP-computed core.)
    "ol_borrower_profile",
    "ol_etf_lookthrough",
    "ol_bond_directory_screen",
    "get_business_summary",
    # K3 wiring (2026-07-09 #39). Same IN_TREE_ONLY gate as the waves above
    # until the OWNER-owned publish vet promotes it. Clean lineage (SEC EDGAR
    # 13F-HR + Form 4 derived fusion) but PLUS-gated 2026-07-10 (OWNER) and
    # therefore OFF the free-only OAuth clean-core allowlist. READ.
    "ol_institutional_confluence",
    # SF-MCP-WRITE Phase 2 (2026-07-27, #242, OWNER-ratified §7.1 Q7): the
    # reference WRITE verb. PERMANENTLY in-tree-only — write capability never
    # ships in the pip twin without its own CISO+COUNSEL+CHAOS vet (plan §9 +
    # feedback_public_repo_persona_vet), and the whole write surface is dark
    # until a deploy sets OL_MCP_WRITE_ENABLED=1.
    "reading_list_annotate",
})

# Tools present ONLY in the pip-installable server. These are the
# yfinance standalone tools — they work without OXFORD_LEDGE_URL.
# In-tree server doesn't implement them because its data layer
# (data_providers) already provides richer versions.
PIP_ONLY_TOOLS: frozenset[str] = frozenset({
    # 2026-07-21 3B keyless-public cut (OWNER call): the 8 vendor-fed PIP_ONLY tools
    # (compare_stocks, get_analyst_recommendations, get_balance_sheet, get_cash_flow,
    # get_company_info, get_financials, get_stock_quote, screen_stocks — all FMP-primary
    # via OXFORD_LEDGE_URL) were REMOVED from the pip server. What remains is gov-public:
    "get_holders",         # SEC 13F (via /api/13f-holdings)
    "get_insider_trades",  # SEC Form 4 (via /api/insider-activity)
    "get_sec_filings",     # SEC EDGAR filings (keyless)
    # (Earlier 2026-07-21 FMP-removal had already dropped calculate_intrinsic_value,
    # get_company_data, get_company_profile, get_market_indicators, get_peer_comparison,
    # get_price_history, get_valuation_history from the pip server.)
})


# Env-gated stub tools in the in-tree server only.
# B.5.1 follow-on (2026-05-27, docs/board/audit/2026-05-20_MCP_B5_DESCRIPTION_UPLIFT.md
# §153): these 3 honest-error stubs are now registered ONLY when
# MCP_ENABLE_STUB_TOOLS=1. Default prod state has them ABSENT from
# in-tree TOOL_DISPATCH and tools/list so Claude Desktop users don't see
# tools that always return {"error": "not_implemented"}. The pip server
# implements its own non-gated copies of get_short_interest and
# get_options_chain (HTTP-backed) — that's why they remain in SHARED_TOOLS:
# the SHARED set is "implemented by both servers when in-tree is fully
# enabled," not "always live in both registries."
IN_TREE_ENV_GATED_STUBS: frozenset[str] = frozenset({
    "get_short_interest",
    "get_options_chain",
    "get_ai_question",
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
