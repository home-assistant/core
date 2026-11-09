"""Test the System Bridge integration."""

import asyncio
from dataclasses import replace
from datetime import timedelta
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from systembridgeconnector.exceptions import (
    AuthenticationException,
    ConnectionClosedException,
    ConnectionErrorException,
    DataMissingException,
)
from systembridgeconnector.models.fixtures.modules.system import FIXTURE_SYSTEM
from systembridgeconnector.models.modules import GetData, Module, ModulesData
from systembridgeconnector.models.system_control import PowerState, PowerStateEvent

from homeassistant.components.system_bridge.config_flow import SystemBridgeConfigFlow
from homeassistant.components.system_bridge.const import DOMAIN, GET_DATA_WAIT_TIMEOUT
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_TOKEN,
    EVENT_HOMEASSISTANT_STOP,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from . import FIXTURE_USER_INPUT, FIXTURE_UUID


@pytest.mark.usefixtures("mock_version")
async def test_entry_setup_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
) -> None:
    """Test integration setup and unload."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_websocket_client.close.assert_not_awaited()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_websocket_client.close.assert_awaited_once()


@pytest.mark.parametrize(
    ("version", "requests_audio"),
    [
        pytest.param("5.15.0", False, id="before_audio"),
        pytest.param("5.16.0", True, id="audio"),
        pytest.param("5.22.1.dev0+abc1234", True, id="dev_build"),
    ],
)
@pytest.mark.usefixtures("mock_version")
async def test_setup_requests_audio_when_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
    version: str,
    requests_audio: bool,
) -> None:
    """Test audio is only requested from backends that answer for it."""
    mock_websocket_client.get_data.return_value = replace(
        mock_websocket_client.get_data.return_value,
        system=replace(FIXTURE_SYSTEM, version=version),
    )

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        call(GetData(modules=[Module.AUDIO]), timeout=GET_DATA_WAIT_TIMEOUT)
        in mock_websocket_client.get_data.await_args_list
    ) is requests_audio


@pytest.mark.usefixtures("mock_version")
async def test_setup_without_audio_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
) -> None:
    """Test setup carries on when the backend has no audio data yet."""
    modules_data = replace(
        mock_websocket_client.get_data.return_value,
        system=replace(FIXTURE_SYSTEM, version="5.16.0"),
    )
    mock_websocket_client.get_data.return_value = None
    mock_websocket_client.get_data.side_effect = [
        modules_data,
        DataMissingException("No data received for modules: ['audio']"),
    ]

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_migration_minor_1_to_2(hass: HomeAssistant) -> None:
    """Test migration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FIXTURE_UUID,
        data={
            CONF_API_KEY: FIXTURE_USER_INPUT[CONF_TOKEN],
            CONF_HOST: FIXTURE_USER_INPUT[CONF_HOST],
            CONF_PORT: FIXTURE_USER_INPUT[CONF_PORT],
        },
        version=SystemBridgeConfigFlow.VERSION,
        minor_version=1,
    )

    with patch(
        "homeassistant.components.system_bridge.async_setup_entry",
        return_value=None,
    ) as mock_setup_entry:
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert len(mock_setup_entry.mock_calls) == 1

    # Check that the version has been updated and the api_key has been moved to token
    assert config_entry.version == SystemBridgeConfigFlow.VERSION
    assert config_entry.minor_version == SystemBridgeConfigFlow.MINOR_VERSION
    assert config_entry.data == {
        CONF_API_KEY: FIXTURE_USER_INPUT[CONF_TOKEN],
        CONF_HOST: FIXTURE_USER_INPUT[CONF_HOST],
        CONF_PORT: FIXTURE_USER_INPUT[CONF_PORT],
        CONF_TOKEN: FIXTURE_USER_INPUT[CONF_TOKEN],
    }
    assert config_entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("mock_version", "mock_websocket_client")
