"""Tests for the Sense integration setup."""

from unittest.mock import MagicMock

import pytest
from sense_energy import (
    SenseAPIException,
    SenseAPITimeoutException,
    SenseWebsocketException,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "exception",
    [
        SenseAPITimeoutException,
        SenseAPIException,
        SenseWebsocketException,
    ],
)
async def test_setup_entry_exceptions(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    exception: type[Exception],
) -> None:
    """Test we handle exceptions during async_setup_entry and can recover."""
    mock_sense.update_realtime.side_effect = exception
    config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY

    # Verify recovery: clear the error and reload the entry
    mock_sense.update_realtime.side_effect = None
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
