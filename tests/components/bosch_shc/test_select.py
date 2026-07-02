"""Tests for the Bosch SHC select platform."""

from unittest.mock import MagicMock, patch

from boschshcpy import SHCShutterContact2, SHCShutterContact2Plus
from boschshcpy.models_impl import SHCRoomThermostat2
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

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DOMAIN = "bosch_shc"

MOCK_ENTRY_DATA = {
    "host": "1.2.3.4",
    "ssl_certificate": "/fake/cert.pem",
    "ssl_key": "/fake/key.pem",
    "hostname": "shc012345",
    "token": "token:shc012345",
}


def _make_mock_session(
    motion_detectors2=None,
    shutter_contacts2=None,
    smart_plugs=None,
    smart_plugs_compact=None,
    smoke_detectors=None,
    twinguards=None,
    thermostats=None,
    roomthermostats=None,
    micromodule_relays=None,
    micromodule_light_controls=None,
):
    """Build a minimal mock SHCSession."""
    session = MagicMock()
    session.information.unique_id = "shc-test-uid"
    session.information.version = "9.99"
    session.information.updateState.name = "UP_TO_DATE"
    session.scenarios = []
    session.device_helper.motion_detectors2 = motion_detectors2 or []
    session.device_helper.shutter_contacts2 = shutter_contacts2 or []
    session.device_helper.smart_plugs = smart_plugs or []
    session.device_helper.smart_plugs_compact = smart_plugs_compact or []
    session.device_helper.smoke_detectors = smoke_detectors or []
    session.device_helper.twinguards = twinguards or []
    session.device_helper.thermostats = thermostats or []
    session.device_helper.roomthermostats = roomthermostats or []
    session.device_helper.micromodule_relays = micromodule_relays or []
    session.device_helper.micromodule_light_controls = micromodule_light_controls or []
    # Other device_helper properties used by other platforms
    session.device_helper.shutter_contacts = []
    session.device_helper.shutter_controls = []
    session.device_helper.micromodule_shutter_controls = []
    session.device_helper.micromodule_blinds = []
    session.device_helper.micromodule_impulse_relays = []
    session.device_helper.light_switches_bsm = []
    session.device_helper.micromodule_light_attached = []
    session.device_helper.climate_controls = []
    session.device_helper.wallthermostats = []
    session.device_helper.motion_detectors = []
    session.device_helper.universal_switches = []
    session.device_helper.camera_eyes = []
    session.device_helper.camera_360 = []
    session.device_helper.camera_outdoor_gen2 = []
    session.device_helper.heating_circuits = []
    return session


def _make_mock_device(serial="device-serial-1", device_id="device-id-1"):
    """Build a minimal mock SHCDevice."""
    device = MagicMock()
    device.serial = serial
    device.id = device_id
    device.root_device_id = device_id
    device.name = "Test Device"
    device.manufacturer = "Bosch"
    device.device_model = "TEST_MODEL"
    device.status = "AVAILABLE"
    device.deleted = False
    device.device_services = []
    return device


async def _setup_entry(hass: HomeAssistant, session: MagicMock) -> MockConfigEntry:
    """Create and set up a mock config entry with the given session."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data=MOCK_ENTRY_DATA,
        unique_id="shc012345",
        title="Test SHC",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.bosch_shc.SHCSession",
            return_value=session,
        ),
        patch(
            "homeassistant.components.bosch_shc.async_get_instance",
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


async def _select_option(hass: HomeAssistant, entity_id: str, option: str) -> None:
    """Call the select_option service for the given entity."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
        blocking=True,
    )


# ---------------------------------------------------------------------------
# Motion sensitivity
# ---------------------------------------------------------------------------


async def test_motion_sensitivity_created(hass: HomeAssistant) -> None:
    """Motion sensitivity select created when attribute is not None."""
    device = _make_mock_device(serial="md2-1", device_id="md2-id-1")
    device.motion_sensitivity = PirSensorConfigurationService.MotionSensitivity.MIDDLE
    device.long_poll_interval = None
    device.supports_smart_sensitivity = False

    session = _make_mock_session(motion_detectors2=[device])
    entry = await _setup_entry(hass, session)
    assert entry.state.value == "loaded"

    state = hass.states.get("select.test_device_motion_sensitivity")
    assert state is not None
    assert state.state == "MIDDLE"


async def test_motion_sensitivity_select_option(hass: HomeAssistant) -> None:
    """Selecting a motion sensitivity option sets the device attribute."""
    device = _make_mock_device(serial="md2-1", device_id="md2-id-1")
    device.motion_sensitivity = PirSensorConfigurationService.MotionSensitivity.MIDDLE
    device.long_poll_interval = None
    device.supports_smart_sensitivity = False

    session = _make_mock_session(motion_detectors2=[device])
    await _setup_entry(hass, session)

    await _select_option(hass, "select.test_device_motion_sensitivity", "HIGH")

    assert (
        device.motion_sensitivity
        == PirSensorConfigurationService.MotionSensitivity.HIGH
    )


async def test_motion_sensitivity_skipped_when_none(hass: HomeAssistant) -> None:
    """Motion sensitivity select not created when attribute is None."""
    device = _make_mock_device(serial="md2-1", device_id="md2-id-1")
    device.motion_sensitivity = None
    device.long_poll_interval = None
    device.supports_smart_sensitivity = False

    session = _make_mock_session(motion_detectors2=[device])
    await _setup_entry(hass, session)

    assert hass.states.get("select.test_device_motion_sensitivity") is None


# ---------------------------------------------------------------------------
# Orientation-light response time
# ---------------------------------------------------------------------------


async def test_orientation_light_response_created(hass: HomeAssistant) -> None:
    """Orientation-light response select created when long_poll_interval is not None."""
    device = _make_mock_device(serial="md2-2", device_id="md2-id-2")
    device.motion_sensitivity = None
    device.long_poll_interval = PollControlService.PollControlState.LONG
    device.supports_smart_sensitivity = False

    session = _make_mock_session(motion_detectors2=[device])
    entry = await _setup_entry(hass, session)
    assert entry.state.value == "loaded"

    state = hass.states.get("select.test_device_orientation_light_response_time")
    assert state is not None
    assert state.state == "LONG"


async def test_orientation_light_response_select_option(hass: HomeAssistant) -> None:
    """Selecting an orientation-light option sets the device attribute."""
    device = _make_mock_device(serial="md2-2", device_id="md2-id-2")
    device.motion_sensitivity = None
    device.long_poll_interval = PollControlService.PollControlState.LONG
    device.supports_smart_sensitivity = False

    session = _make_mock_session(motion_detectors2=[device])
    await _setup_entry(hass, session)

    await _select_option(
        hass, "select.test_device_orientation_light_response_time", "SHORT"
    )

    assert device.long_poll_interval == PollControlService.PollControlState.SHORT


# ---------------------------------------------------------------------------
# Smart sensitivity (security + comfort)
# ---------------------------------------------------------------------------


async def test_smart_sensitivity_selects_created(hass: HomeAssistant) -> None:
    """Both smart sensitivity selects created when feature is available."""
    device = _make_mock_device(serial="md2-3", device_id="md2-id-3")
    device.motion_sensitivity = None
    device.long_poll_interval = None
    device.supports_smart_sensitivity = True

    security_level = PirSensorConfigurationService.MotionSensitivity.HIGH
    comfort_level = PirSensorConfigurationService.MotionSensitivity.LOW

    def _get_smart_sensitivity(ctx):
        if ctx == SmartSensitivityControlService.SmartSensitivityContext.SECURITY:
            return {"manualLevel": security_level}
        return {"manualLevel": comfort_level}

    device.get_smart_sensitivity = _get_smart_sensitivity

    session = _make_mock_session(motion_detectors2=[device])
    entry = await _setup_entry(hass, session)
    assert entry.state.value == "loaded"

    assert hass.states.get("select.test_device_security_sensitivity_level") is not None
    assert hass.states.get("select.test_device_comfort_sensitivity_level") is not None


async def test_smart_sensitivity_select_option_security(hass: HomeAssistant) -> None:
    """Selecting security sensitivity calls set_smart_sensitivity_manual_level."""
    device = _make_mock_device(serial="md2-3", device_id="md2-id-3")
    device.motion_sensitivity = None
    device.long_poll_interval = None
    device.supports_smart_sensitivity = True
    device.get_smart_sensitivity = MagicMock(
        return_value={
            "manualLevel": SmartSensitivityControlService.MotionSensitivity.HIGH
        }
    )

    session = _make_mock_session(motion_detectors2=[device])
    await _setup_entry(hass, session)

    await _select_option(hass, "select.test_device_security_sensitivity_level", "LOW")

    device.set_smart_sensitivity_manual_level.assert_called_once_with(
        SmartSensitivityControlService.SmartSensitivityContext.SECURITY,
        SmartSensitivityControlService.MotionSensitivity.LOW,
    )


