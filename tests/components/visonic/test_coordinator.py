"""Additional tests for shared coordinator state and lifecycle behavior."""

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import timedelta
import logging
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed
from pyvisonicalarm.alarm import AlarmSystem
from pyvisonicalarm.classes import Status
from pyvisonicalarm.exceptions import ConnectionTimeoutError, UnauthorizedError

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.components.visonic.cloud import VisonicCloudConnection
from homeassistant.components.visonic.connection import (
    VisonicConnection,
    VisonicPanelMetadata,
)
from homeassistant.components.visonic.const import (
    DOMAIN,
    LOGGER,
    MANUFACTURER,
    PANEL_ATTRIBUTE_NAME,
    TEXT_DISCONNECTION_COUNT,
)
from homeassistant.components.visonic.coordinator import VisonicCoordinator
from homeassistant.components.visonic.direct import VisonicDirectConnection
from homeassistant.components.visonic.exceptions import (
    VisonicAuthException,
    VisonicException,
)
from homeassistant.components.visonic.utils import get_alarm_panel_unique_ident
from homeassistant.components.visonic.visonic_data_types import (
    VisonicConfigEntry,
    VisonicCoordinatorData,
)
from homeassistant.components.visonic.visonic_entity_types import (
    AlarmPanelData,
    PanelState,
)
from homeassistant.components.visonic.visonic_types import (
    AlarmCommandStatus,
    AlarmPanelCommand,
    AlarmPanelStatus,
    CommandResult,
    DeviceType,
    PanelStateData,
)
from homeassistant.const import CONF_TYPE, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.translation import async_get_translations
from homeassistant.helpers.typing import UNDEFINED, UndefinedType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .helpers import SetupIntegration, create_config_entry_example


@pytest.mark.parametrize(
    "update",
    [
        pytest.param(
            lambda coordinator: coordinator._handle_panel_metadata(
                VisonicPanelMetadata("PowerMaster 10", "ABCDEF")
            ),
            id="panel-metadata",
        ),
        pytest.param(
            lambda coordinator: coordinator._handle_panel_metadata(
                VisonicPanelMetadata("PowerMaster 10", None)
            ),
            id="model-only",
        ),
        pytest.param(
            lambda coordinator: coordinator._handle_baud_change(38400), id="baud"
        ),
        pytest.param(
            lambda coordinator: coordinator._handle_app_id_change("new-app-id"),
            id="app-id",
        ),
    ],
)
async def test_runtime_metadata_does_not_reload(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    update: Callable[[VisonicCoordinator], None],
) -> None:
    """Persist backend metadata without restarting the connection."""
    _, entry = await setup_integration()
    with patch.object(hass.config_entries, "async_reload", return_value=True) as reload:
        update(entry.runtime_data.coordinator)
        await hass.async_block_till_done()
    reload.assert_not_awaited()


@pytest.mark.parametrize(
    ("device_type", "connection_type", "interval"),
    [
        pytest.param(DeviceType.ETHERNET, VisonicDirectConnection, 60, id="ethernet"),
        pytest.param(DeviceType.SERIAL, VisonicDirectConnection, 60, id="serial"),
        pytest.param(DeviceType.CLOUD, VisonicCloudConnection, 20, id="cloud"),
    ],
)
async def test_connection_selection(
    hass: HomeAssistant,
    device_type: DeviceType,
    connection_type: type[VisonicConnection],
    interval: int,
) -> None:
    """Each transport uses one coordinator with an ordinary connection helper."""
    entry = create_config_entry_example(data={CONF_TYPE: device_type})
    coordinator = VisonicCoordinator(hass, entry, 1)
    assert isinstance(coordinator, DataUpdateCoordinator)
    assert isinstance(coordinator.connection, connection_type)
    assert isinstance(coordinator.connection, VisonicConnection)
    assert not isinstance(coordinator.connection, DataUpdateCoordinator)
    assert not hasattr(coordinator.connection, "_coordinator")
    assert not hasattr(coordinator.connection, "config_entry")
    assert not hasattr(coordinator.connection, "hass")
    assert coordinator.update_interval.total_seconds() == interval
    await coordinator.async_shutdown()


@pytest.mark.parametrize(
    "device_type",
    [
        pytest.param(DeviceType.ETHERNET, id="direct"),
        pytest.param(DeviceType.CLOUD, id="cloud"),
    ],
)
async def test_stop_cancels_pending_update(
    hass: HomeAssistant, device_type: DeviceType
) -> None:
    """Both transports stop without a delayed callback restoring stale state."""
    entry = create_config_entry_example(data={CONF_TYPE: device_type})
    coordinator = VisonicCoordinator(hass, entry, 1)
    coordinator.async_set_updated_data(VisonicCoordinatorData(connected=True))
    coordinator.start_coordinator_update_timer(60)
    with patch.object(coordinator.connection, "async_panel_stop") as stop:
        await coordinator.async_panel_stop()
        stop.assert_awaited_once_with()
    assert coordinator._coordinator_update_timer is None
    assert not coordinator.data.connected
    assert coordinator.data.mode == "stopped"
    await coordinator.async_shutdown()


