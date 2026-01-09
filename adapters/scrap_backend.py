from pathlib import Path

def get_backend():
    priv = Path(__file__).resolve().parents[1] / "deps" / "scap_private"
    try:
        if priv.exists() and any(priv.iterdir()):
            from .scap_real import ScrapClient
            return ScrapClient()
    except Exception:
        pass

    from .scrap_stub import ScrapClient
    return ScrapClient()
