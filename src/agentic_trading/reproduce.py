"""Verification entry point for external volunteers (Stage 7).

Responsibilities:
- `uv run python -m agentic_trading.reproduce --tier 2`: regenerate all
  metrics, statistical tests, tables, and figures from the raw JSONL logs —
  no API key required.
- Cross-check every recomputed headline number against CLAIMS.md.
- Report wall-clock timing per tier for REPRODUCING.md.
"""
