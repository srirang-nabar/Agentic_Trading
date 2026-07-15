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
    Dividend,
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
    recent_trade_prices: tuple[int, ...] = ()  # last 10 this session, oldest first
    # carry-over institutions (SSW) only: total periods, so agents/renderers
    # can state remaining payouts; None marks a per-period (Smith) view, in
    # which schedule-based validation applies.
    n_periods: int | None = None


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


def run_ssw_session(
    market: "Any",  # experiments.ssw.SSWMarket
    agents: dict[str, Agent],
    *,
    steps_per_period: int,
    poll_seed: int,
) -> dict[str, Any]:
    """Run one SSW session (carry-over endowments + per-period dividends).

    Identical activation protocol to run_session. The realized dividend is
    applied as a Dividend EVENT after each period close, so the event log
    stays the complete session input and replay needs no RNG (HYPOTHESES A3).
    """
    spec = market.spec
    traders = [
        TraderConfig(trader_id=tid, cash=cash, endowed_units=shares)
        for tid, cash, shares in market.traders
    ]
    trader_ids = sorted(t.trader_id for t in traders)
    if sorted(agents) != trader_ids:
        raise ValueError("agents must match traders exactly")

    exchange = Exchange(traders, carry_over=True)
    rng = random.Random(poll_seed)

    for period in range(1, spec.n_periods + 1):
        exchange.apply(PeriodOpen())
        for step in range(steps_per_period):
            trader_id = trader_ids[rng.randrange(len(trader_ids))]
            view = _view(exchange, trader_id, step, n_periods=spec.n_periods)
            action = agents[trader_id].act(view)
            exchange.apply(_to_event(trader_id, action))
        exchange.apply(PeriodClose())
        exchange.apply(Dividend(amount=market.dividends[period - 1]))

    log = exchange.session_log()
    log["config"] = {
        "n_periods": spec.n_periods,
        "steps_per_period": steps_per_period,
        "poll_seed": poll_seed,
        "activation": "uniform_random_polling",
    }
    log["ssw"] = {
        "dividend_values": list(spec.dividend_values),
        "dividends": list(market.dividends),
        "shares_outstanding": spec.shares_outstanding,
    }
    return log


