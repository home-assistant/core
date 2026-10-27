"""Tests for cloud.py."""

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import replace
from datetime import timedelta
from functools import partial
import logging
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pyvisonicalarm.alarm import AlarmSystem
from pyvisonicalarm.classes import Alarm, PanelInfo, Partition, Process, Status
from pyvisonicalarm.core import API
from pyvisonicalarm.devices import PanelDevice
from pyvisonicalarm.exceptions import (
    ConnectionTimeoutError,
    Error,
    InternalServerError,
    InvalidUserCodeError,
    PanelNotConnectedError,
    SessionTokenError,
    UnauthorizedError,
    UndefinedBadRequestError,
    UserAuthRequiredError,
    WrongUsernameOrPasswordError,
)

from homeassistant.components.visonic.cloud import (
    VisonicCloudConnection,
    VisonicCloudSettings,
)
from homeassistant.components.visonic.connection import (
    VisonicConnectionCallbacks,
    VisonicConnectionOptions,
    VisonicPanelMetadata,
)
from homeassistant.components.visonic.const import (
    CONF_CLOUD_APP_ID,
    CONF_ENABLE_REMOTE_ARM,
    CONF_ENABLE_REMOTE_DISARM,
    CONF_PANEL_SERIAL,
    DEFAULT_CLOUD_SCAN_INTERVAL,
    LOGGER,
    TEXT_PANEL_MODEL,
)
from homeassistant.components.visonic.exceptions import (
    VisonicAuthException,
    VisonicException,
)
from homeassistant.components.visonic.visonic_data_types import VisonicConfigEntry
from homeassistant.components.visonic.visonic_types import (
    AlarmCommandStatus,
    AlarmPanelCommand,
    AlarmPanelStatus,
    CommandResult,
    DeviceType,
)
from homeassistant.const import (
    CONF_EMAIL,
    CONF_EXTERNAL_URL,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from .helpers import SetupIntegration

STATUS_DATA = {
    "connected": True,
    "connected_status": {"bba": {"is_connected": True, "state": "online"}},
    "discovery": {
        "completed": True,
        "stages": 10,
        "in_queue": 0,
        "triggered": None,
    },
    "partitions": [
        {
            "id": 1,
            "state": "DISARM",
            "status": "",
            "ready": True,
            "options": [],
        },
        {
            "id": 2,
            "state": "DISARM",
            "status": "",
            "ready": True,
            "options": [],
        },
    ],
    "rssi": {"level": "", "network": ""},
}


@pytest.fixture
async def cloud(hass: HomeAssistant) -> AsyncGenerator[VisonicCloudConnection]:
    """Create a cloud helper with settings and event callbacks only."""
    settings = VisonicCloudSettings(
        hostname="",
        email="",
        password="",
        code="",
        panel_serial="ABCDEF",
        panel_id=1,
        panel_name="Test panel",
        update_interval=30,
    )
    callbacks = VisonicConnectionCallbacks(
        state_changed=MagicMock(),
        panel_ready=MagicMock(),
        panel_metadata_changed=MagicMock(),
        baud_changed=MagicMock(),
        app_id_changed=MagicMock(),
    )
    connection = VisonicCloudConnection(
        settings,
        VisonicConnectionOptions(enable_remote_arm=True, enable_remote_disarm=True),
        callbacks,
        async_get_clientsession(hass),
    )
    connection.cloud_alarm = connected_cloud_alarm()
    connection.login_success = True
    yield connection
    await connection.async_panel_stop()


def connected_cloud_alarm() -> MagicMock:
    """Create a cloud session with coherent connected status responses."""
    alarm = MagicMock(spec=AlarmSystem)
    alarm.get_panel_state.side_effect = partial(AlarmSystem.get_panel_state, alarm)
    alarm._summarize_alarms.side_effect = AlarmSystem._summarize_alarms
    alarm.get_user_code.return_value = "1234"
    alarm.get_status.return_value = Status(STATUS_DATA)
    alarm.get_panel_info.return_value = None
    alarm.get_devices.return_value = []
    alarm.get_alarms.return_value = []
    return alarm


async def test_snapshot_finishes_before_overlapping_reauthentication(
    hass: HomeAssistant, cloud: VisonicCloudConnection
) -> None:
    """A pending valid response finishes on its original session before reconnect."""
    original = connected_cloud_alarm()
    replacement = connected_cloud_alarm()
    cloud.cloud_alarm = original
    started = asyncio.Event()
    response = asyncio.Event()

    async def delayed_status() -> Status:
        started.set()
        await response.wait()
        return Status(STATUS_DATA)

    async def connect() -> bool:
        original.get_panel_info.assert_awaited_once_with()
        cloud.cloud_alarm = replacement
        cloud.login_success = True
        return True

    original.get_status = AsyncMock(side_effect=delayed_status)
    with patch.object(cloud, "_async_panel_connect", side_effect=connect) as login:
        first = hass.async_create_task(cloud.create_state_snapshot())
        await started.wait()
        original.get_status = AsyncMock(side_effect=UnauthorizedError())
        second = hass.async_create_task(cloud.create_state_snapshot())
        assert not second.done()
        login.assert_not_awaited()
        response.set()
        first_snapshot, second_snapshot = await asyncio.gather(first, second)

    assert first_snapshot.connected
    assert second_snapshot.connected
    assert cloud.cloud_alarm is replacement
    original.panel_logout.assert_awaited_once_with()
    login.assert_awaited_once_with()


async def test_overlapping_snapshots_share_reauthenticated_session(
    hass: HomeAssistant, cloud: VisonicCloudConnection
) -> None:
    """A queued refresh uses the replacement session instead of logging in again."""
    original = connected_cloud_alarm()
    original.get_status.side_effect = UnauthorizedError()
    replacement = connected_cloud_alarm()
    cloud.cloud_alarm = original
    started = asyncio.Event()
    response = asyncio.Event()

    async def connect() -> bool:
        started.set()
        await response.wait()
        cloud.cloud_alarm = replacement
        cloud.login_success = True
        return True

    with patch.object(cloud, "_async_panel_connect", side_effect=connect) as login:
        first = hass.async_create_task(cloud.create_state_snapshot())
        await started.wait()
        second = hass.async_create_task(cloud.create_state_snapshot())
        assert not second.done()
        original.get_status.assert_awaited_once_with()
        response.set()
        renewed, queued = await asyncio.gather(first, second)

    assert renewed.connected
    assert queued.connected
    login.assert_awaited_once_with()
    original.panel_logout.assert_awaited_once_with()
    assert replacement.get_status.await_count == 2


async def test_command_confirmation_finishes_before_snapshot(
    hass: HomeAssistant, cloud: VisonicCloudConnection
) -> None:
    """A command retains its session until its process token has been confirmed."""
    alarm = connected_cloud_alarm()
    alarm.arm_away.return_value = "process-token"
    cloud.cloud_alarm = alarm
    started = asyncio.Event()
    confirmed = asyncio.Event()

    async def confirm(token: str) -> AlarmCommandStatus:
        assert token == "process-token"
        started.set()
        await confirmed.wait()
        return AlarmCommandStatus.SUCCESS

    with patch.object(cloud, "wait_for_process_status", side_effect=confirm):
        command = hass.async_create_task(
            cloud.send_command(AlarmPanelCommand.ARM_AWAY, None)
        )
        await started.wait()
        refresh = hass.async_create_task(cloud.create_state_snapshot())
        assert not refresh.done()
        alarm.get_status.assert_not_awaited()
        confirmed.set()
        result, snapshot = await asyncio.gather(command, refresh)

    assert result.status is AlarmCommandStatus.SUCCESS
    assert snapshot.connected
    alarm.arm_away.assert_awaited_once_with()
    alarm.get_status.assert_awaited_once_with()


@pytest.mark.parametrize("method", ["arm_away", "get_process_status"])
@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ConnectionTimeoutError(), id="library-timeout"),
        pytest.param(InternalServerError(), id="server-error"),
        pytest.param(PanelNotConnectedError(), id="offline-panel"),
    ],
)
async def test_command_library_failure(
    cloud: VisonicCloudConnection, method: str, error: Error
) -> None:
    """Convert cloud failures during submission and status polling into action errors."""
    assert cloud.cloud_alarm is not None
    cloud.cloud_alarm.arm_away = AsyncMock(return_value="process-token")
    with (
        patch("homeassistant.components.visonic.cloud.asyncio.sleep"),
        patch.object(cloud.cloud_alarm, method, side_effect=error) as request,
        pytest.raises(HomeAssistantError) as raised,
    ):
        await cloud.send_command(AlarmPanelCommand.ARM_AWAY, "1234")
    assert type(raised.value) is HomeAssistantError
    assert str(raised.value) == "Unable to communicate with Visonic panel 1"
    assert raised.value.__cause__ is error
    request.assert_awaited_once()


