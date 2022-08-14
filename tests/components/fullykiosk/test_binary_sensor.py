"""Test the Fully Kiosk Browser binary sensors."""
from datetime import timedelta

from asynctest import patch

from homeassistant.components.fullykiosk.const import UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt

from tests.common import async_fire_time_changed
from tests.components.fullykiosk import init_integration


async def test_binary_sensors(hass):
    """Test standard Fully Kiosk binary sensors."""
    await init_integration(hass)
    registry = er.async_get(hass)

    state = hass.states.get("binary_sensor.amazon_fire_plugged_in")
    assert state
    assert state.state == "on"
    entry = registry.async_get("binary_sensor.amazon_fire_plugged_in")
    assert entry
    assert entry.unique_id == "abcdef-123456-plugged"

    state = hass.states.get("binary_sensor.amazon_fire_kiosk_mode")
    assert state
    assert state.state == "on"

    # Test failed update
    with patch(
        "homeassistant.components.fullykiosk.FullyKioskDataUpdateCoordinator._async_update_data",
        side_effect=ConnectionError,
    ):
        async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=UPDATE_INTERVAL))
        await hass.async_block_till_done()

        state = hass.states.get("binary_sensor.amazon_fire_plugged_in")
        assert state
        assert state.state == STATE_UNAVAILABLE