async def test_migration_minor_2_to_3(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration of entity unique ids."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FIXTURE_UUID,
        data={
            CONF_TOKEN: FIXTURE_USER_INPUT[CONF_TOKEN],
            CONF_HOST: "hostname",
            CONF_PORT: FIXTURE_USER_INPUT[CONF_PORT],
        },
        version=1,
        minor_version=2,
    )

    config_entry.add_to_hass(hass)
    assert config_entry.minor_version == 2

    sensor = entity_registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="hostname_cpu_speed",
        config_entry=config_entry,
        original_name="hostname CPU speed",
    )

    notifier = entity_registry.async_get_or_create(
        domain="notify",
        platform=DOMAIN,
        unique_id="hostname",
        config_entry=config_entry,
        original_name="hostname",
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.version == 1
    assert config_entry.minor_version == 3

    assert (
        entity_registry.async_get(sensor.entity_id).unique_id
        == f"{FIXTURE_UUID}_cpu_speed"
    )

    assert entity_registry.async_get(notifier.entity_id).unique_id == FIXTURE_UUID

    assert config_entry.state is ConfigEntryState.LOADED


async def test_migration_minor_future_version(hass: HomeAssistant) -> None:
    """Test migration."""
    config_entry_data = {
        CONF_API_KEY: FIXTURE_USER_INPUT[CONF_TOKEN],
        CONF_HOST: FIXTURE_USER_INPUT[CONF_HOST],
        CONF_PORT: FIXTURE_USER_INPUT[CONF_PORT],
        CONF_TOKEN: FIXTURE_USER_INPUT[CONF_TOKEN],
    }
    config_entry_version = SystemBridgeConfigFlow.VERSION
    config_entry_minor_version = SystemBridgeConfigFlow.MINOR_VERSION + 1
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FIXTURE_UUID,
        data=config_entry_data,
        version=config_entry_version,
        minor_version=config_entry_minor_version,
    )

    with patch(
        "homeassistant.components.system_bridge.async_setup_entry",
        return_value=None,
    ) as mock_setup_entry:
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert len(mock_setup_entry.mock_calls) == 1

    assert config_entry.version == config_entry_version
    assert config_entry.minor_version == config_entry_minor_version
    assert config_entry.data == config_entry_data
    assert config_entry.state is ConfigEntryState.LOADED


async def test_setup_timeout(hass: HomeAssistant) -> None:
    """Test setup with timeout error."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FIXTURE_UUID,
        data=FIXTURE_USER_INPUT,
        version=SystemBridgeConfigFlow.VERSION,
        minor_version=SystemBridgeConfigFlow.MINOR_VERSION,
    )

    with patch(
        "systembridgeconnector.version.Version.check_supported",
        side_effect=TimeoutError,
    ):
        config_entry.add_to_hass(hass)
        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert result is False
        assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unsupported_version_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_version: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an unsupported version creates an issue linked to the entry."""
    mock_version.check_supported.return_value = False

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    issue_id = f"system_bridge_{mock_config_entry.entry_id}_unsupported_version"
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.config_entry_id == mock_config_entry.entry_id

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        pytest.param(
            AuthenticationException,
            ConfigEntryState.SETUP_ERROR,
            id="authentication",
        ),
        pytest.param(
            ConnectionErrorException,
            ConfigEntryState.SETUP_RETRY,
            id="connection_error",
        ),
    ],
)
async def test_version_check_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_version: MagicMock,
    side_effect: type[Exception],
    expected_state: ConfigEntryState,
) -> None:
    """Test setup fails when the version check fails."""
    mock_version.check_supported.side_effect = side_effect

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


