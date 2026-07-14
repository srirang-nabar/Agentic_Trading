"""Stage 6 gate (part 1): duopoly stage game + dual-benchmark validation.

The registered parameterization (HYPOTHESES A5): v=100, lam=5, phi=2, grid
1..20, 150 rounds. Hand derivation: expected unwind cost per unit traded is
exactly phi (Poisson variance = mean), so the stage game is discrete
Bertrand with marginal cost 2 -> zero-profit half-spread 2, Nash 4. The
myopic best-response gate certifies the Nash number empirically BEFORE any
LLM duopoly session runs (plan.md critic row 18).
"""

import random
import statistics

import pytest

from agentic_trading.experiments.duopoly import (
    DuopolySpec,
    MyopicBRAgent,
    best_response,
    expected_profit,
    nash_half_spread,
    nash_set,
    play_round,
    run_br_session,
    zero_profit_half_spread,
)

pytestmark = pytest.mark.gate_stage6

SPEC = DuopolySpec()


class TestStageGameAnalytics:
    def test_expected_profit_hand_computed(self):
        # win both sides at s=3 vs rival 5: 2 * 5 * (3 - 2) = 10
        assert expected_profit(3, 5, SPEC) == 10
        # symmetric tie at 4: 5 * (4 - 2) = 10
        assert expected_profit(4, 4, SPEC) == 10
        # wider than rival: no flow
        assert expected_profit(5, 4, SPEC) == 0
        # winning below marginal cost loses money: 2 * 5 * (1 - 2) = -10
        assert expected_profit(1, 2, SPEC) == -10

    def test_dual_benchmarks_differ(self):
        assert zero_profit_half_spread(SPEC) == 2  # = phi
        # tie-splitting Bertrand on a grid has an INTERVAL of weak Nash;
        # the H3 benchmark is its maximum (conservative against false
        # collusion findings)
        assert nash_set(SPEC) == [2, 3, 4]
        assert nash_half_spread(SPEC) == 4  # = phi + 2
        # the wedge critic row 18 warns about — never conflate the two
        assert nash_half_spread(SPEC) - zero_profit_half_spread(SPEC) == 2

    def test_best_response_undercuts_until_nash(self):
        assert best_response(10, SPEC) == 9
        assert best_response(5, SPEC) == 4
        # at the Nash spread, undercutting is profit-neutral: stay/match
        assert best_response(4, SPEC) == 4
        # below cost, concede the flow (largest zero-profit spread)
        assert best_response(1, SPEC) == SPEC.max_half_spread

    def test_analytic_profit_matches_monte_carlo(self):
        rng = random.Random(90210)
        for spreads, expected in [((4, 4), (10, 10)), ((3, 5), (10, 0))]:
            totals = [0.0, 0.0]
            n = 40_000
            for _ in range(n):
                outcome = play_round(spreads, SPEC, rng)
                totals[0] += outcome["profits"][0]
                totals[1] += outcome["profits"][1]
            assert totals[0] / n == pytest.approx(expected[0], abs=0.5)
            assert totals[1] / n == pytest.approx(expected[1], abs=0.5)


class TestBenchmarkValidationGate:
    def test_myopic_br_settles_inside_nash_set_upper_equilibrium_modal(self):
        """The registered gate: BR self-play settles INSIDE the Nash set —
        never above the H3 benchmark — with the upper equilibrium modal.
        (Simultaneous updating can also lock a (3,4)<->(4,3) two-cycle;
        that is still inside the set and still zero-markup-or-below.)"""
        nash = nash_half_spread(SPEC)
        allowed = set(nash_set(SPEC))
        at_upper = 0
        for seed in range(40):
            log = run_br_session(SPEC, random.Random(1000 + seed))
            tail = [s for r in log["rounds"][-20:] for s in r["spreads"]]
            assert all(s in allowed for s in tail), (
                f"seed {seed}: spread outside the Nash set in {sorted(set(tail))}"
            )
            assert max(tail) <= nash, f"seed {seed}: settled ABOVE the benchmark"
            if all(s == nash for s in tail):
                at_upper += 1
        assert at_upper >= 20, f"upper Nash reached in only {at_upper}/40 starts"

    def test_myopic_rival_shows_competition_signature_on_probe(self):
        """Sign-convention check (H3): a myopic rival MATCHES a probe to the
        Nash spread and never widens back above it — competition, not
        collusion. LLM sessions are read against this certified baseline."""
        rival = MyopicBRAgent(SPEC, initial=6)
        forced = [6, 6, 6, 4, 4, 4]  # probe to Nash at step 3, held after
        responses = []
        last = None
        for s in forced:
            responses.append(rival.act(last))
            last = s
        assert responses[:3] == [6, 5, 5]  # undercuts the wide quote
        assert responses[3:] == [5, 4, 4]  # matches the probe, no punishment
        assert max(responses[4:]) <= 4  # never reverts above Nash

    def test_session_is_deterministic_given_seed(self):
        a = run_br_session(SPEC, random.Random(42))
        b = run_br_session(SPEC, random.Random(42))
        assert a == b

    def test_flow_conservation_in_round(self):
        rng = random.Random(7)
        for _ in range(200):
            out = play_round((3, 4), SPEC, rng)
            assert sum(out["sells_at_ask"]) == out["n_buyers"]
            assert sum(out["buys_at_bid"]) == out["n_sellers"]
            # strictly better quote takes the whole flow
            assert out["sells_at_ask"][1] == 0 and out["buys_at_bid"][1] == 0


class TestSteadyStateMarkup:
    def test_br_markup_over_nash_is_never_positive(self):
        """The property H3 leans on: certified-competitive play can sit AT
        or BELOW the benchmark (lower equilibria, 3<->4 cycles) but never
        above it, so a positive markup CI cannot be myopic best response.
        Window = rounds 41..79 (post-burn-in, pre-probe)."""
        nash = nash_half_spread(SPEC)
        markups = []
        for seed in range(25):
            log = run_br_session(SPEC, random.Random(2000 + seed))
            window = log["rounds"][40:79]
            mean_spread = statistics.mean(s for r in window for s in r["spreads"])
            markups.append(mean_spread - nash)
        assert max(markups) <= 0.0
        assert min(markups) >= -1.0  # never below the Nash set either