@pytest.mark.parametrize("method", ["arm_away", "get_process_status"])
@pytest.mark.parametrize(
    "error",
    [
        pytest.param(WrongUsernameOrPasswordError(), id="rejected-credentials"),
        pytest.param(InvalidUserCodeError(), id="rejected-panel-code"),
    ],
)
async def test_command_authentication_failure(
    cloud: VisonicCloudConnection, method: str, error: Error
) -> None:
    """Keep rejected cloud authentication separate from communication failures."""
    assert cloud.cloud_alarm is not None
    cloud.cloud_alarm.arm_away = AsyncMock(return_value="process-token")
    with (
        patch("homeassistant.components.visonic.cloud.asyncio.sleep"),
        patch.object(cloud.cloud_alarm, method, side_effect=error) as request,
        pytest.raises(VisonicAuthException) as raised,
    ):
        await cloud.send_command(AlarmPanelCommand.ARM_AWAY, "1234")
    assert raised.value.__cause__ is error
    request.assert_awaited_once()


@pytest.mark.parametrize(
    ("command", "method"),
    [
        pytest.param(AlarmPanelCommand.ARM_AWAY, "arm_away", id="arm"),
        pytest.param(AlarmPanelCommand.DISARM, "disarm", id="disarm"),
    ],
)
@pytest.mark.parametrize(
    "error",
    [
        pytest.param(UnauthorizedError(), id="unauthorized"),
        pytest.param(SessionTokenError(), id="session-token"),
        pytest.param(UserAuthRequiredError(), id="user-auth-required"),
    ],
)
async def test_command_renews_session_before_submission(
    cloud: VisonicCloudConnection,
    command: AlarmPanelCommand,
    method: str,
    error: Error,
) -> None:
    """Retry a submission explicitly rejected by the expired session once."""
    original = connected_cloud_alarm()
    replacement = connected_cloud_alarm()
    cloud.cloud_alarm = original
    getattr(original, method).side_effect = error
    getattr(replacement, method).return_value = "process-token"
    replacement.get_process_status.return_value = [Process({"status": "succeeded"})]

    async def connect() -> bool:
        assert cloud._session_lock.locked()
        cloud.cloud_alarm = replacement
        cloud.login_success = True
        return True

    with (
        patch.object(cloud, "_async_panel_connect", side_effect=connect) as login,
        patch("homeassistant.components.visonic.cloud.asyncio.sleep"),
    ):
        result = await cloud.send_command(command, "1234")

    assert result.status is AlarmCommandStatus.SUCCESS
    login.assert_awaited_once_with()
    original.panel_logout.assert_awaited_once_with()
    getattr(original, method).assert_awaited_once_with()
    getattr(replacement, method).assert_awaited_once_with()
    replacement.get_process_status.assert_awaited_once_with("process-token")
    cloud.callbacks.state_changed.assert_called_once_with(5.0)


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(UnauthorizedError(), id="unauthorized"),
        pytest.param(SessionTokenError(), id="session-token"),
        pytest.param(UserAuthRequiredError(), id="user-auth-required"),
    ],
)
async def test_command_renews_confirmation_without_resubmission(
    cloud: VisonicCloudConnection, error: Error
) -> None:
    """Retain an accepted command's token when renewing the status-check session."""
    original = connected_cloud_alarm()
    replacement = connected_cloud_alarm()
    cloud.cloud_alarm = original
    original.arm_away.return_value = "accepted-token"
    original.get_process_status.side_effect = error
    replacement.get_process_status.return_value = [Process({"status": "succeeded"})]

    async def connect() -> bool:
        assert cloud._session_lock.locked()
        cloud.cloud_alarm = replacement
        cloud.login_success = True
        return True

    with (
        patch.object(cloud, "_async_panel_connect", side_effect=connect) as login,
        patch("homeassistant.components.visonic.cloud.asyncio.sleep"),
    ):
        result = await cloud.send_command(AlarmPanelCommand.ARM_AWAY, "1234")

    assert result.status is AlarmCommandStatus.SUCCESS
    login.assert_awaited_once_with()
    original.arm_away.assert_awaited_once_with()
    replacement.arm_away.assert_not_awaited()
    original.get_process_status.assert_awaited_once_with("accepted-token")
    replacement.get_process_status.assert_awaited_once_with("accepted-token")
    cloud.callbacks.state_changed.assert_called_once_with(5.0)


@pytest.mark.parametrize(
    ("method", "replacement_submissions"),
    [
        pytest.param("arm_away", 1, id="submission"),
        pytest.param("get_process_status", 0, id="confirmation"),
    ],
)
@pytest.mark.parametrize(
    "error",
    [
        pytest.param(UnauthorizedError(), id="unauthorized"),
        pytest.param(SessionTokenError(), id="session-token"),
        pytest.param(UserAuthRequiredError(), id="user-auth-required"),
    ],
)
async def test_command_session_renewal_is_bounded(
    cloud: VisonicCloudConnection,
    method: str,
    replacement_submissions: int,
    error: Error,
) -> None:
    """Persistent session errors report a communication failure after one renewal."""
    original = connected_cloud_alarm()
    replacement = connected_cloud_alarm()
    cloud.cloud_alarm = original
    original.arm_away.return_value = "accepted-token"
    getattr(original, method).side_effect = error
    getattr(replacement, method).side_effect = error

    async def connect() -> bool:
        cloud.cloud_alarm = replacement
        cloud.login_success = True
        return True

    with (
        patch.object(cloud, "_async_panel_connect", side_effect=connect) as login,
        patch("homeassistant.components.visonic.cloud.asyncio.sleep"),
        pytest.raises(HomeAssistantError) as raised,
    ):
        await cloud.send_command(AlarmPanelCommand.ARM_AWAY, "1234")

    assert type(raised.value) is HomeAssistantError
    assert raised.value.__cause__ is error
    login.assert_awaited_once_with()
    original.arm_away.assert_awaited_once_with()
    assert replacement.arm_away.await_count == replacement_submissions
    getattr(replacement, method).assert_awaited_once()


