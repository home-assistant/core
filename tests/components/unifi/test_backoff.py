"""Test UniFi backoff policy."""

from unittest.mock import patch

from homeassistant.components.unifi.hub.connection import BackoffPolicy


def test_default_delay_sequence_grows_and_caps() -> None:
    """Verify default policy doubles the delay each attempt up to the cap."""
    policy = BackoffPolicy()

    assert policy.next_delay(0) == 15
    assert policy.next_delay(1) == 30
    assert policy.next_delay(2) == 60
    assert policy.next_delay(3) == 60
    assert policy.next_delay(10_000) == 60


def test_jitter_stays_within_bounds() -> None:
    """Verify the jittered delay spreads around the plain delay."""
    policy = BackoffPolicy()

    with patch("random.uniform", side_effect=lambda low, high: low):
        assert policy.jittered_delay(1) == 30 * 0.8
    with patch("random.uniform", side_effect=lambda low, high: high):
        assert policy.jittered_delay(1) == 30 * 1.2


def test_custom_policy_parameters() -> None:
    """Verify base, factor and maximum are all respected."""
    policy = BackoffPolicy(base=5, factor=3, maximum=50)

    assert policy.next_delay(0) == 5
    assert policy.next_delay(1) == 15
    assert policy.next_delay(2) == 45
    assert policy.next_delay(3) == 50