async def test_smart_sensitivity_select_option_comfort(hass: HomeAssistant) -> None:
    """Selecting comfort sensitivity calls set_smart_sensitivity_manual_level."""
    device = _make_mock_device(serial="md2-3", device_id="md2-id-3")
    device.motion_sensitivity = None
    device.long_poll_interval = None
    device.supports_smart_sensitivity = True
    device.get_smart_sensitivity = MagicMock(
        return_value={
            "manualLevel": SmartSensitivityControlService.MotionSensitivity.MIDDLE
        }
    )

    session = _make_mock_session(motion_detectors2=[device])
    await _setup_entry(hass, session)

    await _select_option(hass, "select.test_device_comfort_sensitivity_level", "HIGH")

    device.set_smart_sensitivity_manual_level.assert_called_once_with(
        SmartSensitivityControlService.SmartSensitivityContext.COMFORT,
        SmartSensitivityControlService.MotionSensitivity.HIGH,
    )


# ---------------------------------------------------------------------------
# Vibration sensitivity
# ---------------------------------------------------------------------------


async def test_vibration_sensitivity_created_for_plus(hass: HomeAssistant) -> None:
    """Vibration sensitivity select created only for ShutterContact2Plus."""
    device = _make_mock_device(serial="sc2p-1", device_id="sc2p-id-1")
    device.__class__ = SHCShutterContact2Plus
    device.sensitivity = VibrationSensorService.SensitivityState.MEDIUM

    session = _make_mock_session(shutter_contacts2=[device])
    entry = await _setup_entry(hass, session)
    assert entry.state.value == "loaded"

    state = hass.states.get("select.test_device_vibration_sensitivity")
    assert state is not None
    assert state.state == "MEDIUM"


async def test_vibration_sensitivity_select_option(hass: HomeAssistant) -> None:
    """Selecting vibration sensitivity sets the device attribute."""
    device = _make_mock_device(serial="sc2p-1", device_id="sc2p-id-1")
    device.__class__ = SHCShutterContact2Plus
    device.sensitivity = VibrationSensorService.SensitivityState.MEDIUM

    session = _make_mock_session(shutter_contacts2=[device])
    await _setup_entry(hass, session)

    await _select_option(hass, "select.test_device_vibration_sensitivity", "HIGH")

    assert device.sensitivity == VibrationSensorService.SensitivityState.HIGH


async def test_vibration_sensitivity_skipped_for_non_plus(hass: HomeAssistant) -> None:
    """Vibration sensitivity not created for plain ShutterContact2."""
    device = _make_mock_device(serial="sc2-1", device_id="sc2-id-1")
    device.__class__ = SHCShutterContact2

    session = _make_mock_session(shutter_contacts2=[device])
    await _setup_entry(hass, session)

    assert hass.states.get("select.test_device_vibration_sensitivity") is None


# ---------------------------------------------------------------------------
# State after power outage
# ---------------------------------------------------------------------------


async def test_state_after_power_outage_created(hass: HomeAssistant) -> None:
    """State-after-power-outage select created for smart plugs."""
    device = _make_mock_device(serial="plug-1", device_id="plug-id-1")
    device.supports_power_switch_configuration = True
    device.state_after_power_outage = (
        PowerSwitchConfigurationService.StateAfterPowerOutage.OFF
    )

    session = _make_mock_session(smart_plugs=[device])
    entry = await _setup_entry(hass, session)
    assert entry.state.value == "loaded"

    state = hass.states.get("select.test_device_state_after_power_outage")
    assert state is not None
    assert state.state == "OFF"


async def test_state_after_power_outage_select_option(hass: HomeAssistant) -> None:
    """Selecting state-after-power-outage sets the device attribute."""
    device = _make_mock_device(serial="plug-1", device_id="plug-id-1")
    device.supports_power_switch_configuration = True
    device.state_after_power_outage = (
        PowerSwitchConfigurationService.StateAfterPowerOutage.OFF
    )

    session = _make_mock_session(smart_plugs=[device])
    await _setup_entry(hass, session)

    await _select_option(
        hass, "select.test_device_state_after_power_outage", "LAST_STATE"
    )

    assert (
        device.state_after_power_outage
        == PowerSwitchConfigurationService.StateAfterPowerOutage.LAST_STATE
    )


