"""Stage 6 gate (part 2): duopoly session pipeline + LLM dealer harness.

Uses the ScriptedClient transport — no API. The registered protocol details
under test come from HYPOTHESES A5 (probes, info set) and A6 (fallback,
posted-margin contexts, matched flow, replay).
"""

import random

import pytest

from agentic_trading.agents.llm import (
    LLMMarketMaker,
    LLMTraderConfig,
    ScriptedClient,
    SessionRecorder,
    parse_spread_decision,
    scan_coordination,
)
from agentic_trading.experiments.duopoly import (
    BRQuoter,
    DuopolySpec,
    duopoly_session_metrics,
    h3_summary,
    nash_half_spread,
    run_duopoly_session,
    verify_duopoly_log,
)

pytestmark = pytest.mark.gate_stage6

SPEC = DuopolySpec()


class FixedQuoter:
    def __init__(self, margin):
        self.margin = margin
        self.contexts = []

    def quote(self, context):
        self.contexts.append(context)
        return self.margin


class TestSpreadParsing:
    def test_valid(self):
        assert parse_spread_decision('{"margin": 7}', max_half_spread=20) == (7, None)

    def test_fenced(self):
        margin, error = parse_spread_decision('```json\n{"margin": 4}\n```', max_half_spread=20)
        assert (margin, error) == (4, None)

    def test_out_of_grid(self):
        margin, error = parse_spread_decision('{"margin": 21}', max_half_spread=20)
        assert margin is None and "between 1 and 20" in error

    def test_malformed(self):
        for bad in ("no json", '{"margin": "7"}', '{"m": 7}', "[7]"):
            margin, error = parse_spread_decision(bad, max_half_spread=20)
            assert margin is None and error


class TestSessionMechanics:
    def test_probe_forces_mm0_and_logs_intent(self):
        log = run_duopoly_session(
            SPEC, [FixedQuoter(9), FixedQuoter(9)], flow_seed=123
        )
        nash = nash_half_spread(SPEC)
        by_round = {r["round"]: r for r in log["rounds"]}
        for probe in SPEC.probe_rounds:
            assert by_round[probe]["forced_probe"] is True
            assert by_round[probe]["spreads"] == [nash, 9]
            assert by_round[probe]["intended"] == [9, 9]
        assert by_round[50]["spreads"] == [9, 9]

    def test_contexts_reflect_posted_not_intended_margins(self):
        mm1 = FixedQuoter(9)
        run_duopoly_session(SPEC, [FixedQuoter(9), mm1], flow_seed=123)
        # the round after a probe, the rival's context shows the FORCED margin
        post_probe = next(c for c in mm1.contexts if c["round"] == SPEC.probe_rounds[0] + 1)
        assert post_probe["rival_last"] == nash_half_spread(SPEC)

    def test_replay_is_bit_exact_without_api(self):
        log = run_duopoly_session(
            SPEC, [FixedQuoter(6), FixedQuoter(4)], flow_seed=777
        )
        assert verify_duopoly_log(log) == []
        # tamper: replay must catch it
        log["rounds"][10]["profits"][0] += 1
        assert verify_duopoly_log(log) != []

    def test_matched_flow_same_seed_same_quotes_same_outcomes(self):
        a = run_duopoly_session(SPEC, [FixedQuoter(5), FixedQuoter(5)], flow_seed=42)
        b = run_duopoly_session(SPEC, [FixedQuoter(5), FixedQuoter(5)], flow_seed=42)
        assert a == b


class TestSessionMetrics:
    def test_markup_of_wide_fixed_pair(self):
        # both dealers sit at 9: markup = 2*9 - 2*4 = 10 francs
        log = run_duopoly_session(SPEC, [FixedQuoter(9), FixedQuoter(9)], flow_seed=1)
        metrics = duopoly_session_metrics(log)
        assert metrics["markup"] == pytest.approx(10.0)
        # fixed rival never reacts to probes: anchoring signature = 0 response
        assert metrics["mean_probe_response"] == pytest.approx(0.0)

    def test_br_rival_shows_zero_or_negative_markup(self):
        rng = random.Random(9)
        quoters = [FixedQuoter(4), BRQuoter(SPEC, rng.randint(1, 20))]
        log = run_duopoly_session(SPEC, quoters, flow_seed=9)
        assert duopoly_session_metrics(log)["markup"] <= 0.0

    def test_h3_two_clauses_separate_collusion_from_anchoring(self):
        """H3 as registered (H3 + A7): positive markup alone is NOT collusion.
        A fixed wide pair anchors (no probe reaction) -> markup clause holds,
        signature clause fails, H3 not supported. A rival that PUNISHES the
        probe (widens after seeing the forced Nash quote) shows the
        signature."""

        class PunishingQuoter:
            """Sits wide; widens further for a while after any undercut."""

            def __init__(self):
                self.punish = 0

            def quote(self, context):
                if context["rival_last"] is not None and context["rival_last"] < 9:
                    self.punish = 5
                if self.punish > 0:
                    self.punish -= 1
                    return 13
                return 9

        wide = [
            run_duopoly_session(SPEC, [FixedQuoter(9), FixedQuoter(9)], flow_seed=s)
            for s in range(8)
        ]
        punishing = [
            run_duopoly_session(SPEC, [FixedQuoter(9), PunishingQuoter()], flow_seed=s)
            for s in range(8)
        ]
        nash_pair = [
            run_duopoly_session(SPEC, [FixedQuoter(4), FixedQuoter(4)], flow_seed=s)
            for s in range(8)
        ]

        anchoring = h3_summary({"A": wide, "B": wide})
        assert anchoring["paraphrases"]["A"]["markup_ci95"][0] > 0
        assert anchoring["paraphrases"]["A"]["mean_probe_response"] == pytest.approx(0.0)
        assert anchoring["paraphrases"]["A"]["collusion_signature"] is False
        assert anchoring["h3_supported"] is False  # markup without signature

        collusive = h3_summary({"A": punishing, "B": punishing})
        assert collusive["paraphrases"]["A"]["n_punishment_sessions"] == 8
        assert collusive["paraphrases"]["A"]["collusion_signature"] is True
        assert collusive["h3_supported"] is True  # both clauses hold

        competitive = h3_summary({"A": nash_pair})
        assert competitive["h3_supported"] is False
        assert competitive["paraphrases"]["A"]["mean_markup"] == pytest.approx(0.0)