async def test_unsupported_version_creates_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_version: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an issue is raised when the System Bridge version is unsupported."""
    mock_version.check_supported.return_value = False

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert issue_registry.async_get_issue(
        DOMAIN, f"system_bridge_{mock_config_entry.entry_id}_unsupported_version"
    )


@pytest.mark.usefixtures("mock_version")
async def test_get_data_authentication_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
) -> None:
    """Test setup starts reauth when getting data fails authentication."""
    mock_websocket_client.get_data.side_effect = AuthenticationException

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


@pytest.mark.parametrize(
    ("side_effect", "expected_state", "reauth"),
    [
        pytest.param(
            AuthenticationException,
            ConfigEntryState.SETUP_ERROR,
            True,
            id="authentication",
        ),
        pytest.param(
            ConnectionClosedException,
            ConfigEntryState.SETUP_RETRY,
            False,
            id="connection_closed",
        ),
        pytest.param(
            ConnectionErrorException,
            ConfigEntryState.SETUP_RETRY,
            False,
            id="connection_error",
        ),
    ],
)
@pytest.mark.usefixtures("mock_version")
async def test_register_data_listener_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
    side_effect: type[Exception],
    expected_state: ConfigEntryState,
    reauth: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup fails when registering the data listener fails."""
    mock_websocket_client.register_data_listener.side_effect = side_effect

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state
    assert (
        any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH})) is reauth
    )
    assert "TestSystem is unavailable" not in caplog.text


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(AuthenticationException, id="authentication"),
        pytest.param(ConnectionClosedException, id="connection_closed"),
        pytest.param(ConnectionResetError, id="connection_reset"),
        pytest.param(ConnectionErrorException, id="connection_error"),
    ],
)
@pytest.mark.usefixtures("mock_version")
async def test_listener_disconnect_marks_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    side_effect: type[Exception],
) -> None:
    """Test entities become unavailable when the WebSocket listener stops."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("update.hostname")
    assert state
    assert state.state != STATE_UNAVAILABLE

    mock_websocket_client.listen.side_effect = side_effect
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("update.hostname")
    assert state
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_version")
async def test_reconnect_backoff_and_logging(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test reconnects back off while the host is away and log once each way."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    register = mock_websocket_client.register_data_listener
    register.side_effect = ConnectionErrorException
    mock_websocket_client.connect.side_effect = ConnectionErrorException
    calls = register.await_count

    # Each failed reconnect doubles the wait, up to 2 minutes
    for wait, expected_calls in (
        (30, calls + 1),
        (30, calls + 1),
        (30, calls + 2),
        (60, calls + 2),
        (60, calls + 3),
        (120, calls + 4),
    ):
        freezer.tick(timedelta(seconds=wait))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert register.await_count == expected_calls

    state = hass.states.get("update.hostname")
    assert state
    assert state.state == STATE_UNAVAILABLE
    assert caplog.text.count("TestSystem is unavailable") == 1
    assert not [
        record
        for record in caplog.records
        if record.name.startswith("homeassistant.components.system_bridge")
        and record.levelno >= logging.WARNING
    ]

    coordinator = mock_config_entry.runtime_data

    async def register_with_buffered_data(*args: Any) -> None:
        coordinator.async_set_updated_data(coordinator.data)

    async def register_fails_after_buffered_data(*args: Any) -> None:
        await register_with_buffered_data()
        raise ConnectionErrorException

    # Data pushed before the register call fails must not log the outage again
    register.side_effect = register_fails_after_buffered_data
    mock_websocket_client.connect.side_effect = None
    freezer.tick(timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert register.await_count == calls + 5
    assert caplog.text.count("TestSystem is unavailable") == 1

    # Data pushed before the register call returns must not hide the recovery
    register.side_effect = register_with_buffered_data
    freezer.tick(timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("update.hostname")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert caplog.text.count("TestSystem is available again") == 1
    assert "Fetching system_bridge data recovered" not in caplog.text
    assert caplog.text.count("TestSystem is unavailable") == 1

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert register.await_count == calls + 7


@pytest.mark.parametrize(
    "power_state",
    [
        pytest.param(PowerState.SLEEPING, id="sleeping"),
        pytest.param(PowerState.SHUTTING_DOWN, id="shutting_down"),
    ],
)
@pytest.mark.usefixtures("mock_version")
async def test_power_state_marks_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    power_state: PowerState,
) -> None:
    """Test the host going to sleep or shutting down is unavailable at once."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    power_state_callback = mock_websocket_client.listen.call_args.kwargs[
        "power_state_callback"
    ]
    await power_state_callback(PowerStateEvent(state=power_state))
    await hass.async_block_till_done()

    state = hass.states.get("update.hostname")
    assert state
    assert state.state == STATE_UNAVAILABLE
    mock_websocket_client.close.assert_awaited_once()

    # A repeated event during the same outage isn't logged again
    await power_state_callback(PowerStateEvent(state=power_state))
    await hass.async_block_till_done()
    assert f"TestSystem is unavailable: {power_state}" in caplog.text

    # Asking for an update before the host has gone doesn't reconnect
    assert await async_setup_component(hass, "homeassistant", {})
    register = mock_websocket_client.register_data_listener
    calls = register.await_count
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: "update.hostname"},
        blocking=True,
    )
    assert register.await_count == calls

    # Reconnects fail quietly while the host is away
    mock_websocket_client.connect.side_effect = ConnectionErrorException
    mock_websocket_client.register_data_listener.side_effect = ConnectionErrorException
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert caplog.text.count("TestSystem is unavailable") == 1

    mock_websocket_client.connect.side_effect = None
    mock_websocket_client.register_data_listener.side_effect = None
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("update.hostname")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert caplog.text.count("TestSystem is available again") == 1


