"""Test for the Mammotion lawn_mower platform."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
from unittest.mock import ANY, MagicMock, call

from aiohttp import ClientConnectionError
from freezegun.api import FrozenDateTimeFactory
from pymammotion.aliyun.exceptions import (
    DeviceOfflineException,
    DeviceUnboundException,
    FailedRequestException,
    GatewayTimeoutException,
    TooManyRequestsException,
)
from pymammotion.data.model.device import Device, MowingDevice
from pymammotion.device.handle import DeviceStateTimeoutError
from pymammotion.messaging.command_queue import Priority
from pymammotion.state.device_state import DeviceSnapshot
from pymammotion.transport.base import (
    AccountInUseError,
    AuthError,
    EventBus,
    NoTransportAvailableError,
    ReLoginRequiredError,
    TransportError,
    TransportRateLimitedError,
)
from pymammotion.utility.constant.device_constant import WorkMode
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lawn_mower import (
    DOMAIN as LAWN_MOWER_DOMAIN,
    SERVICE_DOCK,
    SERVICE_PAUSE,
    SERVICE_START_MOWING,
    SERVICE_STOP,
    LawnMowerActivity,
)
from homeassistant.components.mammotion.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import ACCOUNT_ID, DEFAULT_NAME, push_state, reporting, setup_integration

ENTITY_ID = "lawn_mower.luba"

COMMAND_ERRORS = [
    pytest.param(ClientConnectionError("reset"), id="client_error"),
    pytest.param(DeviceOfflineException(29003, "iot"), id="device_offline"),
    pytest.param(DeviceUnboundException(29004, "iot"), id="device_unbound"),
    pytest.param(FailedRequestException("iot"), id="failed_request"),
    pytest.param(GatewayTimeoutException(20056, "iot"), id="gateway_timeout"),
    pytest.param(TimeoutError, id="timeout"),
    pytest.param(TooManyRequestsException("429", "iot"), id="too_many_requests"),
    pytest.param(TransportError("send failed"), id="transport_error"),
    pytest.param(NoTransportAvailableError("offline"), id="no_transport"),
    pytest.param(TransportRateLimitedError("quota"), id="rate_limited"),
    pytest.param(AccountInUseError("locked"), id="account_in_use"),
    pytest.param(AuthError("rejected"), id="auth_error"),
    pytest.param(KeyError(DEFAULT_NAME), id="not_registered"),
]


def _command(command: str) -> object:
    """Return the call that sends a user command to the default mower."""
    return call(DEFAULT_NAME, command, priority=Priority.USER)


async def _call_service(hass: HomeAssistant, service: str) -> None:
    """Call a lawn mower service on the mower."""
    await hass.services.async_call(
        LAWN_MOWER_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )


@pytest.mark.usefixtures("mock_mower_api")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_mowing_device: MowingDevice,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    mock_mowing_device.report_data.dev.sys_status = WorkMode.MODE_WORKING
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_device_info(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_mammotion: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the mower's device carries what the library knows about it."""
    mower = MowingDevice()
    mower.device_firmwares.device_version = "1.12.3.45"
    mower.mower_state.model_id = "HM432"
    mower.mower_state.ble_mac = "AA:BB:CC:DD:EE:FF"
    mower.mower_state.wifi_mac = "AA:BB:CC:DD:EE:00"
    mock_mammotion.get_device_by_name.return_value = mower

    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, DEFAULT_NAME), mock_config_entry.entry_id
    )
    assert device == snapshot


