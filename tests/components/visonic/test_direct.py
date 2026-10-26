"""Test coordinator functionality."""

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import replace
import logging
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from pyvisonic import (
    AlAlarmType,
    AlCommandStatus,
    AlCondition,
    AlPanelCommand,
    AlPanelStatus,
    AlTerminationType,
)
from pyvisonic.py_enum import AlPanelMode

from homeassistant.components.visonic.const import (
    CONF_ARM_CODE_AUTO,
    CONF_DEVICE_BAUD,
    CONF_ENABLE_REMOTE_ARM,
    CONF_ENABLE_REMOTE_DISARM,
    CONF_PANEL_SERIAL,
    CONF_RETRY_CONNECTION_COUNT,
    CONF_RETRY_CONNECTION_DELAY,
    DOMAIN,
    TEXT_PANEL_MODEL,
)
from homeassistant.components.visonic.coordinator import VisonicCoordinator
from homeassistant.components.visonic.direct import VisonicDirectConnection
from homeassistant.components.visonic.exceptions import VisonicException
from homeassistant.components.visonic.visonic_data_types import VisonicCoordinatorData
from homeassistant.components.visonic.visonic_types import (
    AlarmCommandStatus,
    AlarmPanelCommand,
    AlarmPanelStatus,
    CommandResult,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.translation import async_get_translations

from .helpers import SetupIntegration, create_config_entry_example

ENTITY_ID = "alarm_control_panel.visonic_alarm_p1"
MODULE = "homeassistant.components.visonic.direct"


@pytest.fixture
async def direct_parent(hass: HomeAssistant) -> AsyncGenerator[VisonicCoordinator]:
    """Create a real coordinator with a mocked client and platform side effects."""
    entry = create_config_entry_example(
        options={
            CONF_ENABLE_REMOTE_ARM: True,
            CONF_ENABLE_REMOTE_DISARM: True,
        }
    )
    with patch(f"{MODULE}.VisonicClient", autospec=True) as factory:
        parent = VisonicCoordinator(hass, entry, 1)
        coordinator = cast(VisonicDirectConnection, parent.connection)
    settings, callbacks = factory.call_args.args
    assert settings.host == entry.data["host"]
    assert settings.port == int(entry.data["port"])
    assert settings.panel_id == 1
    assert settings.user_code_slot == 0
    assert callbacks.state_change == coordinator._handle_state_change
    assert callbacks.panel_change == coordinator._handle_panel_change
    assert callbacks.baud_change == parent._handle_baud_change
    coordinator._client.settings = settings
    coordinator._client.is_power_master.return_value = False
    coordinator._client.achieved_powerlink.return_value = False
    coordinator._client.panel_mode = AlPanelMode.STANDARD
    parent.set_alarm_device_information = MagicMock()
    parent.create_alarm_panel = MagicMock()
    yield parent
    await parent.async_shutdown()


@pytest.fixture
def direct(direct_parent: VisonicCoordinator) -> VisonicDirectConnection:
    """Return the direct helper without giving it a coordinator reference."""
    return cast(VisonicDirectConnection, direct_parent.connection)


async def test_async_panel_connect_lifecycle(
    direct_parent: VisonicCoordinator,
    direct: VisonicDirectConnection,
) -> None:
    """Connect the client before refreshing state and creating the alarm."""
    direct_parent.async_config_entry_first_refresh = AsyncMock()
    direct_parent.data = VisonicCoordinatorData(connected=True)
    direct._client.connect.return_value = True

    assert await direct_parent.async_panel_connect() is True

    direct_parent.async_config_entry_first_refresh.assert_awaited_once_with()
    direct_parent.set_alarm_device_information.assert_called_once_with()
    direct_parent.create_alarm_panel.assert_called_once_with()


def test_client_startup_announces_panel(direct: VisonicDirectConnection) -> None:
    """A completed client startup notifies the coordinator to create its alarm."""
    with patch.object(direct.callbacks, "panel_ready") as ready:
        direct._handle_panel_change(AlCondition.STARTUP_SUCCESS, None)
    ready.assert_called_once_with()


@pytest_asyncio.fixture
async def coordinator_parent(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> AsyncGenerator[VisonicCoordinator]:
    """Return a VisonicCoordinator with mocked client."""
    result, entry = await setup_integration()
    assert result
    with patch(f"{MODULE}.VisonicClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.create_state_snapshot.return_value = VisonicCoordinatorData(
            connected=True
        )
        mock_client_cls.return_value = mock_client

        parent = VisonicCoordinator(hass, entry, 1)
        yield parent
        await parent.async_shutdown()


@pytest.fixture
def coordinator(coordinator_parent: VisonicCoordinator) -> VisonicDirectConnection:
    """Return the mocked direct helper."""
    return cast(VisonicDirectConnection, coordinator_parent.connection)


@pytest.mark.asyncio
async def test_ive_been_created(
    coordinator_parent: VisonicCoordinator, coordinator: VisonicDirectConnection
) -> None:
    """Test manual update using create_state_snapshot."""
    # Patch the client snapshot
    coordinator.create_state_snapshot = AsyncMock(
        return_value=VisonicCoordinatorData(connected=True, statusdict={"foo": "bar"})
    )
    # Call ive_been_created and verify data is updated
    coordinator_parent.ive_been_created()
    await asyncio.sleep(1.0)
    assert isinstance(coordinator_parent.data, VisonicCoordinatorData)
    vdc: VisonicCoordinatorData = coordinator_parent.data
    assert vdc.statusdict == {"foo": "bar"}


@pytest.mark.asyncio
async def test_async_set_updated_data_does_not_update_if_same(
    coordinator_parent: VisonicCoordinator,
) -> None:
    """If data hasn't changed, async_set_updated_data does not call parent."""
    data = {"key": "value"}
    coordinator_parent.data = data
    with patch.object(
        coordinator_parent,
        "async_set_updated_data",
        wraps=coordinator_parent.async_set_updated_data,
    ) as mock_update:
        coordinator_parent.async_set_updated_data(data)
        # Should return early, no recursive call
        mock_update.assert_called_once()  # only initial call


@pytest.mark.asyncio
async def test_async_panel_connect_single_attempt(
    coordinator: VisonicDirectConnection,
) -> None:
    """Test async_panel_connect with 0 retry attempts."""
    coordinator._client.connect = AsyncMock(return_value=True)
    result = await coordinator.async_panel_connect()
    assert result is True


@pytest.mark.asyncio
async def test_send_command_preserves_failure_status(
    coordinator_parent: VisonicCoordinator,
    coordinator: VisonicDirectConnection,
) -> None:
    """Return the client's failure status for an allowed panel command."""
    mock_result = CommandResult(
        AlarmCommandStatus.FAIL_INVALID_STATE,
    )
    coordinator_parent.hass.config_entries.async_update_entry(
        coordinator_parent.config_entry,
        options={
            CONF_ENABLE_REMOTE_DISARM: True,
            CONF_ENABLE_REMOTE_ARM: True,
        },
    )
    coordinator._client.send_command = AsyncMock(
        return_value=AlCommandStatus(mock_result.status)
    )
    result: CommandResult = await coordinator.send_command(
        AlarmPanelCommand.ARM_AWAY, "1234"
    )
    assert result.status == AlarmCommandStatus.FAIL_INVALID_STATE


@pytest.mark.asyncio
async def test_get_panel_state_disconnected_returns_unknown(
    coordinator_parent: VisonicCoordinator,
) -> None:
    """The whole-panel state is unknown before panel data is available."""
    coordinator_parent.data = None
    result = coordinator_parent.get_panel_state()
    assert result.alarm_state is None  # None until it's obtained from the panel


async def test_ive_been_created_failure(
    coordinator_parent: VisonicCoordinator,
) -> None:
    """Wrap failures while scheduling the initial state update."""
    coordinator_parent.state_changed_callback = MagicMock(
        side_effect=RuntimeError("failed")
    )

    with pytest.raises(VisonicException, match="Client not created properly"):
        coordinator_parent.ive_been_created()


async def test_async_panel_stop(
    coordinator_parent: VisonicCoordinator, coordinator: VisonicDirectConnection
) -> None:
    """Publish a stopped snapshot and stop the panel client."""
    coordinator._client = MagicMock()
    coordinator._client.is_panel_connected.return_value = False
    coordinator_parent.async_set_updated_data = MagicMock()
    coordinator._client.async_panel_stop = AsyncMock()

    await coordinator_parent.async_panel_stop()

    stopped_data = coordinator_parent.async_set_updated_data.call_args.args[0]
    assert stopped_data.mode == "stopped"
    assert stopped_data.connected is False
    coordinator._client.async_panel_stop.assert_awaited_once_with()


@pytest.mark.parametrize(
    "code",
    [
        pytest.param("bad", id="not-digits"),
        pytest.param("1234\n", id="trailing-newline"),
        pytest.param("1234 ", id="trailing-space"),
    ],
)
async def test_send_command_invalid_pin(
    coordinator: VisonicDirectConnection, code: str
) -> None:
    """Reject a malformed direct panel PIN."""
    coordinator._client = MagicMock()
    coordinator._client.is_panel_connected.return_value = False
    result = await coordinator.send_command(AlarmPanelCommand.ARM_AWAY, code)
    assert result.status is AlarmCommandStatus.FAIL_INVALID_CODE
    coordinator._client.send_command.assert_not_called()


@pytest.mark.parametrize(
    "command",
    [
        pytest.param(AlarmPanelCommand.ARM_HOME, id="home"),
        pytest.param(AlarmPanelCommand.ARM_AWAY, id="away"),
        pytest.param(AlarmPanelCommand.ARM_HOME_INSTANT, id="home-instant"),
        pytest.param(AlarmPanelCommand.ARM_AWAY_INSTANT, id="away-instant"),
    ],
)
@pytest.mark.parametrize(
    ("enabled", "code", "expected_code"),
    [
        pytest.param(True, None, None, id="no-code"),
        pytest.param(True, "", None, id="empty-code"),
        pytest.param(True, "1234", "1234", id="explicit-code"),
        pytest.param(False, "1234", "1234", id="code-required"),
    ],
)
async def test_standard_mode_arming_code(
    direct: VisonicDirectConnection,
    command: AlarmPanelCommand,
    enabled: bool,
    code: str | None,
    expected_code: str | None,
) -> None:
    """Quick arming works in standard mode and preserves supplied valid codes."""
    direct.update_options(replace(direct.options, arm_without_usercode=enabled))
    direct._client.send_command.return_value = AlCommandStatus.SUCCESS

    result = await direct.send_command(command, code)

    assert result.status is AlarmCommandStatus.SUCCESS
    direct._client.send_command.assert_awaited_once_with(
        AlPanelCommand(command), expected_code, None
    )


@pytest.mark.parametrize(
    ("command", "quick_arm", "remote_arm", "code", "expected"),
    [
        pytest.param(
            AlarmPanelCommand.ARM_HOME,
            False,
            True,
            None,
            AlarmCommandStatus.FAIL_INVALID_CODE,
            id="home-code-required",
        ),
        pytest.param(
            AlarmPanelCommand.ARM_AWAY,
            False,
            True,
            None,
            AlarmCommandStatus.FAIL_INVALID_CODE,
            id="away-code-required",
        ),
        pytest.param(
            AlarmPanelCommand.ARM_HOME_INSTANT,
            False,
            True,
            None,
            AlarmCommandStatus.FAIL_INVALID_CODE,
            id="home-instant-code-required",
        ),
        pytest.param(
            AlarmPanelCommand.ARM_AWAY_INSTANT,
            False,
            True,
            None,
            AlarmCommandStatus.FAIL_INVALID_CODE,
            id="away-instant-code-required",
        ),
        pytest.param(
            AlarmPanelCommand.DISARM,
            True,
            True,
            None,
            AlarmCommandStatus.FAIL_INVALID_CODE,
            id="disarm-code-required",
        ),
        pytest.param(
            AlarmPanelCommand.ARM_AWAY,
            True,
            True,
            "bad",
            AlarmCommandStatus.FAIL_INVALID_CODE,
            id="explicit-invalid-code",
        ),
        pytest.param(
            AlarmPanelCommand.ARM_AWAY,
            True,
            False,
            None,
            AlarmCommandStatus.FAIL_USER_CONFIG_PREVENTED,
            id="remote-arm-disabled",
        ),
    ],
)
async def test_standard_mode_arming_restrictions(
    direct: VisonicDirectConnection,
    command: AlarmPanelCommand,
    quick_arm: bool,
    remote_arm: bool,
    code: str | None,
    expected: AlarmCommandStatus,
) -> None:
    """Quick arming preserves PIN validation and remote-control restrictions."""
    direct.update_options(
        replace(
            direct.options, arm_without_usercode=quick_arm, enable_remote_arm=remote_arm
        )
    )

    result = await direct.send_command(command, code)

    assert result.status is expected
    direct._client.send_command.assert_not_awaited()


@pytest.mark.parametrize("enabled", [False, True])
async def test_quick_arm_option_updates_backend(
    hass: HomeAssistant, setup_integration: SetupIntegration, enabled: bool
) -> None:
    """Apply a changed quick-arm option without restarting the connection."""
    _, entry = await setup_integration(options={CONF_ARM_CODE_AUTO: not enabled})
    coordinator = entry.runtime_data.coordinator
    assert coordinator.connection.options.arm_without_usercode is not enabled
    with patch.object(coordinator, "async_request_refresh") as refresh:
        hass.config_entries.async_update_entry(
            entry, options=dict(entry.options) | {CONF_ARM_CODE_AUTO: enabled}
        )
        await hass.async_block_till_done()

    assert coordinator.connection.options.arm_without_usercode is enabled
    refresh.assert_awaited_once_with()


@pytest.mark.parametrize(
    ("command", "enabled_option"),
    [
        pytest.param(AlarmPanelCommand.ARM_AWAY, CONF_ENABLE_REMOTE_ARM, id="arm"),
        pytest.param(AlarmPanelCommand.DISARM, CONF_ENABLE_REMOTE_DISARM, id="disarm"),
    ],
)
async def test_send_command_prevented_by_config(
    coordinator_parent: VisonicCoordinator,
    coordinator: VisonicDirectConnection,
    command: AlarmPanelCommand,
    enabled_option: str,
) -> None:
    """Respect user policy for direct arm and disarm commands."""
    coordinator._client = MagicMock()
    coordinator._client.is_panel_connected.return_value = False
    coordinator_parent.hass.config_entries.async_update_entry(
        coordinator_parent.config_entry, options={enabled_option: False}
    )

    result = await coordinator.send_command(command, "1234")

    assert result.status is AlarmCommandStatus.FAIL_USER_CONFIG_PREVENTED
    coordinator._client.send_command.assert_not_called()


async def test_send_command_success(
    coordinator_parent: VisonicCoordinator, coordinator: VisonicDirectConnection
) -> None:
    """Forward valid arm commands and mark direct success as not bypassed."""
    result = CommandResult(AlarmCommandStatus.SUCCESS)
    coordinator._client = MagicMock()
    coordinator._client.is_panel_connected.return_value = False
    coordinator_parent.hass.config_entries.async_update_entry(
        coordinator_parent.config_entry, options={CONF_ENABLE_REMOTE_ARM: True}
    )
    coordinator._client.send_command = AsyncMock(
        return_value=AlCommandStatus(result.status)
    )

    actual = await coordinator.send_command(AlarmPanelCommand.ARM_AWAY, "1234")

    assert actual.status is AlarmCommandStatus.SUCCESS
    coordinator._client.send_command.assert_awaited_once_with(
        AlPanelCommand.ARM_AWAY, "1234", None
    )


async def test_send_command_failure(
    coordinator_parent: VisonicCoordinator, coordinator: VisonicDirectConnection
) -> None:
    """Preserve command failures while adding the entity context."""
    result = CommandResult(AlarmCommandStatus.FAIL_INVALID_STATE)
    coordinator._client = MagicMock()
    coordinator._client.is_panel_connected.return_value = False
    coordinator_parent.hass.config_entries.async_update_entry(
        coordinator_parent.config_entry, options={CONF_ENABLE_REMOTE_ARM: True}
    )
    coordinator._client.send_command = AsyncMock(
        return_value=AlCommandStatus(result.status)
    )

    actual = await coordinator.send_command(AlarmPanelCommand.ARM_AWAY, "1234")

    assert actual.status is AlarmCommandStatus.FAIL_INVALID_STATE


async def test_send_command_unsupported(
    coordinator: VisonicDirectConnection,
) -> None:
    """Reject commands outside the direct arm/disarm command set."""
    coordinator._client = MagicMock()
    coordinator._client.is_panel_connected.return_value = False
    result = await coordinator.send_command(cast(AlarmPanelCommand, 99), "1234")

    assert result.status is AlarmCommandStatus.FAIL_PANEL_CONFIG_PREVENTED


async def test_get_pin_code(
    coordinator: VisonicDirectConnection, caplog: pytest.LogCaptureFixture
) -> None:
    """Accept valid PINs and powerlink's stored PIN, and warn otherwise."""
    coordinator._client = MagicMock()
    coordinator._client.is_panel_connected.return_value = False
    assert coordinator.get_panel_pin_code("1234") == (True, "1234")
    assert coordinator.get_panel_pin_code("12") == (False, None)

    coordinator._client.achieved_powerlink.return_value = True
    assert coordinator.get_panel_pin_code(None) == (True, None)

    coordinator._client.achieved_powerlink.return_value = False
    assert coordinator.get_panel_pin_code(None) == (False, None)
    assert "Valid 4 digit PIN not found" in caplog.text


async def test_create_state_snapshot_disconnected(
    coordinator: VisonicDirectConnection,
) -> None:
    """Return a disconnected snapshot without querying panel fields."""
    coordinator._client = MagicMock()
    coordinator._client.is_panel_connected.return_value = False
    coordinator._client.get_partitions_in_use.return_value = None
    coordinator._client.is_panel_connected.return_value = False

    result = await coordinator.create_state_snapshot()

    assert result.connected is False
    coordinator._client.get_partition_status.assert_not_called()


@pytest.mark.parametrize(
    ("partitions", "statuses", "siren_active", "expected"),
    [
        pytest.param(
            None,
            {0: AlPanelStatus.DISARMED},
            False,
            AlarmPanelStatus.DISARMED,
            id="unpartitioned",
        ),
        pytest.param(
            {0, 2},
            {0: AlPanelStatus.DISARMED, 2: AlPanelStatus.ARMED_AWAY},
            False,
            AlarmPanelStatus.ARMED_AWAY,
            id="sparse-partitions",
        ),
        pytest.param(
            {0, 1},
            {0: AlPanelStatus.DISARMED, 1: AlPanelStatus.ARMED_HOME},
            True,
            AlarmPanelStatus.ARMED_HOME,
            id="active-siren",
        ),
        pytest.param(
            {0, 1},
            {0: AlPanelStatus.ENTRY_DELAY, 1: AlPanelStatus.ARMED_AWAY},
            False,
            AlarmPanelStatus.ENTRY_DELAY,
            id="entry-delay-first",
        ),
        pytest.param(
            {0, 1},
            {0: AlPanelStatus.ARMED_AWAY, 1: AlPanelStatus.ENTRY_DELAY},
            False,
            AlarmPanelStatus.ENTRY_DELAY,
            id="entry-delay-last",
        ),
        pytest.param(
            {0, 1},
            {0: AlPanelStatus.ENTRY_DELAY_INSTANT, 1: AlPanelStatus.ARMED_AWAY},
            False,
            AlarmPanelStatus.ENTRY_DELAY_INSTANT,
            id="instant-entry-delay",
        ),
        pytest.param(
            {0, 1},
            {0: AlPanelStatus.ENTRY_DELAY, 1: AlPanelStatus.TRIGGERED},
            False,
            AlarmPanelStatus.TRIGGERED,
            id="triggered-over-entry-delay",
        ),
    ],
)
async def test_create_state_snapshot_connected(
    coordinator: VisonicDirectConnection,
    partitions: set[int] | None,
    statuses: dict[int, AlPanelStatus],
    siren_active: bool,
    expected: AlarmPanelStatus,
) -> None:
    """Combine actual partition IDs into a single whole-panel snapshot."""
    coordinator._client = MagicMock()
    coordinator._client.is_panel_connected.return_value = True
    coordinator._client.get_partitions_in_use.return_value = partitions
    coordinator._client.disconnection_count = 3
    coordinator._client.get_panel_status_dict.side_effect = [
        {"emulationmode": "powerlink"},
        {"emulationmode": "powerlink"},
    ]
    coordinator._client.get_partition_status.side_effect = statuses.__getitem__
    coordinator._client.is_any_siren_active.return_value = (
        siren_active,
        0,
        AlAlarmType.NONE,
    )
    result = await coordinator.create_state_snapshot()
    assert result.connected is True
    assert result.armcode is expected
    assert result.siren_active is siren_active
    assert result.disconnection_count == 3
    assert result.statusdict == {"emulationmode": "powerlink"}
    assert coordinator._client.get_panel_status_dict.call_count == 2
    assert {
        item.args[0] for item in coordinator._client.get_partition_status.call_args_list
    } == set(statuses)
    coordinator._client.get_partition_status_dict.assert_not_called()


@pytest.mark.parametrize(
    ("ident", "expected_serial", "expected_title"),
    [
        pytest.param(
            "160E89",
            "160E89",
            "Panel 1 (Identifier 160E89, PowerMaster 30)",
            id="known-ident",
        ),
        pytest.param("", None, "Panel 1 (PowerMaster 30)", id="unknown-ident"),
    ],
)
async def test_client_metadata_persisted_by_coordinator(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    caplog: pytest.LogCaptureFixture,
    ident: str,
    expected_serial: str | None,
    expected_title: str,
) -> None:
    """Use the protocol's panel identifier for metadata and shared panel titles."""
    _, entry = await setup_integration()
    with patch.object(hass.config_entries, "async_schedule_reload"):
        hass.config_entries.async_update_entry(
            entry,
            title="Original title",
            data=dict(entry.data) | {CONF_PANEL_SERIAL: "1412031343."},
        )
        await hass.async_block_till_done()
    coordinator = entry.runtime_data.coordinator.connection
    coordinator._client._visonic_protocol = MagicMock()
    coordinator._client._protocol.get_panel_model.return_value = "PowerMaster 30"
    coordinator._client._protocol.get_panel_ident.return_value = ident
    with patch.object(
        entry.runtime_data.coordinator, "set_alarm_device_information"
    ) as register:
        coordinator._client.save_working_baud(38400)
        coordinator._client.panel_change_event(AlCondition.DOWNLOAD_SUCCESS, None)
    assert entry.data[CONF_DEVICE_BAUD] == 38400
    assert entry.data[TEXT_PANEL_MODEL] == "PowerMaster 30"
    assert entry.data.get(CONF_PANEL_SERIAL) == expected_serial
    assert entry.title == expected_title
    assert entry.runtime_data.coordinator.name == f"Visonic {expected_title}"
    with caplog.at_level(logging.DEBUG, logger="homeassistant.components.visonic"):
        entry.runtime_data.coordinator.async_set_updated_data(VisonicCoordinatorData())
    assert f"Manually updated Visonic {expected_title} data" in caplog.text
    register.assert_called_once_with("PowerMaster 30")
    await hass.async_block_till_done()


async def test_options_update_plain_client_settings(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
) -> None:
    """Keep retry settings current without passing a config entry to the client."""
    _, entry = await setup_integration()
    coordinator = entry.runtime_data.coordinator.connection
    hass.config_entries.async_update_entry(
        entry,
        options=dict(entry.options)
        | {
            CONF_RETRY_CONNECTION_COUNT: 4,
            CONF_RETRY_CONNECTION_DELAY: 120,
        },
    )
    await hass.async_block_till_done()
    assert coordinator._client.settings.retry_count == 4
    assert coordinator._client.settings.retry_delay == 120


async def test_direct_startup_waits_for_state(direct: VisonicDirectConnection) -> None:
    """Connecting waits for usable decoded state rather than scheduled background work."""
    started = asyncio.Event()
    direct._client.connect.side_effect = lambda: started.set() or True
    direct._client.is_panel_connected.return_value = False
    direct.callbacks.state_changed = MagicMock()
    task = asyncio.create_task(direct.async_panel_connect())
    await started.wait()
    assert not task.done()
    direct._client.is_panel_connected.return_value = True
    direct._handle_state_change()
    assert await task
    direct.callbacks.state_changed.assert_called_once_with(0.2)


async def test_direct_startup_rejected(direct: VisonicDirectConnection) -> None:
    """A rejected client start cannot complete backend setup."""
    direct._client.connect.return_value = False
    assert not await direct.async_panel_connect()


async def test_recovery_command_error_reaches_home_assistant(
    hass: HomeAssistant,
    direct_parent: VisonicCoordinator,
    direct: VisonicDirectConnection,
) -> None:
    """A refused command during silence must become a visible action error."""
    hass.config.components.add(DOMAIN)
    await async_get_translations(hass, "en", "exceptions", {DOMAIN})
    direct._client.send_command.return_value = AlCommandStatus.FAIL_RECOVERY_IN_PROGRESS
    result = await direct.send_command(AlarmPanelCommand.ARM_AWAY, "1234")
    assert result.status == AlarmCommandStatus.FAIL_RECOVERY_IN_PROGRESS
    with pytest.raises(HomeAssistantError, match="temporarily silent for recovery"):
        direct_parent.process_command_result(result)


async def test_recovery_failure_stops_and_notifies(
    hass: HomeAssistant,
    direct_parent: VisonicCoordinator,
    direct: VisonicDirectConnection,
) -> None:
    """A recovery deadline stops integration activity and creates a user error."""
    with (
        patch.object(direct_parent, "async_panel_stop", new=AsyncMock()) as stop,
        patch(
            "homeassistant.components.visonic.coordinator.persistent_notification.async_create"
        ) as notify,
    ):
        direct._handle_panel_problem(AlTerminationType.FLOOD_RECOVERY_FAILED)
        await hass.async_block_till_done()
    stop.assert_awaited_once_with()
    notify.assert_called_once()
    assert "integration has stopped" in notify.call_args.args[1]
    assert notify.call_args.kwargs["title"] == "Visonic recovery failed"


async def test_recovery_failure_actually_stops_coordinator_and_client(
    hass: HomeAssistant,
    direct_parent: VisonicCoordinator,
    direct: VisonicDirectConnection,
) -> None:
    """A terminal recovery failure leaves polling and the panel client stopped."""
    with patch(
        "homeassistant.components.visonic.coordinator.persistent_notification.async_create"
    ) as notify:
        direct._handle_panel_problem(AlTerminationType.FLOOD_RECOVERY_FAILED)
        await hass.async_block_till_done()
    assert direct_parent._stopping
    assert not direct_parent.data.connected
    assert direct_parent.data.mode == "stopped"
    direct._client.async_panel_stop.assert_awaited_once_with()
    notify.assert_called_once()
