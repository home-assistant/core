"""Tests for the arcam_fmj integration setup."""

from unittest.mock import AsyncMock, Mock, patch

from arcam.fmj import ConnectionFailed
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize("side_effect", [ConnectionFailed(), TimeoutError()])
async def test_setup_retries_when_unreachable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
) -> None:
    """Setup should signal a retry instead of succeeding when the device is unreachable."""
    client = Mock()
    client.host = "127.0.0.1"
    client.port = 50000
    client.start = AsyncMock(side_effect=side_effect)
    client.stop = AsyncMock()

    with patch("homeassistant.components.arcam_fmj.Client", return_value=client):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
