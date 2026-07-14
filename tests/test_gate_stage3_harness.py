"""Stage 3 gate: LLM harness coding tests (all offline — scripted transport).

Covers: schema fuzzing (malformed output never crashes the harness or
corrupts the book), retry-loop semantics, log completeness, replay-equals-
live, validity accounting, and the contamination recognition scan.
"""

import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agentic_trading.agents.llm import (
    LLMTrader,
    LLMTraderConfig,
    OrderDecision,
    ScriptedClient,
    SessionRecorder,
    parse_decision,
    scan_recognition,
    validate_decision,
)
from agentic_trading.exchange import Side, TraderConfig
from agentic_trading.replay import verify_session_log
from agentic_trading.runner import AgentView, SubmitAction, run_session

pytestmark = pytest.mark.gate_stage3

CFG = LLMTraderConfig(model="test-model", template="smith_a", k_retries=3)


def view(**overrides) -> AgentView:
    defaults = dict(
        trader_id="B1", period=1, step=0, best_bid=40, best_ask=60,
        last_trade_price=50, cash_available=400, inventory_available=0,
        remaining_values=(90, 70), remaining_costs=(), open_orders=(),
    )
    defaults.update(overrides)
    return AgentView(**defaults)


def make_trader(responses: list[str], config: LLMTraderConfig = CFG):
    recorder = SessionRecorder()
    client = ScriptedClient(responses)
    return LLMTrader("B1", client, recorder, config), client, recorder


class TestParsing:
    def test_valid_forms(self):
        for text in (
            '{"action": "bid", "price": 42}',
            '  {"action": "pass", "price": null}  ',
            '```json\n{"action": "ask", "price": 100}\n```',
            '{"action": "cancel", "price": null}',
        ):
            decision, error = parse_decision(text)
            assert error is None and isinstance(decision, OrderDecision)

    def test_invalid_forms_return_errors_not_exceptions(self):
        for text in (
            "I would like to bid 42 francs",
            '{"action": "buy", "price": 42}',       # wrong verb
            '{"action": "bid"}',                     # missing price
            '{"action": "bid", "price": "42"}',      # string price (strict)
            '{"action": "bid", "price": 42.5}',      # float price
            '{"action": "bid", "price": true}',      # bool price
            '{"action": "pass", "price": 3}',        # price on pass
            '{"action": "bid", "price": 42, "note": "hi"}',  # extra key
            '[{"action": "bid", "price": 42}]',      # list
            '"bid 42"', "", "{", "null", "42",
        ):
            decision, error = parse_decision(text)
            assert decision is None and isinstance(error, str), text

    @settings(max_examples=300)
    @given(st.text(max_size=400))
    def test_parser_is_total_over_arbitrary_text(self, text):
        decision, error = parse_decision(text)
        assert (decision is None) != (error is None)


class TestSemanticValidation:
    def test_buyer_cannot_ask_and_seller_cannot_bid(self):
        buyer = view()
        decision, _ = parse_decision('{"action": "ask", "price": 50}')
        assert "cannot sell" in validate_decision(decision, buyer, max_price=200)
        seller = view(remaining_values=(), remaining_costs=(30,), inventory_available=1)
        decision, _ = parse_decision('{"action": "bid", "price": 50}')
        assert "cannot buy" in validate_decision(decision, seller, max_price=200)

    def test_price_bounds_and_cash(self):
        decision, _ = parse_decision('{"action": "bid", "price": 500}')
        assert "between 1 and 200" in validate_decision(decision, view(), max_price=200)
        decision, _ = parse_decision('{"action": "bid", "price": 90}')
        assert "francs available" in validate_decision(
            decision, view(cash_available=50), max_price=200
        )

    def test_cancel_requires_open_order(self):
        decision, _ = parse_decision('{"action": "cancel", "price": null}')
        assert "no resting offer" in validate_decision(decision, view(), max_price=200)
        assert validate_decision(
            decision, view(open_orders=((3, "buy", 40),)), max_price=200
        ) is None


