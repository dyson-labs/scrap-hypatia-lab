"""Sanity check for the configured SCRAP backend."""

from adapters.scrap_backend import get_backend


def main():
    scrap = get_backend()
    print("SCRAP backend:", scrap.__class__.__name__)

    token = scrap.issue_capability_token(
        subject="sat-A",
        caps=["svc:downlink"],
        constraints={"max_hops": 2, "time_window_s": 600},
    )

    req = scrap.make_bound_task_request(
        token=token,
        payment_hash=b"\x11" * 32,
        task_params={"size_bytes": 5_000_000, "deadline_s": 600},
    )

    receipt = scrap.make_receipt(req, b"hello world")
    ok = scrap.verify_receipt(receipt, req)
    print("Receipt verifies:", ok)

if __name__ == "__main__":
    main()
