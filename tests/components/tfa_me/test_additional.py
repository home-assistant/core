"""Test the TFA.me integration: test of additional functions."""

# For test run: "pytest ./tests/components/tfa_me/ --cov=homeassistant.components.tfa_me --cov-report term-missing -vv"

from homeassistant.components.tfa_me.config_flow import is_valid_ip_or_tfa_me


def test_is_valid_ip_or_tfa_me() -> None:
    """Test is_valid_ip_or_tfa_me() for class TFAmeConfigFlow."""

    # Valid IP
    assert is_valid_ip_or_tfa_me({"ip_address": "192.168.1.1"})

    # Valid mDNS
    assert is_valid_ip_or_tfa_me({"ip_address": "012-345-678"})

    # Invalid Host/IP
    assert not is_valid_ip_or_tfa_me({"ip_address": 42})
