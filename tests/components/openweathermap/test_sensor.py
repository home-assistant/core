"""Tests for OpenWeatherMap sensors."""

from syrupy import SnapshotAssertion

from homeassistant.components.openweathermap.const import OWM_MODE_FREE_FORECAST
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_platform

from tests.common import MockConfigEntry, snapshot_platform


async def test_sensor_states(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mode: str,
) -> None:
    """Test sensor states are correctly collected from library with different modes and mocked function responses."""

    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])

    if mode == OWM_MODE_FREE_FORECAST:
        # Free forecast mode does not support sensors
        assert len(entity_registry.entities) == 0
    else:
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )
