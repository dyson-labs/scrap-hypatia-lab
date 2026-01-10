import hashlib
import secrets

class ScrapClient:
    def issue_capability_token(self, subject, caps, constraints):
        payload = f"{subject}|{caps}|{constraints}|{secrets.token_hex(8)}".encode()
        return b"STUB_TOKEN:" + hashlib.sha256(payload).digest()

    def make_bound_task_request(self, token, payment_hash, task_params):
        payload = token + b"|" + payment_hash + b"|" + repr(task_params).encode()
        return b"STUB_REQ:" + hashlib.sha256(payload).digest()

    def make_receipt(self, req, result_bytes):
        h = hashlib.sha256(req + b"|" + result_bytes).digest()
        return b"STUB_RCPT:" + h

    def verify_receipt(self, receipt, req):
        expected = self.make_receipt(req, b"result")
        return receipt == expected



    def admit(self, req, meta=None):
        return True, ""



    def admit(self, req, meta=None):
        return True, ""

