"""LLM trading agents (Stage 3).

Responsibilities:
- Agent loop: market-state rendering → prompt (paraphrased human-subject
  instructions per the contamination protocol) → structured order via a
  strict pydantic JSON schema → submit.
- Retry-on-invalid with error feedback (max k retries, then pass);
  order-validity rate logged per model.
- Full-capture logging: every request/response to JSONL — rendered prompt,
  raw response, parsed order, validity/retry events, model ID, temperature,
  prompt-template hash, timestamps, token counts. A session with any missing
  log record is invalid by construction.
- Sampling temperature > 0, pre-registered in HYPOTHESES.md.
"""