async def test_state_after_power_outage_compact_plug(hass: HomeAssistant) -> None:
    """State-after-power-outage select also created for compact smart plugs."""
    device = _make_mock_device(serial="plugc-1", device_id="plugc-id-1")
    device.supports_power_switch_configuration = True
    device.state_after_power_outage = (
        PowerSwitchConfigurationService.StateAfterPowerOutage.ON
    )

    session = _make_mock_session(smart_plugs_compact=[device])
    entry = await _setup_entry(hass, session)
    assert entry.state.value == "loaded"

    assert hass.states.get("select.test_device_state_after_power_outage") is not None


# ---------------------------------------------------------------------------
# Smoke sensitivity
# ---------------------------------------------------------------------------


async def test_smoke_sensitivity_smoke_detector(hass: HomeAssistant) -> None:
    """Smoke sensitivity select created for smoke detectors."""
    device = _make_mock_device(serial="sd-1", device_id="sd-id-1")
    device.supports_smoke_sensitivity = True
    device.smoke_sensitivity = SmokeSensitivityService.SmokeSensitivityLevel.MIDDLE

    session = _make_mock_session(smoke_detectors=[device])
    entry = await _setup_entry(hass, session)
    assert entry.state.value == "loaded"

    state = hass.states.get("select.test_device_smoke_sensitivity")
    assert state is not None
    assert state.state == "MIDDLE"


async def test_smoke_sensitivity_select_option(hass: HomeAssistant) -> None:
    """Selecting smoke sensitivity sets the device attribute."""
    device = _make_mock_device(serial="sd-1", device_id="sd-id-1")
    device.supports_smoke_sensitivity = True
    device.smoke_sensitivity = SmokeSensitivityService.SmokeSensitivityLevel.MIDDLE

    session = _make_mock_session(smoke_detectors=[device])
    await _setup_entry(hass, session)

    await _select_option(hass, "select.test_device_smoke_sensitivity", "HIGH")

    assert (
        device.smoke_sensitivity == SmokeSensitivityService.SmokeSensitivityLevel.HIGH
    )


async def test_smoke_sensitivity_twinguard(hass: HomeAssistant) -> None:
    """Smoke sensitivity select created for Twinguard."""
    device = _make_mock_device(serial="tg-1", device_id="tg-id-1")
    device.supports_smoke_sensitivity = True
    device.smoke_sensitivity = SmokeSensitivityService.SmokeSensitivityLevel.LOW

    session = _make_mock_session(twinguards=[device])
    entry = await _setup_entry(hass, session)
    assert entry.state.value == "loaded"

    assert hass.states.get("select.test_device_smoke_sensitivity") is not None


# ---------------------------------------------------------------------------
# Display direction
# ---------------------------------------------------------------------------


async def test_display_direction_created(hass: HomeAssistant) -> None:
    """Display direction select created when thermostat supports it."""
    device = _make_mock_device(serial="trv-1", device_id="trv-id-1")
    device.supports_display_direction = True
    device.display_direction = DisplayDirection.Direction.NORMAL
    device.supports_displayed_temperature = False
    device.supports_wall_thermostat_configuration = False
    device.supports_terminal_configuration = False

    session = _make_mock_session(thermostats=[device])
    entry = await _setup_entry(hass, session)
    assert entry.state.value == "loaded"

    state = hass.states.get("select.test_device_display_direction")
    assert state is not None
    assert state.state == "NORMAL"


async def test_display_direction_select_option(hass: HomeAssistant) -> None:
    """Selecting display direction sets the device attribute."""
    device = _make_mock_device(serial="trv-1", device_id="trv-id-1")
    device.supports_display_direction = True
    device.display_direction = DisplayDirection.Direction.NORMAL
    device.supports_displayed_temperature = False
    device.supports_wall_thermostat_configuration = False
    device.supports_terminal_configuration = False

    session = _make_mock_session(thermostats=[device])
    await _setup_entry(hass, session)

    await _select_option(hass, "select.test_device_display_direction", "REVERSED")

    assert device.display_direction == DisplayDirection.Direction.REVERSED


# ---------------------------------------------------------------------------
# Displayed temperature
# ---------------------------------------------------------------------------


