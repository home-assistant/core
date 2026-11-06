"""Tests for TFA.me: test of helper.py."""

from homeassistant.components.tfa_me.helper import user_input_to_tfa_host


def test_user_input_to_tfa_host_station_id() -> None:
    """Test converting a station ID to an mDNS hostname."""
    assert user_input_to_tfa_host("ABC-DEF-123") == "tfa-me-abc-def-123.local"


def test_user_input_to_tfa_host_ip_address() -> None:
    """Test an IP address is returned unchanged."""
    assert user_input_to_tfa_host("192.168.1.42") == "192.168.1.42"
