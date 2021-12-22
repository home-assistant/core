"""Tests for the system info helper."""
import json
from unittest.mock import patch

from homeassistant.const import __version__ as current_version


async def test_get_system_info(hass):
    """Test the get system info."""
    info = await hass.helpers.system_info.async_get_system_info()
    assert isinstance(info, dict)
    assert info["version"] == current_version
    assert info["user"] is not None
    assert json.dumps(info) is not None


async def test_container_installationtype(hass):
    """Test container installation type."""
    with patch("platform.system", return_value="Linux"), patch(
        "os.path.isfile", return_value=True
    ):
        info = await hass.helpers.system_info.async_get_system_info()
        assert info["installation_type"] == "Home Assistant Container"

    with patch("platform.system", return_value="Linux"), patch(
        "os.path.isfile", return_value=True
    ), patch("homeassistant.helpers.system_info.getuser", return_value="user"):
        info = await hass.helpers.system_info.async_get_system_info()
        assert info["installation_type"] == "Unknown"


async def test_getuser_keyerror(hass):
    """Test getuser keyerror."""
    with patch("homeassistant.helpers.system_info.getuser", side_effect=KeyError):
        info = await hass.helpers.system_info.async_get_system_info()
        assert info["user"] is None
