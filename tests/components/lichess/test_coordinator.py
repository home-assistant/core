"""Test the Lichess coordinator."""

from unittest.mock import AsyncMock

from aiolichess.exceptions import AioLichessError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_coordinator_update_failed(
    hass: HomeAssistant,
    mock_lichess_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles update failure."""
    await setup_integration(hass, mock_config_entry)

    mock_lichess_client.get_username.side_effect = AioLichessError

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
