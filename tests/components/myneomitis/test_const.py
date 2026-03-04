"""Tests for the MyNeomitis const module."""

from homeassistant.components.myneomitis.const import CONF_USER_ID, DOMAIN


def test_domain_and_conf_user_id() -> None:
    """Basic constants are set to expected values."""
    assert DOMAIN == "myneomitis"
    assert CONF_USER_ID == "user_id"
