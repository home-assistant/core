"""Test the Anthem A/V Receivers config flow."""
from unittest.mock import ANY, AsyncMock, Mock, patch

from homeassistant import config_entries
from homeassistant.components.anthemav.const import ANTHEMAV_UDATE_SIGNAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_connection_create: AsyncMock,
    mock_anthemav: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload AnthemAv component."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # assert avr is created
    mock_connection_create.assert_called_with(
        host="1.1.1.1", port=14999, update_callback=ANY
    )
    assert mock_config_entry.state == config_entries.ConfigEntryState.LOADED

    # unload
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    # assert unload and avr is closed
    assert mock_config_entry.state == config_entries.ConfigEntryState.NOT_LOADED
    mock_anthemav.close.assert_called_once()


async def test_config_entry_not_ready(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test AnthemAV configuration entry not ready."""

    with patch(
        "anthemav.Connection.create",
        side_effect=OSError,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state is config_entries.ConfigEntryState.SETUP_RETRY


async def test_anthemav_dispatcher_signal(
    hass: HomeAssistant,
    mock_connection_create: AsyncMock,
    mock_anthemav: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test send update signal to dispatcher."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # get the callback function that trigger the signal
    avr_update_callback = mock_connection_create.call_args[1]["update_callback"]

    mock_signal_received = Mock()

    async_dispatcher_connect(
        hass,
        f"{ANTHEMAV_UDATE_SIGNAL}_{mock_config_entry.entry_id}",
        mock_signal_received,
    )

    avr_update_callback("Fake Command")

    await hass.async_block_till_done()

    mock_signal_received.assert_called()
