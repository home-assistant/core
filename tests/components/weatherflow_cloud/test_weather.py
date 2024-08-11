"""Tests for the WeatherFlow Cloud weather platform."""

from unittest.mock import AsyncMock, patch

from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_weather(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_api: AsyncMock,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.weatherflow_cloud.PLATFORMS", [Platform.WEATHER]
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
