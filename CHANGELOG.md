# Changelog

All notable changes to `oxford-ledge-mcp` are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 2.1.0 (2026-07-21)

### Removed (breaking)
- **7 vendor-data-lineage tools** removed so the package's default tool
  surface is free of commercial-vendor data lineage (a redistributability
  tightening — the removed tools proxied FMP/Finnhub-derived data and have
  no distributable source):
  `calculate_intrinsic_value`, `get_company_data`, `get_company_profile`,
  `get_market_indicators`, `get_peer_comparison`, `get_price_history`,
  `get_valuation_history`.
  Removing public tools is backward-incompatible. **`2.0.4` remains
  installable on PyPI** — if you depend on any of the above, pin
  `oxford-ledge-mcp==2.0.4`. See `MIGRATING.md` for replacements.

### Changed
- Calling a removed tool now returns a **structured migration pointer**
  (naming the SEC-XBRL / hosted replacement) instead of a bare
  `Unknown tool: <name>` — so an agent can self-correct.
- Package metadata: the description's tool count is corrected `36 → 29`
  (the live `tools/list` surface), and the `Repository` URL now points at
  the public `github.com/hs902/oxford-ledge-mcp` (was the private monorepo).

### Unchanged
- The `2.0.4` ticker-normalization behavior (`normalize_ticker`) is
  preserved on every surviving tool — a missing/`null` `ticker` still
  surfaces as a structured `ToolError`, never a raw `KeyError`.
- All surviving tools keep their arg names, return shapes, and MCP wire
  format.

## 2.0.4 (2026-05-27)

### Added
- `oxford_ledge_mcp_core.ticker.normalize_ticker(symbol)` helper —
  stdlib-only ticker canonicalization (uppercase + whitespace strip).
  Exported from `oxford_ledge_mcp_core` for downstream callers.
- `min_tier="plus"` markings on five premium analytics tools to mirror
  the in-tree per-tool tier table: `get_options_chain`,
  `get_debt_maturities`, `get_capital_allocation`, `get_13f_holdings`,
  `get_valuation_history`. Standalone stdio mode is unaffected (no
  user-account context); API mode (`OXFORD_LEDGE_URL` set) enforces
  tier server-side as before — observable behavior is unchanged for
  current users.

### Changed
- F5 ticker-normalization callsite sweep across `oxford_ledge_mcp/
  server.py`: replaced inline `args["ticker"].upper().strip()` (and the
  multi-ticker `args["tickers"].split(",")` comprehension) with
  `normalize_ticker(args.get("ticker"))`. All tool input/output
  contracts (arg names, return shapes, MCP tool wire format) are
  unchanged.
- **Improved error message** for missing-`ticker` inputs. Previously a
  request omitting the required `ticker` arg surfaced as a bare
  `KeyError: 'ticker'` (`ToolError.UNKNOWN`). It now reaches the
  existing empty-string validators and surfaces as a structured
  `ToolError` with a friendly message. This is the only observable
  behavior change in 2.0.4 and is strictly improving.

### Fixed
- README install instruction typo: `pip install oxfordledge-mcp` →
  `pip install oxford-ledge-mcp` (matches `pyproject.toml` package
  name; the typo had no functional impact since the typo'd name does
  not resolve on PyPI).
- Version drift: `oxford_ledge_mcp/__init__.py` `__version__` now
  matches `pyproject.toml` `version`.

## 2.0.3 (prior release)

- Initial public release per `git log`.
