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

## Running the experiments

### Option 2 (toy graph + explicit tamper model)

```bash
python -m sim.experiment_min
```

### Option 3 (Hypatia seam; currently uses a stub)

The Option 3 experiment uses `sim/hypatia_stub.py` to stand in for Hypatia so you can land the
integration plumbing immediately. Once you add real Hypatia, swap the stub out.

```bash
python -m sim.experiment_hypatia
```

This prints *headline metrics* that map to the intended "onion-routing-ish" story:

- **avail**: delivered / injected (network availability under outages/congestion)
- **verified**: verified_ok / (verified_ok + verified_bad) (receipt verification under tamper)
- **reach**: completed / jobs (end-to-end feasibility within a deadline)
- **ttfs_mean / ttfs_p90**: time-to-first-success in **timesteps** (inject → verified receipt)

### Optional: generate an animated GIF

The experiment can write a JSONL trace suitable for simple animation:

```bash
python -m sim.experiment_hypatia --trace runs/demo_trace.jsonl
python -m viz.animate_trace runs/demo_trace.jsonl --out runs/demo.gif
```

The resulting GIF is designed for blog posts / briefings.

## Backends

By default the code prefers the real CLI-backed implementation on Windows (since the built artifact in
`deps/scap_private` is a `.exe`). Override with:

```bash
set SCRAP_BACKEND=stub   # (PowerShell: $env:SCRAP_BACKEND='stub')
set SCRAP_BACKEND=real
```

## How to hook in real Hypatia

The only contract you need is in `scrap_hypatia/adapter.py`:

- HypatiaTransport expects a `hypatia_sim` object with:
  - `inject_packet(pkt)`
  - `on_delivery(cb)` where `cb(pkt)` is called when the packet arrives
  - optional: `on_drop(cb)` where `cb(pkt, reason)` is called when a packet is dropped

If your Hypatia API looks different, keep the rest of the repo intact and adapt only those calls.