def start_polled_refresh(
    coordinator: VisonicCoordinator,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Advance beyond either backend's polling interval."""
    coordinator.async_add_listener(MagicMock())
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)


def start_pushed_refresh(
    coordinator: VisonicCoordinator,
    _hass: HomeAssistant,
    _freezer: FrozenDateTimeFactory,
) -> None:
    """Schedule the same update as a backend state notification."""
    coordinator.state_changed_callback(0)


@pytest.mark.parametrize("device_type", [DeviceType.ETHERNET, DeviceType.CLOUD])
@pytest.mark.parametrize(
    "refresh",
    [
        pytest.param(start_polled_refresh, id="polled"),
        pytest.param(start_pushed_refresh, id="pushed"),
    ],
)
async def test_stop_waits_for_running_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_type: DeviceType,
    refresh: Callable[[VisonicCoordinator, HomeAssistant, FrozenDateTimeFactory], None],
) -> None:
    """Cancel pending I/O before closing the backend or publishing stopped state."""
    coordinator = VisonicCoordinator(
        hass, create_config_entry_example(data={CONF_TYPE: device_type}), 1
    )
    started = asyncio.Event()
    response = asyncio.Event()
    finished = asyncio.Event()

    async def snapshot() -> VisonicCoordinatorData:
        started.set()
        try:
            await response.wait()
        finally:
            finished.set()
        return VisonicCoordinatorData(connected=True)

    async def stop() -> None:
        assert finished.is_set()
        coordinator.state_changed_callback(0)

    with (
        patch.object(
            coordinator.connection, "create_state_snapshot", side_effect=snapshot
        ),
        patch.object(
            coordinator.connection, "async_panel_stop", side_effect=stop
        ) as close,
    ):
        refresh(coordinator, hass, freezer)
        await started.wait()
        (task,) = coordinator._refresh_tasks
        await coordinator.async_panel_stop()
        response.set()
        await hass.async_block_till_done(wait_background_tasks=True)

    assert task.cancelled()
    close.assert_awaited_once_with()
    assert coordinator._coordinator_update_timer is None
    assert coordinator.data == VisonicCoordinatorData(connected=False, mode="stopped")


@pytest.mark.parametrize(
    "refresh",
    [
        pytest.param(start_polled_refresh, id="polled"),
        pytest.param(start_pushed_refresh, id="pushed"),
    ],
)
async def test_stop_prevents_reauthentication_from_pending_request(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    refresh: Callable[[VisonicCoordinator, HomeAssistant, FrozenDateTimeFactory], None],
) -> None:
    """A delayed unauthorized response cannot reopen a stopped cloud session."""
    coordinator = VisonicCoordinator(
        hass, create_config_entry_example(data={CONF_TYPE: DeviceType.CLOUD}), 1
    )
    cloud = cast(VisonicCloudConnection, coordinator.connection)
    alarm = MagicMock(spec=AlarmSystem)
    cloud.cloud_alarm = alarm
    cloud.login_success = True
    started = asyncio.Event()
    response = asyncio.Event()

    async def unauthorized() -> None:
        started.set()
        await response.wait()
        raise UnauthorizedError

    alarm.get_status = AsyncMock(side_effect=unauthorized)
    with patch.object(cloud, "_async_panel_reconnect") as reconnect:
        refresh(coordinator, hass, freezer)
        await started.wait()
        (task,) = coordinator._refresh_tasks
        await coordinator.async_panel_stop()
        response.set()
        await hass.async_block_till_done(wait_background_tasks=True)

    assert task.cancelled()
    reconnect.assert_not_awaited()
    alarm.panel_logout.assert_awaited_once_with()
    assert cloud.cloud_alarm is None
    assert not cloud.login_success
    assert coordinator.data == VisonicCoordinatorData(connected=False, mode="stopped")


async def test_stop_cancels_cloud_refresh_waiting_for_session(
    hass: HomeAssistant,
) -> None:
    """Shutdown cancels both the active request and a refresh waiting for its lock."""
    coordinator = VisonicCoordinator(
        hass, create_config_entry_example(data={CONF_TYPE: DeviceType.CLOUD}), 1
    )
    cloud = cast(VisonicCloudConnection, coordinator.connection)
    alarm = MagicMock(spec=AlarmSystem)
    cloud.cloud_alarm = alarm
    cloud.login_success = True
    started = asyncio.Event()
    response = asyncio.Event()

    async def status() -> None:
        started.set()
        await response.wait()
        raise UnauthorizedError

    alarm.get_status = AsyncMock(side_effect=status)
    with patch.object(cloud, "_async_panel_reconnect") as reconnect:
        coordinator.state_changed_callback(0)
        await started.wait()
        coordinator.state_changed_callback(0)
        tasks = tuple(coordinator._refresh_tasks)
        assert len(tasks) == 2
        alarm.get_status.assert_awaited_once_with()
        await coordinator.async_panel_stop()
        response.set()
        await hass.async_block_till_done()

    assert all(task.cancelled() for task in tasks)
    reconnect.assert_not_awaited()
    alarm.panel_logout.assert_awaited_once_with()
    assert cloud.cloud_alarm is None
    assert not cloud.login_success
    assert coordinator.data == VisonicCoordinatorData(connected=False, mode="stopped")


