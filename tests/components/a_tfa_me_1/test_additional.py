"""Test the TFA.me: test of additional functions."""

from homeassistant.components.a_tfa_me_1.config_flow import is_valid_ip_or_tfa_me


def test_is_valid_ip_or_tfa_me() -> None:
    """Test is_valid_ip_or_tfa_me() for class TFAmeConfigFlow."""

    # Valid IP
    assert is_valid_ip_or_tfa_me({"ip_address": "192.168.1.1"})

    # Valid mDNS
    assert is_valid_ip_or_tfa_me({"ip_address": "012-345-678"})

    # Invalid Host/IP
    assert not is_valid_ip_or_tfa_me({"ip_address": 42})
