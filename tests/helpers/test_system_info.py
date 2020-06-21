"""Tests for the system info helper."""
import json

from homeassistant.const import __version__ as current_version


async def test_get_system_info(hass):
    """Test the get system info."""
    info = await hass.helpers.system_info.async_get_system_info()
    assert isinstance(info, dict)
    assert info["version"] == current_version
    assert json.dumps(info) is not None
