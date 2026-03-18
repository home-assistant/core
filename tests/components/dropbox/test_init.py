"""Test the Dropbox integration setup."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from python_dropbox_api import DropboxAuthException, DropboxUnknownException

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_dropbox_client")
async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup of a config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_entry_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_dropbox_client: AsyncMock,
) -> None:
    """Test setup failure when authentication fails."""
    mock_dropbox_client.get_account_info.side_effect = DropboxAuthException(
        "Invalid token"
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    "side_effect",
    [DropboxUnknownException("Unknown error"), TimeoutError("Connection timed out")],
    ids=["unknown_exception", "timeout_error"],
)
async def test_setup_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_dropbox_client: AsyncMock,
    side_effect: Exception,
) -> None:
    """Test setup retry when the service is temporarily unavailable."""
    mock_dropbox_client.get_account_info.side_effect = side_effect
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_implementation_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retry when OAuth implementation is unavailable."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.dropbox.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_dropbox_client")
async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
