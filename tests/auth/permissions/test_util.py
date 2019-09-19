"""Test the permission utils."""

from homeassistant.auth.permissions import util


def test_test_all():
    """Test if we can test the all group."""
    for val in (None, {}, {"all": None}, {"all": {}}):
        assert util.test_all(val, "read") is False

    for val in (True, {"all": True}, {"all": {"read": True}}):
        assert util.test_all(val, "read") is True