async def test_displayed_temperature_created(hass: HomeAssistant) -> None:
    """Displayed temperature select created when thermostat supports it."""
    device = _make_mock_device(serial="trv-2", device_id="trv-id-2")
    device.supports_display_direction = False
    device.supports_displayed_temperature = True
    device.displayed_temperature = (
        DisplayedTemperatureConfiguration.DisplayedTemperature.SETPOINT
    )
    device.supports_wall_thermostat_configuration = False
    device.supports_terminal_configuration = False

    session = _make_mock_session(thermostats=[device])
    entry = await _setup_entry(hass, session)
    assert entry.state.value == "loaded"

    state = hass.states.get("select.test_device_displayed_temperature")
    assert state is not None
    assert state.state == "SETPOINT"


async def test_displayed_temperature_select_option(hass: HomeAssistant) -> None:
    """Selecting displayed temperature sets the device attribute."""
    device = _make_mock_device(serial="trv-2", device_id="trv-id-2")
    device.supports_display_direction = False
    device.supports_displayed_temperature = True
    device.displayed_temperature = (
        DisplayedTemperatureConfiguration.DisplayedTemperature.SETPOINT
    )
    device.supports_wall_thermostat_configuration = False
    device.supports_terminal_configuration = False

    session = _make_mock_session(thermostats=[device])
    await _setup_entry(hass, session)

    await _select_option(hass, "select.test_device_displayed_temperature", "MEASURED")

    assert (
        device.displayed_temperature
        == DisplayedTemperatureConfiguration.DisplayedTemperature.MEASURED
    )


# ---------------------------------------------------------------------------
# Valve type and heater type
# ---------------------------------------------------------------------------


async def test_valve_and_heater_type_created(hass: HomeAssistant) -> None:
    """Valve type and heater type selects created for supported thermostat."""
    device = _make_mock_device(serial="trv-3", device_id="trv-id-3")
    device.supports_display_direction = False
    device.supports_displayed_temperature = False
    device.supports_wall_thermostat_configuration = True
    device.valve_type = WallThermostatConfiguration.ValveType.NORMALLY_CLOSE
    device.heater_type = WallThermostatConfiguration.HeaterType.RADIATOR
    device.supports_terminal_configuration = False

    session = _make_mock_session(thermostats=[device])
    entry = await _setup_entry(hass, session)
    assert entry.state.value == "loaded"

    valve_state = hass.states.get("select.test_device_valve_type")
    heater_state = hass.states.get("select.test_device_heater_type")
    assert valve_state is not None
    assert valve_state.state == "NORMALLY_CLOSE"
    assert heater_state is not None
    assert heater_state.state == "RADIATOR"


async def test_valve_type_select_option(hass: HomeAssistant) -> None:
    """Selecting valve type sets the device attribute."""
    device = _make_mock_device(serial="trv-3", device_id="trv-id-3")
    device.supports_display_direction = False
    device.supports_displayed_temperature = False
    device.supports_wall_thermostat_configuration = True
    device.valve_type = WallThermostatConfiguration.ValveType.NORMALLY_CLOSE
    device.heater_type = None
    device.supports_terminal_configuration = False

    session = _make_mock_session(thermostats=[device])
    await _setup_entry(hass, session)

    await _select_option(hass, "select.test_device_valve_type", "NORMALLY_OPEN")

    assert device.valve_type == WallThermostatConfiguration.ValveType.NORMALLY_OPEN


# ---------------------------------------------------------------------------
# Terminal type (RoomThermostat2 only)
# ---------------------------------------------------------------------------


async def test_terminal_type_created_for_roomthermostat(hass: HomeAssistant) -> None:
    """Terminal type select created for RoomThermostat2."""
    device = _make_mock_device(serial="rth-1", device_id="rth-id-1")
    device.__class__ = SHCRoomThermostat2
    device.supports_display_direction = False
    device.supports_displayed_temperature = False
    device.supports_wall_thermostat_configuration = False
    device.supports_terminal_configuration = True
    device.terminal_type = TerminalConfiguration.Type.NOT_CONNECTED

    session = _make_mock_session(roomthermostats=[device])
    entry = await _setup_entry(hass, session)
    assert entry.state.value == "loaded"

    state = hass.states.get("select.test_device_terminal_type")
    assert state is not None
    assert state.state == "NOT_CONNECTED"


