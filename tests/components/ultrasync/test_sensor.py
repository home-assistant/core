"""Test the UltraSync sensors."""
from datetime import timedelta

from homeassistant.util import dt as dt_util

from . import init_integration

from tests.common import async_fire_time_changed


async def test_sensors(hass, ultrasync_api) -> None:
    """Test the creation and the initial values of the sensors."""
    entry = await init_integration(hass)
    registry = await hass.helpers.entity_registry.async_get_registry()

    sensors = {
        "area01_state": ("area1state", "Ready"),
    }

    for (sensor_id, data) in sensors.items():
        entity_entry = registry.async_get(f"sensor.ultrasync_{data[0]}")
        assert entity_entry
        assert entity_entry.unique_id == f"{entry.entry_id}_{sensor_id}"

        state = hass.states.get(f"sensor.ultrasync_{data[0]}")
        assert state
        assert state.state == data[1]

    # These sensors have not been registered at this point yet:
    sensors = ("zone1state", "zone2state")
    for ident in sensors:
        entity_entry = registry.async_get(f"sensor.ultrasync_{ident}")
        assert entity_entry is None
        state = hass.states.get(f"sensor.ultrasync_{ident}")
        assert state is None

    # trigger an update
    async_fire_time_changed(hass, dt_util.now() + timedelta(days=2))
    await hass.async_block_till_done()

    # Our dynamic sensors would have been created after our first connection
    sensors = {
        "area01_state": ("area1state", "Not Ready"),
        "zone01_state": ("zone1state", "Not Ready"),
        "zone02_state": ("zone2state", "Ready"),
    }

    for (sensor_id, data) in sensors.items():
        entity_entry = registry.async_get(f"sensor.ultrasync_{data[0]}")
        assert entity_entry
        assert entity_entry.unique_id == f"{entry.entry_id}_{sensor_id}"

        state = hass.states.get(f"sensor.ultrasync_{data[0]}")
        assert state
        assert state.state == data[1]

    # trigger an update
    async_fire_time_changed(hass, dt_util.now() + timedelta(days=4))
    await hass.async_block_till_done()

    # Zone02 is gone now
    sensors = {
        "area01_state": ("area1state", "Ready"),
        "zone01_state": ("zone1state", "Ready"),
    }

    for (sensor_id, data) in sensors.items():
        entity_entry = registry.async_get(f"sensor.ultrasync_{data[0]}")
        assert entity_entry
        assert entity_entry.unique_id == f"{entry.entry_id}_{sensor_id}"

        state = hass.states.get(f"sensor.ultrasync_{data[0]}")
        assert state
        assert state.state == data[1]

    # Verify Zone02 is gone (safely unregistered)
    entity_entry = registry.async_get("sensor.ultrasync_zone02_state")
    assert entity_entry is None
    state = hass.states.get("sensor.ultrasync_zone02_state")
    assert state is None