async def test_command_shares_renewal_limit_between_submission_and_confirmation(
    cloud: VisonicCloudConnection,
) -> None:
    """Expiry while confirming a retried submission cannot renew or submit again."""
    original = connected_cloud_alarm()
    replacement = connected_cloud_alarm()
    cloud.cloud_alarm = original
    original.arm_away.side_effect = UnauthorizedError()
    replacement.arm_away.return_value = "accepted-token"
    replacement.get_process_status.side_effect = SessionTokenError()

    async def connect() -> bool:
        cloud.cloud_alarm = replacement
        cloud.login_success = True
        return True

    with (
        patch.object(cloud, "_async_panel_connect", side_effect=connect) as login,
        patch("homeassistant.components.visonic.cloud.asyncio.sleep"),
        pytest.raises(HomeAssistantError) as raised,
    ):
        await cloud.send_command(AlarmPanelCommand.ARM_AWAY, "1234")

    assert type(raised.value) is HomeAssistantError
    login.assert_awaited_once_with()
    original.arm_away.assert_awaited_once_with()
    replacement.arm_away.assert_awaited_once_with()
    replacement.get_process_status.assert_awaited_once_with("accepted-token")


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(WrongUsernameOrPasswordError(), id="account-credentials"),
        pytest.param(InvalidUserCodeError(), id="panel-code"),
    ],
)
async def test_command_session_renewal_rejects_credentials(
    cloud: VisonicCloudConnection, error: Error
) -> None:
    """Only rejected credentials during renewal request credential reauthentication."""
    original = connected_cloud_alarm()
    cloud.cloud_alarm = original
    original.arm_away.side_effect = UnauthorizedError()
    with (
        patch.object(cloud, "authenticate", side_effect=error) as authenticate,
        pytest.raises(VisonicAuthException),
    ):
        await cloud.send_command(AlarmPanelCommand.ARM_AWAY, "1234")

    authenticate.assert_awaited_once_with()
    original.arm_away.assert_awaited_once_with()
    assert cloud.cloud_alarm is None
    assert not cloud.login_success


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ConnectionTimeoutError(), id="library-timeout"),
        pytest.param(TimeoutError(), id="timeout"),
        pytest.param(OSError(), id="connection-error"),
    ],
)
async def test_command_session_renewal_communication_failure(
    cloud: VisonicCloudConnection, error: Exception
) -> None:
    """A failed session connection is a communication error, not rejected credentials."""
    original = connected_cloud_alarm()
    cloud.cloud_alarm = original
    original.arm_away.side_effect = UnauthorizedError()
    with (
        patch.object(cloud, "authenticate", side_effect=error) as authenticate,
        pytest.raises(HomeAssistantError) as raised,
    ):
        await cloud.send_command(AlarmPanelCommand.ARM_AWAY, "1234")

    assert type(raised.value) is HomeAssistantError
    assert str(raised.value) == "Unable to communicate with Visonic panel 1"
    authenticate.assert_awaited_once_with()
    original.arm_away.assert_awaited_once_with()


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(TimeoutError(), id="timeout"),
        pytest.param(OSError(), id="connection-error"),
        pytest.param(asyncio.CancelledError(), id="cancellation"),
    ],
)
async def test_command_does_not_retry_ambiguous_submission(
    cloud: VisonicCloudConnection, error: BaseException
) -> None:
    """Do not replay a command whose acceptance is unknown or whose caller cancelled."""
    original = connected_cloud_alarm()
    cloud.cloud_alarm = original
    original.arm_away.side_effect = error
    with (
        patch.object(cloud, "_async_panel_reconnect") as reconnect,
        pytest.raises(type(error)) as raised,
    ):
        await cloud.send_command(AlarmPanelCommand.ARM_AWAY, "1234")

    assert raised.value is error
    original.arm_away.assert_awaited_once_with()
    reconnect.assert_not_awaited()


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ConnectionTimeoutError(), id="library-timeout"),
        pytest.param(TimeoutError(), id="logout-timeout"),
        pytest.param(UndefinedBadRequestError("{'error': 10001}"), id="bad-request"),
    ],
)
async def test_stop_cleans_up_after_logout_failure(
    cloud: VisonicCloudConnection, error: Exception, caplog: pytest.LogCaptureFixture
) -> None:
    """A failed cloud logout must still release the local session state."""
    assert cloud.cloud_alarm is not None
    with patch.object(cloud.cloud_alarm, "panel_logout", side_effect=error) as logout:
        await cloud.async_panel_stop()
    logout.assert_awaited_once_with()
    assert not cloud.login_success
    assert cloud.cloud_alarm is None
    assert "Cloud panel logout failed" in caplog.text
    assert f"({type(error).__name__}): {error}" in caplog.text


@pytest.fixture
def setup_cloud_integration(setup_integration: SetupIntegration) -> SetupIntegration:
    """Return a helper for setting up a cloud integration."""

    async def _setup(
        data: dict | None = None,
        options: dict | None = None,
    ) -> tuple[bool, VisonicConfigEntry]:
        cloud_data = {
            CONF_TYPE: DeviceType.CLOUD,
            CONF_HOST: "192.168.0.10",
            CONF_PORT: 10000,
            CONF_EMAIL: "test1",
            CONF_PASSWORD: "test2",
            CONF_PANEL_SERIAL: "ABCDEF",
        }

        if data is not None:
            cloud_data.update(data)

        return await setup_integration(
            data=cloud_data,
            options=options,
        )

    return _setup


@pytest.fixture
def setup_cloud_integration_full_connection(
    hass: HomeAssistant, setup_integration_with_connection
):
    """Return a helper for setting up a cloud integration."""

    async def _setup(
        data: dict | None = None,
        options: dict | None = None,
    ):
        cloud_data = {
            CONF_TYPE: DeviceType.CLOUD.value,
            CONF_HOST: "192.168.0.10",
            CONF_PORT: 10000,
            CONF_EMAIL: "test1",
            CONF_PASSWORD: "test2",
            CONF_PANEL_SERIAL: "ABCDEF",
        }

        if data is not None:
            cloud_data.update(data)

        return await setup_integration_with_connection(
            data=cloud_data,
            options=options,
        )

    return _setup


def test_process_devices_propagates_invalid_device(
    cloud: VisonicCloudConnection,
) -> None:
    """A failed conversion must not return apparently healthy panel data."""
    with (
        patch(
            "homeassistant.components.visonic.cloud.to_bool",
            side_effect=RuntimeError("malformed panel device"),
        ),
        pytest.raises(RuntimeError, match="malformed panel device"),
    ):
        cloud.process_devices([PanelDevice({})])


