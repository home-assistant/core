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
        "area02_state": ("area2state", "unknown"),
        "area03_state": ("area3state", "unknown"),
        "area04_state": ("area4state", "unknown"),
    }

    for (sensor_id, data) in sensors.items():
        entity_entry = registry.async_get(f"sensor.ultrasync_{data[0]}")
        assert entity_entry
        assert entity_entry.unique_id == f"{entry.entry_id}_{sensor_id}"

        state = hass.states.get(f"sensor.ultrasync_{data[0]}")
        assert state
        assert state.state == data[1]

    # trigger an update
    async_fire_time_changed(hass, dt_util.now() + timedelta(days=2))
    await hass.async_block_till_done()

    sensors = {
        "area01_state": ("area1state", "Not Ready"),
        "area02_state": ("area2state", "unknown"),
        "area03_state": ("area3state", "unknown"),
        "area04_state": ("area4state", "unknown"),
    }

    for (sensor_id, data) in sensors.items():
        entity_entry = registry.async_get(f"sensor.ultrasync_{data[0]}")
        assert entity_entry
        assert entity_entry.unique_id == f"{entry.entry_id}_{sensor_id}"

        state = hass.states.get(f"sensor.ultrasync_{data[0]}")
        assert state
        assert state.state == data[1]
