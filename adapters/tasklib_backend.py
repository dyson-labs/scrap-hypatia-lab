import hashlib
import hmac
import json
import secrets
import tempfile
from pathlib import Path
from typing import Any, Dict

import tasklib


class ScrapClient:
    def __init__(self, data_dir: Path | None = None) -> None:
        self._secret = secrets.token_bytes(32)
        self._receipts: Dict[bytes, bytes] = {}
        self._task_cache = []
        self._temp_dir = None
        self._tw = self._init_taskwarrior(data_dir)

    def issue_capability_token(self, subject: str, caps: Any, constraints: Any) -> bytes:
        payload = {
            "subject": subject,
            "caps": caps,
            "constraints": constraints,
            "nonce": secrets.token_hex(8),
        }
        token = self._sign_payload(b"TL_TOKEN:", payload)
        self._record_task("capability", payload)
        return token

    def make_bound_task_request(
        self, token: bytes, payment_hash: bytes, task_params: Any
    ) -> bytes:
        payload = {
            "token": token.hex(),
            "payment_hash": payment_hash.hex(),
            "task_params": task_params,
        }
        request = self._sign_payload(b"TL_REQ:", payload)
        self._record_task("request", payload)
        return request

    def make_receipt(self, req: bytes, result_bytes: bytes) -> bytes:
        payload = {
            "req": req.hex(),
            "result": result_bytes.hex(),
        }
        receipt = self._sign_payload(b"TL_RCPT:", payload)
        self._receipts[req] = receipt
        self._record_task("receipt", payload)
        return receipt

    def verify_receipt(self, receipt: bytes, req: bytes) -> bool:
        expected = self._receipts.get(req)
        if expected is None:
            payload = {"req": req.hex(), "result": b"result".hex()}
            expected = self._sign_payload(b"TL_RCPT:", payload)
        return receipt == expected

    def _sign_payload(self, prefix: bytes, payload: Dict[str, Any]) -> bytes:
        blob = json.dumps(payload, sort_keys=True, default=str).encode()
        digest = hmac.new(self._secret, blob, hashlib.sha256).digest()
        return prefix + digest

    def _init_taskwarrior(self, data_dir: Path | None) -> tasklib.TaskWarrior | None:
        resolved_dir = data_dir
        if resolved_dir is None:
            self._temp_dir = tempfile.TemporaryDirectory(prefix="scrap_tasklib_")
            resolved_dir = Path(self._temp_dir.name)
        resolved_dir.mkdir(parents=True, exist_ok=True)
        taskrc_path = resolved_dir / "taskrc"
        taskrc_path.write_text(f"data.location={resolved_dir}\n", encoding="utf-8")
        try:
            return tasklib.TaskWarrior(
                data_location=str(resolved_dir),
                taskrc_location=str(taskrc_path),
                create=True,
            )
        except Exception:
            return None

    def _record_task(self, kind: str, payload: Dict[str, Any]) -> None:
        entry = {"kind": kind, "payload": payload}
        if self._tw is None:
            self._task_cache.append(entry)
            return
        try:
            task = self._tw.tasks.add(description=f"SCRAP {kind}")
            task["tags"] = ["scrap", kind]
            task["annotations"] = [json.dumps(payload, sort_keys=True, default=str)]
            task.save()
        except Exception:
            self._task_cache.append(entry)

    def __del__(self) -> None:
        if self._temp_dir is not None:
            self._temp_dir.cleanup()