@pytest.mark.parametrize(
    ("sys_status", "charge_state", "expected_state"),
    [
        pytest.param(WorkMode.MODE_WORKING, 0, LawnMowerActivity.MOWING, id="mowing"),
        pytest.param(WorkMode.MODE_PAUSE, 0, LawnMowerActivity.PAUSED, id="paused"),
        pytest.param(
            WorkMode.MODE_CHARGING_PAUSE,
            1,
            LawnMowerActivity.PAUSED,
            id="paused-charging",
        ),
        pytest.param(
            WorkMode.MODE_READY, 0, LawnMowerActivity.IDLE, id="ready-undocked"
        ),
        pytest.param(WorkMode.MODE_READY, 1, LawnMowerActivity.DOCKED, id="docked"),
        pytest.param(
            WorkMode.MODE_RETURNING, 0, LawnMowerActivity.RETURNING, id="returning"
        ),
        pytest.param(WorkMode.MODE_LOCK, 0, LawnMowerActivity.ERROR, id="locked"),
        pytest.param(WorkMode.MODE_NOT_ACTIVE, 0, STATE_UNKNOWN, id="not-reported"),
        pytest.param(999, 0, STATE_UNKNOWN, id="unknown-mode"),
    ],
)
@pytest.mark.usefixtures("mock_mower_api")
async def test_activity(
    hass: HomeAssistant,
    mock_mowing_device: MowingDevice,
    mock_config_entry: MockConfigEntry,
    sys_status: int,
    charge_state: int,
    expected_state: str,
) -> None:
    """Test the mower state reflects the reported device status."""
    mock_mowing_device.report_data.dev.sys_status = sys_status
    mock_mowing_device.report_data.dev.charge_state = charge_state

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("service", "sys_status", "charge_state", "expected_commands", "reports"),
    [
        pytest.param(
            SERVICE_START_MOWING, WorkMode.MODE_READY, 1, ["start_job"], 1, id="start"
        ),
        pytest.param(
            SERVICE_START_MOWING,
            WorkMode.MODE_PAUSE,
            0,
            ["resume_execute_task"],
            1,
            id="resume",
        ),
        pytest.param(
            SERVICE_START_MOWING,
            WorkMode.MODE_CHARGING_PAUSE,
            1,
            ["resume_execute_task"],
            1,
            id="resume-charging-paused",
        ),
        pytest.param(
            SERVICE_DOCK,
            WorkMode.MODE_WORKING,
            0,
            ["pause_execute_task", "return_to_dock"],
            1,
            id="dock-while-mowing",
        ),
        pytest.param(
            SERVICE_DOCK,
            WorkMode.MODE_PAUSE,
            0,
            ["return_to_dock"],
            1,
            id="dock-paused",
        ),
        pytest.param(
            SERVICE_DOCK,
            WorkMode.MODE_READY,
            0,
            ["return_to_dock"],
            1,
            id="dock-ready",
        ),
        pytest.param(
            SERVICE_DOCK,
            WorkMode.MODE_RETURNING,
            0,
            [],
            0,
            id="dock-already-returning",
        ),
        pytest.param(
            SERVICE_DOCK, WorkMode.MODE_READY, 1, [], 0, id="dock-when-docked"
        ),
        pytest.param(
            SERVICE_PAUSE,
            WorkMode.MODE_WORKING,
            0,
            ["pause_execute_task"],
            1,
            id="pause",
        ),
        pytest.param(
            SERVICE_PAUSE,
            WorkMode.MODE_RETURNING,
            0,
            ["cancel_return_to_dock"],
            1,
            id="pause-returning",
        ),
        pytest.param(SERVICE_PAUSE, WorkMode.MODE_READY, 0, [], 0, id="pause-idle"),
        pytest.param(SERVICE_STOP, WorkMode.MODE_READY, 0, [], 0, id="stop-idle"),
        pytest.param(SERVICE_STOP, WorkMode.MODE_READY, 1, [], 0, id="stop-docked"),
    ],
)
async def test_services(
    hass: HomeAssistant,
    mock_mammotion: MagicMock,
    mock_mowing_device: MowingDevice,
    mock_config_entry: MockConfigEntry,
    service: str,
    sys_status: int,
    charge_state: int,
    expected_commands: list[str],
    reports: int,
) -> None:
    """Test the lawn mower services send the expected user commands."""
    mock_mowing_device.report_data.dev.sys_status = sys_status
    mock_mowing_device.report_data.dev.charge_state = charge_state

    await setup_integration(hass, mock_config_entry)

    await _call_service(hass, service)

    assert mock_mammotion.send_command_with_args.call_args_list == [
        _command(command) for command in expected_commands
    ]
    assert mock_mammotion.request_report_snapshot.await_count == reports


@pytest.mark.parametrize("error", COMMAND_ERRORS)
async def test_command_not_delivered(
    hass: HomeAssistant,
    mock_mammotion: MagicMock,
    mock_mowing_device: MowingDevice,
    mock_config_entry: MockConfigEntry,
    error: Exception,
) -> None:
    """Test a command that did not reach the mower raises a translated error."""
    mock_mowing_device.report_data.dev.sys_status = WorkMode.MODE_READY
    mock_mammotion.send_command_with_args.side_effect = error

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError) as exc_info:
        await _call_service(hass, SERVICE_START_MOWING)
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "start_failed"
    mock_mammotion.request_report_snapshot.assert_awaited_once_with(DEFAULT_NAME)


