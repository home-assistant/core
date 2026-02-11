"""Tests for the Bitvis Power Hub integration."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test successful integration setup."""
    assert init_integration.state is ConfigEntryState.LOADED
    assert init_integration.runtime_data is not None


async def test_setup_entry_oserror(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that OSError from SharedListener.start results in SETUP_RETRY."""
    mock_config_entry.add_to_hass(hass)
    mock_listener = MagicMock()
    mock_listener.start = AsyncMock(side_effect=OSError("port in use"))
    mock_listener.stop = AsyncMock()
    mock_listener.is_empty = True
    with patch(
        "homeassistant.components.bitvis.coordinator.SharedListener",
        return_value=mock_listener,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_runtime_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that RuntimeError from SharedListener.register results in SETUP_ERROR."""
    mock_config_entry.add_to_hass(hass)
    mock_listener = MagicMock()
    mock_listener.start = AsyncMock()
    mock_listener.stop = AsyncMock()
    mock_listener.is_empty = True
    mock_listener.register.side_effect = RuntimeError("duplicate IP registration")
    with patch(
        "homeassistant.components.bitvis.coordinator.SharedListener",
        return_value=mock_listener,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test that unloading stops the coordinator and unloads platforms."""
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    assert init_integration.state is ConfigEntryState.NOT_LOADED
