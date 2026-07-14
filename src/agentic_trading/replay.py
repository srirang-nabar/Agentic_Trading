"""Deterministic session replay from logs (Stages 1 & 3).

Responsibilities:
- Reconstruct any session bit-exactly from its JSONL log with zero API
  calls: the engine is deterministic given the ordered event sequence.
- Serialization round-trip guarantee: log → objects → log is the identity.
- Replay-equals-live test support: a recorded live session replayed from
  its log must produce the identical market outcome.

This module is the reproducibility spine: all statistics, tables, and
figures are computed from replayed logs, never from live calls.
"""