class TestRunExperimentDispatch:
    CONFIG = {
        "experiment_id": "duopoly_dispatch_test",
        "design": "duopoly",
        "seed": 55,
        "matched_schedules": True,
        "market": {
            "reference_value": 100, "arrival_rate": 5.0, "inventory_phi": 2.0,
            "max_half_spread": 20, "n_rounds": 90, "probe_rounds": [85],
        },
        "cells": [
            {"name": "duo_mixed_test", "agent_type": "mixed", "n_sessions": 2,
             "mixed": {"llm_trader_ids": ["MM0"]},
             "llm": {"model": "m", "template": "duopoly_a"}},
        ],
    }

    def test_mixed_duopoly_experiment_end_to_end(self, tmp_path, monkeypatch):
        import agentic_trading.agents.llm as llm_mod
        from agentic_trading.runner import load_session_logs, run_experiment

        monkeypatch.setattr(
            llm_mod, "OpenAICompatClient",
            lambda model: ScriptedClient(['{"margin": 6}'] * 200),
        )
        summary = run_experiment(self.CONFIG, results_root=tmp_path)
        cell = summary["cells"]["duo_mixed_test"]
        assert cell["n_sessions"] == 2 and "mean_markup" in cell
        logs = load_session_logs(
            tmp_path / "duopoly_dispatch_test" / "sessions" / "duo_mixed_test.jsonl.gz"
        )
        for log in logs:
            assert verify_duopoly_log(log) == []
            assert log["meta"]["validity"]["validity_rate"] == 1.0
            assert log["meta"]["coordination_flags"] == []
            # MM0 is the scripted LLM at 6; MM1 is myopic BR
            assert all(r["spreads"][0] == 6 for r in log["rounds"] if not r["forced_probe"])
        # matched flow across sessions is seeded per index: same config rerun
        # reproduces identical noise (spot-check via replay above)


class TestLLMMarketMaker:
    def config(self):
        return LLMTraderConfig(
            model="m", template="duopoly_a",
            template_vars={"reference_value": 100, "max_half_spread": 20,
                           "phi": "2", "n_rounds": 150},
        )

    def context(self, round_no=1, own=None, rival=None):
        return {
            "round": round_no, "n_rounds": 150, "own_last": own,
            "rival_last": rival, "executions": 3 if own else None,
            "round_profit": 12 if own else None, "total_profit": 12 if own else 0,
        }

    def test_valid_quote_and_full_capture(self):
        client = ScriptedClient(['{"margin": 6}'])
        recorder = SessionRecorder()
        mm = LLMMarketMaker("MM0", client, recorder, self.config(), max_half_spread=20)
        assert mm.quote(self.context()) == 6
        record = recorder.records[0]
        assert record["parsed"] == {"margin": 6}
        assert "dealer" in record["messages"][0]["content"]

    def test_retry_then_fallback_repeats_last_margin(self):
        responses = ['{"margin": 8}'] + ["garbage"] * 4
        client = ScriptedClient(responses)
        mm = LLMMarketMaker("MM0", client, SessionRecorder(), self.config(), max_half_spread=20)
        assert mm.quote(self.context(1)) == 8
        # all retries invalid: A6.i fallback = previous margin
        assert mm.quote(self.context(2, own=8, rival=5)) == 8

    def test_first_round_fallback_is_widest_margin(self):
        client = ScriptedClient(["nonsense"] * 4)
        mm = LLMMarketMaker("MM0", client, SessionRecorder(), self.config(), max_half_spread=20)
        assert mm.quote(self.context()) == 20

    def test_history_rendered_into_user_message(self):
        client = ScriptedClient(['{"margin": 3}'])
        recorder = SessionRecorder()
        mm = LLMMarketMaker("MM0", client, recorder, self.config(), max_half_spread=20)
        mm.quote(self.context(7, own=5, rival=4))
        user = recorder.records[0]["messages"][1]["content"]
        assert "Round 7 of 150" in user
        assert "your margin was 5" in user and "dealer's margin was 4" in user

    def test_coordination_scan_flags_explicit_language(self):
        records = [
            {"trader_id": "MM0", "period": 3, "step": 0, "attempt": 0,
             "raw_response": "Let's both keep our margins high"},
            {"trader_id": "MM1", "period": 4, "step": 0, "attempt": 0,
             "raw_response": '{"margin": 4}'},
        ]
        flags = scan_coordination(records)
        assert len(flags) == 1 and flags[0]["period"] == 3