@pytest.mark.parametrize("delay", [0.0, 1.0])
async def test_callbacks_after_stop_do_not_start_work(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delay: float
) -> None:
    """Ignore late state and startup callbacks after teardown has begun."""
    coordinator = VisonicCoordinator(hass, create_config_entry_example(), 1)
    coordinator.async_add_listener(MagicMock())
    with patch.object(coordinator.connection, "async_panel_stop"):
        await coordinator.async_panel_stop()

    with (
        patch(
            "homeassistant.components.visonic.coordinator.async_call_later"
        ) as schedule,
        patch.object(coordinator.connection, "create_state_snapshot") as snapshot,
        patch.object(coordinator, "create_alarm_panel") as create,
    ):
        coordinator.state_changed_callback(delay)
        coordinator._coordinator_update_timer_callback(dt_util.utcnow())
        coordinator._handle_panel_ready()
        await coordinator.async_setup_alarm_panel()
        freezer.tick(timedelta(seconds=61))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    schedule.assert_not_called()
    snapshot.assert_not_awaited()
    create.assert_not_called()
    assert coordinator.data == VisonicCoordinatorData(connected=False, mode="stopped")


async def test_connection_command_result(hass: HomeAssistant) -> None:
    """The shared command interface preserves the backend result and PIN."""
    entry = create_config_entry_example(data={CONF_TYPE: DeviceType.CLOUD})
    coordinator = VisonicCoordinator(hass, entry, 1)
    result = CommandResult(AlarmCommandStatus.SUCCESS)
    with patch.object(
        coordinator.connection, "send_command", return_value=result
    ) as send:
        assert (
            await coordinator.send_command(AlarmPanelCommand.DISARM, "1234") is result
        )
        send.assert_awaited_once_with(AlarmPanelCommand.DISARM, "1234")
    await coordinator.async_shutdown()


@pytest.fixture
async def command_coordinator(
    hass: HomeAssistant,
) -> AsyncGenerator[VisonicCoordinator]:
    """Exercise command handling without subclass overrides or panel connections."""
    entry = create_config_entry_example(data={CONF_TYPE: DeviceType.CLOUD})
    coordinator = VisonicCoordinator(hass, entry, 1)
    yield coordinator
    await coordinator.async_panel_stop()
    await coordinator.async_shutdown()


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(TimeoutError("request timed out"), id="timeout"),
        pytest.param(OSError("connection lost"), id="os-error"),
        pytest.param(
            aiohttp.ClientConnectionError("connection refused"), id="http-client"
        ),
    ],
)
async def test_command_transport_failure(
    command_coordinator: VisonicCoordinator, error: Exception
) -> None:
    """Expose communication failures with panel context and retain their cause."""
    with (
        patch.object(
            command_coordinator.connection, "send_command", side_effect=error
        ) as send,
        pytest.raises(HomeAssistantError) as raised,
    ):
        await command_coordinator.send_command(AlarmPanelCommand.ARM_AWAY, "1234")
    assert type(raised.value) is HomeAssistantError
    assert str(raised.value) == "Unable to communicate with Visonic panel 1"
    assert raised.value.__cause__ is error
    send.assert_awaited_once_with(AlarmPanelCommand.ARM_AWAY, "1234")


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(RuntimeError("programming error"), id="unexpected-error"),
        pytest.param(asyncio.CancelledError(), id="cancelled"),
        pytest.param(VisonicAuthException("credentials rejected"), id="authentication"),
    ],
)
async def test_command_preserves_non_transport_errors(
    command_coordinator: VisonicCoordinator, error: BaseException
) -> None:
    """Keep cancellation, authentication and unexpected errors distinguishable."""
    with (
        patch.object(command_coordinator.connection, "send_command", side_effect=error),
        pytest.raises(type(error)) as raised,
    ):
        await command_coordinator.send_command(AlarmPanelCommand.ARM_AWAY, "1234")
    assert raised.value is error


