"""Tests for the BSB-Lan sensor platform."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_with_selected_platforms

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_CURRENT_TEMP = "sensor.bsb_lan_current_temperature"
ENTITY_OUTSIDE_TEMP = "sensor.bsb_lan_outside_temperature"


async def test_sensor_entity_properties(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the sensor entity properties."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensors_not_created_when_data_unavailable(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensors are not created when sensor data is not available."""
    # Set all sensor data to None to simulate no sensors available
    mock_bsblan.sensor.return_value.current_temperature = None
    mock_bsblan.sensor.return_value.outside_temperature = None

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    # Should not create any sensor entities
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    sensor_entities = [entry for entry in entity_entries if entry.domain == "sensor"]
    assert len(sensor_entities) == 0


async def test_partial_sensors_created_when_some_data_available(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test only available sensors are created when some sensor data is available."""
    # Only current temperature available, outside temperature not
    mock_bsblan.sensor.return_value.outside_temperature = None

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    # Should create only the current temperature sensor
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    sensor_entities = [entry for entry in entity_entries if entry.domain == "sensor"]
    assert len(sensor_entities) == 1
    assert sensor_entities[0].entity_id == ENTITY_CURRENT_TEMP
