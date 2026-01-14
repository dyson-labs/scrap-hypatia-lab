import os
import platform
from pathlib import Path

def get_backend():
    """Return a SCRAP client implementation.

    Default behavior:
      - Prefer the tasklib-backed implementation if tasklib is installed.
      - Otherwise prefer the real CLI-backed implementation if the private repo is
        present *and* we're on Windows (because the built artifact is a .exe in your repo).
      - Otherwise fall back to the pure-Python stub.

    Override behavior with:
      - SCRAP_BACKEND=stub     -> always use stub
      - SCRAP_BACKEND=real     -> force real (will raise if not available)
      - SCRAP_BACKEND=tasklib  -> force tasklib (will raise if not available)
    """

    forced = os.environ.get("SCRAP_BACKEND", "").strip().lower()
    if forced == "stub":
        from .scrap_stub import ScrapClient
        return ScrapClient()
    if forced == "tasklib":
        from .tasklib_backend import ScrapClient
        return ScrapClient()

    priv = Path(__file__).resolve().parents[1] / "deps" / "scap_private"
    is_windows = platform.system().lower().startswith("win")

    if forced == "real" or (is_windows and priv.exists() and any(priv.iterdir())):
        from .scap_real import ScrapClient
        return ScrapClient()

    if forced == "" and _tasklib_available():
        from .tasklib_backend import ScrapClient
        return ScrapClient()

    from .scrap_stub import ScrapClient
    return ScrapClient()


def _tasklib_available() -> bool:
    from importlib.util import find_spec

    return find_spec("tasklib") is not None
