"""Continuous double auction exchange engine (Stage 1).

Responsibilities:
- Limit order book with price-time priority, immediate crossing,
  cancellation, and per-period open/close.
- Agent activation protocol: seeded random polling (Gode–Sunder style);
  a polled agent may pass; identical mechanism across all agent types.
  LLM response latency must never influence order priority.
- Strictly deterministic given an ordered event sequence: all tie-breaking
  explicit, no wall-clock or iteration-order dependence.
- Induced-value machinery: private valuations/costs, budget constraints,
  surplus accounting.
- Session serialization: the full event log per session IS the replay format.

Correctness is the product — this module is exhaustively tested and serves
as the project's calibration certificate.
"""
