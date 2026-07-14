"""Claim verification and (Stage 7) the volunteer reproduction entry point.

`verify_claims(notebook_id, computed)` is the final cell of every notebook:
it parses CLAIMS.md and asserts that each claim attributed to that notebook
matches the value the notebook just computed from the logs. A claim without
a green assert may not appear in the README.

Stage 7 adds `python -m agentic_trading.reproduce --tier 2`: regenerate all
metrics, tests, tables, and figures from raw JSONL logs, no API key.
"""

from __future__ import annotations

from pathlib import Path

_CLAIMS_PATH = Path(__file__).resolve().parents[2] / "CLAIMS.md"


def load_claims(path: Path | str = _CLAIMS_PATH) -> list[dict[str, str]]:
    """Parse the CLAIMS.md table into row dicts."""
    rows = []
    for line in Path(path).read_text().splitlines():
        if not line.startswith("|") or line.startswith("| --") or line.startswith("| Claim ID"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 6 and cells[0]:
            rows.append(
                {
                    "claim_id": cells[0],
                    "claim": cells[1],
                    "value": cells[2],
                    "notebook_cell": cells[3],
                    "pytest_test": cells[4],
                    "log_source": cells[5],
                }
            )
    return rows


def verify_claims(
    notebook_id: str, computed: dict[str, str], path: Path | str = _CLAIMS_PATH
) -> str:
    """Assert every CLAIMS.md row for this notebook against computed values."""
    rows = [r for r in load_claims(path) if notebook_id in r["notebook_cell"]]
    if not rows:
        raise AssertionError(f"no CLAIMS.md rows reference notebook {notebook_id!r}")
    for row in rows:
        claim_id = row["claim_id"]
        if claim_id not in computed:
            raise AssertionError(f"notebook did not compute claim {claim_id}")
        if computed[claim_id] != row["value"]:
            raise AssertionError(
                f"claim {claim_id}: notebook computed {computed[claim_id]!r} "
                f"but CLAIMS.md says {row['value']!r}"
            )
    return f"OK: {len(rows)} claim(s) verified against CLAIMS.md"
