"""Stage 5 gate (part 1): bubble metrics on hand-worked toy sessions.

Every expected value below is computed by hand from the formulas fixed in
HYPOTHESES.md A3.vi before any Stage 5 session ran. Experiment QC tests are
added alongside the committed logs (test_gate_stage5.py).
"""

import pytest

from agentic_trading.bubbles import (
    fundamental_values,
    h2_summary,
    period_prices,
    shape_criterion,
    ssw_metrics,
)

pytestmark = pytest.mark.gate_stage5


def make_log(n_periods, trades, dividend_values=(0, 8, 28, 60), shares=12):
    return {
        "final": {"period": n_periods},
        "trades": [{"period": p, "price": price} for p, price in trades],
        "ssw": {
            "dividend_values": list(dividend_values),
            "dividends": [0] * n_periods,
            "shares_outstanding": shares,
        },
    }


# 4-period toy, FV = (96, 72, 48, 24), FV_bar = 60:
# period 1: prices 90, 98 -> mean 94, deviation -2
# period 2: price 92      -> deviation +20  (peak)
# period 3: price 50      -> deviation +2
# period 4: price 25      -> deviation +1
TOY = make_log(4, [(1, 90), (1, 98), (2, 92), (3, 50), (4, 25)])


class TestFundamentalValues:
    def test_registered_ssw_schedule(self):
        fv = fundamental_values(15, [0, 8, 28, 60])
        assert fv[0] == 360 and fv[-1] == 24
        assert fv[1] - fv[0] == -24
        assert sum(fv) / 15 == 192  # FV_bar used to normalize RAD/RD

    def test_toy_schedule(self):
        assert fundamental_values(4, [0, 8, 28, 60]) == (96, 72, 48, 24)


class TestSessionMetrics:
    def test_period_prices_mean_and_median(self):
        assert period_prices(TOY, "mean")[1] == 94
        assert period_prices(TOY, "median")[1] == 94
        log = make_log(1, [(1, 10), (1, 20), (1, 90)])
        assert period_prices(log, "mean")[1] == 40
        assert period_prices(log, "median")[1] == 20

    def test_rad_and_rd_hand_computed(self):
        m = ssw_metrics(TOY)
        assert m["rad"] == pytest.approx((2 + 20 + 2 + 1) / 4 / 60)
        assert m["rd"] == pytest.approx((-2 + 20 + 2 + 1) / 4 / 60)

    def test_untraded_periods_are_omitted_not_zero_filled(self):
        # only periods 1 and 3 trade: deviations -2 and +2, N = 2
        log = make_log(4, [(1, 94), (3, 50)])
        m = ssw_metrics(log)
        assert m["rad"] == pytest.approx((2 + 2) / 2 / 60)
        assert m["rd"] == pytest.approx(0.0)
        assert m["n_traded_periods"] == 2

    def test_amplitude_king_et_al(self):
        # (max dev - min dev) / FV_1 = (20 - (-2)) / 96
        assert ssw_metrics(TOY)["amplitude"] == pytest.approx(22 / 96)

    def test_duration_longest_rising_run(self):
        # deviations -2, +20, +2, +1 -> longest strictly rising run is 2
        assert ssw_metrics(TOY)["duration"] == 2

    def test_duration_broken_by_untraded_period(self):
        # deviations 0, +5 | gap | +6, +7: runs of 2 and 2, never 3
        log = make_log(
            5, [(1, 120), (2, 101), (4, 54), (5, 31)]
        )  # FV = (120, 96, 72, 48, 24)
        assert ssw_metrics(log)["duration"] == 2

    def test_turnover(self):
        assert ssw_metrics(TOY)["turnover"] == pytest.approx(5 / 12)

    def test_zero_trade_session(self):
        m = ssw_metrics(make_log(4, []))
        assert m["rd"] == 0.0 and m["rad"] == 0.0
        assert m["amplitude"] is None and m["duration"] is None
        assert m["turnover"] == 0.0 and m["shape_ok"] is False
        assert m["zero_trade_session"] is True


class TestShapeCriterion:
    def test_peak_inside_window_with_crash_passes(self):
        assert shape_criterion(TOY, window=(2, 3)) is True

    def test_peak_outside_window_fails(self):
        assert shape_criterion(TOY, window=(3, 12)) is False

    def test_no_positive_peak_fails(self):
        log = make_log(4, [(1, 90), (2, 60), (3, 40), (4, 20)])  # all below FV
        assert shape_criterion(log, window=(1, 4)) is False

    def test_no_crash_fails(self):
        # peak +20 in period 3, but final two deviations average >= half peak
        log = make_log(4, [(1, 96), (2, 72), (3, 68), (4, 40)])  # devs 0,0,20,16
        assert shape_criterion(log, window=(2, 3)) is False

    def test_fewer_than_two_traded_periods_fails(self):
        assert shape_criterion(make_log(4, [(2, 92)]), window=(1, 4)) is False


def bubble_log():
    """15-period log passing the registered (3, 12) window.

    Deviations (single trade per traded period): period 1: -60, period 3:
    +188 (peak), period 14: +12, period 15: +6 -> tail mean 9 < 94.
    """
    return make_log(15, [(1, 300), (3, 500), (14, 60), (15, 30)])


class TestH2Summary:
    def test_sign_and_shape_binomials_exact(self):
        logs = [bubble_log() for _ in range(6)]
        summary = h2_summary({"A": logs, "B": logs})
        cell = summary["paraphrases"]["A"]
        assert cell["n_rd_positive"] == 6 and cell["n_shape_ok"] == 6
        assert cell["p_rd_sign"] == pytest.approx(1 / 64)
        assert cell["p_shape"] == pytest.approx(1 / 64)
        assert summary["conjunction_p"] == pytest.approx(1 / 64)
        assert summary["h2_supported"] is True

    def test_negative_rd_not_supported(self):
        log = make_log(15, [(1, 100), (2, 100)])  # deviations -260, -236
        summary = h2_summary({"A": [log] * 6})
        cell = summary["paraphrases"]["A"]
        assert cell["n_rd_positive"] == 0
        assert cell["p_rd_sign"] == pytest.approx(1.0)
        assert summary["h2_supported"] is False

    def test_experience_wilcoxon_all_positive_pairs(self):
        inexp = [bubble_log() for _ in range(6)]
        # experienced sessions trade closer to FV -> smaller RD, distinct diffs
        exp = [
            make_log(15, [(1, 300), (3, 500 - 12 * k), (14, 60), (15, 30)])
            for k in range(1, 7)
        ]
        summary = h2_summary(
            {"A": inexp}, experienced_logs=exp, paired_inexperienced_logs=inexp
        )
        e = summary["experience"]
        assert e["n_pairs"] == 6
        assert e["mean_rd_reduction"] > 0
        assert e["p_wilcoxon"] == pytest.approx(1 / 64)
