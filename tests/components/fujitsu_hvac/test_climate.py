"""Test for the climate entities of Fujitsu HVAC."""

from unittest.mock import AsyncMock

from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_coordinator_initial_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_devices: list[AsyncMock],
    mock_ayla_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that coordinator returns the data we expect after the first refresh."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
