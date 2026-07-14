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
        min_equilibrium_quantity=market_cfg.get("min_equilibrium_quantity", 3),
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
            if cell["agent_type"] in ("zi_c", "zi_u"):
                agents = build_zi_agents(
                    traders,
                    kind=cell["agent_type"],
                    max_price=spec.price_high,
                    seed_for=lambda tid, i=index: derive_seed(base_seed, cell_name, i, "agent", tid),
                )
                recorder = None
            elif cell["agent_type"] == "llm":
                agents, recorder = _build_llm_agents(traders, cell["llm"], spec.price_high)
            else:
                raise ValueError(f"unknown agent_type: {cell['agent_type']!r}")
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
            if recorder is not None:
                _attach_llm_capture(log, cell, agents, recorder)
            lines.append(session_log_to_json(log))
            metrics = session_metrics(log)
            metrics["cell"] = cell_name
            metrics["session_index"] = index
            if recorder is not None:
                metrics["validity"] = log["meta"]["validity"]
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


def _build_llm_agents(traders, llm_cfg: dict[str, Any], max_price: int):
    """One shared client + recorder per session; one LLMTrader per trader."""
    from agentic_trading.agents.llm import (
        LLMTrader,
        LLMTraderConfig,
        OpenAICompatClient,
        SessionRecorder,
    )

    client = OpenAICompatClient(llm_cfg["model"])
    recorder = SessionRecorder()
    config = LLMTraderConfig(
        model=llm_cfg["model"],
        template=llm_cfg["template"],
        temperature=llm_cfg.get("temperature", 0.7),
        max_tokens=llm_cfg.get("max_tokens", 80),
        max_price=max_price,
        k_retries=llm_cfg.get("k_retries", 3),
    )
    agents = {t.trader_id: LLMTrader(t.trader_id, client, recorder, config) for t in traders}
    return agents, recorder


def _attach_llm_capture(log, cell, agents, recorder) -> None:
    """Full-capture attachment + the invalid-by-construction completeness check."""
    from agentic_trading.agents.llm import scan_recognition

    client = next(iter(agents.values())).client
    if len(recorder.records) != client.call_count:
        raise RuntimeError(
            f"log completeness violated: {client.call_count} API calls but "
            f"{len(recorder.records)} records — session is invalid by construction"
        )
    llm_cfg = cell["llm"]
    log["llm_calls"] = recorder.records
    log["meta"]["llm"] = {
        "model": llm_cfg["model"],
        "revision": llm_cfg.get("revision"),
        "template": llm_cfg["template"],
        "temperature": llm_cfg.get("temperature", 0.7),
    }
    log["meta"]["validity"] = recorder.validity_stats()
    log["meta"]["recognition_flags"] = scan_recognition(recorder.records)


def load_session_logs(path: Path | str) -> list[dict[str, Any]]:
    """Read one cell's gzip JSONL session logs back into dicts."""
    import json

    with gzip.open(path, "rt") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_budget(results_root: Path | str = "results") -> Path:
    """Regenerate results/budget.md from every experiment's logs.

    Token counts are summed from the llm_call records themselves, so the
    cost-accounting gate test can recompute them independently and demand
    an exact match. Local-model cost is GPU-time (billed hourly by the
    rental provider), tracked as wall-clock LLM time per experiment.
    """
    results_root = Path(results_root)
    rows = []
    totals = {"prompt": 0, "completion": 0, "calls": 0}
    for exp_dir in sorted(p for p in results_root.iterdir() if p.is_dir()):
        sessions_dir = exp_dir / "sessions"
        if not sessions_dir.is_dir():
            continue
        prompt = completion = calls = 0
        wall_seconds = 0.0
        for gz in sorted(sessions_dir.glob("*.jsonl.gz")):
            for log in load_session_logs(gz):
                records = log.get("llm_calls", [])
                calls += len(records)
                prompt += sum(r["prompt_tokens"] for r in records)
                completion += sum(r["completion_tokens"] for r in records)
                if records:
                    wall_seconds += records[-1]["ts"] - records[0]["ts"]
        if calls:
            rows.append(
                f"| {exp_dir.name} | {calls} | {prompt} | {completion} | "
                f"{wall_seconds / 3600:.2f} |"
            )
            totals["prompt"] += prompt
            totals["completion"] += completion
            totals["calls"] += calls

    text = (
        "# Budget ledger (regenerated from logs by `runner.write_budget`)\n\n"
        "Soft cap: **$150** for frontier-API spend (HYPOTHESES.md). Local-model\n"
        "cells cost GPU rental time, not tokens — tracked as wall-clock hours of\n"
        "LLM traffic; billable GPU hours are bounded below by this figure.\n\n"
        "| Experiment | LLM calls | Prompt tokens | Completion tokens | LLM wall-clock (h) |\n"
        "| --- | --- | --- | --- | --- |\n"
        + "\n".join(rows)
        + f"\n\n**Totals:** {totals['calls']} calls, {totals['prompt']} prompt + "
        f"{totals['completion']} completion tokens.\n\n"
        "Frontier-API dollar spend to date: **$0.00** (no frontier cells run yet).\n"
        + _projection_section(results_root)
    )
    path = results_root / "budget.md"
    path.write_text(text)
    return path


