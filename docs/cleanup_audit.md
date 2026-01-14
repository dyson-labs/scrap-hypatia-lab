# Cleanup audit

## Backend options

The SCRAP adapter layer supports three backend modes:

- **stub**: pure-Python placeholder used when no real backend is available.
- **real**: CLI-backed implementation (Windows only, with `deps/scap_private`).
- **tasklib**: Taskwarrior-backed adapter using the `tasklib` Python package.

Select the backend with `SCRAP_BACKEND`:

```bash
export SCRAP_BACKEND=stub
export SCRAP_BACKEND=real
export SCRAP_BACKEND=tasklib
```

If `SCRAP_BACKEND` is unset, the tasklib adapter is preferred when `tasklib` is installed, otherwise
Windows hosts fall back to the real CLI-backed binary, and everything else uses the stub.

## Tasklib setup

Install the tasklib dependency using:

```bash
pip install -r requirements.txt
```

Tasklib expects Taskwarrior to be available on the host, so ensure you have the `task` binary
installed if you want to persist task audit entries.