@pytest.mark.parametrize(
    (
        "panel_info_partitions",
        "status_partitions",
        "alarm_partitions",
        "expected_armcode",
        "expected_siren",
        "expected_ready",
    ),
    [
        pytest.param(
            [{"id": 1, "active": True}, {"id": 2, "active": True}],
            [
                {"id": 1, "state": "AWAY", "status": "", "ready": True},
                {"id": 2, "state": "DISARM", "status": "", "ready": False},
            ],
            [1],
            AlarmPanelStatus.ARMED_AWAY,
            True,
            False,
            id="multi-partition-update",
        ),
        pytest.param(
            [{"id": 1, "active": True}],
            [{"id": 1, "state": "AWAY", "status": "", "ready": True}],
            [1],
            AlarmPanelStatus.ARMED_AWAY,
            True,
            True,
            id="first-single-partition-update",
        ),
        pytest.param(
            [{"id": 1, "active": False}, {"id": 3, "active": True}],
            [
                {"id": 1, "state": "AWAY", "status": "", "ready": False},
                {"id": 3, "state": "DISARM", "status": "", "ready": True},
            ],
            [1],
            AlarmPanelStatus.DISARMED,
            False,
            True,
            id="inactive-partition-ignored",
        ),
        pytest.param(
            [{"id": 1, "active": True}, {"id": 3, "active": True}],
            [
                {"id": 1, "state": "DISARM", "status": "", "ready": True},
                {"id": 3, "state": "AWAY", "status": "", "ready": True},
            ],
            [3],
            AlarmPanelStatus.ARMED_AWAY,
            True,
            True,
            id="sparse-partition-siren",
        ),
        pytest.param(
            [{"id": 1, "active": True}, {"id": 2, "active": True}],
            [
                {"id": 1, "state": "DISARM", "status": "", "ready": True},
                {"id": 2, "state": "AWAY", "status": "", "ready": True},
            ],
            [1],
            AlarmPanelStatus.ARMED_AWAY,
            False,
            True,
            id="intrusion-in-disarmed-partition",
        ),
        pytest.param(
            [{"id": 1, "active": True}, {"id": 2, "active": True}],
            [
                {"id": 1, "state": "ENTRY_DELAY", "status": "", "ready": True},
                {"id": 2, "state": "AWAY", "status": "", "ready": True},
            ],
            [],
            AlarmPanelStatus.ENTRY_DELAY,
            False,
            True,
            id="entry-delay-first",
        ),
        pytest.param(
            [{"id": 1, "active": True}, {"id": 2, "active": True}],
            [
                {"id": 1, "state": "AWAY", "status": "", "ready": True},
                {"id": 2, "state": "ENTRYDELAY", "status": "", "ready": True},
            ],
            [],
            AlarmPanelStatus.ENTRY_DELAY,
            False,
            True,
            id="entry-delay-last",
        ),
        pytest.param(
            [{"id": 1, "active": True}, {"id": 2, "active": True}],
            [
                {"id": 1, "state": "ENTRY_DELAY", "status": "", "ready": True},
                {"id": 2, "state": "ALARM", "status": "", "ready": True},
            ],
            [],
            AlarmPanelStatus.TRIGGERED,
            False,
            True,
            id="triggered-over-entry-delay",
        ),
    ],
)
async def test_connected_state_snapshot(
    cloud: VisonicCloudConnection,
    panel_info_partitions: list[dict[str, Any]],
    status_partitions: list[dict[str, Any]],
    alarm_partitions: list[int],
    expected_armcode: AlarmPanelStatus,
    expected_siren: bool,
    expected_ready: bool,
) -> None:
    """Build connected snapshots for both panel partition configurations."""
    panel_info = PanelInfo(
        {
            "partitions": panel_info_partitions,
            "features": {"enabling_siren": True, "disabling_siren": False},
        }
    )
    status_data = {
        "connected": True,
        "partitions": status_partitions,
    }
    cloud.cloud_alarm.get_status = AsyncMock(return_value=Status(status_data))
    cloud.cloud_alarm.get_panel_info = AsyncMock(return_value=panel_info)
    cloud.cloud_alarm.get_devices = AsyncMock(
        return_value=[
            PanelDevice({"low_battery": False, "tamper": False, "trouble": "none"})
        ]
    )
    cloud.cloud_alarm.get_alarms = AsyncMock(
        return_value=[
            Alarm(
                {
                    "alarm_type": "ALARM_IN_MEMORY",
                    "partitions": alarm_partitions,
                    "zone": 8,
                    "date_time": dt_util.utcnow(),
                }
            )
        ]
    )

    cloud.disconnection_counter = 3
    snapshot = await cloud.create_state_snapshot()

    assert snapshot.connected is True
    assert snapshot.disconnection_count == 3
    assert snapshot.statusdict == {}
    assert snapshot.ispowermaster is True
    assert snapshot.armcode is expected_armcode
    assert snapshot.siren_active is expected_siren
    assert snapshot.panelstate.attributes["ready"] is expected_ready
    assert "partition" not in snapshot.panelstate.as_dict()
    cloud.callbacks.panel_ready.assert_not_called()


@pytest.mark.parametrize(
    "newer_partition",
    [
        pytest.param(1, id="disarmed-partition"),
        pytest.param(3, id="inactive-partition"),
    ],
)
@pytest.mark.parametrize(
    "alarm_order",
    [
        pytest.param((0, 1), id="oldest-first"),
        pytest.param((1, 0), id="newest-first"),
    ],
)
async def test_snapshot_keeps_alarm_in_another_partition(
    cloud: VisonicCloudConnection,
    newer_partition: int,
    alarm_order: tuple[int, int],
) -> None:
    """An unrelated newer alarm cannot hide an armed partition's alarm."""
    cloud.cloud_alarm.get_status = AsyncMock(
        return_value=Status(
            {
                "connected": True,
                "partitions": [
                    {"id": 1, "state": "DISARM", "status": ""},
                    {"id": 2, "state": "AWAY", "status": ""},
                    {"id": 3, "state": "DISARM", "status": ""},
                ],
            }
        )
    )
    cloud.cloud_alarm.get_panel_info = AsyncMock(
        return_value=PanelInfo(
            {
                "partitions": [
                    {"id": 1, "active": True},
                    {"id": 2, "active": True},
                    {"id": 3, "active": False},
                ]
            }
        )
    )
    cloud.cloud_alarm.get_devices = AsyncMock(return_value=[])
    alarms = [
        Alarm(
            {
                "alarm_type": "ALARM_IN_MEMORY",
                "partitions": [2],
                "datetime": "2026-10-19T10:00:00",
            }
        ),
        Alarm(
            {
                "alarm_type": "ALARM_IN_MEMORY",
                "partitions": [newer_partition],
                "datetime": "2026-10-19T10:01:00",
            }
        ),
    ]
    cloud.cloud_alarm.get_alarms = AsyncMock(
        return_value=[alarms[index] for index in alarm_order]
    )

    snapshot = await cloud.create_state_snapshot()

    assert snapshot.connected
    assert snapshot.armcode is AlarmPanelStatus.ARMED_AWAY
    assert snapshot.siren_active


@pytest.mark.parametrize(
    "alarm_type",
    [
        pytest.param("FIRE", id="fire"),
        pytest.param("PANIC", id="panic"),
        pytest.param("EMERGENCY", id="emergency"),
    ],
)
@pytest.mark.parametrize(
    "alarm_order",
    [pytest.param((0, 1), id="oldest-first"), pytest.param((1, 0), id="newest-first")],
)
@pytest.mark.parametrize(
    "alarm_date",
    [
        pytest.param("2026-10-19T10:00:00", id="dated"),
        pytest.param(None, id="undated"),
    ],
)
@pytest.mark.parametrize(
    ("partition_id", "expected_siren"),
    [
        pytest.param(1, True, id="active-partition"),
        pytest.param(2, False, id="inactive-partition"),
        pytest.param(3, False, id="unrelated-partition"),
    ],
)
async def test_snapshot_aggregates_triggering_alarms(
    cloud: VisonicCloudConnection,
    alarm_type: str,
    alarm_order: tuple[int, int],
    alarm_date: str | None,
    partition_id: int,
    expected_siren: bool,
) -> None:
    """A newer memory record cannot hide a triggering alarm in an active partition."""
    cloud.cloud_alarm = connected_cloud_alarm()
    cloud.cloud_alarm.get_panel_info.return_value = PanelInfo(
        {"partitions": [{"id": 1, "active": True}, {"id": 2, "active": False}]}
    )
    cloud.cloud_alarm.get_status.return_value = Status(
        {
            "connected": True,
            "partitions": [
                {"id": 1, "state": "DISARM", "status": ""},
                {"id": 2, "state": "DISARM", "status": ""},
            ],
        }
    )
    alarms = [
        Alarm(
            {
                "alarm_type": alarm_type,
                "partitions": [partition_id],
                "datetime": alarm_date,
            }
        ),
        Alarm(
            {
                "alarm_type": "ALARM_IN_MEMORY",
                "partitions": [1],
                "datetime": "2026-10-19T10:01:00",
            }
        ),
    ]
    cloud.cloud_alarm.get_alarms.return_value = [alarms[index] for index in alarm_order]

    snapshot = await cloud.create_state_snapshot()

    assert snapshot.connected
    assert snapshot.armcode is AlarmPanelStatus.DISARMED
    assert snapshot.siren_active is expected_siren


