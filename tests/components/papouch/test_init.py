"""Tests for the Papouch initialization, coordinator, and diagnostics."""

from unittest.mock import MagicMock

import aiohttp
from aiopapouch.exceptions import DeviceAuthError, DeviceConnectionError

from homeassistant.components.papouch.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_setup_unload_and_reload(
    hass: HomeAssistant, mock_config_entry, mock_papouch_client
) -> None:
    """Test successful setup, reload and unload of the integration."""
    mock_config_entry.add_to_hass(hass)

    # Test nastartování
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Test Options Flow Reload (update_listener)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={"refresh_rate": 30}
    )
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Test odpojení
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_missing_unique_id(
    hass: HomeAssistant, mock_papouch_client
) -> None:
    """Test adding unique_id to a legacy entry during setup."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={"ip_address": "192.168.1.50"}, unique_id=None
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.unique_id == "00:11:22:33:44:55"


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


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry,
    mock_papouch_client,
) -> None:
    """Test diagnostics extraction."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert diagnostics["entry_data"]["ip_address"] == "192.168.1.50"
    assert diagnostics["entry_data"]["password"] == "**REDACTED**"
    assert "temperature" in diagnostics["data"]
