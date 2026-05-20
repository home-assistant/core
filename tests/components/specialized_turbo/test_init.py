"""Tests for Specialized Turbo integration setup."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful setup of a config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.specialized_turbo.coordinator.establish_connection",
        new_callable=AsyncMock,
        return_value=AsyncMock(),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful unloading of a config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.specialized_turbo.coordinator.establish_connection",
        new_callable=AsyncMock,
        return_value=AsyncMock(),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert result is True
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
