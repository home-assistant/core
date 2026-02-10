"""Tests for the Lyngdorf integration."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry_unsupported_model(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup fails when model is not supported."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.lyngdorf.lookup_receiver_model",
        return_value=None,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_connection_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_lyngdorf_model
) -> None:
    """Test setup retries when connection to receiver fails."""
    mock_config_entry.add_to_hass(hass)

    receiver = MagicMock()
    receiver.async_connect = AsyncMock(side_effect=ConnectionError("Connection failed"))
    receiver.async_disconnect = AsyncMock()

    with (
        patch(
            "homeassistant.components.lyngdorf.lookup_receiver_model",
            return_value=mock_lyngdorf_model,
        ),
        patch(
            "homeassistant.components.lyngdorf.async_create_receiver",
            return_value=receiver,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_timeout(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_lyngdorf_model
) -> None:
    """Test setup retries when connection times out."""
    mock_config_entry.add_to_hass(hass)

    receiver = MagicMock()
    receiver.async_connect = AsyncMock(side_effect=TimeoutError("Connection timeout"))
    receiver.async_disconnect = AsyncMock()

    with (
        patch(
            "homeassistant.components.lyngdorf.lookup_receiver_model",
            return_value=mock_lyngdorf_model,
        ),
        patch(
            "homeassistant.components.lyngdorf.async_create_receiver",
            return_value=receiver,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test unloading the config entry."""
    assert init_integration.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED
