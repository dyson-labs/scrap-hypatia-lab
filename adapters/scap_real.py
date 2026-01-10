import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAP_DIR = ROOT / "deps" / "scap_private"
CLI = SCAP_DIR / "target" / "debug" / "scap-cli.exe"

def _hex_to_bytes(s: str) -> bytes:
    return bytes.fromhex(s.strip())

class ScrapClient:
    def __init__(self):
        if not CLI.exists():
            raise RuntimeError(
                f"Expected CLI at {CLI}. "
                f"Build it with: (cd deps/scap_private) cargo build -p scap-cli"
            )

    def issue_capability_token(self, subject, caps, constraints):
        out = subprocess.check_output([str(CLI), "issue-token"], text=True)
        return _hex_to_bytes(out)

    def make_bound_task_request(self, token, payment_hash, task_params):
        out = subprocess.check_output([str(CLI), "make-request"], text=True)
        return _hex_to_bytes(out)

    def make_receipt(self, req, result_bytes):
        out = subprocess.check_output([str(CLI), "make-receipt"], text=True)
        return _hex_to_bytes(out)

    def verify_receipt(self, receipt, req):
        return subprocess.call([str(CLI), "verify-receipt"]) == 0
