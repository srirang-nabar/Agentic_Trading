# Contamination probe (out-of-band recognition test)

Model: `Qwen/Qwen2.5-7B-Instruct` — 10 probes per template,
temperature 0.7. A response counts as *recognized* when it names the design
(pattern scan over the response; raw responses in `contamination_probe.json`
for manual review). Protocol: plan.md Stage 3; flagged sessions stay in the
analysis and recognition is reported as a moderator.

| Template | Recognition rate |
| --- | --- |
| smith_a | 100% |
| smith_b | 100% |
