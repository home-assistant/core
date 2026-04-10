"""Tests for the Fish Audio integration setup."""

from __future__ import annotations

from unittest.mock import AsyncMock

from fishaudio import FishAudioError, ServerError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup(
    hass: HomeAssistant,
    mock_fishaudio_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entry setup and unload."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Unload
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "exception",
    [
        FishAudioError("Connection error"),
        ServerError(500, "Connection error"),
    ],
)
async def test_setup_retry_on_error(
    hass: HomeAssistant,
    mock_fishaudio_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test entry setup with API errors that should trigger retry."""
    mock_fishaudio_client.account.get_credits.side_effect = exception
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
