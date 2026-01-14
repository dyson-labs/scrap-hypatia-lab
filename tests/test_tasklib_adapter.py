import pytest


tasklib = pytest.importorskip("tasklib")


from adapters.tasklib_backend import ScrapClient


def test_tasklib_receipt_roundtrip():
    client = ScrapClient()
    token = client.issue_capability_token("alice", ["read"], {"scope": "demo"})
    req = client.make_bound_task_request(token, b"payment", {"job": "demo"})
    receipt = client.make_receipt(req, b"result")

    assert client.verify_receipt(receipt, req)
    assert receipt.startswith(b"TL_RCPT:")