async def test_terminal_type_select_option(hass: HomeAssistant) -> None:
    """Selecting terminal type sets the device attribute."""
    device = _make_mock_device(serial="rth-1", device_id="rth-id-1")
    device.__class__ = SHCRoomThermostat2
    device.supports_display_direction = False
    device.supports_displayed_temperature = False
    device.supports_wall_thermostat_configuration = False
    device.supports_terminal_configuration = True
    device.terminal_type = TerminalConfiguration.Type.NOT_CONNECTED

    session = _make_mock_session(roomthermostats=[device])
    await _setup_entry(hass, session)

    await _select_option(
        hass,
        "select.test_device_terminal_type",
        "FLOOR_SENSOR_CONNECTED",
    )

    assert device.terminal_type == TerminalConfiguration.Type.FLOOR_SENSOR_CONNECTED


# ---------------------------------------------------------------------------
# Switch configuration (switch type, actuator type, output mode)
# ---------------------------------------------------------------------------


async def test_switch_config_selects_created(hass: HomeAssistant) -> None:
    """Switch type, actuator type, output mode selects created for micromodule relay."""
    device = _make_mock_device(serial="relay-1", device_id="relay-id-1")
    device.supports_switch_configuration = True
    device.switch_type = SwitchConfiguration.SwitchType.PUSHBUTTON
    device.actuator_type = SwitchConfiguration.ActuatorType.NORMALLY_OPEN
    device.output_mode = SwitchConfiguration.OutputMode.ATTACHED

    session = _make_mock_session(micromodule_relays=[device])
    entry = await _setup_entry(hass, session)
    assert entry.state.value == "loaded"

    assert hass.states.get("select.test_device_switch_type").state == "PUSHBUTTON"
    assert hass.states.get("select.test_device_actuator_type").state == "NORMALLY_OPEN"
    assert hass.states.get("select.test_device_output_mode").state == "ATTACHED"


async def test_switch_type_select_option(hass: HomeAssistant) -> None:
    """Selecting switch type sets the device attribute."""
    device = _make_mock_device(serial="relay-1", device_id="relay-id-1")
    device.supports_switch_configuration = True
    device.switch_type = SwitchConfiguration.SwitchType.PUSHBUTTON
    device.actuator_type = None
    device.output_mode = None

    session = _make_mock_session(micromodule_relays=[device])
    await _setup_entry(hass, session)

    await _select_option(hass, "select.test_device_switch_type", "SWITCH")

    assert device.switch_type == SwitchConfiguration.SwitchType.SWITCH


async def test_actuator_type_select_option(hass: HomeAssistant) -> None:
    """Selecting actuator type sets the device attribute."""
    device = _make_mock_device(serial="relay-2", device_id="relay-id-2")
    device.supports_switch_configuration = True
    device.switch_type = None
    device.actuator_type = SwitchConfiguration.ActuatorType.NORMALLY_OPEN
    device.output_mode = None

    session = _make_mock_session(micromodule_relays=[device])
    await _setup_entry(hass, session)

    await _select_option(hass, "select.test_device_actuator_type", "NORMALLY_CLOSED")

    assert device.actuator_type == SwitchConfiguration.ActuatorType.NORMALLY_CLOSED


async def test_output_mode_select_option(hass: HomeAssistant) -> None:
    """Selecting output mode sets the device attribute."""
    device = _make_mock_device(serial="relay-3", device_id="relay-id-3")
    device.supports_switch_configuration = True
    device.switch_type = None
    device.actuator_type = None
    device.output_mode = SwitchConfiguration.OutputMode.ATTACHED

    session = _make_mock_session(micromodule_relays=[device])
    await _setup_entry(hass, session)

    await _select_option(hass, "select.test_device_output_mode", "DETACHED")

    assert device.output_mode == SwitchConfiguration.OutputMode.DETACHED


async def test_switch_config_selects_for_light_control(hass: HomeAssistant) -> None:
    """Switch config selects also created for micromodule light controls."""
    device = _make_mock_device(serial="lc-1", device_id="lc-id-1")
    device.supports_switch_configuration = True
    device.switch_type = SwitchConfiguration.SwitchType.SWITCH
    device.actuator_type = None
    device.output_mode = None

    session = _make_mock_session(micromodule_light_controls=[device])
    entry = await _setup_entry(hass, session)
    assert entry.state.value == "loaded"

    assert hass.states.get("select.test_device_switch_type") is not None


async def test_no_selects_when_no_devices(hass: HomeAssistant) -> None:
    """No select entities when all device lists are empty."""
    session = _make_mock_session()
    entry = await _setup_entry(hass, session)
    assert entry.state.value == "loaded"

    select_states = [
        s for s in hass.states.async_all() if s.entity_id.startswith("select.")
    ]
    assert len(select_states) == 0
