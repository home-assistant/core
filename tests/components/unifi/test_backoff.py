"""Test UniFi backoff policy."""

from homeassistant.components.unifi.hub.backoff import BackoffPolicy


def test_default_delay_sequence_grows_and_caps() -> None:
    """Verify default policy doubles the delay each attempt up to the cap."""
    policy = BackoffPolicy()

    assert policy.next_delay(0) == 15
    assert policy.next_delay(1) == 30
    assert policy.next_delay(2) == 60
    assert policy.next_delay(3) == 120
    assert policy.next_delay(4) == 240
    assert policy.next_delay(5) == 300  # capped
    assert policy.next_delay(10) == 300  # stays capped


def test_custom_policy_parameters() -> None:
    """Verify base, factor and maximum are all respected."""
    policy = BackoffPolicy(base=5, factor=3, maximum=50)

    assert policy.next_delay(0) == 5
    assert policy.next_delay(1) == 15
    assert policy.next_delay(2) == 45
    assert policy.next_delay(3) == 50  # capped
