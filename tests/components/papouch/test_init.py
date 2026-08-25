"""Tests for the Papouch initialization and coordinator."""

from unittest.mock import MagicMock

import aiohttp
from aiopapouch.exceptions import DeviceAuthError, DeviceConnectionError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_setup_unload_and_reload(
    hass: HomeAssistant, mock_config_entry, mock_papouch_client
) -> None:
    """Test successful setup, reload and unload of the integration."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_auth_error(
    hass: HomeAssistant, mock_config_entry, mock_papouch_client
) -> None:
    """Test setup fails due to invalid password (401)."""
    _, mock_create, _ = mock_papouch_client
    mock_create.side_effect = aiohttp.ClientResponseError(
        request_info=MagicMock(), history=(), status=401, message="Unauthorized"
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_connection_error(
    hass: HomeAssistant, mock_config_entry, mock_papouch_client
) -> None:
    """Test setup retries due to connection error."""
    _, mock_create, _ = mock_papouch_client
    mock_create.side_effect = aiohttp.ClientError()

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_unknown_device(
    hass: HomeAssistant, mock_config_entry, mock_papouch_client
) -> None:
    """Test setup retries if device is unknown."""
    _, mock_create, _ = mock_papouch_client
    mock_create.return_value = None

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_auth_error(
    hass: HomeAssistant, mock_config_entry, mock_papouch_client
) -> None:
    """Test coordinator handles auth errors during update."""
    mock_client, _, _ = mock_papouch_client
    mock_client.fetch_data.side_effect = DeviceAuthError()

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_coordinator_connection_error(
    hass: HomeAssistant, mock_config_entry, mock_papouch_client
) -> None:
    """Test coordinator handles connection errors during update."""
    mock_client, _, _ = mock_papouch_client
    mock_client.fetch_data.side_effect = DeviceConnectionError()

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
