"""Stage 2 gate: the Gode-Sunder calibration certificate (HARD gate).

Statistical acceptance tests at pre-registered thresholds (HYPOTHESES.md),
computed from the committed session logs in results/zi_baseline — never
from live simulation. Plus: bit-exact regeneration of the whole experiment
from its config, replay verification, and the no-discard audit.

If ZI-C efficiency fails here, the engine or the metrics are wrong. Stop.
"""

import math
from pathlib import Path

import pytest
from scipy import stats

from agentic_trading.metrics import rank_biserial, session_metrics
from agentic_trading.replay import verify_session_log
from agentic_trading.runner import load_config, load_session_logs, run_experiment

pytestmark = pytest.mark.gate_stage2

ROOT = Path(__file__).resolve().parent.parent
EXPERIMENT = ROOT / "results" / "zi_baseline"
CONFIG = ROOT / "configs" / "zi_baseline.yaml"

# Pre-registered thresholds (HYPOTHESES.md, Stage 2 calibration section).
ZIC_MEAN_FLOOR = 0.90
ZIC_CI_FAILURE_REGION = 0.85
MW_P_THRESHOLD = 0.001
EFFECT_SIZE_FLOOR = 0.5


@pytest.fixture(scope="module")
def logs():
    return {
        cell: load_session_logs(EXPERIMENT / "sessions" / f"{cell}.jsonl.gz")
        for cell in ("zi_c", "zi_u")
    }


@pytest.fixture(scope="module")
def efficiencies(logs):
    return {
        cell: [session_metrics(log)["efficiency"] for log in cell_logs]
        for cell, cell_logs in logs.items()
    }


def test_zic_efficiency_gate(efficiencies):
    e = efficiencies["zi_c"]
    n = len(e)
    mean = sum(e) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in e) / (n - 1))
    lower_cb = mean - stats.t.ppf(0.95, n - 1) * sd / math.sqrt(n)
    assert mean >= ZIC_MEAN_FLOOR, f"ZI-C mean efficiency {mean:.3f} below floor"
    assert lower_cb > ZIC_CI_FAILURE_REGION, (
        f"95% lower confidence bound {lower_cb:.3f} does not exclude the failure region"
    )


def test_zic_beats_ziu(efficiencies):
    zi_c, zi_u = efficiencies["zi_c"], efficiencies["zi_u"]
    u, p = stats.mannwhitneyu(zi_c, zi_u, alternative="greater")
    r = rank_biserial(u, len(zi_c), len(zi_u))
    assert p < MW_P_THRESHOLD, f"Mann-Whitney one-sided p={p:.2e} not significant"
    assert r >= EFFECT_SIZE_FLOOR, f"rank-biserial r={r:.3f} below 'large' floor"


def test_no_discard_audit(logs):
    config = load_config(CONFIG)
    configured = {c["name"]: c["n_sessions"] for c in config["cells"]}
    logged = {cell: len(cell_logs) for cell, cell_logs in logs.items()}
    assert logged == configured, "logged session counts must equal configured counts"


def test_every_tenth_session_replays_bit_exactly(logs):
    for cell_logs in logs.values():
        for log in cell_logs[::10]:
            assert verify_session_log(log) == []


def test_full_experiment_regenerates_bit_identically(tmp_path):
    """Pure-simulation cells are bit-reproducible from config — prove it."""
    config = load_config(CONFIG)
    run_experiment(config, results_root=tmp_path)
    for cell in ("zi_c", "zi_u"):
        stored = (EXPERIMENT / "sessions" / f"{cell}.jsonl.gz").read_bytes()
        regenerated = (tmp_path / "zi_baseline" / "sessions" / f"{cell}.jsonl.gz").read_bytes()
        assert stored == regenerated, f"{cell}: regeneration differs from committed logs"


def test_claims_md_matches_logs(efficiencies):
    """The pytest half of the CLAIMS.md ledger (GS-1..GS-4)."""
    from agentic_trading.reproduce import load_claims

    claims = {row["claim_id"]: row["value"] for row in load_claims()}
    zi_c, zi_u = efficiencies["zi_c"], efficiencies["zi_u"]
    u, p = stats.mannwhitneyu(zi_c, zi_u, alternative="greater")
    computed = {
        "GS-1": f"{sum(zi_c) / len(zi_c):.3f}",
        "GS-2": f"{sum(zi_u) / len(zi_u):.3f}",
        "GS-3": "<0.001" if p < 0.001 else f"{p:.3f}",
        "GS-4": f"{rank_biserial(u, len(zi_c), len(zi_u)):.3f}",
    }
    for claim_id, value in computed.items():
        assert claims.get(claim_id) == value, (
            f"{claim_id}: CLAIMS.md says {claims.get(claim_id)!r}, logs give {value!r}"
        )
