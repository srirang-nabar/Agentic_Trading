"""Config-driven experiment runner (Stages 2–6).

Responsibilities:
- Load `configs/*.yaml` (market design, agent roster, model, prompt variant,
  seeds, session count) and execute sessions.
- Write results to `results/<experiment_id>/` with the config copied
  alongside; append-only JSONL session logs under `sessions/`.
- Enforce the no-discard rule and per-session token-cost tracking
  (running total in results/budget.md, $150 soft cap).
- Every experiment has a `--smoke` variant (3 sessions, local model)
  exercising the identical code path.
"""