# Anthropic pricing per MTok as of 2026-07 (claude-api skill reference).
# Prompts (~600 tok) sit below these models' prompt-caching minimums, so no
# cache discount is assumed. Sequential in-session calls rule out the Batches
# API discount. Update prices when re-projecting.
_FRONTIER_PRICING = {
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-8": (5.00, 25.00),
}


def _projection_section(results_root: Path) -> str:
    """Stage 3 gate: extrapolate frontier cost from measured smoke tokens."""
    smoke = results_root / "llm_smoke" / "sessions" / "qwen_smoke.jsonl.gz"
    if not smoke.is_file():
        return ""
    logs = load_session_logs(smoke)
    records = [r for log in logs for r in log["llm_calls"]]
    in_per_call = sum(r["prompt_tokens"] for r in records) / len(records)
    out_per_call = sum(r["completion_tokens"] for r in records) / len(records)
    polls = {
        (i, r["trader_id"], r["period"], r["step"])
        for i, log in enumerate(logs)
        for r in log["llm_calls"]
    }
    retry_factor = len(records) / len(polls)

    # Pre-registered frontier design: Stage 4 Smith (2 paraphrases x 30
    # sessions x 1440 polls, 8 LLM traders) + Stage 6 duopoly (frontier pair
    # 2x150x30x2 framings + mixed pair 1x150x30x2).
    stage4_calls = 2 * 30 * 6 * 240 * retry_factor
    stage6_calls = (2 + 1) * 150 * 30 * 2 * retry_factor
    lines = [
        "\n## Stage 4-6 frontier projection (Stage 3 gate)\n",
        f"Measured on the smoke cell: {in_per_call:.0f} prompt + {out_per_call:.0f} "
        f"completion tokens/call, retry factor {retry_factor:.2f}. Projected frontier "
        f"calls: Stage 4 = {stage4_calls:,.0f}, Stage 6 = {stage6_calls:,.0f} "
        "(Stage 5 frontier cells: none pre-declared; model scale is exploratory, local-only).\n",
        "| Frontier model | Stage 4 | Stage 6 | Total | Fits $150 cap? |",
        "| --- | --- | --- | --- | --- |",
    ]
    for model, (price_in, price_out) in _FRONTIER_PRICING.items():
        def dollars(calls: float) -> float:
            return (
                calls * in_per_call * price_in + calls * out_per_call * price_out
            ) / 1e6

        s4, s6 = dollars(stage4_calls), dollars(stage6_calls)
        total = s4 + s6
        verdict = "yes" if total <= 150 else "no — pre-registered fallback required"
        lines.append(f"| {model} | ${s4:.0f} | ${s6:.0f} | **${total:.0f}** | {verdict} |")
    lines.append(
        "\nDecision recorded here per the gate: the frontier-tier model is chosen at "
        "Stage 4 kickoff. If the chosen tier exceeds the cap, the pre-registered "
        "fallback applies (paraphrase robustness on the local model; frontier runs "
        "paraphrase A only; claims scoped accordingly)."
    )
    return "\n".join(lines) + "\n"


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
