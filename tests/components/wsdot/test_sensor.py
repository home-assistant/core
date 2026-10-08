"""The tests for the WSDOT platform."""

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


async def test_travel_sensor_details(
    hass: HomeAssistant,
    mock_travel_time: AsyncMock,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the wsdot Travel Time sensor details."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
