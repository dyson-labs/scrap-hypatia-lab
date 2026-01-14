# Visualization

## Ring animation (histogram)

Each ring animation now includes a time–space diagram and a cumulative completion curve to
help compare mode A (GSs only) against mode B (ISLs forwarding).

```bash
python tools/animate_ring.py --log runs/modeA.jsonl --out runs/anim_ring_modeA.mp4
python tools/animate_ring.py --log runs/modeB.jsonl --out runs/anim_ring_modeB.mp4
```

## Orbit animation

Orbit animations now include the same time–space diagram and cumulative completion curve
for quick visual comparison between mode A and mode B runs.

```bash
python tools/animate_orbit.py --log runs/modeA.jsonl --out runs/anim_orbit_modeA.mp4
python tools/animate_orbit.py --log runs/modeB.jsonl --out runs/anim_orbit_modeB.mp4
```
