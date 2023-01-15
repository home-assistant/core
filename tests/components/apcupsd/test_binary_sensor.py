"""Test binary sensors of APCUPSd integration."""


from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_STATUS, init_integration


async def test_binary_sensor(hass: HomeAssistant):
    """Test states of binary sensor."""
    await init_integration(hass, status=MOCK_STATUS)
    registry = er.async_get(hass)

    state = hass.states.get("binary_sensor.ups_online_status")
    assert state
    assert state.state == "on"
    entry = registry.async_get("binary_sensor.ups_online_status")
    assert entry
    assert entry.unique_id == "XXXXXXXXXXXX_statflag"
