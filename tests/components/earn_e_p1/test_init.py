"""Tests for the EARN-E P1 Meter integration setup."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import MOCK_HOST, MOCK_SERIAL


async def test_setup_entry_success(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test successful setup of a config entry."""
    with patch(
        "homeassistant.components.earn_e_p1.coordinator.EarnEP1Coordinator.async_start",
        new_callable=AsyncMock,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None
    assert mock_config_entry.runtime_data.host == MOCK_HOST
    assert mock_config_entry.runtime_data.serial == MOCK_SERIAL


async def test_setup_entry_oserror_raises_not_ready(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test that OSError during setup raises ConfigEntryNotReady."""
    with patch(
        "homeassistant.components.earn_e_p1.coordinator.EarnEP1Coordinator.async_start",
        new_callable=AsyncMock,
        side_effect=OSError("Address in use"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(hass: HomeAssistant, mock_config_entry) -> None:
    """Test unloading a config entry."""
    with patch(
        "homeassistant.components.earn_e_p1.coordinator.EarnEP1Coordinator.async_start",
        new_callable=AsyncMock,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    with patch(
        "homeassistant.components.earn_e_p1.coordinator.EarnEP1Coordinator.async_stop",
        new_callable=AsyncMock,
    ):
        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
