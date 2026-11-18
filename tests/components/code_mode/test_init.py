"""Tests for the Code Mode setup."""

from unittest.mock import patch

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_setup_retry_when_sandbox_fails(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup is retried when the worker pool cannot start."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.code_mode.AsyncMonty", autospec=True
    ) as mock_pool:
        mock_pool.return_value.__aenter__.side_effect = OSError("No binary")
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