class TestRetryLoop:
    def test_invalid_then_valid_with_feedback(self):
        trader, client, recorder = make_trader(
            ["gibberish", '{"action": "bid", "price": 999}', '{"action": "bid", "price": 55}']
        )
        action = trader.act(view())
        assert action == SubmitAction(side=Side.BUY, price=55)
        assert client.call_count == 3
        assert [r["attempt"] for r in recorder.records] == [0, 1, 2]
        # Error feedback from attempt N appears in attempt N+1's user message.
        second_user = recorder.records[1]["messages"][1]["content"]
        assert "previous reply was invalid" in second_user
        third_user = recorder.records[2]["messages"][1]["content"]
        assert "between 1 and 200" in third_user

    def test_retries_bounded_then_forced_pass(self):
        trader, client, recorder = make_trader(["junk"] * 10)
        assert trader.act(view()) is None
        assert client.call_count == CFG.k_retries + 1
        stats = recorder.validity_stats()
        assert stats == {
            "n_llm_polls": 1, "n_llm_calls": 4, "validity_rate": 0.0,
            "first_attempt_rate": 0.0, "forced_passes": 1,
        }

    def test_transport_error_recorded_and_passes(self):
        class ExplodingClient:
            call_count = 0

            def complete(self, messages, *, temperature, max_tokens):
                self.call_count += 1
                raise ConnectionError("boom")

        recorder = SessionRecorder()
        trader = LLMTrader("B1", ExplodingClient(), recorder, CFG)
        assert trader.act(view()) is None
        assert len(recorder.records) == 1
        assert "transport error" in recorder.records[0]["error"]


class TestLogCompleteness:
    @settings(max_examples=100)
    @given(st.lists(st.text(max_size=60), min_size=1, max_size=8))
    def test_one_record_per_api_call_with_hash_and_model(self, responses):
        trader, client, recorder = make_trader(responses)
        trader.act(view())
        assert len(recorder.records) == client.call_count >= 1
        for record in recorder.records:
            assert record["model"] == "test-model"
            assert len(record["template_sha256"]) == 64
            assert record["raw_response"] is not None


ROSTER = (
    TraderConfig("B1", cash=400, values=(90, 70)),
    TraderConfig("B2", cash=400, values=(80,)),
    TraderConfig("S1", costs=(20, 40)),
)


def run_scripted_session(response_streams: dict[str, list[str]]):
    recorder = SessionRecorder()
    agents = {
        tid: LLMTrader(tid, ScriptedClient(stream), recorder, CFG)
        for tid, stream in response_streams.items()
    }
    log = run_session(ROSTER, agents, n_periods=2, steps_per_period=20, poll_seed=99)
    log["llm_calls"] = recorder.records
    return log, recorder


class TestSessionIntegration:
    def test_replay_equals_live_for_llm_session(self):
        log, _ = run_scripted_session(
            {
                "B1": ['{"action": "bid", "price": 50}'] * 5,
                "B2": ['{"action": "bid", "price": 45}'] * 5,
                "S1": ['{"action": "ask", "price": 48}'] * 5,
            }
        )
        assert log["trades"], "scripted quotes should cross"
        assert verify_session_log(log) == []

    @settings(max_examples=50, deadline=1000)
    @given(
        st.lists(st.text(max_size=50), max_size=6),
        st.lists(st.text(max_size=50), max_size=6),
    )
    def test_garbage_output_never_corrupts_the_book(self, junk_a, junk_b):
        log, _ = run_scripted_session(
            {"B1": junk_a, "B2": junk_b, "S1": ['{"action": "ask", "price": 25}'] * 3}
        )
        assert verify_session_log(log) == []
        accounts = {a["trader_id"]: a for a in log["final"]["accounts"]}
        total_cash = sum(a["cash"] for a in accounts.values())
        assert total_cash == sum(t.cash for t in ROSTER), "cash not conserved"
        for account in accounts.values():
            assert account["cash"] >= 0


class TestRecognitionScan:
    def test_flags_verbalized_recognition(self):
        records = [
            {"trader_id": "B1", "period": 1, "step": 3, "attempt": 0,
             "raw_response": "This looks like Vernon Smith's double auction!"},
            {"trader_id": "B2", "period": 1, "step": 4, "attempt": 0,
             "raw_response": '{"action": "pass", "price": null}'},
        ]
        flags = scan_recognition(records)
        assert len(flags) == 1
        assert "double auction" in flags[0]["patterns"]

    def test_prompt_templates_do_not_leak_design_names(self):
        from agentic_trading.agents.llm import PromptTemplate, RECOGNITION_PATTERNS

        for name in ("smith_a", "smith_b"):
            text = PromptTemplate.load(name).text.lower()
            for pattern in RECOGNITION_PATTERNS:
                assert pattern not in text, f"{name} leaks {pattern!r}"
