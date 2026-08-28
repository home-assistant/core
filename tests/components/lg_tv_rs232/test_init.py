"""Tests for the LG TV RS-232 integration init."""

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import MockLGTV

from tests.common import MockConfigEntry


async def test_setup_connection_error(
    hass: HomeAssistant,
    mock_lgtv: MockLGTV,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a connection failure results in a retry."""
    mock_lgtv.connect.side_effect = TimeoutError

    with patch(
        "homeassistant.components.lg_tv_rs232.LGTV",
        return_value=mock_lgtv,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    mock_lgtv: MockLGTV,
    init_components: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading a config entry disconnects from the TV."""
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_lgtv.disconnect.assert_awaited_once()


async def test_remove_entry_while_loaded(
    hass: HomeAssistant,
    mock_lgtv: MockLGTV,
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

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_lgtv.disconnect.assert_awaited_once()
