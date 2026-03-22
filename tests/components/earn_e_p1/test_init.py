"""Tests for the EARN-E P1 Meter integration setup."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.earn_e_p1.const import DOMAIN

from .conftest import MOCK_HOST, MOCK_SERIAL


async def test_setup_entry_success(
    hass: HomeAssistant, mock_config_entry, mock_listener
) -> None:
    """Test successful setup of a config entry."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None
    assert mock_config_entry.runtime_data.host == MOCK_HOST
    assert mock_config_entry.runtime_data.serial == MOCK_SERIAL
    mock_listener.start.assert_awaited_once()
    mock_listener.register.assert_called_once()


async def test_setup_entry_oserror_raises_not_ready(
    hass: HomeAssistant, mock_config_entry, mock_listener
) -> None:
    """Test that OSError during setup raises ConfigEntryNotReady."""
    mock_listener.start = AsyncMock(side_effect=OSError("Address in use"))

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry, mock_listener
) -> None:
    """Test unloading a config entry stops the shared listener."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert DOMAIN in hass.data

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_listener.unregister.assert_called()
    mock_listener.stop.assert_awaited()
    assert DOMAIN not in hass.data
