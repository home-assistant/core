"""Test alarm control panel."""

from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import cast
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pyvisonic import AlCondition, AlPanelCommand, AlPanelStatus
from pyvisonicalarm.alarm import AlarmSystem

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.components.visonic.alarm_control_panel import VisonicAlarm
from homeassistant.components.visonic.cloud import VisonicCloudConnection
from homeassistant.components.visonic.const import (
    CONF_ARM_CODE_AUTO,
    CONF_ARM_HOME_ENABLED,
    CONF_ENABLE_REMOTE_ARM,
    CONF_ENABLE_REMOTE_DISARM,
    CONF_INSTANT_ARM_AWAY,
    CONF_INSTANT_ARM_HOME,
    CONF_PANEL_NUMBER,
    CONF_PANEL_SERIAL,
    DOMAIN,
    FORM_CLOUD,
    FORM_DEVICE_NO_PANEL,
    FORM_SELECT_PANEL,
    TRANSLATE_EXCEPTION_DISARM_CODE_NOT_ENTERED,
    Platform,
)
from homeassistant.components.visonic.coordinator import VisonicCoordinator
from homeassistant.components.visonic.direct import VisonicDirectConnection
from homeassistant.components.visonic.visonic_data_types import (
    VisonicConfigEntry,
    VisonicCoordinatorData,
)
from homeassistant.components.visonic.visonic_entity_types import AlarmPanelData
from homeassistant.components.visonic.visonic_types import (
    AlarmCommandStatus,
    AlarmPanelCommand,
    AlarmPanelStatus,
    CommandResult,
    DeviceType,
    PanelStateData,
)
from homeassistant.const import (
    CONF_CODE,
    CONF_EMAIL,
    CONF_EXTERNAL_URL,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant, HomeAssistantError
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from .helpers import SetupIntegration, create_mock_config_entry


@pytest.mark.usefixtures("mock_panel_connect", "mock_async_zeroconf")
@pytest.mark.parametrize(
    ("device_type", "powerlink", "code_format", "code_arm_required"),
    [
        pytest.param(DeviceType.ETHERNET, True, None, False, id="powerlink"),
        pytest.param(DeviceType.SERIAL, False, CodeFormat.NUMBER, True, id="serial"),
        pytest.param(DeviceType.CLOUD, True, None, False, id="cloud"),
    ],
)
@pytest.mark.parametrize(
    ("armcode", "expected_state"),
    [
        pytest.param(
            AlarmPanelStatus.ARMED_AWAY, AlarmControlPanelState.ARMED_AWAY, id="armed"
        ),
        pytest.param(
            AlarmPanelStatus.ENTRY_DELAY, AlarmControlPanelState.PENDING, id="pending"
        ),
        pytest.param(
            AlarmPanelStatus.ENTRY_DELAY_INSTANT,
            AlarmControlPanelState.PENDING,
            id="pending-instant",
        ),
        pytest.param(
            AlarmPanelStatus.TRIGGERED,
            AlarmControlPanelState.TRIGGERED,
            id="triggered",
        ),
    ],
)
async def test_initial_entity_state(
    hass: HomeAssistant,
    device_type: DeviceType,
    powerlink: bool,
    code_format: CodeFormat | None,
    code_arm_required: bool,
    armcode: AlarmPanelStatus,
    expected_state: AlarmControlPanelState,
) -> None:
    """Publish the existing snapshot before any subsequent panel update or poll."""
    entry = create_mock_config_entry(
        data={CONF_TYPE: device_type},
        options={CONF_ARM_HOME_ENABLED: True, CONF_ARM_CODE_AUTO: False},
    )
    entry.add_to_hass(hass)
    snapshot = VisonicCoordinatorData(
        connected=True,
        achieved_powerlink=powerlink,
        armcode=armcode,
        statusdict={"panel_test_attribute": "initial snapshot"},
    )
    with (
        patch.object(
            VisonicDirectConnection, "create_state_snapshot", return_value=snapshot
        ),
        patch.object(
            VisonicCloudConnection, "create_state_snapshot", return_value=snapshot
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        state = hass.states.get("alarm_control_panel.visonic_alarm_p1")
        assert state is not None
        assert state.state == expected_state
        assert state.attributes["supported_features"] == (
            AlarmControlPanelEntityFeature.ARM_HOME
            | AlarmControlPanelEntityFeature.ARM_AWAY
        )
        assert state.attributes["code_format"] == code_format
        assert state.attributes["code_arm_required"] is code_arm_required
        assert state.attributes["panel_test_attribute"] == "initial snapshot"
        assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("mock_async_zeroconf")
@pytest.mark.parametrize("device_type", [DeviceType.ETHERNET, DeviceType.SERIAL])
@pytest.mark.parametrize(
    ("mock_visonic_client", "expected_format"),
    [
        pytest.param(True, None, id="powerlink"),
        pytest.param(False, CodeFormat.NUMBER, id="standard-plus"),
    ],
    indirect=["mock_visonic_client"],
)
async def test_startup_success_waits_for_initial_snapshot(
    hass: HomeAssistant,
    mock_visonic_client: MagicMock,
    device_type: DeviceType,
    expected_format: CodeFormat | None,
) -> None:
    """An early startup notification cannot create an alarm with empty state."""
    entry = create_mock_config_entry(
        data={CONF_TYPE: device_type}, options={CONF_ARM_HOME_ENABLED: True}
    )
    entry.add_to_hass(hass)
    entity_id = "alarm_control_panel.visonic_alarm_p1"
    mock_visonic_client.get_partition_status.return_value = AlPanelStatus.ARMED_AWAY

    async def connect(connection: VisonicDirectConnection) -> bool:
        connection.callbacks.panel_ready()
        await hass.async_block_till_done()
        assert not hass.states.async_entity_ids("alarm_control_panel")
        return True

    with patch.object(
        VisonicDirectConnection,
        "async_panel_connect",
        autospec=True,
        side_effect=connect,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == AlarmControlPanelState.ARMED_AWAY
    assert state.attributes["supported_features"] == (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
    )
    assert state.attributes["code_format"] == expected_format

    mock_visonic_client.callbacks.panel_change(AlCondition.STARTUP_SUCCESS, None)
    await hass.async_block_till_done()
    assert hass.states.async_entity_ids("alarm_control_panel") == [entity_id]
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("mock_async_zeroconf")
@pytest.mark.parametrize(
    ("command", "panel_command"),
    [
        pytest.param("alarm_arm_home", AlPanelCommand.ARM_HOME, id="home"),
        pytest.param("alarm_arm_away", AlPanelCommand.ARM_AWAY, id="away"),
    ],
)
@pytest.mark.parametrize(
    ("mock_visonic_client", "quick_arm", "service_data"),
    [
        pytest.param(True, False, {}, id="powerlink-stored-pin"),
        pytest.param(True, True, {}, id="powerlink-quick-arm"),
        pytest.param(False, True, {}, id="fallback-quick-arm"),
        pytest.param(False, False, {CONF_CODE: "1234"}, id="fallback-explicit-pin"),
    ],
    indirect=["mock_visonic_client"],
)
async def test_local_arm_service_accepts_code(
    hass: HomeAssistant,
    mock_visonic_client: MagicMock,
    command: str,
    panel_command: AlPanelCommand,
    quick_arm: bool,
    service_data: dict[str, str],
) -> None:
    """Local arming reaches the library with its stored PIN or a supplied code."""
    entry = create_mock_config_entry(
        options={
            CONF_ENABLE_REMOTE_ARM: True,
            CONF_ARM_CODE_AUTO: quick_arm,
            CONF_INSTANT_ARM_HOME: False,
            CONF_INSTANT_ARM_AWAY: False,
        }
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get("alarm_control_panel.visonic_alarm_p1")
    assert state is not None
    assert state.state == AlarmControlPanelState.DISARMED

    await hass.services.async_call(
        "alarm_control_panel",
        command,
        {"entity_id": "alarm_control_panel.visonic_alarm_p1"} | service_data,
        blocking=True,
    )
    mock_visonic_client.send_command.assert_awaited_once_with(
        panel_command, service_data.get(CONF_CODE), None
    )
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("mock_async_zeroconf")
@pytest.mark.parametrize("command", ["alarm_arm_home", "alarm_arm_away"])
@pytest.mark.parametrize(
    ("mock_visonic_client", "remote_arm", "error_key"),
    [
        pytest.param(False, True, "code_arm_required", id="fallback-needs-code"),
        pytest.param(
            True,
            False,
            "fail_user_config_prevented",
            id="powerlink-remote-arm-disabled",
        ),
    ],
    indirect=["mock_visonic_client"],
)
async def test_local_arm_service_rejects_missing_code_or_permission(
    hass: HomeAssistant,
    mock_visonic_client: MagicMock,
    command: str,
    remote_arm: bool,
    error_key: str,
) -> None:
    """Stored Powerlink codes do not bypass the remote-arm permission."""
    entry = create_mock_config_entry(
        options={
            CONF_ENABLE_REMOTE_ARM: remote_arm,
            CONF_ARM_CODE_AUTO: False,
            CONF_INSTANT_ARM_HOME: False,
            CONF_INSTANT_ARM_AWAY: False,
        }
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get("alarm_control_panel.visonic_alarm_p1")
    assert state is not None
    assert state.state == AlarmControlPanelState.DISARMED

    with pytest.raises(ServiceValidationError) as raised:
        await hass.services.async_call(
            "alarm_control_panel",
            command,
            {"entity_id": "alarm_control_panel.visonic_alarm_p1"},
            blocking=True,
        )
    assert raised.value.translation_key == error_key
    mock_visonic_client.send_command.assert_not_awaited()
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("mock_panel_connect", "mock_async_zeroconf")
@pytest.mark.parametrize("command", ["arm_home", "arm_away", "disarm"])
async def test_cloud_service_reuses_configured_code(
    hass: HomeAssistant, command: str
) -> None:
    """Cloud actions without a code reach the session authenticated with the saved PIN."""
    entry = cast(
        VisonicConfigEntry,
        create_mock_config_entry(
            data={CONF_TYPE: DeviceType.CLOUD, CONF_PANEL_NUMBER: 3, CONF_CODE: "1234"},
            options={
                CONF_ENABLE_REMOTE_ARM: True,
                CONF_ENABLE_REMOTE_DISARM: True,
                CONF_INSTANT_ARM_HOME: False,
                CONF_INSTANT_ARM_AWAY: False,
            },
        ),
    )
    entry.add_to_hass(hass)
    cloud_alarm = MagicMock(spec=AlarmSystem)
    cloud_alarm.get_user_code.return_value = entry.data[CONF_CODE]
    cloud_command = getattr(cloud_alarm, command)
    cloud_command.return_value = "process-token"
    with (
        patch.object(
            VisonicCloudConnection,
            "create_state_snapshot",
            return_value=VisonicCoordinatorData(
                connected=True, achieved_powerlink=True
            ),
        ),
        patch.object(
            VisonicCloudConnection,
            "wait_for_process_status",
            return_value=AlarmCommandStatus.SUCCESS,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        cloud = cast(VisonicCloudConnection, entry.runtime_data.coordinator.connection)
        cloud.cloud_alarm = cloud_alarm
        cloud.login_success = True
        assert cloud.settings.code == "1234"
        state = hass.states.get("alarm_control_panel.visonic_alarm_p3")
        assert state is not None
        assert state.attributes["code_arm_required"] is False
        assert state.attributes["code_format"] is None
        await hass.services.async_call(
            "alarm_control_panel",
            f"alarm_{command}",
            {"entity_id": state.entity_id},
            blocking=True,
        )
        cloud_alarm.get_user_code.assert_called()
        cloud_command.assert_awaited_once_with()
        assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures(
    "mock_connection_test", "mock_panel_connect", "mock_async_zeroconf"
)
@pytest.mark.parametrize("command", ["arm_home", "arm_away"])
async def test_cloud_reconfigure_uses_normal_arming(
    hass: HomeAssistant, command: str
) -> None:
    """A loaded local panel loses hidden instant settings after switching to cloud."""
    shared_options = {
        CONF_ENABLE_REMOTE_ARM: True,
        CONF_ENABLE_REMOTE_DISARM: False,
        CONF_ARM_HOME_ENABLED: True,
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TYPE: DeviceType.ETHERNET,
            CONF_PANEL_NUMBER: 3,
            CONF_HOST: "192.0.2.1",
            CONF_PORT: "30000",
        },
        options=shared_options
        | {
            CONF_ARM_CODE_AUTO: True,
            CONF_INSTANT_ARM_HOME: True,
            CONF_INSTANT_ARM_AWAY: True,
        },
    )
    entry.add_to_hass(hass)
    snapshot = VisonicCoordinatorData(connected=True, achieved_powerlink=True)
    with (
        patch(
            "homeassistant.components.visonic.direct.VisonicDirectConnection.create_state_snapshot",
            return_value=snapshot,
        ),
        patch.object(
            VisonicCloudConnection, "create_state_snapshot", return_value=snapshot
        ),
        patch.object(
            VisonicCloudConnection,
            "wait_for_process_status",
            return_value=AlarmCommandStatus.SUCCESS,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        result = await entry.start_reconfigure_flow(hass)
        assert result["step_id"] == FORM_DEVICE_NO_PANEL
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TYPE: DeviceType.CLOUD.title()}
        )
        assert result["step_id"] == FORM_CLOUD
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EXTERNAL_URL: "cloud.example.com",
                CONF_EMAIL: "user@example.com",
                CONF_PASSWORD: "password",
            },
        )
        assert result["step_id"] == FORM_SELECT_PANEL
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PANEL_SERIAL: "ABCDEF", CONF_CODE: "1234"}
        )
        assert result["reason"] == "reconfigure_successful"
        await hass.async_block_till_done(wait_background_tasks=True)
        assert entry.data[CONF_TYPE] == DeviceType.CLOUD
        assert entry.options == shared_options
        cloud = cast(VisonicCloudConnection, entry.runtime_data.coordinator.connection)
        cloud_alarm = MagicMock(spec=AlarmSystem)
        cloud_alarm.get_user_code.return_value = "1234"
        cloud.cloud_alarm = cloud_alarm
        cloud.login_success = True
        cloud_command = getattr(cloud_alarm, command)
        cloud_command.return_value = "process-token"
        state = hass.states.get("alarm_control_panel.visonic_alarm_p3")
        assert state is not None
        assert state.attributes["code_arm_required"] is False
        await hass.services.async_call(
            "alarm_control_panel",
            f"alarm_{command}",
            {"entity_id": state.entity_id},
            blocking=True,
        )
        cloud_command.assert_awaited_once_with()
        cloud_alarm.arm_home_instant.assert_not_awaited()
        cloud_alarm.arm_away_instant.assert_not_awaited()
        assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_async_alarm_disarm_code_not_entered(
    setup_integration: SetupIntegration,
    wait_for_coordinator_timer: Callable[[], Awaitable[None]],
) -> None:
    """Test disarm raises an error when a code is required but not supplied."""
    identifier = "test_identifier"

    options = {
        CONF_INSTANT_ARM_HOME: False,
        CONF_INSTANT_ARM_AWAY: False,
    }
    result, entry = await setup_integration(options=options)
    assert result
    coordinator: VisonicCoordinator = entry.runtime_data.coordinator
    coordinator.data = VisonicCoordinatorData(connected=False, ispowermaster=True)

    coordinator.process_command_result = MagicMock()
    alarm = VisonicAlarm(entry, identifier=identifier)
    assert alarm.available is False
    assert alarm.alarm_state is None
    assert alarm.supported_features == 0
    alarm.coordinator.send_command = AsyncMock()

    with pytest.raises(ServiceValidationError) as exc_info:
        await alarm.async_alarm_disarm(None)

    assert exc_info.value.translation_key == (
        TRANSLATE_EXCEPTION_DISARM_CODE_NOT_ENTERED
    )
    alarm.coordinator.send_command.assert_not_awaited()

    await wait_for_coordinator_timer()


@pytest.mark.parametrize(
    ("achieved_powerlink", "expected"),
    [
        pytest.param(True, None, id="powerlink"),
        pytest.param(False, CodeFormat.NUMBER, id="fallback"),
    ],
)
@pytest.mark.asyncio
async def test_update_local_sets_attributes(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    wait_for_coordinator_timer: Callable[[], Awaitable[None]],
    achieved_powerlink: bool,
    expected: CodeFormat | None,
) -> None:
    """Test update_local updates HA entity attributes from PanelState."""

    identifier = "test_identifier"
    options = {
        CONF_INSTANT_ARM_HOME: True,
        CONF_INSTANT_ARM_AWAY: True,
    }
    result, entry = await setup_integration(options=options)
    assert result

    alarm = VisonicAlarm(entry, identifier=identifier)

    state = PanelStateData(
        alarm_state=AlarmControlPanelState.ARMED_HOME,
        attributes={"foo": "bar"},
        connected=True,
        achieved_powerlink=achieved_powerlink,
    )

    alarm.coordinator = MagicMock()
    alarm.panel_state_data = state

    alarm.update_local(entry)

    assert alarm._attr_alarm_state == AlarmControlPanelState.ARMED_HOME
    assert alarm._attr_extra_state_attributes == {"foo": "bar"}
    assert alarm._attr_supported_features
    assert alarm._attr_code_format is expected
    assert alarm.code_arm_required is (not achieved_powerlink)
    await wait_for_coordinator_timer()


@pytest.mark.asyncio
async def test_update_local_handles_unavailable(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    wait_for_coordinator_timer: Callable[[], Awaitable[None]],
) -> None:
    """If state.connected is False, supported_features should be 0."""

    identifier = "test_identifier"
    options = {
        CONF_INSTANT_ARM_HOME: True,
        CONF_INSTANT_ARM_AWAY: True,
    }
    result, entry = await setup_integration(options=options)
    assert result
    alarm = VisonicAlarm(entry, identifier=identifier)
    alarm.coordinator = MagicMock()

    state = PanelStateData(
        alarm_state=AlarmControlPanelState.DISARMED,
        attributes={},
        connected=False,
        achieved_powerlink=True,
    )

    alarm.coordinator = MagicMock()
    alarm.panel_state_data = state

    alarm.update_local(entry)

    assert alarm._attr_supported_features == 0
    assert alarm.code_format == CodeFormat.NUMBER
    await wait_for_coordinator_timer()


type AlarmSetup = tuple[MockConfigEntry, MagicMock, MagicMock, MagicMock, MagicMock]


@pytest.fixture
async def alarm_setup(
    hass: HomeAssistant, mock_connection_test: AsyncMock
) -> AsyncGenerator[AlarmSetup]:
    """Load the real alarm platform while isolating panel I/O and entity addition."""
    entry = create_mock_config_entry()
    entry.add_to_hass(hass)
    coordinator = MagicMock(spec=VisonicCoordinator)
    coordinator.data = None
    coordinator.async_panel_connect = AsyncMock(return_value=True)
    with (
        patch(
            "homeassistant.components.visonic.VisonicCoordinator",
            return_value=coordinator,
        ),
        patch(
            "homeassistant.helpers.entity_platform.EntityPlatform.async_add_entities",
            autospec=True,
        ) as add_entities,
        patch(
            "homeassistant.components.visonic.alarm_control_panel.async_dispatcher_connect",
            wraps=async_dispatcher_connect,
        ) as connect,
        patch(
            "homeassistant.components.visonic.alarm_control_panel.VisonicAlarm",
            autospec=True,
        ) as factory,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield entry, coordinator, add_entities, connect, factory
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_async_add_alarm(
    hass: HomeAssistant,
    alarm_setup: AlarmSetup,
) -> None:
    """Dispatcher discoveries create alarm entities without extra keypad entities."""
    entry, _, add_entities, _, factory = alarm_setup
    async_dispatcher_send(
        hass,
        f"{DOMAIN}_{entry.entry_id}_add_{Platform.ALARM_CONTROL_PANEL}",
        AlarmPanelData("test"),
    )
    await hass.async_block_till_done()
    factory.assert_called_once_with(entry=entry, identifier="test")
    add_entities.assert_called_once_with(
        ANY,
        [factory.return_value],
        update_before_add=True,
        config_subentry_id=None,
    )


async def test_async_setup_entry_registers_alarm_callback(
    hass: HomeAssistant, alarm_setup: AlarmSetup
) -> None:
    """Entry unloading removes the alarm platform's dispatcher listener."""
    entry, _, _, connect, factory = alarm_setup
    connect.assert_called_once_with(
        hass, f"{DOMAIN}_{entry.entry_id}_add_{Platform.ALARM_CONTROL_PANEL}", ANY
    )
    assert await hass.config_entries.async_unload(entry.entry_id)
    async_dispatcher_send(
        hass,
        f"{DOMAIN}_{entry.entry_id}_add_{Platform.ALARM_CONTROL_PANEL}",
        AlarmPanelData("test"),
    )
    await hass.async_block_till_done()
    factory.assert_not_called()


def test_visonic_alarm_properties() -> None:
    """Test the alarm control panel properties."""
    alarm = object.__new__(VisonicAlarm)

    alarm._attr_code_arm_required = True
    alarm._attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_HOME
    )

    assert alarm.code_arm_required is True
    assert alarm.supported_features == (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_HOME
    )


@pytest.mark.parametrize(
    ("instant_home", "instant_away", "home_command", "away_command"),
    [
        (False, False, AlarmPanelCommand.ARM_HOME, AlarmPanelCommand.ARM_AWAY),
        (
            True,
            True,
            AlarmPanelCommand.ARM_HOME_INSTANT,
            AlarmPanelCommand.ARM_AWAY_INSTANT,
        ),
    ],
    ids=["standard", "instant"],
)
async def test_alarm_arm_commands(
    instant_home: bool,
    instant_away: bool,
    home_command: AlarmPanelCommand,
    away_command: AlarmPanelCommand,
) -> None:
    """Send standard or instant arm commands using the selected panel identifier."""
    alarm = object.__new__(VisonicAlarm)
    alarm._entry = MagicMock(
        options={
            CONF_INSTANT_ARM_HOME: instant_home,
            CONF_INSTANT_ARM_AWAY: instant_away,
        }
    )
    alarm._panel_ident = "Panel one"
    alarm.coordinator = MagicMock()
    alarm.coordinator.send_command = AsyncMock()

    await alarm.async_alarm_arm_home()
    await alarm.async_alarm_arm_away("1234")

    assert alarm.coordinator.send_command.await_args_list[0].args == (
        home_command,
        None,
    )
    assert alarm.coordinator.send_command.await_args_list[1].args == (
        away_command,
        "1234",
    )


async def test_alarm_disarm_command() -> None:
    """Send disarm with a supplied code when a keypad code is required."""
    alarm = object.__new__(VisonicAlarm)
    alarm._attr_code_format = CodeFormat.NUMBER
    alarm._attr_name = None
    alarm._panel_ident = "Panel one"
    alarm.coordinator = MagicMock()
    alarm.coordinator.send_command = AsyncMock()

    await alarm.async_alarm_disarm("4321")

    alarm.coordinator.send_command.assert_awaited_once_with(
        AlarmPanelCommand.DISARM, "4321"
    )


@pytest.mark.parametrize("action", ["disarm", "arm_home", "arm_away"])
@pytest.mark.parametrize(
    ("status", "exception_type", "reason"),
    [
        pytest.param(
            AlarmCommandStatus.FAIL_INVALID_CODE,
            ServiceValidationError,
            "not allowed without valid pin",
            id="invalid-code",
        ),
        pytest.param(
            AlarmCommandStatus.FAIL_PANEL_NO_CONNECTION,
            HomeAssistantError,
            "no connection to panel",
            id="disconnected",
        ),
    ],
)
async def test_alarm_command_failure(
    setup_integration: SetupIntegration,
    action: str,
    status: AlarmCommandStatus,
    exception_type: type[HomeAssistantError],
    reason: str,
) -> None:
    """Surface backend command failures through the alarm platform actions."""
    result, entry = await setup_integration()
    assert result
    alarm = VisonicAlarm(entry, "test")
    with (
        patch.object(
            entry.runtime_data.coordinator.connection,
            "send_command",
            return_value=CommandResult(status),
        ) as send,
        pytest.raises(exception_type) as raised,
    ):
        await getattr(alarm, f"async_alarm_{action}")("1234")
    assert type(raised.value) is exception_type
    assert (
        str(raised.value)
        == f"Visonic Panel 1 Failed to Send Command To Panel, {reason}"
    )
    send.assert_awaited_once()
