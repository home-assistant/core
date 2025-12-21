"""Hue BLE light tests."""

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


async def test_light(
    hass: HomeAssistant,
    mock_scanner_count: AsyncMock,
    mock_light: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test light entity setup."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
