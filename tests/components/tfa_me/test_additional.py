"""Test the TFA.me integration: test of additional functions."""

# For test run: "pytest ./tests/components/tfa_me/ --cov=homeassistant.components.tfa_me --cov-report term-missing -vv"

from tfa_me_ha_local.validators import TFAmeValidator


def test_is_valid_ip_or_tfa_me() -> None:
    """Test is_valid_ip_or_tfa_me() for class TFAmeConfigFlow."""

    validator = TFAmeValidator()
    # Valid IP
    assert validator.is_valid_ip_or_tfa_me("192.168.1.1")

    # Valid mDNS
    assert validator.is_valid_ip_or_tfa_me("012-345-678")

    # Invalid Host/IP
    assert not validator.is_valid_ip_or_tfa_me(42)