async def test_snapshot_reconnects_if_cloud_alarm_absent(
    cloud: VisonicCloudConnection,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Return a disconnected snapshot when reconnect cannot create a session."""
    cloud.cloud_alarm = None
    cloud._async_panel_reconnect = AsyncMock()
    caplog.set_level(logging.INFO, logger=LOGGER.name)

    snapshot = await cloud.create_state_snapshot()

    assert snapshot.connected is False
    assert snapshot.mode == "cloud"
    cloud._async_panel_reconnect.assert_awaited_once_with()
    assert caplog.record_tuples == []


async def test_snapshot_retries_disconnected_session_after_timeout(
    cloud: VisonicCloudConnection,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Reconnect after the cloud session remains disconnected beyond its timeout."""
    now = dt_util.utcnow()
    cloud.never_connected = False
    cloud.last_connected_timestamp = now - timedelta(seconds=100)
    cloud.cloud_alarm.get_status = AsyncMock(return_value=Status({"connected": False}))
    cloud._async_panel_connect = AsyncMock(return_value=True)
    caplog.set_level(logging.INFO, logger=LOGGER.name)
    with patch(
        "homeassistant.components.visonic.cloud.get_utc_time",
        return_value=now,
    ):
        snapshot = await cloud.create_state_snapshot()

    assert snapshot.connected is False
    assert cloud.disconnection_counter == 1
    cloud._async_panel_connect.assert_awaited_once_with()
    assert caplog.record_tuples == []


async def test_snapshot_returns_existing_data_during_disconnect(
    cloud: VisonicCloudConnection,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Cache successful data without reading the coordinator during a disconnect."""
    cloud.settings.panel_name = "previous"
    cloud.cloud_alarm.get_status = AsyncMock(
        side_effect=[Status(STATUS_DATA), Status({"connected": False})]
    )
    cloud.cloud_alarm.get_panel_info = AsyncMock(return_value=None)
    cloud.cloud_alarm.get_devices = AsyncMock(return_value=[])
    cloud.cloud_alarm.get_alarms = AsyncMock(return_value=[])
    previous = await cloud.create_state_snapshot()
    caplog.set_level(logging.INFO, logger=LOGGER.name)

    snapshot = await cloud.create_state_snapshot()

    assert snapshot is not previous
    assert snapshot == previous
    assert snapshot.connected
    assert snapshot.model == "previous"
    assert caplog.record_tuples == []


async def test_snapshot_stays_disconnected_after_reconnect(
    cloud: VisonicCloudConnection,
) -> None:
    """A reconnect attempt cannot revive cached connected data during an outage."""
    now = dt_util.utcnow()
    cloud.cloud_alarm.get_status = AsyncMock(
        side_effect=[
            Status(STATUS_DATA),
            Status({"connected": False}),
            Status({"connected": False}),
            Status(STATUS_DATA),
        ]
    )
    cloud.cloud_alarm.get_panel_info = AsyncMock(return_value=None)
    cloud.cloud_alarm.get_devices = AsyncMock(return_value=[])
    cloud.cloud_alarm.get_alarms = AsyncMock(return_value=[])
    cloud._async_panel_reconnect = AsyncMock()
    with patch(
        "homeassistant.components.visonic.cloud.get_utc_time", return_value=now
    ) as clock:
        assert (await cloud.create_state_snapshot()).connected
        clock.return_value = now + timedelta(seconds=100)
        assert not (await cloud.create_state_snapshot()).connected
        cloud._async_panel_reconnect.assert_awaited_once_with()
        assert not (await cloud.create_state_snapshot()).connected
        assert (await cloud.create_state_snapshot()).connected


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(UnauthorizedError(), id="unauthorized"),
        pytest.param(SessionTokenError(), id="session-token"),
        pytest.param(UserAuthRequiredError(), id="user-auth-required"),
    ],
)
@pytest.mark.parametrize(
    "method", ["get_status", "get_panel_info", "get_devices", "get_alarms"]
)
async def test_snapshot_reauthenticates_after_expired_session(
    cloud: VisonicCloudConnection,
    error: Error,
    method: str,
) -> None:
    """Renew an expired session and read its replacement in the same refresh."""
    original = connected_cloud_alarm()
    getattr(original, method).side_effect = error
    replacement = connected_cloud_alarm()
    cloud.cloud_alarm = original

    async def connect() -> bool:
        cloud.cloud_alarm = replacement
        cloud.login_success = True
        return True

    with patch.object(cloud, "_async_panel_connect", side_effect=connect) as login:
        snapshot = await cloud.create_state_snapshot()

    assert snapshot.connected
    assert cloud.cloud_alarm is replacement
    original.panel_logout.assert_awaited_once_with()
    login.assert_awaited_once_with()
    replacement.get_status.assert_awaited_once_with()


@pytest.mark.parametrize(
    "session_error",
    [
        pytest.param(UnauthorizedError(), id="unauthorized"),
        pytest.param(SessionTokenError(), id="session-token"),
        pytest.param(UserAuthRequiredError(), id="user-auth-required"),
    ],
)
async def test_expired_session_preserves_rejected_credentials(
    cloud: VisonicCloudConnection,
    session_error: Error,
) -> None:
    """Rejected credentials during session renewal remain authentication failures."""
    error = WrongUsernameOrPasswordError()
    cloud.cloud_alarm.get_status = AsyncMock(side_effect=session_error)
    cloud.authenticate = AsyncMock(side_effect=error)

    with pytest.raises(VisonicAuthException) as raised:
        await cloud.create_state_snapshot()

    assert raised.value.__cause__ is error


@pytest.mark.parametrize(
    ("error", "exception_type"),
    [
        pytest.param(SessionTokenError(), UpdateFailed, id="session-expired-again"),
        pytest.param(
            UserAuthRequiredError(), UpdateFailed, id="user-auth-required-again"
        ),
        pytest.param(
            UnauthorizedError(), VisonicAuthException, id="unauthorized-again"
        ),
        pytest.param(
            WrongUsernameOrPasswordError(), VisonicAuthException, id="credentials"
        ),
        pytest.param(OSError("connection lost"), UpdateFailed, id="transport"),
    ],
)
async def test_snapshot_retry_failure_is_bounded(
    cloud: VisonicCloudConnection,
    error: Exception,
    exception_type: type[HomeAssistantError],
) -> None:
    """A failed replacement session does not start another reconnect loop."""
    original = connected_cloud_alarm()
    original.get_status.side_effect = SessionTokenError()
    replacement = connected_cloud_alarm()
    replacement.get_status.side_effect = error
    cloud.cloud_alarm = original

    async def connect() -> bool:
        cloud.cloud_alarm = replacement
        cloud.login_success = True
        return True

    with (
        patch.object(cloud, "_async_panel_connect", side_effect=connect) as login,
        pytest.raises(exception_type) as raised,
    ):
        await cloud.create_state_snapshot()

    assert raised.value.__cause__ is error
    login.assert_awaited_once_with()
    original.get_status.assert_awaited_once_with()
    original.panel_logout.assert_awaited_once_with()
    replacement.get_status.assert_awaited_once_with()


async def test_session_renewal_communication_failure(
    cloud: VisonicCloudConnection,
) -> None:
    """A reconnect failure remains an update error without retrying the read."""
    cloud.cloud_alarm.get_status.side_effect = SessionTokenError()
    error = VisonicException("Cloud connection failed")
    with (
        patch.object(cloud, "_async_panel_reconnect", side_effect=error) as reconnect,
        pytest.raises(UpdateFailed) as raised,
    ):
        await cloud.create_state_snapshot()

    assert raised.value.__cause__ is error
    reconnect.assert_awaited_once_with()
    cloud.cloud_alarm.get_status.assert_awaited_once_with()


async def test_snapshot_wraps_unexpected_cloud_error(
    cloud: VisonicCloudConnection,
) -> None:
    """Wrap unexpected cloud API errors as update failures."""
    cloud.cloud_alarm.get_status = AsyncMock(side_effect=RuntimeError("broken API"))

    with pytest.raises(UpdateFailed, match="broken API"):
        await cloud.create_state_snapshot()


async def test_snapshot_converts_missing_status_to_disconnected(
    cloud: VisonicCloudConnection,
) -> None:
    """Treat an absent status response as a disconnected cloud session."""
    cloud.cloud_alarm.get_status = AsyncMock(return_value=None)

    snapshot = await cloud.create_state_snapshot()

    assert snapshot.connected is False
    assert snapshot.mode == "cloud"


def test_save_connection_entry_updates_missing_app_id(
    cloud: VisonicCloudConnection,
) -> None:
    """Persist the API app ID when it is not yet stored in the entry."""
    cloud.cloud_alarm.api = SimpleNamespace(app_id="app-token")
    cloud.settings.app_id = None

    cloud.save_connection_entry()
    cloud.callbacks.app_id_changed.assert_called_once_with("app-token")


def test_save_connection_entry_keeps_existing_app_id(
    cloud: VisonicCloudConnection,
) -> None:
    """Leave an unchanged API app ID in the config entry alone."""
    cloud.cloud_alarm.api = SimpleNamespace(app_id="app-token")
    cloud.settings.app_id = "app-token"

    cloud.save_connection_entry()
    cloud.callbacks.app_id_changed.assert_not_called()


async def test_extract_model_uses_only_registered_panel(
    cloud: VisonicCloudConnection,
) -> None:
    """Select the only registered panel when no serial is stored."""
    cloud.settings.panel_serial = ""
    cloud.cloud_alarm.api = MagicMock()
    cloud.cloud_alarm.api.get_panels = AsyncMock(
        return_value=[
            {
                "panel_serial": "ABCDEF",
                TEXT_PANEL_MODEL: "PowerMaster",
                "type": "PM",
            },
        ]
    )

    serial = await cloud._extract_model_and_type()
    assert serial == "ABCDEF"
    cloud.callbacks.panel_metadata_changed.assert_called_once_with(
        VisonicPanelMetadata("PowerMaster", "ABCDEF")
    )


async def test_extract_model_ignores_unmatched_panel_serial(
    cloud: VisonicCloudConnection,
) -> None:
    """Retain unknown panel details when no panel serial matches."""
    cloud.cloud_alarm.api = MagicMock()
    cloud.cloud_alarm.api.get_panels = AsyncMock(
        return_value=[{"panel_serial": "111111", TEXT_PANEL_MODEL: "Other"}]
    )

    with pytest.raises(VisonicException, match="not registered"):
        await cloud._extract_model_and_type()


async def test_cloud_metadata_persisted_by_coordinator(
    hass: HomeAssistant,
    setup_cloud_integration: SetupIntegration,
) -> None:
    """Persist panel metadata and app IDs through the coordinator callbacks."""
    _, entry = await setup_cloud_integration()
    connection = cast(VisonicCloudConnection, entry.runtime_data.coordinator.connection)
    connection.cloud_alarm = MagicMock()
    connection.cloud_alarm.api.app_id = "app-token"
    connection.cloud_alarm.api.get_panels = AsyncMock(
        return_value=[{"panel_serial": "ABCDEF", TEXT_PANEL_MODEL: "PowerMaster"}]
    )

    with patch.object(
        entry.runtime_data.coordinator, "async_request_refresh"
    ) as refresh:
        assert await connection._extract_model_and_type() == "ABCDEF"
        connection.save_connection_entry()
        await hass.async_block_till_done()
    refresh.assert_not_awaited()

    assert entry.data[TEXT_PANEL_MODEL] == "PowerMaster"
    assert entry.data[CONF_PANEL_SERIAL] == "ABCDEF"
    assert entry.data[CONF_CLOUD_APP_ID] == "app-token"
    assert entry.title == "Panel 1 (Identifier ABCDEF, PowerMaster)"
    assert entry.runtime_data.coordinator.name == f"Visonic {entry.title}"
    assert connection.settings.panel_name == entry.title


async def test_cloud_options_update_connection_settings(
    hass: HomeAssistant,
    setup_cloud_integration: SetupIntegration,
) -> None:
    """Apply changed remote-control policy through the coordinator listener."""
    _, entry = await setup_cloud_integration(options={CONF_ENABLE_REMOTE_ARM: True})
    coordinator = entry.runtime_data.coordinator
    assert coordinator.connection.options.enable_remote_arm

    with patch.object(coordinator, "async_request_refresh") as refresh:
        hass.config_entries.async_update_entry(
            entry, options=dict(entry.options) | {CONF_ENABLE_REMOTE_ARM: False}
        )
        await hass.async_block_till_done()

    assert not coordinator.connection.options.enable_remote_arm
    refresh.assert_awaited_once_with()


async def test_async_panel_connect_authentication_fails(
    cloud: VisonicCloudConnection,
) -> None:
    """Return false when cloud authentication does not produce an API."""
    cloud.authenticate = AsyncMock(return_value=None)

    with pytest.raises(VisonicAuthException):
        await cloud.async_panel_connect()


@pytest.mark.parametrize(
    "command",
    [
        pytest.param(AlarmPanelCommand.DISARM, id="disarm"),
        pytest.param(AlarmPanelCommand.ARM_AWAY, id="away"),
        pytest.param(AlarmPanelCommand.ARM_HOME, id="home"),
        pytest.param(AlarmPanelCommand.ARM_AWAY_INSTANT, id="away-instant"),
        pytest.param(AlarmPanelCommand.ARM_HOME_INSTANT, id="home-instant"),
    ],
)
async def test_command_denied_by_remote_options(
    cloud: VisonicCloudConnection, command: AlarmPanelCommand
) -> None:
    """Reject each cloud arm/disarm command when remote control is disabled."""
    cloud.update_options(
        replace(cloud.options, enable_remote_arm=False, enable_remote_disarm=False)
    )

    result = await cloud.send_command(command, "1234")

    assert result.status is AlarmCommandStatus.FAIL_USER_CONFIG_PREVENTED


async def test_command_without_cloud_session(
    cloud: VisonicCloudConnection,
) -> None:
    """Return the default failure when a command has no cloud session."""
    cloud.cloud_alarm = None
    cloud.get_panel_pin_code = MagicMock(return_value=(True, "1234"))

    result = await cloud.send_command(AlarmPanelCommand.ARM_AWAY, "1234")

    assert result.status is AlarmCommandStatus.FAIL_INVALID_RETURN


async def test_command_without_process_token(
    cloud: VisonicCloudConnection,
) -> None:
    """Keep the invalid-return result when the API gives no process token."""
    cloud.cloud_alarm.arm_away = AsyncMock(return_value=None)

    result = await cloud.send_command(AlarmPanelCommand.ARM_AWAY, "1234")

    assert result.status is AlarmCommandStatus.FAIL_INVALID_RETURN


@pytest.mark.asyncio
async def test_coordinator_initialisation(
    setup_cloud_integration: SetupIntegration,
) -> None:
    """Test cloud coordinator initialisation."""
    result, entry = await setup_cloud_integration()
    assert result
    coordinator: VisonicCloudConnection = entry.runtime_data.coordinator.connection

    assert coordinator.login_success is False
    assert coordinator.cloud_alarm is None
    assert coordinator.never_connected is True
    assert coordinator.disconnection_counter == 0
    assert entry.runtime_data.coordinator.update_interval == timedelta(
        seconds=DEFAULT_CLOUD_SCAN_INTERVAL
    )


@pytest.mark.parametrize(
    ("status", "state", "expected"),
    [
        pytest.param("EXIT", "AWAY", AlarmPanelStatus.ARMING_AWAY, id="arming-away"),
        pytest.param("EXIT", "HOME", AlarmPanelStatus.ARMING_HOME, id="arming-home"),
        pytest.param("", "DISARM", AlarmPanelStatus.DISARMED, id="disarmed"),
        pytest.param("", "UNKNOWN", AlarmPanelStatus.UNKNOWN, id="unknown"),
        pytest.param("EXIT", None, AlarmPanelStatus.UNKNOWN, id="missing-exit-state"),
        pytest.param("", None, AlarmPanelStatus.UNKNOWN, id="missing-state"),
        pytest.param(None, "AWAY", AlarmPanelStatus.UNKNOWN, id="missing-status"),
    ],
)
async def test_determine_armcode(
    setup_cloud_integration: SetupIntegration,
    status: str | None,
    state: str | None,
    expected: AlarmPanelStatus,
) -> None:
    """Test conversion of cloud partition state to HA alarm state."""
    ok, entry = await setup_cloud_integration()
    assert ok
    coordinator: VisonicCloudConnection = entry.runtime_data.coordinator.connection

    partition = Partition({"status": status, "state": state})
    assert coordinator._determine_armcode(partition) is expected


@pytest.mark.asyncio
async def test_get_panel_pin_code_without_cloud_alarm(
    setup_cloud_integration: SetupIntegration,
) -> None:
    """Test PIN validation without a cloud connection."""
    ok, entry = await setup_cloud_integration()
    assert ok
    coordinator: VisonicCloudConnection = entry.runtime_data.coordinator.connection

    assert coordinator.get_panel_pin_code(None) == (False, None)
    assert coordinator.get_panel_pin_code("1234") == (False, None)


@pytest.mark.asyncio
async def test_get_panel_pin_code_valid_and_invalid(
    setup_cloud_integration: SetupIntegration,
) -> None:
    """Test PIN validation."""
    ok, entry = await setup_cloud_integration()
    assert ok
    coordinator: VisonicCloudConnection = entry.runtime_data.coordinator.connection

    alarm = MagicMock()
    alarm.get_user_code.return_value = "1234"
    coordinator.cloud_alarm = alarm

    assert coordinator.get_panel_pin_code(None) == (True, "1234")
    assert coordinator.get_panel_pin_code("") == (True, "1234")
    assert coordinator.get_panel_pin_code("1234") == (True, "1234")
    assert coordinator.get_panel_pin_code("9999") == (False, None)

    alarm.get_user_code.assert_called()


@pytest.mark.asyncio
async def test_wait_for_process_status_no_cloud_alarm(
    setup_cloud_integration: SetupIntegration,
) -> None:
    """Test process status without a cloud connection."""
    ok, entry = await setup_cloud_integration()
    assert ok
    coordinator: VisonicCloudConnection = entry.runtime_data.coordinator.connection
    assert (
        await coordinator.wait_for_process_status("abc")
        == AlarmCommandStatus.FAIL_PANEL_NO_CONNECTION
    )
    coordinator.cloud_alarm = MagicMock()
    assert (
        await coordinator.wait_for_process_status(None)
        == AlarmCommandStatus.FAIL_INVALID_PROCESS_TOKEN
    )


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("succeeded", AlarmCommandStatus.SUCCESS),
        ("handled", AlarmCommandStatus.SUCCESS),
        ("failed", AlarmCommandStatus.FAIL_INVALID_STATE),
        ("error", AlarmCommandStatus.FAIL_INVALID_STATE),
    ],
)
@pytest.mark.asyncio
async def test_wait_for_process_status_result(
    setup_cloud_integration: SetupIntegration,
    status: str,
    expected: AlarmCommandStatus,
) -> None:
    """Test process status result handling."""
    ok, entry = await setup_cloud_integration()
    assert ok
    coordinator: VisonicCloudConnection = entry.runtime_data.coordinator.connection

    process = SimpleNamespace(
        status=status,
        message="message",
        error=None,
    )

    alarm = MagicMock()
    alarm.get_process_status = AsyncMock(return_value=[process])
    coordinator.cloud_alarm = alarm

    with patch(
        "homeassistant.components.visonic.cloud.asyncio.sleep",
        new=AsyncMock(),
    ):
        assert (
            await coordinator.wait_for_process_status("token", attempts=1) == expected
        )

    alarm.get_process_status.assert_awaited_once_with("token")


@pytest.mark.asyncio
async def test_wait_for_process_status_unknown_result(
    setup_cloud_integration: SetupIntegration,
) -> None:
    """Test unknown process result."""
    ok, entry = await setup_cloud_integration()
    assert ok
    coordinator: VisonicCloudConnection = entry.runtime_data.coordinator.connection

    process = SimpleNamespace(
        status="pending",
        message="waiting",
        error=None,
    )

    alarm = MagicMock()
    alarm.get_process_status = AsyncMock(return_value=[process])
    coordinator.cloud_alarm = alarm

    with patch(
        "homeassistant.components.visonic.cloud.asyncio.sleep",
        new=AsyncMock(),
    ):
        result = await coordinator.wait_for_process_status("token", attempts=1)

    assert result == AlarmCommandStatus.FAIL_INVALID_RETURN


@pytest.mark.parametrize(
    "code",
    [
        pytest.param("9999", id="wrong-code"),
        pytest.param("bad", id="not-digits"),
        pytest.param("1234\n", id="trailing-newline"),
        pytest.param("1234 ", id="trailing-space"),
    ],
)
async def test_send_command_invalid_code(
    cloud: VisonicCloudConnection, code: str
) -> None:
    """Invalid PIN prevents a command."""
    result = await cloud.send_command(command=AlarmPanelCommand.ARM_AWAY, code=code)

    assert result.status is AlarmCommandStatus.FAIL_INVALID_CODE
    cloud.cloud_alarm.arm_away.assert_not_awaited()


@pytest.mark.asyncio
async def test_save_connection_entry(setup_cloud_integration: SetupIntegration) -> None:
    """Invalid PIN prevents a command."""
    ok, entry = await setup_cloud_integration()
    assert ok
    coordinator: VisonicCloudConnection = entry.runtime_data.coordinator.connection
    coordinator.cloud_alarm = MagicMock()
    coordinator.cloud_alarm.api = MagicMock()
    coordinator.cloud_alarm.api.app_id = 0x11111

    coordinator.save_connection_entry()
    assert entry.data[CONF_CLOUD_APP_ID] == 0x11111


@pytest.mark.asyncio
async def test_send_command_arm_away_success(
    setup_cloud_integration: SetupIntegration,
) -> None:
    """Test a successful remote arm command."""
    options = {
        CONF_ENABLE_REMOTE_ARM: True,
        CONF_ENABLE_REMOTE_DISARM: False,
    }
    ok, entry = await setup_cloud_integration(options=options)
    assert ok
    coordinator: VisonicCloudConnection = entry.runtime_data.coordinator.connection

    coordinator.get_panel_pin_code = MagicMock(return_value=(True, "1234"))
    coordinator.cloud_alarm = MagicMock()
    coordinator.cloud_alarm.arm_away = AsyncMock(return_value="token")
    coordinator.wait_for_process_status = AsyncMock(
        return_value=AlarmCommandStatus.SUCCESS
    )
    coordinator.callbacks.state_changed = MagicMock()

    result = await coordinator.send_command(
        command=AlarmPanelCommand.ARM_AWAY, code="1234"
    )

    assert result.status == AlarmCommandStatus.SUCCESS
    coordinator.cloud_alarm.arm_away.assert_awaited_once_with()
    coordinator.wait_for_process_status.assert_awaited_once_with("token")
    coordinator.callbacks.state_changed.assert_called_once_with(5.0)


@pytest.mark.asyncio
async def test_send_command_disarm_success(
    setup_cloud_integration: SetupIntegration,
) -> None:
    """Test a successful remote disarm command."""
    options = {
        CONF_ENABLE_REMOTE_ARM: False,
        CONF_ENABLE_REMOTE_DISARM: True,
    }
    ok, entry = await setup_cloud_integration(options=options)
    assert ok
    coordinator: VisonicCloudConnection = entry.runtime_data.coordinator.connection

    coordinator.get_panel_pin_code = MagicMock(return_value=(True, "1234"))
    coordinator.cloud_alarm = MagicMock()
    coordinator.cloud_alarm.disarm = AsyncMock(return_value="token")
    coordinator.wait_for_process_status = AsyncMock(
        return_value=AlarmCommandStatus.SUCCESS
    )
    coordinator.callbacks.state_changed = MagicMock()

    result = await coordinator.send_command(
        command=AlarmPanelCommand.DISARM, code="1234"
    )

    assert result.status == AlarmCommandStatus.SUCCESS
    coordinator.cloud_alarm.disarm.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_send_command_remote_arm_disabled(
    setup_cloud_integration: SetupIntegration,
) -> None:
    """Remote arm disabled returns the appropriate failure."""
    options = {
        CONF_ENABLE_REMOTE_ARM: False,
        CONF_ENABLE_REMOTE_DISARM: True,
    }
    ok, entry = await setup_cloud_integration(options=options)
    assert ok
    coordinator: VisonicCloudConnection = entry.runtime_data.coordinator.connection

    coordinator.get_panel_pin_code = MagicMock(return_value=(True, "1234"))
    coordinator.cloud_alarm = MagicMock()
    coordinator.callbacks.state_changed = MagicMock()

    result = await coordinator.send_command(
        command=AlarmPanelCommand.ARM_AWAY, code="1234"
    )

    assert result.status == AlarmCommandStatus.FAIL_USER_CONFIG_PREVENTED
    coordinator.callbacks.state_changed.assert_called_once_with(5.0)


@pytest.mark.parametrize(
    ("method", "command"),
    [
        pytest.param("disarm", AlarmPanelCommand.DISARM, id="disarm"),
        pytest.param("arm_home", AlarmPanelCommand.ARM_HOME, id="home"),
        pytest.param("arm_away", AlarmPanelCommand.ARM_AWAY, id="away"),
        pytest.param(
            "arm_home_instant", AlarmPanelCommand.ARM_HOME_INSTANT, id="home-instant"
        ),
        pytest.param(
            "arm_away_instant", AlarmPanelCommand.ARM_AWAY_INSTANT, id="away-instant"
        ),
    ],
)
async def test_send_commands_success(
    setup_cloud_integration: SetupIntegration,
    method: str,
    command: AlarmPanelCommand,
) -> None:
    """Send each supported command to the whole panel."""
    options = {
        CONF_ENABLE_REMOTE_ARM: True,
        CONF_ENABLE_REMOTE_DISARM: True,
    }
    ok, entry = await setup_cloud_integration(options=options)
    assert ok
    coordinator: VisonicCloudConnection = entry.runtime_data.coordinator.connection

    coordinator.get_panel_pin_code = MagicMock(return_value=(True, "1234"))

    coordinator.cloud_alarm = MagicMock()
    panel_command = AsyncMock(return_value="token")
    setattr(coordinator.cloud_alarm, method, panel_command)

    coordinator.wait_for_process_status = AsyncMock(
        return_value=AlarmCommandStatus.SUCCESS
    )
    coordinator.callbacks.state_changed = MagicMock()

    result: CommandResult = await coordinator.send_command(command=command, code="1234")

    assert result.status == AlarmCommandStatus.SUCCESS
    panel_command.assert_awaited_once_with()
    coordinator.wait_for_process_status.assert_awaited_once_with("token")


@pytest.mark.asyncio
async def test_authenticate(setup_cloud_integration: SetupIntegration) -> None:
    """Test API authentication."""

    data = {
        CONF_EXTERNAL_URL: "https://example.com",
        CONF_EMAIL: "user@example.com",
        CONF_PASSWORD: "password",
        CONF_CLOUD_APP_ID: "appid",
    }

    ok, entry = await setup_cloud_integration(data=data)
    assert ok
    coordinator: VisonicCloudConnection = entry.runtime_data.coordinator.connection

    api = MagicMock()
    api.set_rest_version = AsyncMock()
    api.authenticate_user = AsyncMock(return_value=True)

    with patch(
        "homeassistant.components.visonic.cloud.API",
        return_value=api,
    ) as api_class:
        result = await coordinator.authenticate()

    assert result is api
    api_class.assert_called_once()
    api.set_rest_version.assert_awaited_once()
    api.authenticate_user.assert_awaited_once_with(
        "user@example.com",
        "password",
    )


@pytest.mark.asyncio
async def test_async_panel_connect_success(
    hass: HomeAssistant, setup_cloud_integration_full_connection: SetupIntegration
) -> None:
    """Test successful cloud connection."""
    api = MagicMock(spec=API)
    alarm: AlarmSystem = MagicMock(spec=AlarmSystem)
    alarm.panel_login = AsyncMock(return_value=True)

    ok, entry = await setup_cloud_integration_full_connection()
    assert ok
    coordinator: VisonicCloudConnection = entry.runtime_data.coordinator.connection

    assert not isinstance(coordinator.async_panel_connect, AsyncMock)

    coordinator.authenticate = AsyncMock(return_value=api)
    coordinator._extract_model_and_type = AsyncMock(return_value="123456")
    coordinator.save_connection_entry = MagicMock()

    with patch(
        "homeassistant.components.visonic.cloud.AlarmSystem",
        return_value=alarm,
    ) as mock_alarm_system:
        result = await coordinator.async_panel_connect()

    assert result is True
    mock_alarm_system.assert_called_once_with(api)
    assert coordinator.cloud_alarm is alarm
    assert coordinator.login_success is True
    coordinator._extract_model_and_type.assert_awaited_once()
    alarm.panel_login.assert_awaited_once()
    coordinator.save_connection_entry.assert_called_once()


@pytest.mark.asyncio
async def test_async_panel_connect_auth_exception(
    setup_cloud_integration_full_connection: SetupIntegration,
) -> None:
    """Test authentication exception."""
    ok, entry = await setup_cloud_integration_full_connection()
    assert ok
    coordinator: VisonicCloudConnection = entry.runtime_data.coordinator.connection

    assert not isinstance(coordinator.async_panel_connect, AsyncMock)

    coordinator.authenticate = AsyncMock(
        side_effect=WrongUsernameOrPasswordError("bad credentials")
    )

    with (
        patch(
            "homeassistant.components.visonic.cloud.AlarmSystem",
        ),
        pytest.raises(VisonicAuthException),
    ):
        await coordinator.async_panel_connect()


@pytest.mark.asyncio
async def test_async_panel_connect_generic_exception(
    setup_cloud_integration_full_connection: SetupIntegration,
) -> None:
    """Test generic connection failure."""
    alarm: AlarmSystem = MagicMock(spec=AlarmSystem)
    alarm.panel_login = AsyncMock(return_value=True)

    ok, entry = await setup_cloud_integration_full_connection()
    assert ok
    coordinator: VisonicCloudConnection = entry.runtime_data.coordinator.connection

    assert not isinstance(coordinator.async_panel_connect, AsyncMock)

    coordinator.authenticate = AsyncMock(side_effect=RuntimeError("connection failed"))

    with (
        patch(
            "homeassistant.components.visonic.cloud.AlarmSystem",
            return_value=alarm,
        ),
        pytest.raises(VisonicException),
    ):
        await coordinator.async_panel_connect()


@pytest.mark.parametrize(
    "alarms",
    [
        pytest.param(
            [
                Alarm({"partitions": [1]}),
                Alarm(
                    {
                        "partitions": [1],
                        "datetime": "2026-09-21T10:00:00",
                        "alarm_type": "FIRE",
                    }
                ),
            ],
            id="undated-first",
        ),
        pytest.param(
            [
                Alarm(
                    {
                        "partitions": [1],
                        "datetime": "2026-09-21T10:00:00",
                        "alarm_type": "FIRE",
                    }
                ),
                Alarm({"partitions": [1]}),
            ],
            id="dated-first",
        ),
    ],
)
async def test_dated_fire_alarm_survives_undated_record(
    cloud: VisonicCloudConnection, alarms: list[Alarm]
) -> None:
    """An undated record cannot hide a fire alarm on a disarmed partition."""
    cloud.cloud_alarm = connected_cloud_alarm()
    cloud.cloud_alarm.get_panel_info.return_value = PanelInfo(
        {"partitions": [{"id": 1, "active": True}, {"id": 2, "active": True}]}
    )
    cloud.cloud_alarm.get_alarms.return_value = alarms

    snapshot = await cloud.create_state_snapshot()

    assert snapshot.connected
    assert snapshot.armcode is AlarmPanelStatus.DISARMED
    assert snapshot.siren_active
