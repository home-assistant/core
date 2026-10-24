"""Tests for TSUN integration setup."""

from unittest.mock import AsyncMock

from tsun_local_api import TsunConnectionError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tsun_client: AsyncMock,
) -> None:
    """Test successful setup and unloading."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retries_when_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tsun_client: AsyncMock,
) -> None:
    """Test setup is retried when the device cannot be reached."""
    mock_tsun_client.async_read.side_effect = TsunConnectionError("offline")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
