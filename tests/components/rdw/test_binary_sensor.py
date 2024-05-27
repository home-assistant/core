"""Tests for the sensors provided by the RDW integration."""

from unittest.mock import AsyncMock, patch

from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_vehicle_binary_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_rdw: AsyncMock,
) -> None:
    """Test the RDW vehicle binary sensors."""
    with patch("homeassistant.components.rdw.PLATFORMS", [Platform.BINARY_SENSOR]):
        await init_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
