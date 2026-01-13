import os
import pytest

from sim.hypatia_real import build_real_hypatia_sim, hypatia_cmd_available, is_linux_or_wsl


pytestmark = pytest.mark.integration


def test_real_hypatia_smoke(tmp_path):
    if not is_linux_or_wsl():
        pytest.skip("Real Hypatia smoke test runs only on Linux/WSL.")

    hypatia_cmd = os.environ.get("HYPATIA_CMD")
    if not hypatia_cmd or not hypatia_cmd_available(hypatia_cmd):
        pytest.skip("HYPATIA_CMD not set or not available.")

    artifact_path = tmp_path / "hypatia_schedule.json"
    sim = build_real_hypatia_sim(
        hypatia_cmd=hypatia_cmd,
        artifact_path=str(artifact_path),
        n_sats=3,
        n_ground=1,
        steps=2,
        seed=1,
    )
    assert sim.ground_nodes
    assert sim.sat_nodes
    sim.step(1)
