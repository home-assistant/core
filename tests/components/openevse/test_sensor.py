"""Tests for the OpenEVSE sensor platform."""

from unittest.mock import MagicMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


async def test_sensor_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setting up the sensor platform."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    entity_registry.async_update_entity("sensor.ir_temperature", disabled_by=None)
    entity_registry.async_update_entity("sensor.rtc_temperature", disabled_by=None)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