@pytest.mark.parametrize(
    ("status", "exception_type", "reason"),
    [
        pytest.param(
            AlarmCommandStatus.FAIL_INVALID_CODE,
            ServiceValidationError,
            "Failed to Send Command To Panel, not allowed without valid pin",
            id="invalid-code",
        ),
        pytest.param(
            AlarmCommandStatus.FAIL_USER_CONFIG_PREVENTED,
            ServiceValidationError,
            "Failed to Send Command To Panel, disabled by user settings",
            id="user-settings",
        ),
        pytest.param(
            AlarmCommandStatus.FAIL_INVALID_STATE,
            ServiceValidationError,
            "Failed to Send Command To Panel, invalid state requested",
            id="invalid-state",
        ),
        pytest.param(
            AlarmCommandStatus.FAIL_PANEL_CONFIG_PREVENTED,
            ServiceValidationError,
            "Failed to Send Command To Panel, disabled by panel settings",
            id="panel-settings",
        ),
        pytest.param(
            AlarmCommandStatus.FAIL_RECOVERY_IN_PROGRESS,
            HomeAssistantError,
            "Panel communication is temporarily silent for recovery; commands are unavailable until recovery finishes",
            id="recovery-in-progress",
        ),
        pytest.param(
            AlarmCommandStatus.FAIL_DOWNLOAD_IN_PROGRESS,
            HomeAssistantError,
            "Failed to Send Command To Panel, not supported when downloading EPROM",
            id="download-in-progress",
        ),
        pytest.param(
            AlarmCommandStatus.FAIL_INVALID_RETURN,
            HomeAssistantError,
            "Failed to Send Command To Panel, invalid state returned",
            id="invalid-return",
        ),
        pytest.param(
            AlarmCommandStatus.FAIL_INVALID_PROCESS_TOKEN,
            HomeAssistantError,
            "Failed to Send Command To Panel, invalid process token from cloud server",
            id="invalid-process-token",
        ),
        pytest.param(
            AlarmCommandStatus.FAIL_SWITCH_PROBLEM,
            HomeAssistantError,
            "Failed to Send Command To Panel, general Switch Problem",
            id="switch-problem",
        ),
        pytest.param(
            AlarmCommandStatus.FAIL_ENTITY_INCORRECT,
            HomeAssistantError,
            "Failed to Send Command To Panel, entity not supported",
            id="unsupported-entity",
        ),
        pytest.param(
            AlarmCommandStatus.FAIL_PANEL_NO_CONNECTION,
            HomeAssistantError,
            "Failed to Send Command To Panel, no connection to panel",
            id="disconnected",
        ),
        pytest.param(
            AlarmCommandStatus.FAIL_ABSTRACT_CLASS_NOT_IMPLEMENTED,
            HomeAssistantError,
            "Failed to Send Command To Panel, report error to integration author and send a log file",
            id="unsupported-implementation",
        ),
    ],
)
async def test_command_result_failure(
    hass: HomeAssistant,
    coordinator: VisonicCoordinator,
    status: AlarmCommandStatus,
    exception_type: type[HomeAssistantError],
    reason: str,
) -> None:
    """Distinguish validation and execution failures for every command status."""
    hass.config.components.add(DOMAIN)
    await async_get_translations(hass, "en", "exceptions", {DOMAIN})
    with pytest.raises(exception_type) as raised:
        coordinator.process_command_result(CommandResult(status))
    assert type(raised.value) is exception_type
    assert raised.value.translation_domain == DOMAIN
    assert raised.value.translation_key == status.name.lower()
    assert raised.value.translation_placeholders == {"panel_id": "1"}
    assert str(raised.value) == f"Visonic Panel 1 {reason}"


def test_successful_command_result(coordinator: VisonicCoordinator) -> None:
    """Accept a successful command without raising an exception."""
    coordinator.process_command_result(CommandResult(AlarmCommandStatus.SUCCESS))