@pytest.mark.usefixtures("mock_version")
async def test_power_state_during_registration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a sleep event while registering doesn't report the host as back."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    mock_websocket_client.connected = False

    async def register_then_sleep(*args: Any) -> None:
        await coordinator.async_handle_power_state(
            PowerStateEvent(state=PowerState.SLEEPING)
        )

    mock_websocket_client.register_data_listener.side_effect = register_then_sleep
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("update.hostname")
    assert state
    assert state.state == STATE_UNAVAILABLE
    assert "TestSystem is available again" not in caplog.text

    # The next attempt backs off to 60 seconds
    register = mock_websocket_client.register_data_listener
    calls = register.await_count
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert register.await_count == calls

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert register.await_count == calls + 1


@pytest.mark.usefixtures("mock_version")
async def test_power_state_while_waiting_for_registration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a sleep event stops a registration still waiting for its response."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    registering = asyncio.Event()
    cancelled = asyncio.Event()

    async def register_without_response(*args: Any) -> None:
        registering.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    async def listen_then_sleep(
        callback: Any = None,
        _: bool = False,
        power_state_callback: Any = None,
    ) -> None:
        await registering.wait()
        await power_state_callback(PowerStateEvent(state=PowerState.SLEEPING))
        await asyncio.Event().wait()

    mock_websocket_client.connected = False
    mock_websocket_client.listen.side_effect = listen_then_sleep
    mock_websocket_client.register_data_listener.side_effect = register_without_response
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert cancelled.is_set()
    state = hass.states.get("update.hostname")
    assert state
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_version")
async def test_power_state_from_running_listener(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a sleep event from the listener closes the socket after it cancels."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    async def listen_then_sleep(
        callback: Any = None,
        _: bool = False,
        power_state_callback: Any = None,
    ) -> None:
        await power_state_callback(PowerStateEvent(state=PowerState.SLEEPING))
        await asyncio.Event().wait()

    closed = asyncio.Event()

    async def close() -> None:
        # Yield so closing from the cancelled listener itself would be interrupted
        await asyncio.sleep(0)
        closed.set()

    mock_websocket_client.connected = False
    mock_websocket_client.listen.side_effect = listen_then_sleep
    mock_websocket_client.close.side_effect = close
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    coordinator = mock_config_entry.runtime_data
    assert coordinator.listen_task.cancelled()
    assert closed.is_set()
    state = hass.states.get("update.hostname")
    assert state
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_power_state_resumed_ignored(
    hass: HomeAssistant,
    mock_websocket_client: MagicMock,
) -> None:
    """Test the host waking while connected changes nothing."""
    power_state_callback = mock_websocket_client.listen.call_args.kwargs[
        "power_state_callback"
    ]
    await power_state_callback(PowerStateEvent(state=PowerState.RESUMED))
    await hass.async_block_till_done()

    state = hass.states.get("update.hostname")
    assert state
    assert state.state != STATE_UNAVAILABLE
    mock_websocket_client.close.assert_not_awaited()


@pytest.mark.usefixtures("init_integration")
async def test_homeassistant_stop_closes_websocket(
    hass: HomeAssistant,
    mock_websocket_client: MagicMock,
) -> None:
    """Test the WebSocket is closed when Home Assistant stops."""
    mock_websocket_client.close.assert_not_awaited()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    mock_websocket_client.close.assert_awaited_once()


@pytest.mark.parametrize(
    ("side_effect", "return_value"),
    [
        pytest.param(TimeoutError, None, id="timeout"),
        pytest.param(ConnectionErrorException, None, id="connection_error"),
        pytest.param(DataMissingException, None, id="data_missing"),
        pytest.param(None, ModulesData(), id="missing_system"),
    ],
)
@pytest.mark.usefixtures("mock_version")
async def test_get_data_failure_closes_websocket(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
    side_effect: type[Exception] | None,
    return_value: ModulesData | None,
) -> None:
    """Test setup retries and closes the websocket when getting data fails."""
    mock_websocket_client.get_data.side_effect = side_effect
    mock_websocket_client.get_data.return_value = return_value

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_websocket_client.close.assert_awaited_once()


@pytest.mark.usefixtures("mock_version")
async def test_platform_setup_failure_cleans_up(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
) -> None:
    """Test the stop listener is removed when setup fails after the first refresh."""
    assert await async_setup_component(hass, "media_source", {})
    stop_listeners = hass.bus.async_listeners().get(EVENT_HOMEASSISTANT_STOP, 0)

    mock_config_entry.add_to_hass(hass)
    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        side_effect=ConfigEntryNotReady,
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.bus.async_listeners().get(EVENT_HOMEASSISTANT_STOP, 0) == stop_listeners
    mock_websocket_client.close.assert_awaited_once()