def _view(
    exchange: Exchange, trader_id: str, step: int, n_periods: int | None = None
) -> AgentView:
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
        recent_trade_prices=tuple(t["price"] for t in exchange.trades[-10:]),
        n_periods=n_periods,
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
    from agentic_trading.agents.zi import build_ssw_zi_agents, build_zi_agents
    from agentic_trading.bubbles import ssw_metrics
    from agentic_trading.experiments.smith import SmithMarketSpec, generate_smith_market
    from agentic_trading.experiments.ssw import (
        SSWMarketSpec,
        generate_ssw_market,
        render_experience,
    )
    from agentic_trading.metrics import session_metrics
    from agentic_trading.replay import session_log_to_json

    from agentic_trading.manifest import write_manifest

    experiment_id = config["experiment_id"]
    base_seed = config["seed"]
    market_cfg = config["market"]
    design = config.get("design", "smith")
    if design == "smith":
        spec = SmithMarketSpec(
            n_buyers=market_cfg["n_buyers"],
            n_sellers=market_cfg["n_sellers"],
            units_per_trader=market_cfg["units_per_trader"],
            price_low=market_cfg["price_low"],
            price_high=market_cfg["price_high"],
            cash_endowment=market_cfg["cash_endowment"],
            min_equilibrium_quantity=market_cfg.get("min_equilibrium_quantity", 3),
        )
    elif design == "ssw":
        spec = SSWMarketSpec(
            n_periods=market_cfg["n_periods"],
            dividend_values=tuple(market_cfg["dividend_values"]),
            endowment_classes=tuple(
                (int(c), int(s)) for c, s in market_cfg["endowment_classes"]
            ),
            traders_per_class=market_cfg["traders_per_class"],
            price_low=market_cfg["price_low"],
            price_high=market_cfg["price_high"],
        )
    elif design == "duopoly":
        from agentic_trading.experiments.duopoly import DuopolySpec

        spec = DuopolySpec(
            reference_value=market_cfg["reference_value"],
            arrival_rate=market_cfg["arrival_rate"],
            inventory_phi=market_cfg["inventory_phi"],
            max_half_spread=market_cfg["max_half_spread"],
            n_rounds=market_cfg["n_rounds"],
            probe_rounds=tuple(market_cfg["probe_rounds"]),
        )
    else:
        raise ValueError(f"unknown design: {design!r}")

    results_root = Path(results_root)
    out_dir = results_root / experiment_id
    (out_dir / "sessions").mkdir(parents=True, exist_ok=True)
    with open(out_dir / "config.yaml", "w") as f:
        yaml.safe_dump(config, f, sort_keys=True)

    summary: dict[str, Any] = {"experiment_id": experiment_id, "cells": {}}
    # matched_schedules (HYPOTHESES A2.ii): market + polling seeds are shared
    # across cells for a session index, so every cell trades session i in the
    # identical market with the identical polling order.
    seed_scope_shared = config.get("matched_schedules", False)
    for cell in config["cells"]:
        cell_name = cell["name"]
        seed_scope = "shared" if seed_scope_shared else cell_name
        is_llm = cell["agent_type"] in ("llm", "mixed")
        # Pure-simulation cells stay sequential so their gzip output remains
        # bit-reproducible; LLM cells are I/O-bound and parallelize safely
        # (independent sessions, one client+recorder each).
        parallel = int(config.get("parallel_sessions", 1)) if is_llm else 1

        # Experience treatment (A3.iii-iv): the source cell must appear
        # earlier in the config; its committed logs supply the transcripts,
        # and the dividend seed is tagged so the fresh path can't be leaked
        # by the transcript.
        experience_source = cell.get("experience_from")
        experience_logs = (
            load_session_logs(out_dir / "sessions" / f"{experience_source}.jsonl.gz")
            if experience_source
            else None
        )

        def run_one(index: int, cell=cell, cell_name=cell_name, seed_scope=seed_scope,
                    experience_logs=experience_logs):
            agent_type = cell["agent_type"]
            market_tags = ("market", "experienced") if experience_logs else ("market",)
            market_rng = random.Random(
                derive_seed(base_seed, seed_scope, index, *market_tags)
            )
            recorder = None
            llm_agents = None
            if design == "smith":
                traders, eq = generate_smith_market(market_rng, spec)
                if agent_type in ("zi_c", "zi_u"):
                    agents = build_zi_agents(
                        traders,
                        kind=agent_type,
                        max_price=spec.price_high,
                        seed_for=lambda tid, i=index: derive_seed(base_seed, cell_name, i, "agent", tid),
                    )
                elif agent_type == "llm":
                    agents, recorder = _build_llm_agents(traders, cell["llm"], spec.price_high)
                    llm_agents = agents
                else:
                    raise ValueError(f"unknown agent_type: {agent_type!r}")
                log = run_session(
                    traders,
                    agents,
                    n_periods=market_cfg["n_periods"],
                    steps_per_period=market_cfg["steps_per_period"],
                    poll_seed=derive_seed(base_seed, seed_scope, index, "poll"),
                )
            elif design == "duopoly":
                from agentic_trading.experiments.duopoly import (
                    BRQuoter,
                    duopoly_session_metrics,
                    run_duopoly_session,
                )

                mm_ids = ["MM0", "MM1"]
                llm_ids = (
                    mm_ids if agent_type == "llm"
                    else list(cell["mixed"]["llm_trader_ids"]) if agent_type == "mixed"
                    else None
                )
                if llm_ids is None:
                    raise ValueError(f"unknown agent_type: {agent_type!r}")
                llm_agents, recorder = _build_llm_market_makers(
                    llm_ids, cell["llm"], spec
                )
                quoters = []
                for mm in mm_ids:
                    if mm in llm_agents:
                        quoters.append(llm_agents[mm])
                    else:
                        init_rng = random.Random(
                            derive_seed(base_seed, cell_name, index, "agent", mm)
                        )
                        quoters.append(
                            BRQuoter(spec, init_rng.randint(1, spec.max_half_spread))
                        )
                log = run_duopoly_session(
                    spec,
                    quoters,
                    flow_seed=derive_seed(base_seed, seed_scope, index, "flow"),
                )
                log["meta"] = {
                    "experiment_id": experiment_id,
                    "cell": cell_name,
                    "agent_type": agent_type,
                    "session_index": index,
                }
                _attach_llm_capture(log, cell, llm_agents, recorder, coordination=True)
                metrics = duopoly_session_metrics(log)
                metrics["cell"] = cell_name
                metrics["session_index"] = index
                metrics["validity"] = log["meta"]["validity"]
                return session_log_to_json(log), metrics
            else:  # ssw
                market = generate_ssw_market(spec, market_rng)
                trader_configs = [
                    TraderConfig(trader_id=tid, cash=cash, endowed_units=shares)
                    for tid, cash, shares in market.traders
                ]
                all_ids = [t.trader_id for t in trader_configs]
                llm_ids = (
                    all_ids
                    if agent_type == "llm"
                    else list(cell["mixed"]["llm_trader_ids"])
                    if agent_type == "mixed"
                    else []
                )
                agents = {}
                zi_ids = [tid for tid in all_ids if tid not in llm_ids]
                if agent_type not in ("zi_c", "llm", "mixed"):
                    raise ValueError(f"unknown agent_type: {agent_type!r}")
                if zi_ids:
                    agents.update(build_ssw_zi_agents(
                        zi_ids,
                        max_price=spec.price_high,
                        seed_for=lambda tid, i=index: derive_seed(base_seed, cell_name, i, "agent", tid),
                    ))
                if llm_ids:
                    experience_by_trader = (
                        {tid: render_experience(experience_logs[index], tid) for tid in llm_ids}
                        if experience_logs
                        else None
                    )
                    llm_traders = [t for t in trader_configs if t.trader_id in llm_ids]
                    llm_agents, recorder = _build_llm_agents(
                        llm_traders,
                        cell["llm"],
                        spec.price_high,
                        template_vars={
                            "n_periods": spec.n_periods,
                            "payouts": _payout_phrase(spec.dividend_values),
                            "mean_payout": f"{spec.expected_dividend:g}",
                        },
                        experience_by_trader=experience_by_trader,
                    )
                    agents.update(llm_agents)
                log = run_ssw_session(
                    market,
                    agents,
                    steps_per_period=market_cfg["steps_per_period"],
                    poll_seed=derive_seed(base_seed, seed_scope, index, "poll"),
                )
            log["meta"] = {
                "experiment_id": experiment_id,
                "cell": cell_name,
                "agent_type": agent_type,
                "session_index": index,
            }
            if recorder is not None:
                _attach_llm_capture(log, cell, llm_agents, recorder)
            metrics = session_metrics(log) if design == "smith" else ssw_metrics(log)
            metrics["cell"] = cell_name
            metrics["session_index"] = index
            if recorder is not None:
                metrics["validity"] = log["meta"]["validity"]
            return session_log_to_json(log), metrics

        cell_sessions = _execute_cell(
            out_dir / "sessions" / f"{cell_name}.jsonl.gz",
            run_one,
            cell["n_sessions"],
            parallel,
        )
        if design == "smith":
            headline_key, values = "mean_efficiency", [s["efficiency"] for s in cell_sessions]
        elif design == "duopoly":
            headline_key, values = "mean_markup", [s["markup"] for s in cell_sessions]
        else:
            headline_key, values = "mean_rd", [s["rd"] for s in cell_sessions]
        summary["cells"][cell_name] = {
            "n_sessions": len(cell_sessions),
            headline_key: sum(values) / len(values),
            "sessions": cell_sessions,
        }
        print(f"[{experiment_id}] {cell_name}: n={len(cell_sessions)} "
              f"{headline_key}={summary['cells'][cell_name][headline_key]:.3f}",
              flush=True)

    import json

    with open(out_dir / "summary.json", "w") as f:
        json.dump(summary, f, sort_keys=True, indent=1)
    write_manifest(results_root, results_root / "MANIFEST.sha256")
    return summary


