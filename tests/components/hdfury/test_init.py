"""Tests for the HDFury integration init."""

from unittest.mock import AsyncMock

from hdfury import HDFuryError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup_entry_board_fetch_failure(
    hass: HomeAssistant,
    mock_hdfury_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries when board data fetch fails."""
    mock_hdfury_client.get_board.side_effect = HDFuryError()

    await setup_integration(hass, mock_config_entry, [])

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
