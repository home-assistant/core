"""Test Mikrotik setup process."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from librouteros.exceptions import ConnectionClosed, LibRouterosError
import pytest

from homeassistant.components.mikrotik.const import (
    IDENTITY,
    MIKROTIK_SERVICES,
    ROUTERBOARD,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from . import setup_integration
from .conftest import MockConfigEntryFactory
from .const import MOCK_DATA

from tests.common import async_fire_time_changed

_BASE_COMMAND_RESPONSES: dict[str, list[dict[str, Any]]] = {
    MIKROTIK_SERVICES[IDENTITY]: [{"name": "Mikrotik"}]
}


def _command_side_effect(
    error_cmd: str, error: Exception
) -> Callable[..., list[dict[str, Any]]]:
    """Return minimal hub responses, except for one command that raises."""

    def side_effect(cmd: str, **params: Any) -> list[dict[str, Any]]:
        if cmd == error_cmd:
            raise error
        return _BASE_COMMAND_RESPONSES.get(cmd, [])

    return side_effect


async def test_successful_config_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntryFactory
) -> None:
    """Test config entry successful setup."""
    entry = mock_config_entry()
    await setup_integration(hass, entry, command_responses={})
    assert entry.state is ConfigEntryState.LOADED


async def test_hub_connect_uses_ssl_when_verify_ssl_enabled(
    hass: HomeAssistant, mock_config_entry: MockConfigEntryFactory
) -> None:
    """Test setup wraps the hub connection in an SSL context when verify_ssl is set."""
    entry = mock_config_entry(data={**MOCK_DATA, CONF_VERIFY_SSL: True})

    with patch("librouteros.connect", return_value=MagicMock()) as mock_connect:
        await setup_integration(hass, entry, command_responses={})

    assert entry.state is ConfigEntryState.LOADED
    assert "ssl_wrapper" in mock_connect.call_args.kwargs


@pytest.mark.parametrize(
    "error",
    [ConnectionClosed(), OSError(), TimeoutError()],
    ids=["connection_closed", "os_error", "timeout_error"],
)
async def test_hub_connection_error(
    hass: HomeAssistant,
    mock_api: MagicMock,
    mock_config_entry: MockConfigEntryFactory,
    error: Exception,
) -> None:
    """Test setup retries when the hub can't be reached after connecting."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    mock_api.side_effect = error

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "error",
    [
        LibRouterosError("no route to host"),
        OSError(),
        TimeoutError(),
        ConnectionClosed(),
    ],
    ids=["cannot_connect", "os_error", "timeout_error", "connection_closed"],
)
async def test_hub_connect_error_retries_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntryFactory,
    error: Exception,
) -> None:
    """Test setup retries when the initial connection to the hub fails."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    with patch("librouteros.connect", side_effect=error):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_hub_login_error_starts_reauth(
    hass: HomeAssistant, mock_config_entry: MockConfigEntryFactory
) -> None:
    """Test setup starts a reauth flow when the hub rejects the credentials."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    with patch(
        "librouteros.connect",
        side_effect=LibRouterosError("invalid user name or password"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert any(entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


async def test_optional_command_error_is_suppressed(
    hass: HomeAssistant, mock_api: MagicMock, mock_config_entry: MockConfigEntryFactory
) -> None:
    """Test setup succeeds when an optional command isn't supported by the hub."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    mock_api.side_effect = _command_side_effect(
        MIKROTIK_SERVICES[ROUTERBOARD], LibRouterosError("no such command prefix")
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED


async def test_optional_command_unexpected_error_fails_setup(
    hass: HomeAssistant, mock_api: MagicMock, mock_config_entry: MockConfigEntryFactory
) -> None:
    """Test setup fails when an optional command raises an unexpected error."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    mock_api.side_effect = _command_side_effect(
        MIKROTIK_SERVICES[ROUTERBOARD], LibRouterosError("permission denied")
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_required_command_error_fails_setup(
    hass: HomeAssistant, mock_api: MagicMock, mock_config_entry: MockConfigEntryFactory
) -> None:
    """Test setup fails on a required command even with a suppressible message."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    mock_api.side_effect = _command_side_effect(
        MIKROTIK_SERVICES[IDENTITY], LibRouterosError("no such command prefix")
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    "error",
    [OSError(), TimeoutError(), ConnectionClosed()],
    ids=["os_error", "timeout_error", "connection_closed"],
)
async def test_connection_lost_during_refresh_raises_update_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntryFactory,
    error: Exception,
) -> None:
    """Test a lost connection during a scheduled refresh is treated as UpdateFailed.

    ConfigEntryNotReady is only special-cased on the first refresh; raising
    it from later scheduled refreshes falls through to the coordinator's
    generic exception handler instead of the dedicated UpdateFailed one.
    """
    entry = mock_config_entry()
    await setup_integration(hass, entry, command_responses={})
    assert entry.state is ConfigEntryState.LOADED

    coordinator = entry.runtime_data

    with patch.object(
        entry.runtime_data.api,
        "command",
        side_effect=error,
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, UpdateFailed)


async def test_hub_reconnect_error_during_refresh_raises_update_failed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntryFactory
) -> None:
    """Test a failed reconnect during a scheduled refresh is treated as UpdateFailed."""
    entry = mock_config_entry()
    await setup_integration(hass, entry, command_responses={})
    assert entry.state is ConfigEntryState.LOADED

    coordinator = entry.runtime_data

    with patch("librouteros.connect", side_effect=OSError()):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, UpdateFailed)


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntryFactory
) -> None:
    """Test unloading an entry."""
    entry = mock_config_entry()
    await setup_integration(hass, entry, command_responses={})

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