def _payout_phrase(dividend_values: Sequence[int]) -> str:
    """(0, 8, 28, 60) -> '0, 8, 28, or 60' for the instruction templates."""
    values = [str(v) for v in dividend_values]
    return ", ".join(values[:-1]) + f", or {values[-1]}"


def _build_llm_agents(
    traders,
    llm_cfg: dict[str, Any],
    max_price: int,
    *,
    template_vars: dict[str, Any] | None = None,
    experience_by_trader: dict[str, str] | None = None,
):
    """One shared client + recorder per session; one LLMTrader per trader."""
    from agentic_trading.agents.llm import (
        AnthropicChatClient,
        LLMTrader,
        LLMTraderConfig,
        OpenAICompatClient,
        SessionRecorder,
    )

    provider = llm_cfg.get("provider", "openai_compat")
    if provider == "anthropic":
        client = AnthropicChatClient(llm_cfg["model"])
    elif provider == "openai_compat":
        client = OpenAICompatClient(llm_cfg["model"])
    else:
        raise ValueError(f"unknown provider: {provider!r}")
    recorder = SessionRecorder()
    config = LLMTraderConfig(
        model=llm_cfg["model"],
        template=llm_cfg["template"],
        temperature=llm_cfg.get("temperature", 0.7),
        max_tokens=llm_cfg.get("max_tokens", 80),
        max_price=max_price,
        k_retries=llm_cfg.get("k_retries", 3),
        persona=llm_cfg.get("persona", "neutral"),
        memory=llm_cfg.get("memory", "none"),
        template_vars=template_vars or {},
    )
    agents = {
        t.trader_id: LLMTrader(
            t.trader_id,
            client,
            recorder,
            config,
            experience=(experience_by_trader or {}).get(t.trader_id),
        )
        for t in traders
    }
    return agents, recorder


