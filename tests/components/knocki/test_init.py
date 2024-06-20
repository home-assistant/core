"""Test the Home Knocki init module."""

from __future__ import annotations

from unittest.mock import AsyncMock

from knocki import KnockiConnectionError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_knocki_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_initialization_failure(
    hass: HomeAssistant,
    mock_knocki_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test initialization failure."""
    mock_knocki_client.get_triggers.side_effect = KnockiConnectionError

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
