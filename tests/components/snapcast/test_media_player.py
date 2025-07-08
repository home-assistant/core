"""Test the snapcast media player implementation."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_server: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test basic state information."""

    # Setup and verify the integration is loaded
    with patch("secrets.token_hex", return_value="mock_token"):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