def _attach_llm_capture(log, cell, agents, recorder, *, coordination: bool = False) -> None:
    """Full-capture attachment + the invalid-by-construction completeness check."""
    from agentic_trading.agents.llm import scan_coordination, scan_recognition

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
        "provider": llm_cfg.get("provider", "openai_compat"),
        "template": llm_cfg["template"],
        "temperature": llm_cfg.get("temperature", 0.7),
        "persona": llm_cfg.get("persona", "neutral"),
        "memory": llm_cfg.get("memory", "none"),
    }
    if cell.get("experience_from"):
        log["meta"]["llm"]["experience_from"] = cell["experience_from"]
    log["meta"]["validity"] = recorder.validity_stats()
    log["meta"]["recognition_flags"] = scan_recognition(recorder.records)
    if coordination:  # duopoly guardrail (A5.vii)
        log["meta"]["coordination_flags"] = scan_coordination(recorder.records)


def _build_llm_market_makers(mm_ids, llm_cfg: dict[str, Any], spec):
    """Two dealers can share one client + recorder (one session, one log)."""
    from agentic_trading.agents.llm import (
        AnthropicChatClient,
        LLMMarketMaker,
        LLMTraderConfig,
        OpenAICompatClient,
        SessionRecorder,
    )

    provider = llm_cfg.get("provider", "openai_compat")
    if provider == "anthropic":
        client = AnthropicChatClient(llm_cfg["model"])
    elif provider == "openai_compat":
        client = OpenAICompatClient(llm_cfg["model"])
    else:
        raise ValueError(f"unknown provider: {provider!r}")
    recorder = SessionRecorder()
    config = LLMTraderConfig(
        model=llm_cfg["model"],
        template=llm_cfg["template"],
        temperature=llm_cfg.get("temperature", 0.7),
        max_tokens=llm_cfg.get("max_tokens", 80),
        k_retries=llm_cfg.get("k_retries", 3),
        persona=llm_cfg.get("persona", "neutral"),
        template_vars={
            "reference_value": spec.reference_value,
            "max_half_spread": spec.max_half_spread,
            "phi": f"{spec.inventory_phi:g}",
            "n_rounds": spec.n_rounds,
        },
    )
    agents = {
        mm: LLMMarketMaker(
            mm, client, recorder, config, max_half_spread=spec.max_half_spread
        )
        for mm in mm_ids
    }
    return agents, recorder


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


def _execute_cell(path: Path, run_one, n_sessions: int, parallel: int) -> list[dict]:
    """Run a cell's sessions, writing each log line in session-index order.

    Gzip mtime is pinned to 0 and sequential cells avoid mid-stream flushes,
    so pure-simulation output stays byte-identical on regeneration. Parallel
    (LLM) cells flush after every session for crash-safety — their bytes are
    not reproducible anyway (live sampling).
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    metrics_by_index: list[dict | None] = [None] * n_sessions
    with open(path, "wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            with io.TextIOWrapper(gz, encoding="utf-8") as text:
                if parallel <= 1:
                    for index in range(n_sessions):
                        line, metrics = run_one(index)
                        text.write(line + "\n")
                        metrics_by_index[index] = metrics
                else:
                    done: dict[int, tuple[str, dict]] = {}
                    next_index = 0
                    with ThreadPoolExecutor(max_workers=parallel) as pool:
                        futures = {pool.submit(run_one, i): i for i in range(n_sessions)}
                        for future in as_completed(futures):
                            done[futures[future]] = future.result()
                            while next_index in done:
                                line, metrics = done.pop(next_index)
                                text.write(line + "\n")
                                text.flush()
                                metrics_by_index[next_index] = metrics
                                next_index += 1
    return metrics_by_index


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
        key = next(k for k in cell if k.startswith("mean_"))
        print(f"{name}: n={cell['n_sessions']} {key}={cell[key]:.3f}")
