# scrap-hypatia-lab
Utilizing SCAP/SISL (SCRAP) inside Hypatia to characterize performance and demonstrate utility.

## Status

- Option 1: plumbing + toy metrics ✅
- Option 2: adversarial integrity tests ✅
- Option 3: embed SCRAP in Hypatia 🚧

Option 3 is **system integration** (not "another security option").
Hypatia provides topology/link outages/mobility/congestion.
SCRAP provides authorization/receipts/integrity/confidentiality tradeoffs.

This repo now contains a minimal "seam" that lets you drive SCRAP over a Hypatia-provided model.

## Quick start (new to the repo)

If you just want to run the default Experiment 001 workflow (simulation → metrics → plots → animations),
follow these steps. You do **not** need Hypatia installed for this path.

1) **Run the simulation (produces JSONL logs):**

```bash
python -m sim.experiment_isl_tasking
```

This writes:
- `runs/modeA.jsonl` (ground-gated baseline)
- `runs/modeB.jsonl` (ISL-forwarded)

2) **Compute metrics (writes a CSV summary):**

```bash
python -m analysis.metrics
```

3) **Generate the summary plot (SVG):**

```bash
python -m analysis.plot_experiment
```

4) **Generate animations (GIF/MP4):**

> Note: use the **module** form (`python -m tools.animate_*`) so imports work on Windows.

```bash
python -m tools.animate_ring --log runs/modeA.jsonl --out runs/anim_ring_modeA.mp4
python -m tools.animate_ring --log runs/modeB.jsonl --out runs/anim_ring_modeB.mp4
python -m tools.animate_orbit --log runs/modeA.jsonl --out runs/anim_orbit_modeA.mp4
python -m tools.animate_orbit --log runs/modeB.jsonl --out runs/anim_orbit_modeB.mp4
```

Animations require:
- `matplotlib` and `pillow` (Python packages)
- `ffmpeg` (optional, for MP4; without it, GIFs are generated)

If you want a full “stress” run (max attack/outage/congestion):

```bash
python -m sim.experiment_isl_tasking --attack-p 1.0 --outage-p 1.0 --congestion-p 1.0
```

## Running the experiments

### Option 2 (toy graph + explicit tamper model)

```bash
python -m sim.experiment_min
```

### Option 3 (Hypatia seam; currently uses a stub by default)

The Option 3 experiment uses `sim/hypatia_stub.py` to stand in for Hypatia so you can land the
integration plumbing immediately. Once you add real Hypatia, swap the stub out.
Even in real schedule mode, packet drops from `--outage` and `--congestion` are synthetic
probability-based events applied at delivery time (they do not come from Hypatia itself).

```bash
python -m sim.experiment_hypatia
```

To use a real Hypatia schedule generator (WSL/Linux only):

```bash
export HYPATIA_CMD="python -m hypatia.cli"
python -m sim.experiment_hypatia --hypatia-mode real --hypatia-cmd "$HYPATIA_CMD"
```

Quick sanity check for the real Hypatia command wrapper:

```bash
python -m sim.experiment_hypatia --hypatia-mode real --hypatia-cmd "python tools/hypatia_cli.py --ping"
```

This prints *headline metrics* that map to the intended "onion-routing-ish" story:

- **avail**: delivered / injected (network availability under outages/congestion)
- **verified**: verified_ok / (verified_ok + verified_bad) (receipt verification under tamper)
- **reach**: completed / jobs (end-to-end feasibility within a deadline)
- **ttfs_mean / ttfs_p90**: time-to-first-success in **timesteps** (inject → verified receipt)

### Experiment 001 (ISL tasking vs ground-gated baseline)

See `docs/experiments/experiment_001.md` for the full workflow (run, metrics, plots) of
Experiment 001.

### Visualization helpers

Experiment 001 includes visualization helpers documented in `docs/visualization.md`.

## Backends

The SCRAP seam supports multiple backends:

- `stub`: pure-Python fallback (default).
- `real`: private CLI-backed implementation (Windows + `deps/scap_private`).
- `tasklib`: Taskwarrior-backed adapter (requires `tasklib`).

By default the code prefers the tasklib implementation if `tasklib` is installed; otherwise it
prefers the real CLI-backed implementation on Windows (since the built artifact in
`deps/scap_private` is a `.exe`). Override with:

```bash
set SCRAP_BACKEND=stub    # (PowerShell: $env:SCRAP_BACKEND='stub')
set SCRAP_BACKEND=real
set SCRAP_BACKEND=tasklib
```

To enable the tasklib adapter, install dependencies:

```bash
pip install -r requirements.txt
```

## How to hook in real Hypatia

The only contract you need is in `scrap_hypatia/adapter.py`:

- HypatiaTransport expects a `hypatia_sim` object with:
  - `inject_packet(pkt)`
  - `on_delivery(cb)` where `cb(pkt)` is called when the packet arrives
  - optional: `on_drop(cb)` where `cb(pkt, reason)` is called when a packet is dropped
  - optional: `step(n)` and `can_send(src, dst, meta)` if you want pre-flight checks

### Wiring a real Hypatia simulator

You can point the experiment at a real Hypatia simulator class using:

```bash
python -m sim.experiment_hypatia \
  --hypatia-sim your_pkg.hypatia_sim:HypatiaSim \
  --hypatia-sim-kwargs '{"config_path": "path/to/config.json"}' \
  --ground-nodes "ground-0,ground-1"
```

If your simulator exposes `sat_nodes` and `ground_nodes`, the experiment will use those directly.
Otherwise, pass `--ground-nodes` and ensure your sim exposes `n_sats` or `sat_nodes`.

### TLE sources

The experiment accepts:

- Local file paths (e.g. `data/tle_leo_sample.txt`)
- URLs (e.g. `https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle`)
- Named sources:
  - `celestrak:active`
  - `celestrak:leo`

Remote downloads are cached under `data/cache`.

If your Hypatia API looks different, keep the rest of the repo intact and adapt only those calls.

## Testing

Stub-only (runs anywhere):

```bash
pytest
```

Integration (WSL/Linux + Hypatia only):

```bash
pytest -m integration
```

Expected runtimes are seconds, not minutes. Integration tests are opt-in and skipped automatically when Hypatia is unavailable.

## WSL2 Hypatia setup

See `docs/wsl2_hypatia_setup.md` for a WSL2-specific setup guide.