@pytest.mark.parametrize(
    ("service", "sys_status", "results", "expected_translation_key"),
    [
        pytest.param(
            SERVICE_START_MOWING,
            WorkMode.MODE_READY,
            [TimeoutError],
            "start_failed",
            id="start",
        ),
        pytest.param(
            SERVICE_START_MOWING,
            WorkMode.MODE_PAUSE,
            [TimeoutError],
            "resume_failed",
            id="resume",
        ),
        pytest.param(
            SERVICE_START_MOWING,
            WorkMode.MODE_CHARGING_PAUSE,
            [TimeoutError],
            "resume_failed",
            id="resume-charging-paused",
        ),
        pytest.param(
            SERVICE_DOCK,
            WorkMode.MODE_WORKING,
            [TimeoutError],
            "pause_failed",
            id="dock-pause-fails",
        ),
        pytest.param(
            SERVICE_DOCK,
            WorkMode.MODE_WORKING,
            [None, TimeoutError],
            "dock_failed",
            id="dock-return-fails",
        ),
        pytest.param(
            SERVICE_DOCK,
            WorkMode.MODE_READY,
            [TimeoutError],
            "dock_failed",
            id="dock-ready",
        ),
        pytest.param(
            SERVICE_PAUSE,
            WorkMode.MODE_WORKING,
            [TimeoutError],
            "pause_failed",
            id="pause",
        ),
        pytest.param(
            SERVICE_PAUSE,
            WorkMode.MODE_RETURNING,
            [TimeoutError],
            "dock_cancel_failed",
            id="pause-returning",
        ),
        pytest.param(
            SERVICE_STOP,
            WorkMode.MODE_WORKING,
            [TimeoutError],
            "pause_failed",
            id="stop-mowing-pause-fails",
        ),
        pytest.param(
            SERVICE_STOP,
            WorkMode.MODE_WORKING,
            [None, TimeoutError],
            "stop_failed",
            id="stop-mowing-cancel-fails",
        ),
        pytest.param(
            SERVICE_STOP,
            WorkMode.MODE_PAUSE,
            [TimeoutError],
            "stop_failed",
            id="stop-paused",
        ),
        pytest.param(
            SERVICE_STOP,
            WorkMode.MODE_CHARGING_PAUSE,
            [TimeoutError],
            "stop_failed",
            id="stop-charging-paused",
        ),
        pytest.param(
            SERVICE_STOP,
            WorkMode.MODE_RETURNING,
            [TimeoutError],
            "dock_cancel_failed",
            id="stop-returning-cancel-return-fails",
        ),
        pytest.param(
            SERVICE_STOP,
            WorkMode.MODE_RETURNING,
            [None, TimeoutError],
            "stop_failed",
            id="stop-returning-cancel-job-fails",
        ),
    ],
)
async def test_services_command_failure(
    hass: HomeAssistant,
    mock_mammotion: MagicMock,
    mock_mowing_device: MowingDevice,
    mock_config_entry: MockConfigEntry,
    service: str,
    sys_status: int,
    results: list[type[Exception] | None],
    expected_translation_key: str,
) -> None:
    """Test each step of an action raises its own translated error."""
    mock_mowing_device.report_data.dev.sys_status = sys_status
    mock_mammotion.send_command_with_args.side_effect = results
    mock_mammotion.wait_for.return_value = reporting(WorkMode.MODE_PAUSE)

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError) as exc_info:
        await _call_service(hass, service)
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == expected_translation_key
    mock_mammotion.request_report_snapshot.assert_awaited_once_with(DEFAULT_NAME)


def _reports(*states: Device) -> Callable[..., Awaitable[Device]]:
    """Return a wait that sees the mower report these states in turn."""

    async def _wait_for(
        device_name: str, predicate: Callable[[Device], bool], *, timeout: float
    ) -> Device:
        return next(state for state in states if predicate(state))

    return _wait_for


@pytest.mark.parametrize(
    ("sys_status", "reported_mode", "expected_commands", "waits"),
    [
        pytest.param(
            WorkMode.MODE_WORKING,
            WorkMode.MODE_PAUSE,
            ["pause_execute_task", "cancel_job"],
            1,
            id="mowing",
        ),
        pytest.param(
            WorkMode.MODE_PAUSE, WorkMode.MODE_PAUSE, ["cancel_job"], 0, id="paused"
        ),
        pytest.param(
            WorkMode.MODE_CHARGING_PAUSE,
            WorkMode.MODE_CHARGING_PAUSE,
            ["cancel_job"],
            0,
            id="charging-paused",
        ),
        pytest.param(
            WorkMode.MODE_RETURNING,
            WorkMode.MODE_PAUSE,
            ["cancel_return_to_dock", "cancel_job"],
            1,
            id="returning-pauses",
        ),
        pytest.param(
            WorkMode.MODE_RETURNING,
            WorkMode.MODE_READY,
            ["cancel_return_to_dock"],
            1,
            id="returning-stops",
        ),
    ],
)
async def test_stop(
    hass: HomeAssistant,
    mock_mammotion: MagicMock,
    mock_mowing_device: MowingDevice,
    mock_config_entry: MockConfigEntry,
    sys_status: int,
    reported_mode: WorkMode,
    expected_commands: list[str],
    waits: int,
) -> None:
    """Test stopping cancels the job once the mower has come to a pause."""
    mock_mowing_device.report_data.dev.sys_status = sys_status
    # Reports that must not end the wait come first.
    mock_mammotion.wait_for.side_effect = _reports(
        Device(),
        reporting(WorkMode.MODE_WORKING),
        reporting(WorkMode.MODE_RETURNING),
        reporting(reported_mode),
    )

    await setup_integration(hass, mock_config_entry)

    await _call_service(hass, SERVICE_STOP)

    assert mock_mammotion.send_command_with_args.call_args_list == [
        _command(command) for command in expected_commands
    ]
    assert (
        mock_mammotion.wait_for.call_args_list
        == [call(DEFAULT_NAME, ANY, timeout=30)] * waits
    )
    mock_mammotion.request_report_snapshot.assert_awaited_once_with(DEFAULT_NAME)


