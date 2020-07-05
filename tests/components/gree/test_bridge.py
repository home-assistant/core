"""Tests for the Gree Integration."""
from homeassistant.components.gree.bridge import DeviceHelper

from tests.async_mock import patch


@patch("homeassistant.components.gree.bridge.socket")
async def test_get_ip_for_valid_host(mock):
    """Test gree integration is setup."""
    mock.gethostbyname.return_value = "1.1.1.1"

    host = DeviceHelper.get_ip("fake-host")
    assert host == "1.1.1.1"


@patch("homeassistant.components.gree.bridge.socket")
async def test_get_ip_for_invalid_host(mock):
    """Test gree integration is setup."""
    mock.gethostbyname.return_value = "1.1.1.1"

    host = DeviceHelper.get_ip(None)
    assert host is None
