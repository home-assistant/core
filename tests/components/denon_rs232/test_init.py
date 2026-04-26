"""Tests for the Denon RS232 integration init."""

from unittest.mock import AsyncMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import MockReceiver

from tests.common import MockConfigEntry


async def test_remove_entry_while_loaded(
    hass: HomeAssistant,
    mock_receiver: MockReceiver,
    init_components: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test removing a config entry does not schedule a reload.

    When removing a loaded entry, disconnect() fires the subscriber callback
    with state=None. The callback must not schedule a reload because the entry
    is already being removed (state is no longer LOADED).
    """

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Entry should be fully removed without errors from the disconnect callback.
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_receiver.disconnect.assert_awaited_once()
