"""Deterministic session replay from logs (Stage 1).

The session log is the primary scientific artifact. Its `events` list is the
complete input to the deterministic engine, so replaying it through a fresh
Exchange must reproduce every outcome, trade, and final state bit-exactly —
with zero API calls. `verify_session_log` is the executable form of that
guarantee and is property-tested in the Stage 1 suite.
"""

from __future__ import annotations

import json
from typing import Any

from agentic_trading.exchange import Exchange, TraderConfig, event_from_dict


def traders_from_log(log: dict[str, Any]) -> list[TraderConfig]:
    return [
        TraderConfig(
            trader_id=t["trader_id"],
            cash=t["cash"],
            values=tuple(t["values"]),
            costs=tuple(t["costs"]),
        )
        for t in log["traders"]
    ]


def replay_session_log(log: dict[str, Any]) -> dict[str, Any]:
    """Re-run a session log's events through a fresh Exchange.

    Provenance keys the engine does not own (e.g. the runner's "config")
    are carried through unchanged, so a replayed log is byte-identical to
    the original — replay must never strip provenance.
    """
    exchange = Exchange(traders_from_log(log))
    for event_dict in log["events"]:
        exchange.apply(event_from_dict(event_dict))
    replayed = exchange.session_log()
    for key, value in log.items():
        if key not in replayed:
            replayed[key] = value
    return replayed


def verify_session_log(log: dict[str, Any]) -> list[str]:
    """Bit-exact replay check. Returns mismatch descriptions; [] = verified."""
    replayed = replay_session_log(log)
    mismatches: list[str] = []
    for key in ("traders", "events", "outcomes", "trades", "final"):
        if _canonical(log[key]) != _canonical(replayed[key]):
            mismatches.append(f"replay mismatch in {key!r}")
    return mismatches


def session_log_to_json(log: dict[str, Any]) -> str:
    """Canonical JSON form (sorted keys) — what lands in results/ JSONL."""
    return _canonical(log)


def session_log_from_json(text: str) -> dict[str, Any]:
    return json.loads(text)


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))
