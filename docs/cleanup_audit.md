# Cleanup Audit Plan (scrap-hypatia-lab)

## Scope and current experiments

**Primary experiments called out by current docs:**

- Option 2 toy-graph experiment (`python -m sim.experiment_min`).
- Option 3 Hypatia seam experiment (`python -m sim.experiment_hypatia`).
- Experiment 001 (ISL tasking vs ground-gated baseline) with analysis/plotting helpers.

These are the experiments preserved in the cleanup plan below.

## Audit commands used

- `ls`
- `rg --files -g 'AGENTS.md'`
- `rg -n "animate_trace|trace" -S`
- `rg -n "TraceWriter|animate" -S`
- `rg -n "admit\(" -S`
- `rg -n "sim\.run|run\.py" -S README.md README_experiment.md docs scripts sim`

## Cleanup plan (file-by-file)

Legend: **ACTIVE & REQUIRED**, **ARCHIVE CANDIDATE**, **DELETE**, **MOVE / RENAME**.

### Root docs

| File | Category | Why unused/misleading? | Superseded by | Proposed action |
| --- | --- | --- | --- | --- |
| `README.md` | ACTIVE & REQUIRED | Primary repo overview and current experiment entrypoints. | N/A | Keep. |
| `README_experiment.md` | MOVE / RENAME | Describes Experiment 001 but is not referenced by the main README; root-level placement suggests it is the main README. | Move under `docs/experiments/experiment_001.md` and link from `README.md`. | Move/rename + add link. |

### Experiment drivers (sim/)

| File | Category | Why unused/misleading? | Superseded by | Proposed action |
| --- | --- | --- | --- | --- |
| `sim/experiment_min.py` | ACTIVE & REQUIRED | Option 2 experiment entrypoint referenced in README. | N/A | Keep. |
| `sim/experiment_hypatia.py` | ACTIVE & REQUIRED | Option 3 seam experiment referenced in README. | N/A | Keep. |
| `sim/experiment_isl_tasking.py` | ACTIVE & REQUIRED | Experiment 001 driver referenced by `README_experiment.md`. | N/A | Keep. |
| `sim/hypatia_stub.py` | ACTIVE & REQUIRED | Default Hypatia stand-in for Option 3 and Experiment 001. | N/A | Keep. |
| `sim/hypatia_real.py` | ACTIVE & REQUIRED | Real Hypatia CLI-backed schedule adapter used by Option 3. | N/A | Keep. |
| `sim/leo_data.py` | ACTIVE & REQUIRED | TLE parsing and sampling used by Option 3 stub. | N/A | Keep. |
| `sim/run.py` | MOVE / RENAME | Standalone backend sanity check is not referenced by docs and is not an experiment. Current location implies an experiment driver. | N/A | Move to `tools/` or `scripts/` as a `check_scrap_backend.py` utility, or delete if unused. |

### Adapters & core glue

| File | Category | Why unused/misleading? | Superseded by | Proposed action |
| --- | --- | --- | --- | --- |
| `scrap_hypatia/adapter.py` | ACTIVE & REQUIRED | Core Hypatia adapter used by Option 3 experiments. | N/A | Keep. |
| `adapters/scrap_backend.py` | ACTIVE & REQUIRED | Backend selection logic used by experiments. | N/A | Keep. |
| `adapters/scrap_stub.py` | MOVE / RENAME | Contains duplicated `admit` method definitions that are never referenced; suggests unused interface surface. | No current callers. | Remove duplicate method or remove unused `admit` entirely. |
| `adapters/scap_real.py` | ACTIVE & REQUIRED | Real SCRAP CLI adapter used when `SCRAP_BACKEND=real`. | N/A | Keep. |

### Analysis & visualization

| File | Category | Why unused/misleading? | Superseded by | Proposed action |
| --- | --- | --- | --- | --- |
| `analysis/metrics.py` | ACTIVE & REQUIRED | Computes Experiment 001 metrics. | N/A | Keep. |
| `analysis/plot_experiment.py` | ACTIVE & REQUIRED | Renders Experiment 001 SVG summary. | N/A | Keep. |
| `tools/animate_ring.py` | ACTIVE & REQUIRED | Visualization helper for Experiment 001 logs. | N/A | Keep. |
| `tools/animate_orbit.py` | ACTIVE & REQUIRED | Visualization helper for Experiment 001 logs. | N/A | Keep. |
| `tools/common_log.py` | ACTIVE & REQUIRED | Shared log parsing for animation tools. | N/A | Keep. |
| `docs/visualization.md` | ACTIVE & REQUIRED | Documents current visualization helpers. | N/A | Keep (consider linking from README). |
| `scripts/run_animation.ps1` | ARCHIVE CANDIDATE | Not referenced by docs; overlaps with documented Python commands. | `docs/visualization.md` commands. | Keep under `scripts/` if used by Windows users, or move to `docs/` appendix; otherwise archive/delete. |
| **Missing** `viz/trace.py` & `viz/animate_trace` | DELETE (doc/flag cleanup) | README references a `viz` module that does not exist; `sim.experiment_hypatia` tries to import it but silently disables tracing. | Current `tools/animate_*` scripts cover Experiment 001 only. | Remove the `--trace` flag and README instructions *or* add the missing module; prefer deletion if not actively used. |

