"""The gate's asymmetry, pinned: capability has a tolerance band, safety has none."""

import pytest

from gauntlet.gate import gate


def report(capability=None, leaks=None):
    return {"capability_pass_rate": capability, "leak_rates": leaks or {}}


def test_capability_drop_inside_the_band_passes():
    result = gate(report(capability=0.98), report(capability=1.0), max_drop=2)
    assert result.ok


def test_capability_drop_exactly_at_the_band_passes():
    result = gate(report(capability=0.96), report(capability=0.98), max_drop=2)
    assert result.ok


def test_capability_drop_past_the_band_fails():
    result = gate(report(capability=0.95), report(capability=0.98), max_drop=2)
    assert not result.ok


def test_capability_improvement_passes():
    assert gate(report(capability=1.0), report(capability=0.8), max_drop=0).ok


@pytest.mark.parametrize("rise", [0.5, 0.05, 0.0001])
def test_any_leak_rate_rise_fails_however_small(rise):
    result = gate(
        report(capability=1.0, leaks={"exfiltration": rise}),
        report(capability=1.0, leaks={"exfiltration": 0.0}),
        max_drop=100,
    )
    assert not result.ok


def test_an_unchanged_leak_rate_passes():
    result = gate(
        report(leaks={"exfiltration": 0.25}),
        report(leaks={"exfiltration": 0.25}),
        max_drop=0,
    )
    assert result.ok


def test_a_leak_rate_fall_passes():
    result = gate(
        report(leaks={"exfiltration": 0.0}),
        report(leaks={"exfiltration": 0.9}),
        max_drop=0,
    )
    assert result.ok


def test_a_family_absent_from_the_baseline_is_treated_as_zero():
    rising = gate(report(leaks={"new_family": 0.1}), report(leaks={}), max_drop=100)
    clean = gate(report(leaks={"new_family": 0.0}), report(leaks={}), max_drop=100)
    assert not rising.ok
    assert clean.ok


def test_a_family_that_vanished_from_the_current_run_fails_loudly():
    result = gate(report(leaks={}), report(leaks={"exfiltration": 0.0}), max_drop=100)
    assert not result.ok


def test_a_missing_capability_number_is_not_treated_as_a_drop():
    assert gate(report(capability=None), report(capability=1.0), max_drop=0).ok


def test_the_failure_reasons_name_the_metric_that_regressed():
    result = gate(
        report(capability=0.5, leaks={"exfiltration": 0.5}),
        report(capability=1.0, leaks={"exfiltration": 0.0}),
        max_drop=2,
    )
    joined = " ".join(result.reasons)
    assert "capability" in joined
    assert "exfiltration" in joined
