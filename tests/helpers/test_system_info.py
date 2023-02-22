"""Tests for the system info helper."""
import json
from unittest.mock import patch

from homeassistant.const import __version__ as current_version
from homeassistant.core import HomeAssistant
from homeassistant.helpers.system_info import async_get_system_info


async def test_get_system_info(hass: HomeAssistant) -> None:
    """Test the get system info."""
    info = await async_get_system_info(hass)
    assert isinstance(info, dict)
    assert info["version"] == current_version
    assert info["user"] is not None
    assert json.dumps(info) is not None


async def test_container_installationtype(hass: HomeAssistant) -> None:
    """Test container installation type."""
    with patch("platform.system", return_value="Linux"), patch(
        "os.path.isfile", return_value=True
    ), patch("homeassistant.helpers.system_info.getuser", return_value="root"):
        info = await async_get_system_info(hass)
        assert info["installation_type"] == "Home Assistant Container"

    with patch("platform.system", return_value="Linux"), patch(
        "os.path.isfile", side_effect=lambda file: file == "/.dockerenv"
    ), patch("homeassistant.helpers.system_info.getuser", return_value="user"):
        info = await async_get_system_info(hass)
        assert info["installation_type"] == "Unsupported Third Party Container"


async def test_getuser_keyerror(hass: HomeAssistant) -> None:
    """Test getuser keyerror."""
    with patch("homeassistant.helpers.system_info.getuser", side_effect=KeyError):
        info = await async_get_system_info(hass)
        assert info["user"] is None
