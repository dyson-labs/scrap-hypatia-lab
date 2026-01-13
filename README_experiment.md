# Experiment 001: ISL Tasking vs Ground-Gated Baseline

Goal: quantify the operational benefit of ISL-forwarded tasking with limited permissions vs ground-gated tasking.

## Fixed parameters

- 20 satellites, 2 ground stations
- Simulation duration: 24 hours (144 steps at 10 minutes/step)
- Task stream: 1 task every 10 minutes (144/day)
- Task TTL: 90 minutes (deadline = created_at + 9 steps)
- Ground contact window: every 60 minutes (every 6 steps)
- Default acceptance radius: 2.0 (can be overridden via `--radius`)

## Run the experiment

```bash
python -m sim.experiment_isl_tasking
```

This writes:

- `runs/modeA.jsonl` (ground-gated baseline)
- `runs/modeB.jsonl` (ISL-forwarded with restricted capability token)

## Compute metrics

```bash
python -m analysis.metrics
```

This prints a comparison table and writes `runs/summary.csv`.

## Expected result

Mode B should reduce p90 latency and deadline misses relative to Mode A.
