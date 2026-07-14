# Reproducing the results

> Status: skeleton (Stage 0). Sections are filled in as stages complete; measured
> wall-clock times per tier are added in Stage 7 on a reference machine.

LLM APIs are inherently non-replayable — models are updated, deprecated, and sample
stochastically. This project's reproducibility spine is therefore **log-and-replay**:
every LLM interaction is captured in append-only JSONL under
`results/<experiment_id>/sessions/`, the exchange engine is deterministic given an
order sequence, and **all** statistics, tables, and figures are computed from logs,
never from live calls. You can verify everything without an API key.

## Tier 1 — Verify claims (≤10 min, CPU laptop, no API key)

```bash
uv sync --frozen
# run the numbered notebooks in notebooks/ top-to-bottom
```

The notebooks replay committed session logs and **assert** every headline number
against `CLAIMS.md`. If a notebook runs green, the claims it covers are verified.

## Tier 2 — Recompute everything (≤1 hr, no API key)

```bash
uv run python -m agentic_trading.reproduce --tier 2
```

Regenerates all metrics, statistical tests, tables, and figures from the raw JSONL
logs, including re-running every statistical test, and cross-checks the results
against `CLAIMS.md`.

## Tier 3 — Re-run experiments (local model required; frontier cells at your own cost)

- **Local-8B cells are fully re-runnable:** the model is pinned by exact HF
  revision/quantization hash in the experiment config. Expect *statistical*
  reproduction (same distributions within pre-registered tolerances), not bit-exact
  transcripts — sampling is stochastic by design (temperature > 0).
- **Frontier-API cells are archival:** re-running them queries whatever the provider
  now serves, which may be a different model than the one logged. For these cells,
  Tier 3 offers **replay-only** verification (Tiers 1–2). This asymmetry is the
  honest ceiling of LLM reproducibility, and we state it plainly rather than
  pretending otherwise.

## Integrity

`results/MANIFEST.sha256` hashes all session logs, configs, and derived tables:

```bash
uv run python -c "from pathlib import Path; from agentic_trading.manifest import verify_manifest; print(verify_manifest(Path('results')) or 'OK')"
```
