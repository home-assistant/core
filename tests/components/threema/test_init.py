"""Test the Threema Gateway integration setup."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from threema.gateway import GatewayError
from threema.gateway.exception import GatewayServerError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_send: MagicMock,
) -> None:
    """Test successful setup of a config entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries on connection error (ConfigEntryNotReady)."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.threema.client.Connection", autospec=True
    ) as connection_class:
        connection = MagicMock()
        connection.__aenter__ = AsyncMock(return_value=connection)
        connection.__aexit__ = AsyncMock(return_value=None)
        connection.get_credits = AsyncMock(
            side_effect=GatewayError("Connection refused")
        )
        connection_class.return_value = connection

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup fails on auth error (ConfigEntryAuthFailed)."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.threema.client.Connection", autospec=True
    ) as connection_class:
        connection = MagicMock()
        connection.__aenter__ = AsyncMock(return_value=connection)
        connection.__aexit__ = AsyncMock(return_value=None)
        connection.get_credits = AsyncMock(side_effect=GatewayServerError(status=401))
        connection_class.return_value = connection

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_send: MagicMock,
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_server_error_non_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries on non-401 server error."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.threema.client.Connection", autospec=True
    ) as connection_class:
        connection = MagicMock()
        connection.__aenter__ = AsyncMock(return_value=connection)
        connection.__aexit__ = AsyncMock(return_value=None)
        connection.get_credits = AsyncMock(side_effect=GatewayServerError(status=500))
        connection_class.return_value = connection

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_update_listener_reloads(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_send: MagicMock,
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