### Tests

| File | Category | Why unused/misleading? | Superseded by | Proposed action |
| --- | --- | --- | --- | --- |
| `tests/test_hypatia_stub.py` | ACTIVE & REQUIRED | Exercises Option 3 stub path. | N/A | Keep. |
| `tests/test_hypatia_real_smoke.py` | ACTIVE & REQUIRED | Integration smoke test for real Hypatia. | N/A | Keep. |
| `tests/conftest.py` | ACTIVE & REQUIRED | Test path setup. | N/A | Keep. |
| `pytest.ini` | ACTIVE & REQUIRED | Defines integration marker. | N/A | Keep. |

### Data & dependencies

| File | Category | Why unused/misleading? | Superseded by | Proposed action |
| --- | --- | --- | --- | --- |
| `data/tle_leo_sample.txt` | ACTIVE & REQUIRED | Default local TLE catalog used by Option 3. | N/A | Keep. |
| `vendor/tasklib/` | DELETE | Empty vendor directory; no references or content. | N/A | Remove directory. |

### Misc

| File | Category | Why unused/misleading? | Superseded by | Proposed action |
| --- | --- | --- | --- | --- |
| `docs/wsl2_hypatia_setup.md` | ACTIVE & REQUIRED | Setup instructions referenced by README. | N/A | Keep. |
| `scripts/setup_wsl2_hypatia.sh` | ACTIVE & REQUIRED | Helper script referenced by setup docs. | N/A | Keep. |

## Proposed minimal directory structure

```text
scrap-hypatia-lab/
├── README.md
├── docs/
│   ├── experiments/
│   │   └── experiment_001.md
│   ├── visualization.md
│   ├── wsl2_hypatia_setup.md
│   └── cleanup_audit.md
├── sim/
│   ├── experiment_min.py
│   ├── experiment_hypatia.py
│   ├── experiment_isl_tasking.py
│   ├── hypatia_stub.py
│   ├── hypatia_real.py
│   └── leo_data.py
├── scrap_hypatia/
│   └── adapter.py
├── adapters/
│   ├── scrap_backend.py
│   ├── scrap_stub.py
│   └── scap_real.py
├── analysis/
│   ├── metrics.py
│   └── plot_experiment.py
├── tools/
│   ├── animate_ring.py
│   ├── animate_orbit.py
│   ├── common_log.py
│   └── hypatia_cli.py
├── scripts/
│   └── setup_wsl2_hypatia.sh
├── data/
│   └── tle_leo_sample.txt
└── tests/
    ├── conftest.py
    ├── test_hypatia_stub.py
    └── test_hypatia_real_smoke.py
```

## What the repo is after cleanup

After cleanup, this repo is a focused experimental harness for two current research threads: (1) the Option 2 toy-graph SCRAP integrity/leakage experiment and (2) the Option 3 Hypatia seam experiment with a real/stub back-end boundary. Experiment 001 is clearly documented under `docs/experiments/` with its analysis and visualization pipeline, while setup and visualization instructions live in `docs/` and tooling lives in `tools/`.

The cleanup removes misleading stubs (like missing `viz` modules) and consolidates experiment docs so external reviewers can quickly see what is runnable today, what is supporting tooling, and what is legacy or optional.

## Optional commit plan

1. **Cleanup commit 1 (docs + structure):** Move `README_experiment.md` to `docs/experiments/experiment_001.md`, add a link from `README.md`, add/update `docs/cleanup_audit.md`.
2. **Cleanup commit 2 (remove dead paths):** Remove `vendor/tasklib/`, remove the unused `--trace` flag and `viz` references, and remove duplicate/unused methods from `adapters/scrap_stub.py`.
3. **Cleanup commit 3 (tooling):** Move `sim/run.py` to `tools/check_scrap_backend.py` or delete it if not needed; optionally archive `scripts/run_animation.ps1` if Windows users do not depend on it.