@pytest.mark.parametrize(
    ("sys_status", "wait_error", "expected_translation_key"),
    [
        pytest.param(
            WorkMode.MODE_WORKING,
            DeviceStateTimeoutError(DEFAULT_NAME),
            "pause_failed",
            id="no-pause-reported",
        ),
        pytest.param(
            WorkMode.MODE_WORKING,
            KeyError(DEFAULT_NAME),
            "pause_failed",
            id="device-not-registered",
        ),
        pytest.param(
            WorkMode.MODE_WORKING,
            TransportRateLimitedError("quota"),
            "pause_failed",
            id="rate-limited",
        ),
        pytest.param(
            WorkMode.MODE_WORKING,
            ReLoginRequiredError(ACCOUNT_ID, "refresh token rejected"),
            "pause_failed",
            id="login-rejected",
        ),
        pytest.param(
            WorkMode.MODE_RETURNING,
            DeviceStateTimeoutError(DEFAULT_NAME),
            "dock_cancel_failed",
            id="returning-not-stopped",
        ),
    ],
)
async def test_stop_wait_failure(
    hass: HomeAssistant,
    mock_mammotion: MagicMock,
    mock_mowing_device: MowingDevice,
    mock_config_entry: MockConfigEntry,
    sys_status: int,
    wait_error: Exception,
    expected_translation_key: str,
) -> None:
    """Test stopping raises when the mower never comes to a pause."""
    mock_mowing_device.report_data.dev.sys_status = sys_status
    mock_mammotion.wait_for.side_effect = wait_error

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError) as exc_info:
        await _call_service(hass, SERVICE_STOP)
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == expected_translation_key
    assert _command("cancel_job") not in (
        mock_mammotion.send_command_with_args.call_args_list
    )
    mock_mammotion.request_report_snapshot.assert_awaited_once_with(DEFAULT_NAME)


def _never_reported(
    waiting: asyncio.Event,
) -> Callable[..., Awaitable[Device]]:
    """Return a wait that, as the library does, times out on a mode never reported."""

    async def _wait_for(
        device_name: str, predicate: Callable[[Device], bool], *, timeout: float
    ) -> Device:
        waiting.set()
        try:
            async with asyncio.timeout(timeout):
                await asyncio.Event().wait()
        except TimeoutError:
            raise DeviceStateTimeoutError(device_name, timeout) from None
        raise AssertionError("unreachable")

    return _wait_for


async def test_stop_gives_up_after_30_seconds(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_mammotion: MagicMock,
    mock_mowing_device: MowingDevice,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test stopping waits 30 seconds for the pause before failing."""
    mock_mowing_device.report_data.dev.sys_status = WorkMode.MODE_WORKING
    waiting = asyncio.Event()
    mock_mammotion.wait_for.side_effect = _never_reported(waiting)
    await setup_integration(hass, mock_config_entry)

    # Not async_block_till_done: it would wait for the stop it is timing.
    stop = hass.async_create_background_task(
        _call_service(hass, SERVICE_STOP), "stop mower"
    )
    await waiting.wait()
    freezer.tick(timedelta(seconds=29))
    async_fire_time_changed(hass)
    await asyncio.sleep(0)
    assert not stop.done()

    freezer.tick(timedelta(seconds=1))
    async_fire_time_changed(hass)
    # A few loop turns, not await: with time frozen a missed deadline never fires.
    for _ in range(5):
        await asyncio.sleep(0)
    gave_up_at_30_seconds = stop.done()
    # Ends a wait that missed the deadline, so a failure does not hang teardown.
    async_fire_time_changed(hass, fire_all=True)

    with pytest.raises(HomeAssistantError) as exc_info:
        await stop
    assert gave_up_at_30_seconds
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "pause_failed"


async def test_availability(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_state_bus: EventBus[DeviceSnapshot],
) -> None:
    """Test the entity follows the mower's availability as reports arrive."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE

    mock_mower_api.is_online.return_value = False
    await push_state(mock_state_bus, MowingDevice())
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    mock_mower_api.is_online.return_value = True
    await push_state(mock_state_bus, MowingDevice())
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE
