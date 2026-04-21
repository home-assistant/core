"""Test ScorpionTrack integration setup."""

from __future__ import annotations

from unittest.mock import AsyncMock

from pyscorpiontrack import (
    ScorpionTrackConnectionError,
    ScorpionTrackInvalidTokenError,
    ScorpionTrackShareUnavailableError,
)
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """Test successful setup and unload of entry."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (ScorpionTrackInvalidTokenError("Invalid token"), ConfigEntryState.SETUP_ERROR),
        (
            ScorpionTrackShareUnavailableError("Share expired"),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            ScorpionTrackConnectionError("Connection failed"),
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
)
async def test_setup_entry_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scorpiontrack_client: AsyncMock,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup with token and connection errors."""
    mock_scorpiontrack_client.async_get_share.side_effect = exception

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is expected_state
