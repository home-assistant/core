"""Tests for the Bosch SHC select platform."""

from unittest.mock import MagicMock, create_autospec, patch

from boschshcpy import (
    SHCShutterContact2,
    SHCShutterContact2Plus,
    SHCSmokeDetector,
    SHCTwinguard,
)
from boschshcpy.models_impl import (
    SHCLightControl,
    SHCMicromoduleRelay,
    SHCMotionDetector2,
    SHCRoomThermostat2,
    SHCSmartPlug,
    SHCThermostat,
    SHCThermostatGen2,
)
from boschshcpy.services_impl import (
    DisplayDirection,
    DisplayedTemperatureConfiguration,
    PirSensorConfigurationService,
    PollControlService,
    PowerSwitchConfigurationService,
    SmartSensitivityControlService,
    SmokeSensitivityService,
    SwitchConfiguration,
    TerminalConfiguration,
    VibrationSensorService,
    WallThermostatConfiguration,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


def _make_device(
    spec: type, serial: str = "device-serial-1", **attrs: object
) -> MagicMock:
    """Build an autospecced SHC device with the base attributes SHCEntity needs."""
    device = create_autospec(spec, instance=True)
    device.serial = serial
    device.id = f"{serial}-id"
    device.root_device_id = "shc-test-uid"
    device.name = "Test Device"
    device.manufacturer = "Bosch"
    device.device_model = "TEST_MODEL"
    device.status = "AVAILABLE"
    device.deleted = False
    device.device_services = []
    for key, value in attrs.items():
        setattr(device, key, value)
    return device


async def _setup_select_platform(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """Set up the bosch_shc config entry with only the select platform loaded."""
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.bosch_shc.SHCSession",
            return_value=mock_session,
        ),
        patch("homeassistant.components.bosch_shc.async_get_instance"),
        patch("homeassistant.components.bosch_shc.PLATFORMS", [Platform.SELECT]),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


async def _select_option(hass: HomeAssistant, entity_id: str, option: str) -> None:
    """Call the select_option service for the given entity."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
        blocking=True,
    )


def _rich_motion_detector2() -> MagicMock:
    """A Motion Detector II with every gated select available."""
    return _make_device(
        SHCMotionDetector2,
        serial="md2-1",
        motion_sensitivity=PirSensorConfigurationService.MotionSensitivity.MIDDLE,
        long_poll_interval=PollControlService.PollControlState.LONG,
        supports_smart_sensitivity=True,
        get_smart_sensitivity=lambda ctx: {
            "manualLevel": SmartSensitivityControlService.MotionSensitivity.HIGH
        },
    )


def _rich_shutter_contact2_plus() -> MagicMock:
    """A Shutter Contact 2 Plus (the only shutter_contacts2 variant with vibration)."""
    return _make_device(
        SHCShutterContact2Plus,
        serial="sc2p-1",
        sensitivity=VibrationSensorService.SensitivityState.MEDIUM,
    )


def _rich_smart_plug() -> MagicMock:
    """A smart plug with power-outage behavior configured."""
    return _make_device(
        SHCSmartPlug,
        serial="plug-1",
        supports_power_switch_configuration=True,
        state_after_power_outage=PowerSwitchConfigurationService.StateAfterPowerOutage.OFF,
    )


def _rich_smoke_detector() -> MagicMock:
    """A smoke detector with sensitivity configured."""
    return _make_device(
        SHCSmokeDetector,
        serial="sd-1",
        supports_smoke_sensitivity=True,
        smoke_sensitivity=SmokeSensitivityService.SmokeSensitivityLevel.MIDDLE,
    )


def _rich_thermostat_gen2() -> MagicMock:
    """A Gen2 TRV with display/wall-thermostat selects available.

    valve_type/heater_type only exist on SHCThermostatGen2 — not on Gen1
    SHCThermostat, and not on SHCRoomThermostat2 either.
    """
    return _make_device(
        SHCThermostatGen2,
        serial="trv2-1",
        name="Gen2 Thermostat",
        supports_display_direction=True,
        display_direction=DisplayDirection.Direction.NORMAL,
        supports_displayed_temperature=True,
        displayed_temperature=DisplayedTemperatureConfiguration.DisplayedTemperature.SETPOINT,
        supports_wall_thermostat_configuration=True,
        valve_type=WallThermostatConfiguration.ValveType.NORMALLY_CLOSE,
        heater_type=WallThermostatConfiguration.HeaterType.RADIATOR,
    )


def _rich_room_thermostat2() -> MagicMock:
    """A Room Thermostat 2 with display + terminal-type selects available.

    RoomThermostat2 has no valve_type/heater_type — those are Gen2-only.
    """
    return _make_device(
        SHCRoomThermostat2,
        serial="rth2-1",
        name="Room Thermostat 2",
        supports_display_direction=True,
        display_direction=DisplayDirection.Direction.NORMAL,
        supports_displayed_temperature=True,
        displayed_temperature=DisplayedTemperatureConfiguration.DisplayedTemperature.SETPOINT,
        supports_terminal_configuration=True,
        terminal_type=TerminalConfiguration.Type.NOT_CONNECTED,
    )


def _rich_micromodule_relay() -> MagicMock:
    """A micromodule relay with every gated switch-config select available."""
    return _make_device(
        SHCMicromoduleRelay,
        serial="relay-1",
        switch_type=SwitchConfiguration.SwitchType.PUSHBUTTON,
        actuator_type=SwitchConfiguration.ActuatorType.NORMALLY_OPEN,
        output_mode=SwitchConfiguration.OutputMode.ATTACHED,
    )


async def test_selects(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
) -> None:
    """All 17 select entities are created for a fully-featured SHC installation."""
    mock_session.device_helper.motion_detectors2 = [_rich_motion_detector2()]
    mock_session.device_helper.shutter_contacts2 = [_rich_shutter_contact2_plus()]
    mock_session.device_helper.smart_plugs = [_rich_smart_plug()]
    mock_session.device_helper.smoke_detectors = [_rich_smoke_detector()]
    mock_session.device_helper.thermostats = [_rich_thermostat_gen2()]
    mock_session.device_helper.roomthermostats = [_rich_room_thermostat2()]
    mock_session.device_helper.micromodule_relays = [_rich_micromodule_relay()]

    await _setup_select_platform(hass, mock_config_entry, mock_session)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_no_selects_when_no_devices(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
) -> None:
    """No select entities are created when all device lists are empty."""
    await _setup_select_platform(hass, mock_config_entry, mock_session)

    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )


async def test_motion_sensitivity(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """Motion sensitivity is created, reflects state, and can be changed."""
    device = _rich_motion_detector2()
    mock_session.device_helper.motion_detectors2 = [device]
    await _setup_select_platform(hass, mock_config_entry, mock_session)

    state = hass.states.get("select.test_device_motion_sensitivity")
    assert state is not None
    assert state.state == "middle"

    await _select_option(hass, "select.test_device_motion_sensitivity", "high")
    assert (
        device.motion_sensitivity
        == PirSensorConfigurationService.MotionSensitivity.HIGH
    )


async def test_motion_sensitivity_skipped_when_none(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """Motion sensitivity select is not created when the attribute is None."""
    device = _rich_motion_detector2()
    device.motion_sensitivity = None
    mock_session.device_helper.motion_detectors2 = [device]
    await _setup_select_platform(hass, mock_config_entry, mock_session)

    assert hass.states.get("select.test_device_motion_sensitivity") is None


async def test_orientation_light_response(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """Orientation-light response is created, reflects state, and can be changed."""
    device = _rich_motion_detector2()
    mock_session.device_helper.motion_detectors2 = [device]
    await _setup_select_platform(hass, mock_config_entry, mock_session)

    state = hass.states.get("select.test_device_orientation_light_response_time")
    assert state is not None
    assert state.state == "long"

    await _select_option(
        hass, "select.test_device_orientation_light_response_time", "short"
    )
    assert device.long_poll_interval == PollControlService.PollControlState.SHORT


async def test_smart_sensitivity_security_and_comfort(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """Both smart-sensitivity selects are created and can be changed independently."""
    device = _rich_motion_detector2()
    mock_session.device_helper.motion_detectors2 = [device]
    await _setup_select_platform(hass, mock_config_entry, mock_session)

    assert hass.states.get("select.test_device_security_sensitivity_level") is not None
    assert hass.states.get("select.test_device_comfort_sensitivity_level") is not None

    await _select_option(hass, "select.test_device_security_sensitivity_level", "low")
    device.set_smart_sensitivity_manual_level.assert_called_once_with(
        SmartSensitivityControlService.SmartSensitivityContext.SECURITY,
        SmartSensitivityControlService.MotionSensitivity.LOW,
    )
    device.set_smart_sensitivity_manual_level.reset_mock()

    await _select_option(hass, "select.test_device_comfort_sensitivity_level", "high")
    device.set_smart_sensitivity_manual_level.assert_called_once_with(
        SmartSensitivityControlService.SmartSensitivityContext.COMFORT,
        SmartSensitivityControlService.MotionSensitivity.HIGH,
    )


async def test_vibration_sensitivity(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """Vibration sensitivity is created only for ShutterContact2Plus."""
    device = _rich_shutter_contact2_plus()
    mock_session.device_helper.shutter_contacts2 = [device]
    await _setup_select_platform(hass, mock_config_entry, mock_session)

    state = hass.states.get("select.test_device_vibration_sensitivity")
    assert state is not None
    assert state.state == "medium"

    await _select_option(hass, "select.test_device_vibration_sensitivity", "high")
    assert device.sensitivity == VibrationSensorService.SensitivityState.HIGH


async def test_vibration_sensitivity_skipped_for_non_plus(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """Vibration sensitivity is not created for a plain ShutterContact2."""
    device = _make_device(SHCShutterContact2, serial="sc2-1")
    mock_session.device_helper.shutter_contacts2 = [device]
    await _setup_select_platform(hass, mock_config_entry, mock_session)

    assert hass.states.get("select.test_device_vibration_sensitivity") is None


@pytest.mark.parametrize(
    "device_helper_attr",
    ["smart_plugs", "smart_plugs_compact"],
)
async def test_state_after_power_outage(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    device_helper_attr: str,
) -> None:
    """State-after-power-outage is created for both plug variants and can be changed."""
    device = _rich_smart_plug()
    setattr(mock_session.device_helper, device_helper_attr, [device])
    await _setup_select_platform(hass, mock_config_entry, mock_session)

    state = hass.states.get("select.test_device_state_after_power_outage")
    assert state is not None
    assert state.state == "off"

    await _select_option(
        hass, "select.test_device_state_after_power_outage", "last_state"
    )
    assert (
        device.state_after_power_outage
        == PowerSwitchConfigurationService.StateAfterPowerOutage.LAST_STATE
    )


@pytest.mark.parametrize(
    ("device_helper_attr", "spec"),
    [("smoke_detectors", SHCSmokeDetector), ("twinguards", SHCTwinguard)],
)
async def test_smoke_sensitivity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    device_helper_attr: str,
    spec: type,
) -> None:
    """Smoke sensitivity is created for both smoke detectors and Twinguard."""
    device = _make_device(
        spec,
        serial="sd-1",
        supports_smoke_sensitivity=True,
        smoke_sensitivity=SmokeSensitivityService.SmokeSensitivityLevel.MIDDLE,
    )
    setattr(mock_session.device_helper, device_helper_attr, [device])
    await _setup_select_platform(hass, mock_config_entry, mock_session)

    state = hass.states.get("select.test_device_smoke_sensitivity")
    assert state is not None
    assert state.state == "middle"

    await _select_option(hass, "select.test_device_smoke_sensitivity", "high")
    assert (
        device.smoke_sensitivity == SmokeSensitivityService.SmokeSensitivityLevel.HIGH
    )


async def test_display_direction(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """Display direction is created, reflects state, and can be changed."""
    device = _rich_room_thermostat2()
    mock_session.device_helper.roomthermostats = [device]
    await _setup_select_platform(hass, mock_config_entry, mock_session)

    state = hass.states.get("select.room_thermostat_2_display_direction")
    assert state is not None
    assert state.state == "normal"

    await _select_option(hass, "select.room_thermostat_2_display_direction", "reversed")
    assert device.display_direction == DisplayDirection.Direction.REVERSED


async def test_displayed_temperature(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """Displayed temperature is created, reflects state, and can be changed."""
    device = _rich_room_thermostat2()
    mock_session.device_helper.roomthermostats = [device]
    await _setup_select_platform(hass, mock_config_entry, mock_session)

    state = hass.states.get("select.room_thermostat_2_displayed_temperature")
    assert state is not None
    assert state.state == "setpoint"

    await _select_option(
        hass, "select.room_thermostat_2_displayed_temperature", "measured"
    )
    assert (
        device.displayed_temperature
        == DisplayedTemperatureConfiguration.DisplayedTemperature.MEASURED
    )


async def test_valve_and_heater_type(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """Valve type and heater type are both created and can be changed independently.

    Only SHCThermostatGen2 has these — not Gen1 SHCThermostat, and not
    SHCRoomThermostat2 either.
    """
    device = _rich_thermostat_gen2()
    mock_session.device_helper.thermostats = [device]
    await _setup_select_platform(hass, mock_config_entry, mock_session)

    valve_state = hass.states.get("select.gen2_thermostat_valve_type")
    heater_state = hass.states.get("select.gen2_thermostat_heater_type")
    assert valve_state is not None
    assert valve_state.state == "normally_close"
    assert heater_state is not None
    assert heater_state.state == "radiator"

    await _select_option(hass, "select.gen2_thermostat_valve_type", "normally_open")
    assert device.valve_type == WallThermostatConfiguration.ValveType.NORMALLY_OPEN


async def test_terminal_type_only_for_roomthermostat2(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """Terminal type is created only for RoomThermostat2 and can be changed."""
    device = _rich_room_thermostat2()
    mock_session.device_helper.roomthermostats = [device]
    await _setup_select_platform(hass, mock_config_entry, mock_session)

    state = hass.states.get("select.room_thermostat_2_terminal_type")
    assert state is not None
    assert state.state == "not_connected"

    await _select_option(
        hass, "select.room_thermostat_2_terminal_type", "floor_sensor_connected"
    )
    assert device.terminal_type == TerminalConfiguration.Type.FLOOR_SENSOR_CONNECTED


async def test_gen1_thermostat_does_not_crash_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """A Gen1 TRV in thermostats must not crash select setup.

    Gen1 SHCThermostat has none of the display/wall-thermostat-config
    properties Gen2 and RoomThermostat2 have; setup must not access them
    on a Gen1 instance. Autospec (spec, not spec_set) would otherwise let
    a test silently pass even if the code regressed, so this device is
    deliberately built without any of those attributes.
    """
    device = _make_device(SHCThermostat, serial="trv1-1")
    mock_session.device_helper.thermostats = [device]
    await _setup_select_platform(hass, mock_config_entry, mock_session)

    assert hass.states.get("select.test_device_display_direction") is None
    assert hass.states.get("select.test_device_valve_type") is None


@pytest.mark.parametrize(
    "device_helper_attr",
    ["micromodule_relays", "micromodule_light_controls"],
)
async def test_switch_configuration_selects(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    device_helper_attr: str,
) -> None:
    """Switch type, actuator type and output mode are created for both device kinds."""
    spec = (
        SHCMicromoduleRelay
        if device_helper_attr == "micromodule_relays"
        else SHCLightControl
    )
    device = _make_device(
        spec,
        serial="relay-1",
        switch_type=SwitchConfiguration.SwitchType.PUSHBUTTON,
        actuator_type=SwitchConfiguration.ActuatorType.NORMALLY_OPEN,
        output_mode=SwitchConfiguration.OutputMode.ATTACHED,
    )
    setattr(mock_session.device_helper, device_helper_attr, [device])
    await _setup_select_platform(hass, mock_config_entry, mock_session)

    assert hass.states.get("select.test_device_switch_type").state == "pushbutton"
    assert hass.states.get("select.test_device_actuator_type").state == "normally_open"
    assert hass.states.get("select.test_device_output_mode").state == "attached"

    await _select_option(hass, "select.test_device_switch_type", "switch")
    assert device.switch_type == SwitchConfiguration.SwitchType.SWITCH

    await _select_option(hass, "select.test_device_actuator_type", "normally_closed")
    assert device.actuator_type == SwitchConfiguration.ActuatorType.NORMALLY_CLOSED

    await _select_option(hass, "select.test_device_output_mode", "detached")
    assert device.output_mode == SwitchConfiguration.OutputMode.DETACHED