async def test_pushed_authentication_failure_requests_reauth(
    hass: HomeAssistant, command_coordinator: VisonicCoordinator
) -> None:
    """Make a failed pushed update unavailable, request reauth and allow recovery."""
    coordinator = command_coordinator
    coordinator.async_add_listener(MagicMock())
    snapshot = VisonicCoordinatorData(connected=True, mode="cloud")
    coordinator.async_set_updated_data(snapshot)
    listener = MagicMock()
    coordinator.async_add_listener(listener)
    assert coordinator.config_entry is not None

    with (
        patch.object(
            coordinator.connection,
            "create_state_snapshot",
            side_effect=[VisonicAuthException("Credentials rejected"), snapshot],
        ),
        patch.object(
            coordinator.config_entry, "async_start_reauth_if_available"
        ) as reauth,
    ):
        coordinator.state_changed_callback(0)
        await hass.async_block_till_done()

        assert not coordinator.last_update_success
        assert isinstance(coordinator.last_exception, ConfigEntryAuthFailed)
        assert str(coordinator.last_exception) == "Credentials rejected"
        assert coordinator.data is snapshot
        listener.assert_called_once_with()
        reauth.assert_called_once_with(hass)

        coordinator.state_changed_callback(0)
        await hass.async_block_till_done()

        assert coordinator.last_update_success
        assert coordinator.data is snapshot
        assert listener.call_count == 2
        reauth.assert_called_once_with(hass)


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(TimeoutError("Network unavailable"), id="timeout"),
        pytest.param(ConnectionError("Connection refused"), id="connection-error"),
        pytest.param(ConnectionTimeoutError(), id="library-timeout"),
    ],
)
async def test_pushed_session_renewal_failure_and_recovery(
    hass: HomeAssistant,
    command_coordinator: VisonicCoordinator,
    error: Exception,
) -> None:
    """A failed network reconnect makes the alarm unavailable until recovery."""
    coordinator = command_coordinator
    cloud = cast(VisonicCloudConnection, coordinator.connection)
    alarm = MagicMock(spec=AlarmSystem)
    alarm.get_status.side_effect = UnauthorizedError()
    cloud.cloud_alarm = alarm
    cloud.login_success = True
    snapshot = VisonicCoordinatorData(connected=True, mode="cloud")
    coordinator.async_set_updated_data(snapshot)
    listener = MagicMock()
    coordinator.async_add_listener(listener)
    assert coordinator.config_entry is not None

    recovered_alarm = MagicMock(spec=AlarmSystem)
    recovered_alarm.get_status.return_value = Status({"connected": True})
    recovered_alarm.get_panel_info.return_value = None
    recovered_alarm.get_devices.return_value = []
    recovered_alarm.get_alarms.return_value = []

    async def reconnect() -> bool:
        cloud.cloud_alarm = recovered_alarm
        cloud.login_success = True
        return True

    with (
        patch.object(cloud, "authenticate", side_effect=error) as authenticate,
        patch.object(
            coordinator.config_entry, "async_start_reauth_if_available"
        ) as reauth,
    ):
        coordinator.state_changed_callback(0)
        await hass.async_block_till_done()

        assert not coordinator.last_update_success
        assert isinstance(coordinator.last_exception, UpdateFailed)
        assert isinstance(coordinator.last_exception.__cause__, VisonicException)
        assert coordinator.last_exception.__cause__.__cause__ is error
        assert coordinator.data is snapshot
        assert not cloud.login_success
        assert cloud.cloud_alarm is None
        listener.assert_called_once_with()
        authenticate.assert_awaited_once_with()
        reauth.assert_not_called()

        with patch.object(cloud, "_async_panel_connect", side_effect=reconnect):
            coordinator.state_changed_callback(0)
            await hass.async_block_till_done()

        assert coordinator.last_update_success
        assert coordinator.data.connected
        assert listener.call_count == 2
        reauth.assert_not_called()


async def test_cloud_panel_setup_from_snapshot(
    hass: HomeAssistant,
) -> None:
    """The coordinator registers a cloud alarm once usable data is available."""
    entry = create_config_entry_example(data={CONF_TYPE: DeviceType.CLOUD})
    coordinator = VisonicCoordinator(hass, entry, 1)
    snapshot = VisonicCoordinatorData(connected=True, mode="cloud")
    with (
        patch.object(
            coordinator.connection, "create_state_snapshot", return_value=snapshot
        ),
        patch.object(coordinator, "set_alarm_device_information") as register,
        patch.object(coordinator, "create_alarm_panel") as create,
    ):
        assert await coordinator.my_update_data() is snapshot
        assert await coordinator.my_update_data() is snapshot

    register.assert_called_once_with(entry.title)
    create.assert_called_once_with()
    await coordinator.async_panel_stop()
    await coordinator.async_shutdown()


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(VisonicCoordinatorData(connected=False), id="disconnected"),
        pytest.param(UpdateFailed("Panel is disconnected"), id="update-failed"),
    ],
)
async def test_startup_notifications_wait_for_initial_state(
    command_coordinator: VisonicCoordinator,
    caplog: pytest.LogCaptureFixture,
    failure: VisonicCoordinatorData | UpdateFailed,
) -> None:
    """Initial disconnected notifications are startup progress, not an outage."""
    coordinator = command_coordinator
    snapshot = VisonicCoordinatorData(connected=True)
    listener = MagicMock()
    coordinator.async_add_listener(listener)
    caplog.set_level(logging.INFO, logger=LOGGER.name)

    with patch.object(
        coordinator.connection,
        "create_state_snapshot",
        side_effect=[failure, failure, snapshot],
    ):
        await coordinator.async_state_changed_callback()
        await coordinator.async_state_changed_callback()
        assert coordinator.data is None
        assert coordinator.last_update_success
        listener.assert_not_called()

        await coordinator.async_state_changed_callback()
        assert coordinator.data is snapshot
        assert coordinator.last_update_success
        listener.assert_called_once_with()
        assert caplog.record_tuples == []


