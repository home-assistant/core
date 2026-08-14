"""Tests for the lights provided by the Lunatone integration."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from lunatone_rest_api_client.models import SensorData
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_setup(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_sensors: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Lunatone sensor setup."""
    await setup_integration(hass, mock_config_entry)

    entities = hass.states.async_all(Platform.SENSOR)
    for entity_state in entities:
        entity_entry = entity_registry.async_get(entity_state.entity_id)
        assert entity_entry
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert entity_state == snapshot(name=f"{entity_entry.entity_id}-state")


async def test_sensor_value_update(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_sensors: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Lunatone sensor value update."""
    sensor_values = (22, 55, 20)

    await setup_integration(hass, mock_config_entry)

    async def fake_update():
        for i, sensor_value in enumerate(sensor_values):
            sensor: SensorData = mock_lunatone_sensors.data.sensors[i]
            sensor.value = sensor_value

    mock_lunatone_sensors.async_update.side_effect = fake_update

    entities = hass.states.async_all(Platform.SENSOR)
    assert entities[0].state == "unknown"
    assert entities[1].state == "unknown"
    assert entities[2].state == "unknown"

    freezer.tick(timedelta(seconds=40))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entities = hass.states.async_all(Platform.SENSOR)
    assert entities[0].state == "22"
    assert entities[1].state == "55"
    assert entities[2].state == "20"
