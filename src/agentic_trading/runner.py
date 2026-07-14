"""Session runner and config-driven experiment runner (Stages 1–2).

The activation protocol is part of the engine spec, pre-registered in
HYPOTHESES.md: at each step a uniformly random trader (seeded RNG,
Gode–Sunder style) is polled and may submit an order, cancel one of its
resting orders, or pass. The protocol is identical for every agent type —
ZI, LLM, or scripted — and response latency never affects priority: an
agent acts if and only if it is polled, in poll order.

The resulting event sequence (not the RNG) is what the session log records,
so replay needs no seed.

`run_experiment` executes a configs/*.yaml experiment: every cell's sessions
are written as gzip JSONL (one canonical-JSON session log per line, gzip
mtime pinned to 0 so regeneration is byte-identical), the config is copied
alongside, and results/MANIFEST.sha256 is refreshed. All seeds derive from
the config seed via SHA-256 (never Python's salted hash), so a re-run from
config reproduces identical logs — the Stage 2 determinism gate.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Sequence, Union

import yaml

from agentic_trading.exchange import (
    Cancel,
    Exchange,
    Pass,
    PeriodClose,
    PeriodOpen,
    Side,
    Submit,
    TraderConfig,
)


@dataclass(frozen=True)
class SubmitAction:
    side: Side
    price: int


@dataclass(frozen=True)
class CancelAction:
    order_id: int


Action = Union[SubmitAction, CancelAction, None]


@dataclass(frozen=True)
class AgentView:
    """Everything a polled agent is allowed to see."""

    trader_id: str
    period: int
    step: int
    best_bid: int | None
    best_ask: int | None
    last_trade_price: int | None
    cash_available: int
    inventory_available: int
    remaining_values: tuple[int, ...]
    remaining_costs: tuple[int, ...]
    open_orders: tuple[tuple[int, str, int], ...]  # (order_id, side, price)


class Agent(Protocol):
    def act(self, view: AgentView) -> Action: ...


def run_session(
    traders: Sequence[TraderConfig],
    agents: dict[str, Agent],
    *,
    n_periods: int,
    steps_per_period: int,
    poll_seed: int,
) -> dict[str, Any]:
    """Run one session; returns the complete session log (see replay.py)."""
    trader_ids = sorted(t.trader_id for t in traders)
    if sorted(agents) != trader_ids:
        raise ValueError("agents must match traders exactly")

    exchange = Exchange(traders)
    rng = random.Random(poll_seed)

    for _ in range(n_periods):
        exchange.apply(PeriodOpen())
        for step in range(steps_per_period):
            trader_id = trader_ids[rng.randrange(len(trader_ids))]
            action = agents[trader_id].act(_view(exchange, trader_id, step))
            exchange.apply(_to_event(trader_id, action))
        exchange.apply(PeriodClose())

    log = exchange.session_log()
    log["config"] = {
        "n_periods": n_periods,
        "steps_per_period": steps_per_period,
        "poll_seed": poll_seed,
        "activation": "uniform_random_polling",
    }
    return log


def _view(exchange: Exchange, trader_id: str, step: int) -> AgentView:
    acct = exchange.account(trader_id)
    cfg = exchange.config(trader_id)
    bid = exchange.best_bid()
    ask = exchange.best_ask()
    last_price = exchange.trades[-1]["price"] if exchange.trades else None
    open_orders = tuple(exchange.open_orders_for(trader_id))
    return AgentView(
        trader_id=trader_id,
        period=exchange.period,
        step=step,
        best_bid=bid.price if bid else None,
        best_ask=ask.price if ask else None,
        last_trade_price=last_price,
        cash_available=acct["cash"] - acct["committed_cash"],
        inventory_available=acct["inventory"] - acct["n_open_asks"],
        remaining_values=cfg.values[acct["n_bought"] + acct["n_open_bids"]:],
        remaining_costs=cfg.costs[acct["n_sold"] + acct["n_open_asks"]:],
        open_orders=open_orders,
    )


def _to_event(trader_id: str, action: Action):
    if action is None:
        return Pass(trader_id)
    if isinstance(action, SubmitAction):
        return Submit(trader_id=trader_id, side=action.side, price=action.price)
    if isinstance(action, CancelAction):
        return Cancel(trader_id=trader_id, order_id=action.order_id)
    raise TypeError(f"not an action: {action!r}")


# ---- config-driven experiments (Stage 2+) ----


def derive_seed(*parts: Any) -> int:
    """Deterministic 64-bit seed from labels via SHA-256.

    Never seed from Python strings directly: str hashing is salted per
    process (PYTHONHASHSEED) and would silently break bit-reproducibility.
    """
    text = "|".join(str(p) for p in parts)
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big")


def load_config(path: Path | str) -> dict[str, Any]:
    with open(path) as f:
        return yaml.safe_load(f)


def run_experiment(
    config: dict[str, Any], results_root: Path | str = "results"
) -> dict[str, Any]:
    """Run every cell of a Smith-design ZI experiment from its config.

    Layout: results/<experiment_id>/sessions/<cell>.jsonl.gz (one canonical
    JSON session log per line), config.yaml copied alongside, summary.json
    with per-session metrics, and a refreshed results/MANIFEST.sha256.
    """
    from agentic_trading.agents.zi import build_zi_agents
    from agentic_trading.experiments.smith import SmithMarketSpec, generate_smith_market
    from agentic_trading.metrics import session_metrics
    from agentic_trading.replay import session_log_to_json

    from agentic_trading.manifest import write_manifest

    experiment_id = config["experiment_id"]
    base_seed = config["seed"]
    market_cfg = config["market"]
    spec = SmithMarketSpec(
        n_buyers=market_cfg["n_buyers"],
        n_sellers=market_cfg["n_sellers"],
        units_per_trader=market_cfg["units_per_trader"],
        price_low=market_cfg["price_low"],
        price_high=market_cfg["price_high"],
        cash_endowment=market_cfg["cash_endowment"],
    )

    results_root = Path(results_root)
    out_dir = results_root / experiment_id
    (out_dir / "sessions").mkdir(parents=True, exist_ok=True)
    with open(out_dir / "config.yaml", "w") as f:
        yaml.safe_dump(config, f, sort_keys=True)

    summary: dict[str, Any] = {"experiment_id": experiment_id, "cells": {}}
    for cell in config["cells"]:
        cell_name = cell["name"]
        cell_sessions = []
        lines = []
        for index in range(cell["n_sessions"]):
            market_rng = random.Random(derive_seed(base_seed, cell_name, index, "market"))
            traders, eq = generate_smith_market(market_rng, spec)
            agents = build_zi_agents(
                traders,
                kind=cell["agent_type"],
                max_price=spec.price_high,
                seed_for=lambda tid, i=index: derive_seed(base_seed, cell_name, i, "agent", tid),
            )
            log = run_session(
                traders,
                agents,
                n_periods=market_cfg["n_periods"],
                steps_per_period=market_cfg["steps_per_period"],
                poll_seed=derive_seed(base_seed, cell_name, index, "poll"),
            )
            log["meta"] = {
                "experiment_id": experiment_id,
                "cell": cell_name,
                "agent_type": cell["agent_type"],
                "session_index": index,
            }
            lines.append(session_log_to_json(log))
            metrics = session_metrics(log)
            metrics["cell"] = cell_name
            metrics["session_index"] = index
            cell_sessions.append(metrics)

        _write_gzip_lines(out_dir / "sessions" / f"{cell_name}.jsonl.gz", lines)
        efficiencies = [s["efficiency"] for s in cell_sessions]
        summary["cells"][cell_name] = {
            "n_sessions": len(cell_sessions),
            "mean_efficiency": sum(efficiencies) / len(efficiencies),
            "sessions": cell_sessions,
        }

    import json

    with open(out_dir / "summary.json", "w") as f:
        json.dump(summary, f, sort_keys=True, indent=1)
    write_manifest(results_root, results_root / "MANIFEST.sha256")
    return summary


def load_session_logs(path: Path | str) -> list[dict[str, Any]]:
    """Read one cell's gzip JSONL session logs back into dicts."""
    import json

    with gzip.open(path, "rt") as f:
        return [json.loads(line) for line in f if line.strip()]


def _write_gzip_lines(path: Path, lines: list[str]) -> None:
    """Gzip with mtime pinned to 0: byte-identical on regeneration."""
    with open(path, "wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            with io.TextIOWrapper(gz, encoding="utf-8") as text:
                for line in lines:
                    text.write(line + "\n")


if __name__ == "__main__":
    import argparse

    # `python -m agentic_trading.runner` loads this file twice (as __main__
    # and as agentic_trading.runner). Route through the canonical import so
    # isinstance checks see one set of Action classes, not two.
    from agentic_trading import runner as _canonical

    parser = argparse.ArgumentParser(description="Run a config-driven experiment")
    parser.add_argument("config", help="path to configs/<experiment>.yaml")
    parser.add_argument("--results-root", default="results")
    args = parser.parse_args()
    result = _canonical.run_experiment(
        _canonical.load_config(args.config), args.results_root
    )
    for name, cell in result["cells"].items():
        print(f"{name}: n={cell['n_sessions']} mean_efficiency={cell['mean_efficiency']:.3f}")