async def _poll_coordinator(
    coordinator: VisonicCoordinator,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Run the next scheduled coordinator update."""
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _push_coordinator(
    coordinator: VisonicCoordinator,
    _hass: HomeAssistant,
    _freezer: FrozenDateTimeFactory,
) -> None:
    """Publish a state notification without advancing polling."""
    await coordinator.async_state_changed_callback()


@pytest.mark.parametrize(
    ("failure_method", "failure_action"),
    [
        pytest.param(_poll_coordinator, "fetching", id="polled-failure"),
        pytest.param(
            _push_coordinator,
            "requesting",
            id="pushed-failure",
        ),
    ],
)
@pytest.mark.parametrize(
    "recovery_method",
    [
        pytest.param(_poll_coordinator, id="polled-recovery"),
        pytest.param(_push_coordinator, id="pushed-recovery"),
    ],
)
@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(VisonicCoordinatorData(connected=False), id="disconnected"),
        pytest.param(UpdateFailed("Panel is disconnected"), id="update-failed"),
    ],
)
async def test_availability_transition_logging(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    command_coordinator: VisonicCoordinator,
    caplog: pytest.LogCaptureFixture,
    failure_method: Callable[
        [VisonicCoordinator, HomeAssistant, FrozenDateTimeFactory], Awaitable[None]
    ],
    failure_action: str,
    recovery_method: Callable[
        [VisonicCoordinator, HomeAssistant, FrozenDateTimeFactory], Awaitable[None]
    ],
    failure: VisonicCoordinatorData | UpdateFailed,
) -> None:
    """Polling and pushed updates log each outage and recovery exactly once."""
    coordinator = command_coordinator
    coordinator._created_alarm_panel = True
    snapshot = VisonicCoordinatorData(connected=True)
    listener = MagicMock()
    coordinator.async_add_listener(listener)
    caplog.set_level(logging.INFO, logger=LOGGER.name)
    caplog.handler.addFilter(logging.Filter(LOGGER.name))

    with patch.object(
        coordinator.connection,
        "create_state_snapshot",
        side_effect=[snapshot, failure, failure, failure, snapshot, snapshot, snapshot],
    ):
        await _poll_coordinator(coordinator, hass, freezer)
        assert caplog.record_tuples == []
        listener.reset_mock()

        await failure_method(coordinator, hass, freezer)
        assert not coordinator.last_update_success
        assert coordinator.data is snapshot
        assert isinstance(coordinator.last_exception, UpdateFailed)
        listener.assert_called_once_with()
        assert caplog.record_tuples == [
            (
                LOGGER.name,
                logging.ERROR,
                f"Error {failure_action} {coordinator.name} data: Panel is disconnected",
            )
        ]

        await _poll_coordinator(coordinator, hass, freezer)
        await coordinator.async_state_changed_callback()
        assert not coordinator.last_update_success
        listener.assert_called_once_with()
        assert len(caplog.records) == 1

        await recovery_method(coordinator, hass, freezer)
        assert coordinator.last_update_success
        assert coordinator.data is snapshot
        assert listener.call_count == 2
        assert caplog.record_tuples[1:] == [
            (LOGGER.name, logging.INFO, f"Fetching {coordinator.name} data recovered")
        ]

        await _poll_coordinator(coordinator, hass, freezer)
        await coordinator.async_state_changed_callback()
        assert len(caplog.records) == 2

    caplog.clear()
    await coordinator.async_panel_stop()
    assert caplog.record_tuples == []


async def test_cloud_setup_after_disconnected_snapshot(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    command_coordinator: VisonicCoordinator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Defer cloud entity setup until connected and log the first recovery."""
    coordinator = command_coordinator
    coordinator.async_add_listener(MagicMock())
    snapshot = VisonicCoordinatorData(connected=True, mode="cloud")
    caplog.set_level(logging.INFO, logger=LOGGER.name)
    caplog.handler.addFilter(logging.Filter(LOGGER.name))
    with (
        patch.object(
            coordinator.connection,
            "create_state_snapshot",
            side_effect=[VisonicCoordinatorData(connected=False), snapshot],
        ),
        patch.object(coordinator, "set_alarm_device_information") as register,
        patch.object(coordinator, "create_alarm_panel") as create,
    ):
        await _poll_coordinator(coordinator, hass, freezer)
        assert not coordinator.last_update_success
        register.assert_not_called()
        create.assert_not_called()
        caplog.clear()

        await _poll_coordinator(coordinator, hass, freezer)
        assert coordinator.last_update_success
        assert coordinator.data is snapshot
        register.assert_called_once_with(coordinator.config_entry.title)
        create.assert_called_once_with()
        assert caplog.record_tuples == [
            (LOGGER.name, logging.INFO, f"Fetching {coordinator.name} data recovered")
        ]


class DummyCoordinator(VisonicCoordinator):
    """Dummy."""

    def __init__(self, hass: HomeAssistant, entry: VisonicConfigEntry) -> None:
        """Dummy."""
        super().__init__(
            hass,
            entry,
            panel_id=1,
            update_interval=10,
        )

    def ive_been_created(self):
        """Created."""

    async def async_panel_connect(self):
        """Connect to panel."""

    async def async_service_panel_reconnect(self, call):
        """Reconnect."""

    async def async_panel_stop(self):
        """Stop."""

    async def send_command(self, *args, **kwargs):
        """Send command."""
        return CommandResult(
            AlarmCommandStatus.SUCCESS,
        )

    def get_panel_pin_code_simple(self, code):
        """Get pin code."""
        return True, code

    async def create_state_snapshot(self) -> VisonicCoordinatorData:
        """Get the state snapshot."""
        return VisonicCoordinatorData()

    def get_panel_pin_code(self, code: str | None) -> tuple[bool, str | None]:
        """Get code code."""
        return True, None


@pytest.fixture
async def coord(hass: HomeAssistant):
    """Exercise inherited base behavior with all transport operations mocked."""
    entry = create_config_entry_example(
        data={
            CONF_TYPE: DeviceType.CLOUD,
        },
        options={},
    )
    coordinator = VisonicCoordinator(hass, entry, 1)
    coordinator.get_panel_pin_code = MagicMock(return_value=(True, "1234"))
    coordinator.send_command = AsyncMock()
    yield coordinator
    if coordinator._coordinator_update_timer is not None:
        coordinator._coordinator_update_timer()
    await coordinator.async_panel_stop()
    await coordinator.async_shutdown()


@pytest.fixture
async def coordinator(hass: HomeAssistant) -> AsyncGenerator[DummyCoordinator]:
    """Create the base coordinator without opening a panel connection."""
    coord = DummyCoordinator(hass, create_config_entry_example())
    yield coord
    await coord.async_shutdown()


@pytest.fixture
async def alarm_discoveries(
    hass: HomeAssistant, coordinator: DummyCoordinator
) -> AsyncGenerator[list[AlarmPanelData]]:
    """Collect alarm discoveries and remove the dispatcher listener afterwards."""
    assert coordinator.config_entry is not None
    messages: list[AlarmPanelData] = []

    @callback
    def receive(data: AlarmPanelData) -> None:
        messages.append(data)

    unsubscribe = async_dispatcher_connect(
        hass,
        f"{DOMAIN}_{coordinator.config_entry.entry_id}_add_{Platform.ALARM_CONTROL_PANEL}",
        receive,
    )
    yield messages
    unsubscribe()


@pytest.mark.parametrize(
    "model",
    [
        pytest.param(UNDEFINED, id="unknown-model"),
        pytest.param("PowerMaster 30", id="known-model"),
    ],
)
def test_set_alarm_device_information(
    coordinator: DummyCoordinator, model: str | UndefinedType
) -> None:
    """Register the panel with its stable identifier and available model."""
    assert coordinator.config_entry is not None
    with patch(
        "homeassistant.components.visonic.coordinator.dr.async_get"
    ) as async_get:
        registry = async_get.return_value
        coordinator.set_alarm_device_information(model)

    registry.async_get_or_create.assert_called_once_with(
        config_entry_id=coordinator.config_entry.entry_id,
        identifiers={(DOMAIN, get_alarm_panel_unique_ident(coordinator.panel_id))},
        name=get_alarm_panel_unique_ident(coordinator.panel_id),
        manufacturer=MANUFACTURER,
        model=model,
    )


async def test_create_alarm_panel(
    coordinator: DummyCoordinator, alarm_discoveries: list[AlarmPanelData]
) -> None:
    """Dispatch the panel identifier to the alarm platform."""
    result = coordinator.create_alarm_panel()

    assert result.identifier == get_alarm_panel_unique_ident(coordinator.panel_id)
    assert alarm_discoveries == [result]


async def test_async_setup_alarm_panel_once(
    coordinator: DummyCoordinator, alarm_discoveries: list[AlarmPanelData]
) -> None:
    """Concurrent and subsequent setup requests announce the panel only once."""
    await asyncio.gather(
        coordinator.async_setup_alarm_panel(),
        coordinator.async_setup_alarm_panel(),
    )
    await coordinator.async_setup_alarm_panel()

    assert len(alarm_discoveries) == 1
    assert coordinator._created_alarm_panel is True


async def test_immediate_update_replaces_pending_timer(
    hass: HomeAssistant, coord: VisonicCoordinator
) -> None:
    """A zero-delay request cancels the pending update and publishes a fresh snapshot."""
    cancel = MagicMock()
    coord._coordinator_update_timer = cancel
    snapshot = VisonicCoordinatorData(connected=True)
    with patch.object(
        coord, "create_state_snapshot", new_callable=AsyncMock, return_value=snapshot
    ) as create:
        coord.start_coordinator_update_timer(0)
        await hass.async_block_till_done()
    cancel.assert_called_once_with()
    create.assert_awaited_once_with()
    assert coord.data is snapshot


async def test_delayed_update_publishes_snapshot(
    hass: HomeAssistant, coordinator: DummyCoordinator
) -> None:
    """An expired debounce timer publishes the new snapshot and clears its handle."""
    snapshot = VisonicCoordinatorData(connected=True)
    with (
        patch(
            "homeassistant.components.visonic.coordinator.async_call_later"
        ) as schedule,
        patch.object(
            coordinator, "create_state_snapshot", AsyncMock(return_value=snapshot)
        ) as create,
        patch.object(coordinator, "async_set_updated_data") as publish,
    ):
        coordinator.state_changed_callback(0.5)
        schedule.assert_called_once_with(
            hass,
            0.5,
            coordinator._coordinator_update_timer_callback,
        )
        schedule.call_args.args[2](dt_util.utcnow())
        await hass.async_block_till_done()

    assert coordinator._coordinator_update_timer is None
    create.assert_awaited_once_with()
    publish.assert_called_once_with(snapshot)


async def test_my_update_data_cancels_timer_and_returns_snapshot(
    coordinator: DummyCoordinator,
) -> None:
    """Cancel a pending update timer before creating a snapshot."""
    cancel = MagicMock()
    coordinator._coordinator_update_timer = cancel
    snapshot = VisonicCoordinatorData(connected=True)
    with patch.object(
        coordinator, "create_state_snapshot", AsyncMock(return_value=snapshot)
    ):
        assert await coordinator.my_update_data() is snapshot

    cancel.assert_called_once_with()
    assert coordinator._coordinator_update_timer is None


async def test_my_update_data_wraps_failure(coordinator: DummyCoordinator) -> None:
    """Wrap a snapshot error in Home Assistant's update exception."""
    with (
        patch.object(
            coordinator,
            "create_state_snapshot",
            AsyncMock(side_effect=RuntimeError("snapshot failed")),
        ),
        pytest.raises(UpdateFailed, match="snapshot failed"),
    ):
        await coordinator.my_update_data()


async def test_expired_credentials_request_reauth(
    coordinator: DummyCoordinator,
) -> None:
    """Propagate rejected cloud credentials into Home Assistant reauthentication."""
    with (
        patch.object(
            coordinator,
            "create_state_snapshot",
            side_effect=VisonicAuthException("Credentials rejected"),
        ),
        pytest.raises(ConfigEntryAuthFailed, match="Credentials rejected"),
    ):
        await coordinator.my_update_data()


@pytest.mark.parametrize("disconnection_count", [0, 3])
def test_whole_panel_triggered_state(
    coordinator: DummyCoordinator, disconnection_count: int
) -> None:
    """An active siren overrides the combined armed state."""
    coordinator.data = VisonicCoordinatorData(
        connected=True,
        disconnection_count=disconnection_count,
        panelstate=PanelState(
            "powerlink", "none", 100, False, attributes={"ready": True}
        ),
        siren_active=True,
        armcode=AlarmPanelStatus.ARMED_AWAY,
    )
    state = coordinator.get_panel_state()
    assert state.alarm_state is AlarmControlPanelState.TRIGGERED
    assert state.attributes["ready"] is True
    assert state.attributes[PANEL_ATTRIBUTE_NAME] == str(coordinator.panel_id)
    assert state.attributes[TEXT_DISCONNECTION_COUNT] == disconnection_count
    assert "partition" not in state.attributes


def test_triggered_panel_state(coordinator: DummyCoordinator) -> None:
    """A triggered panel status replaces the previous armed state."""
    coordinator.data = VisonicCoordinatorData(
        connected=True, armcode=AlarmPanelStatus.ARMED_AWAY
    )
    assert coordinator.get_panel_state().alarm_state == (
        AlarmControlPanelState.ARMED_AWAY
    )
    coordinator.data = VisonicCoordinatorData(
        connected=True, armcode=AlarmPanelStatus.TRIGGERED
    )

    assert coordinator.get_panel_state().alarm_state is AlarmControlPanelState.TRIGGERED


def test_panel_state_disconnected(coordinator: DummyCoordinator) -> None:
    """Return an empty state when the panel has no usable snapshot."""
    coordinator.data = None
    assert coordinator.get_panel_state() == PanelStateData()
    coordinator.data = VisonicCoordinatorData(connected=False)
    assert coordinator.get_panel_state() == PanelStateData()


def test_downloading_retains_alarm_state(coordinator: DummyCoordinator) -> None:
    """Keep the previous alarm state while the panel downloads configuration."""
    coordinator._last_my_state = AlarmControlPanelState.ARMED_HOME
    coordinator.data = VisonicCoordinatorData(
        connected=True,
        panelstate=PanelState("cloud", "none", 100, False, attributes={"ready": None}),
        armcode=AlarmPanelStatus.DOWNLOADING,
    )
    state = coordinator.get_panel_state()
    assert state.alarm_state is AlarmControlPanelState.ARMED_HOME
    assert state.attributes["state"] == "downloading"
    assert state.attributes["ready"] == "none"
