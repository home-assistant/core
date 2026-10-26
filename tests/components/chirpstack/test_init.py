"""Set up, recover, and unload a ChirpStack connection."""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from lorawan_connection import ConnectionUnavailable
from lorawan_connection.backend.chirpstack import AuthenticationError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
def mock_registration() -> Generator[AsyncMock]:
    """Observe registration with the shared integration."""
    with patch(
        "homeassistant.components.chirpstack.lorawan.async_register_connection",
        return_value=Mock(),
    ) as register:
        yield register


async def test_setup_and_unload(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    mock_connection: Mock,
    mock_registration: AsyncMock,
) -> None:
    """Register the connected backend and release it on unload."""
    assert await hass.config_entries.async_setup(connection_entry.entry_id)
    mock_connection.async_connect.assert_awaited_once_with()
    mock_registration.assert_awaited_once_with(
        hass,
        connection_entry,
        connection=mock_connection,
        configuration_url="http://server:8080/",
    )
    assert connection_entry.runtime_data.connection is mock_connection
    assert await hass.config_entries.async_unload(connection_entry.entry_id)
    mock_connection.on_disconnect.return_value.assert_called_once_with()
    mock_registration.return_value.assert_called_once_with()
    mock_connection.close.assert_awaited_once_with()
    assert connection_entry.state is ConfigEntryState.NOT_LOADED

    await hass.async_stop()
    mock_connection.close.assert_awaited_once_with()
    mock_connection.on_disconnect.return_value.assert_called_once_with()
    mock_registration.return_value.assert_called_once_with()


@pytest.mark.parametrize(
    ("error", "state"),
    [
        (ConnectionUnavailable("offline"), ConfigEntryState.SETUP_RETRY),
        (AuthenticationError("rejected"), ConfigEntryState.SETUP_ERROR),
        (RuntimeError("unexpected"), ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_failure(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    mock_connection: Mock,
    mock_registration: AsyncMock,
    error: Exception,
    state: ConfigEntryState,
) -> None:
    """Failed connections are closed and never registered."""
    mock_connection.async_connect.side_effect = error
    assert not await hass.config_entries.async_setup(connection_entry.entry_id)
    assert connection_entry.state is state
    mock_connection.close.assert_awaited_once_with()
    mock_registration.assert_not_awaited()
    await hass.async_block_till_done()


async def test_registration_failure(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    mock_connection: Mock,
    mock_registration: AsyncMock,
) -> None:
    """Close the connection if registration fails."""
    mock_registration.side_effect = ConnectionUnavailable("replay failed")
    assert not await hass.config_entries.async_setup(connection_entry.entry_id)
    assert connection_entry.state is ConfigEntryState.SETUP_RETRY
    mock_connection.close.assert_awaited_once_with()


async def test_setup_cancelled(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    mock_connection: Mock,
) -> None:
    """Cancellation closes the pending connection."""
    mock_connection.async_connect.side_effect = asyncio.CancelledError
    assert not await hass.config_entries.async_setup(connection_entry.entry_id)
    assert connection_entry.state is ConfigEntryState.SETUP_ERROR
    mock_connection.close.assert_awaited_once_with()


async def test_disconnect(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    mock_connection: Mock,
) -> None:
    """A lost connection schedules a config entry reload."""
    assert await hass.config_entries.async_setup(connection_entry.entry_id)
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        mock_connection.on_disconnect.call_args.args[0]()
    reload.assert_called_once_with(connection_entry.entry_id)
    await hass.config_entries.async_unload(connection_entry.entry_id)


async def test_shutdown(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    mock_connection: Mock,
    mock_registration: AsyncMock,
) -> None:
    """Home Assistant shutdown withdraws and closes the connection."""
    assert await hass.config_entries.async_setup(connection_entry.entry_id)
    mock_connection.close.side_effect = mock_connection.on_disconnect.call_args.args[0]
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        await hass.async_stop()
    reload.assert_not_called()
    mock_connection.on_disconnect.return_value.assert_called_once_with()
    mock_registration.return_value.assert_called_once_with()
    mock_connection.close.assert_awaited_once_with()
