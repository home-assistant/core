"""Test binary sensors of APCUPSd integration."""
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_STATUS, async_init_integration


async def test_binary_sensor(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test states of binary sensor."""
    await async_init_integration(hass, status=MOCK_STATUS)

    state = hass.states.get("binary_sensor.ups_online_status")
    assert state
    assert state.state == "on"
    entry = entity_registry.async_get("binary_sensor.ups_online_status")
    assert entry
    assert entry.unique_id == "XXXXXXXXXXXX_statflag"


async def test_no_binary_sensor(hass: HomeAssistant) -> None:
    """Test binary sensor when STATFLAG is not available."""
    status = MOCK_STATUS.copy()
    status.pop("STATFLAG")
    await async_init_integration(hass, status=status)

    state = hass.states.get("binary_sensor.ups_online_status")
    assert state is None
