"""Test for Arve sensors."""

from datetime import timedelta
from unittest.mock import MagicMock

from asyncarve import ArveConnectionError
from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import async_init_integration

from tests.common import MockConfigEntry, async_fire_time_changed

SENSORS = (
    "air_quality_index",
    "carbon_dioxide",
    "humidity",
    "pm10",
    "pm2_5",
    "temperature",
    "total_volatile_organic_compounds",
)


async def test_sensors(
    hass: HomeAssistant,
    mock_arve: MagicMock,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Arve sensors."""
    await async_init_integration(hass, mock_config_entry)

    for sensor in SENSORS:
        state = hass.states.get(f"sensor.test_sensor_{sensor}")
        assert state
        assert state == snapshot(name=f"test_sensor_{sensor}")

        entry = entity_registry.async_get(state.entity_id)
        assert entry
        assert entry.device_id
        assert entry == snapshot(name=f"entry_{sensor}")


async def test_sensor_unavailable_on_update_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_arve: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensor becomes unavailable when the update fails."""
    entity_id = "sensor.test_sensor_temperature"
    await async_init_integration(hass, mock_config_entry)

    assert (state := hass.states.get(entity_id))
    assert state.state == "26.02"

    mock_arve.get_devices.side_effect = ArveConnectionError

    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE

    mock_arve.get_devices.side_effect = None

    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(entity_id))
    assert state.state == "26.02"
