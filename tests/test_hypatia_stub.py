from sim.experiment_hypatia import run_trial


def test_stub_run_trial_metrics_sane():
    result = run_trial(
        steps=3,
        inject_per_step=2,
        seed=7,
        attack_p=0.0,
        outage_p=0.0,
        congestion_p=0.0,
        ttl_steps=5,
        deadline_steps=4,
        n_sats=10,
        n_ground=2,
        tle_source=None,
    )

    assert result["injected"] >= 0
    assert result["delivered"] >= 0
    assert 0.0 <= result["availability"] <= 1.0
    assert 0.0 <= result["verified"] <= 1.0
    assert 0.0 <= result["reachability"] <= 1.0
    assert result["completed"] <= result["total_jobs"]


def test_stub_run_trial_deterministic():
    args = dict(
        steps=2,
        inject_per_step=1,
        seed=11,
        attack_p=0.0,
        outage_p=0.0,
        congestion_p=0.0,
        ttl_steps=4,
        deadline_steps=3,
        n_sats=6,
        n_ground=1,
        tle_source=None,
    )
    result_a = run_trial(**args)
    result_b = run_trial(**args)
    assert result_a == result_b
