"""Tests for the Sony TV RS-232 integration init."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from sony_tv_rs232 import ConnectionLostError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import MockSonyTV


@pytest.mark.parametrize(
    "exception",
    [OSError("No such device"), ConnectionLostError("could not open connection")],
)
async def test_setup_connection_error(
    hass: HomeAssistant,
    mock_sony_tv: MockSonyTV,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test a connection failure results in a retry.

    The library raises the kit's ConnectionLostError for a port or proxy
    that cannot be opened (the transport's own error is the cause).
    """
    mock_sony_tv.connect.side_effect = exception

    with patch(
        "homeassistant.components.sony_tv_rs232.SonyTV",
        return_value=mock_sony_tv,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    mock_sony_tv: MockSonyTV,
    init_components: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading a config entry disconnects from the TV."""
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_sony_tv.disconnect.assert_awaited_once()


async def test_link_drop_does_not_reload(
    hass: HomeAssistant,
    mock_sony_tv: MockSonyTV,
    init_components: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a dropped serial link is left to the library to reconnect.

    The library reconnects on its own; reloading the entry would run a second
    reconnect loop against the same port.
    """
    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        mock_sony_tv.mock_state(None)
        await hass.async_block_till_done()

    mock_reload.assert_not_called()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_sony_tv.disconnect.assert_not_awaited()
