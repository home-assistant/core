"""Test Mikrotik setup process."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from librouteros.exceptions import ConnectionClosed, LibRouterosError
import pytest

from homeassistant.components.mikrotik.const import (
    ARP,
    CONF_ARP_PING,
    CONF_FORCE_DHCP,
    DHCP,
    IDENTITY,
    MIKROTIK_SERVICES,
    PING,
    ROUTERBOARD,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from . import setup_integration
from .conftest import MockConfigEntryFactory
from .const import ARP_DATA, DHCP_DATA, MOCK_DATA

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
    hass: HomeAssistant,
    mock_api: MagicMock,
    mock_config_entry: MockConfigEntryFactory,
) -> None:
    """Test a dropped connection with a failed reconnect is treated as UpdateFailed."""
    entry = mock_config_entry()
    await setup_integration(hass, entry, command_responses={})
    assert entry.state is ConfigEntryState.LOADED

    coordinator = entry.runtime_data

    mock_api.side_effect = ConnectionClosed()

    with patch("librouteros.connect", side_effect=OSError()):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, UpdateFailed)


async def test_connection_dropped_during_refresh_reconnects_and_succeeds(
    hass: HomeAssistant,
    mock_api: MagicMock,
    mock_config_entry: MockConfigEntryFactory,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a dropped connection triggers a single reconnect and the refresh succeeds."""
    entry = mock_config_entry()
    await setup_integration(hass, entry, command_responses={})
    assert entry.state is ConfigEntryState.LOADED

    calls = 0

    def flaky_call(cmd: str, **params: Any) -> list[dict[str, Any]]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ConnectionClosed
        return []

    mock_api.side_effect = flaky_call

    with patch(
        "homeassistant.components.mikrotik.coordinator.get_api", return_value=mock_api
    ) as mock_get_api:
        freezer.tick(timedelta(seconds=10))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    assert mock_get_api.call_count == 1


async def test_connection_dropped_during_arp_ping_retries_with_params(
    hass: HomeAssistant,
    mock_api: MagicMock,
    mock_config_entry: MockConfigEntryFactory,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a dropped connection during an arp-ping reconnects and retries with params."""
    entry = mock_config_entry(options={CONF_ARP_PING: True, CONF_FORCE_DHCP: True})
    await setup_integration(hass, entry, command_responses={})
    assert entry.state is ConfigEntryState.LOADED

    ping_cmd = MIKROTIK_SERVICES[PING]
    # a single tracked device keeps the arp-ping call count deterministic
    responses = {
        MIKROTIK_SERVICES[DHCP]: DHCP_DATA[:1],
        MIKROTIK_SERVICES[ARP]: ARP_DATA[:1],
    }
    ping_calls = 0

    def flaky_call(cmd: str, **params: Any) -> list[dict[str, Any]]:
        nonlocal ping_calls
        if cmd == ping_cmd:
            ping_calls += 1
            if ping_calls == 1:
                raise ConnectionClosed
            return [{"seq": "0"}]
        return responses.get(cmd, [])

    mock_api.side_effect = flaky_call

    with patch(
        "homeassistant.components.mikrotik.coordinator.get_api", return_value=mock_api
    ) as mock_get_api:
        freezer.tick(timedelta(seconds=10))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.last_update_success is True
    # the arp-ping command carries params, so the reconnect retries it with them
    assert mock_get_api.call_count == 1
    assert ping_calls == 2


async def test_scheduled_refresh_reuses_persistent_connection(
    hass: HomeAssistant, mock_config_entry: MockConfigEntryFactory
) -> None:
    """Test scheduled refreshes reuse the open connection instead of reconnecting."""
    entry = mock_config_entry()
    await setup_integration(hass, entry, command_responses={})
    assert entry.state is ConfigEntryState.LOADED

    with patch("librouteros.connect") as mock_connect:
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
        await hass.async_block_till_done(wait_background_tasks=True)
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=20))
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    mock_connect.assert_not_called()


async def test_unload_entry(
    hass: HomeAssistant,
    mock_api: MagicMock,
    mock_config_entry: MockConfigEntryFactory,
) -> None:
    """Test unloading an entry closes the persistent connection."""
    entry = mock_config_entry()
    await setup_integration(hass, entry, command_responses={})

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    mock_api.close.assert_called_once()
