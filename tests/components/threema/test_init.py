"""Test the Threema Gateway integration setup."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.threema.client import (
    ThreemaAuthError,
    ThreemaConnectionError,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_credentials: AsyncMock,
    mock_send_message: AsyncMock,
) -> None:
    """Test successful setup of a config entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (ThreemaConnectionError("Connection refused"), ConfigEntryState.SETUP_RETRY),
        (ThreemaAuthError("Invalid credentials"), ConfigEntryState.SETUP_ERROR),
        (ThreemaConnectionError("Server error"), ConfigEntryState.SETUP_RETRY),
    ],
    ids=["connection_error", "auth_error", "server_error_non_auth"],
)
async def test_setup_entry_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_credentials: AsyncMock,
    side_effect: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup handles various errors correctly."""
    mock_config_entry.add_to_hass(hass)
    mock_credentials.side_effect = side_effect

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_credentials: AsyncMock,
    mock_send_message: AsyncMock,
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_update_listener_reloads(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_credentials: AsyncMock,
    mock_send_message: AsyncMock,
) -> None:
    """Test that update listener reloads the entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload"
    ) as mock_reload:
        mock_reload.return_value = None
        hass.config_entries.async_update_entry(mock_config_entry, title="Updated")
        await hass.async_block_till_done()

        mock_reload.assert_called_once_with(mock_config_entry.entry_id)
