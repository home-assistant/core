"""The test for the version binary sensor platform."""
from __future__ import annotations

from homeassistant.components.version.const import DEFAULT_CONFIGURATION
from homeassistant.core import HomeAssistant

from .common import setup_version_integration


async def test_version_binary_sensor_local_source(hass: HomeAssistant):
    """Test the Version binary sensor with local source."""
    await setup_version_integration(hass)

    state = hass.states.get("binary_sensor.local_installation_update_available")
    assert not state


async def test_version_binary_sensor(hass: HomeAssistant):
    """Test the Version binary sensor."""
    await setup_version_integration(hass, {**DEFAULT_CONFIGURATION, "source": "pypi"})

    state = hass.states.get("binary_sensor.local_installation_update_available")
    assert state
