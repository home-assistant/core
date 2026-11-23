"""Tests for the Frontier Silicon integration setup."""

from unittest.mock import AsyncMock

from afsapi import FSConnectionError
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_setup_retry_closes_the_client(
    hass: HomeAssistant, mock_afsapi: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """An unreachable device must not leave the client's HTTP session open."""
    mock_afsapi.get_power.side_effect = FSConnectionError
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_afsapi.close.assert_awaited_once()


async def test_unload_closes_the_client(
    hass: HomeAssistant, mock_afsapi: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Unloading the entry closes the client's HTTP session."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    mock_afsapi.close.assert_not_awaited()

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    mock_afsapi.close.assert_awaited_once()
