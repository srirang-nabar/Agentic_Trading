"""Stage 0 gate: protocol, literature sweep & environment.

Run with: uv run pytest -m gate_stage0
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.gate_stage0


def test_package_imports():
    import agentic_trading
    from agentic_trading import manifest, metrics, replay, reproduce, runner  # noqa: F401
    from agentic_trading.agents import llm, zi  # noqa: F401
    from agentic_trading.experiments import duopoly, smith, ssw  # noqa: F401

    assert agentic_trading.__version__


def test_related_work_exists_and_is_substantive():
    related_work = ROOT / "report" / "related_work.md"
    assert related_work.is_file(), "Day-1 literature sweep is blocking for Stage 0"
    assert len(related_work.read_text()) > 2000, "related_work.md looks like a stub"


def test_hypotheses_preregistered():
    hypotheses = ROOT / "HYPOTHESES.md"
    assert hypotheses.is_file()
    text = hypotheses.read_text()
    for required in ("H1", "H2", "H3", "Holm", "temperature", "activation"):
        assert required.lower() in text.lower(), (
            f"HYPOTHESES.md missing pre-registered element: {required}"
        )
    assert "2026-07-14" in text, "HYPOTHESES.md must be dated"


def test_repro_skeleton_exists():
    assert (ROOT / "REPRODUCING.md").is_file()
    assert (ROOT / "CLAIMS.md").is_file()


def test_manifest_helper_round_trip(tmp_path):
    from agentic_trading.manifest import verify_manifest, write_manifest

    (tmp_path / "a.txt").write_text("alpha")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("beta")

    write_manifest(tmp_path)
    assert verify_manifest(tmp_path) == []

    (tmp_path / "a.txt").write_text("tampered")
    assert verify_manifest(tmp_path) == ["hash mismatch: a.txt"]
