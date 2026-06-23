"""Tests for the Bosch SHC select platform."""

from unittest.mock import AsyncMock, MagicMock

from boschshcpy import SHCShutterContact2Plus
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

from homeassistant.components.bosch_shc.const import DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import make_device, setup_integration

from tests.common import MockConfigEntry

# ---------------------------------------------------------------------------
# MotionSensitivitySelect — motion_detectors2
# ---------------------------------------------------------------------------


async def test_motion_sensitivity_select_state_and_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """MotionSensitivitySelect is created for MD2 with motion_sensitivity attr."""
    device = make_device("md2-ms", "Motion Detector 2", status="AVAILABLE")
    device.motion_sensitivity = PirSensorConfigurationService.MotionSensitivity.HIGH

    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.motion_detector_2_motion_sensitivity")
    assert state is not None
    assert state.state == "HIGH"
    assert state.attributes["options"] == ["HIGH", "MIDDLE", "LOW"]


async def test_motion_sensitivity_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """async_select_option calls async_set_motion_sensitivity with the enum value."""
    device = make_device("md2-ms2", "Motion Detector 2 B", status="AVAILABLE")
    device.motion_sensitivity = PirSensorConfigurationService.MotionSensitivity.MIDDLE
    device.async_set_motion_sensitivity = AsyncMock()

    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.motion_detector_2_b_motion_sensitivity",
            "option": "LOW",
        },
        blocking=True,
    )
    device.async_set_motion_sensitivity.assert_awaited_once_with(
        PirSensorConfigurationService.MotionSensitivity.LOW
    )


async def test_motion_sensitivity_skipped_when_attr_absent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """MotionSensitivitySelect is NOT created when motion_sensitivity attr is absent."""
    device = make_device("md2-noms", "Motion Detector 2 NoMS", status="AVAILABLE")
    # Deleting the auto-created MagicMock attribute makes hasattr() return False,
    # which is exactly the condition select.py checks first.
    del device.motion_sensitivity

    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("select.motion_detector_2_noms_motion_sensitivity") is None


# ---------------------------------------------------------------------------
# OrientationLightResponseSelect — motion_detectors2
# ---------------------------------------------------------------------------


async def test_orientation_light_response_select_state_and_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """OrientationLightResponseSelect is created for MD2 with long_poll_interval."""
    device = make_device("md2-olr", "Motion Detector 2 OLR", status="AVAILABLE")
    device.long_poll_interval = PollControlService.PollControlState.LONG
    device.motion_sensitivity = PirSensorConfigurationService.MotionSensitivity.HIGH

    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(
        "select.motion_detector_2_olr_orientation_light_response_time"
    )
    assert state is not None
    assert state.state == "LONG"
    assert state.attributes["options"] == ["LONG", "SHORT"]


async def test_orientation_light_response_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """async_select_option calls async_set_long_poll_interval with correct enum."""
    device = make_device("md2-olr2", "Motion Detector 2 OLR2", status="AVAILABLE")
    device.long_poll_interval = PollControlService.PollControlState.LONG
    device.motion_sensitivity = PirSensorConfigurationService.MotionSensitivity.HIGH
    device.async_set_long_poll_interval = AsyncMock()

    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.motion_detector_2_olr2_orientation_light_response_time",
            "option": "SHORT",
        },
        blocking=True,
    )
    device.async_set_long_poll_interval.assert_awaited_once_with(
        PollControlService.PollControlState.SHORT
    )


async def test_orientation_light_response_skipped_when_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """OrientationLightResponseSelect is NOT created when long_poll_interval is None."""
    device = make_device("md2-noolr", "Motion Detector 2 NoOLR", status="AVAILABLE")
    device.long_poll_interval = None
    # motion_sensitivity missing → also no MotionSensitivity entity but that's fine
    type(device).motion_sensitivity = property(
        lambda self: (_ for _ in ()).throw(AttributeError("absent"))
    )

    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("select.motion_detector_2_noolr_orientation_light_response_time")
        is None
    )


async def test_orientation_light_response_unknown_value_returns_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """current_option returns None (unavailable) when value is UNKNOWN (not in options)."""
    device = make_device("md2-ukn", "Motion Detector 2 UKN", status="AVAILABLE")
    device.long_poll_interval = PollControlService.PollControlState.UNKNOWN
    type(device).motion_sensitivity = property(
        lambda self: (_ for _ in ()).throw(AttributeError("absent"))
    )

    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(
        "select.motion_detector_2_ukn_orientation_light_response_time"
    )
    assert state is not None
    # UNKNOWN is not in _attr_options → current_option returns None → state is "unknown"
    assert state.state in ("unknown", "unavailable")


# ---------------------------------------------------------------------------
# VibrationSensitivitySelect — shutter_contacts2 (SHCShutterContact2Plus only)
# ---------------------------------------------------------------------------


async def test_vibration_sensitivity_select_state_and_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """VibrationSensitivitySelect is created for SHCShutterContact2Plus devices."""
    device = MagicMock(spec=SHCShutterContact2Plus)
    device.id = "sc2plus-1"
    device.name = "Window Sensor Plus"
    device.serial = "sc2plus-1"
    device.root_device_id = "shc-root"
    device.device_model = "SHC_SC2PLUS"
    device.manufacturer = "BOSCH"
    device.deleted = False
    device.device_services = []
    device.room_id = "room-1"
    device.status = "AVAILABLE"
    device.sensitivity = VibrationSensorService.SensitivityState.HIGH

    mock_setup_dependencies.device_helper.shutter_contacts2 = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.window_sensor_plus_vibration_sensitivity")
    assert state is not None
    assert state.state == "HIGH"
    assert state.attributes["options"] == [
        "VERY_HIGH",
        "HIGH",
        "MEDIUM",
        "LOW",
        "VERY_LOW",
    ]


async def test_vibration_sensitivity_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """async_select_option calls async_set_sensitivity with correct enum value."""
    device = MagicMock(spec=SHCShutterContact2Plus)
    device.id = "sc2plus-2"
    device.name = "Window Sensor Plus B"
    device.serial = "sc2plus-2"
    device.root_device_id = "shc-root"
    device.device_model = "SHC_SC2PLUS"
    device.manufacturer = "BOSCH"
    device.deleted = False
    device.device_services = []
    device.room_id = "room-1"
    device.status = "AVAILABLE"
    device.sensitivity = VibrationSensorService.SensitivityState.MEDIUM
    device.async_set_sensitivity = AsyncMock()

    mock_setup_dependencies.device_helper.shutter_contacts2 = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.window_sensor_plus_b_vibration_sensitivity",
            "option": "LOW",
        },
        blocking=True,
    )
    device.async_set_sensitivity.assert_awaited_once_with(
        VibrationSensorService.SensitivityState.LOW
    )


async def test_vibration_sensitivity_skipped_for_non_plus(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """VibrationSensitivitySelect is NOT created for plain SHCShutterContact2 (not Plus)."""
    # A plain MagicMock (no SHCShutterContact2Plus spec) passes isinstance check = False.
    device = make_device("sc2-plain", "Plain Shutter Contact", status="AVAILABLE")
    device.sensitivity = VibrationSensorService.SensitivityState.LOW

    mock_setup_dependencies.device_helper.shutter_contacts2 = [device]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("select.plain_shutter_contact_vibration_sensitivity") is None


# ---------------------------------------------------------------------------
# StateAfterPowerOutageSelect — smart_plugs / smart_plugs_compact
# ---------------------------------------------------------------------------


async def test_state_after_power_outage_select_state_and_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """StateAfterPowerOutageSelect is created for smart plugs with the service."""
    device = make_device("plug-1", "Smart Plug", status="AVAILABLE")
    device.supports_power_switch_configuration = True
    device.state_after_power_outage = (
        PowerSwitchConfigurationService.StateAfterPowerOutage.LAST_STATE
    )

    mock_setup_dependencies.device_helper.smart_plugs = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.smart_plug_state_after_power_outage")
    assert state is not None
    assert state.state == "LAST_STATE"
    assert state.attributes["options"] == ["OFF", "ON", "LAST_STATE"]


async def test_state_after_power_outage_select_compact_plug(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """StateAfterPowerOutageSelect is also created for smart_plugs_compact."""
    device = make_device("plug-c1", "Smart Plug Compact", status="AVAILABLE")
    device.supports_power_switch_configuration = True
    device.state_after_power_outage = (
        PowerSwitchConfigurationService.StateAfterPowerOutage.OFF
    )

    mock_setup_dependencies.device_helper.smart_plugs_compact = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.smart_plug_compact_state_after_power_outage")
    assert state is not None
    assert state.state == "OFF"


async def test_state_after_power_outage_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """async_select_option sets state_after_power_outage to the mapped enum."""
    device = make_device("plug-2", "Smart Plug 2", status="AVAILABLE")
    device.supports_power_switch_configuration = True
    device.state_after_power_outage = (
        PowerSwitchConfigurationService.StateAfterPowerOutage.OFF
    )
    device.async_set_state_after_power_outage = AsyncMock()

    mock_setup_dependencies.device_helper.smart_plugs = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.smart_plug_2_state_after_power_outage",
            "option": "ON",
        },
        blocking=True,
    )
    device.async_set_state_after_power_outage.assert_awaited_once_with(
        PowerSwitchConfigurationService.StateAfterPowerOutage.ON
    )


async def test_state_after_power_outage_skipped_when_not_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Entity is NOT created when supports_power_switch_configuration is False."""
    device = make_device("plug-ns", "Smart Plug NS", status="AVAILABLE")
    device.supports_power_switch_configuration = False
    device.state_after_power_outage = (
        PowerSwitchConfigurationService.StateAfterPowerOutage.OFF
    )

    mock_setup_dependencies.device_helper.smart_plugs = [device]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("select.smart_plug_ns_state_after_power_outage") is None


async def test_state_after_power_outage_skipped_when_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Entity is NOT created when state_after_power_outage property is None."""
    device = make_device("plug-noneval", "Smart Plug None", status="AVAILABLE")
    device.supports_power_switch_configuration = True
    device.state_after_power_outage = None

    mock_setup_dependencies.device_helper.smart_plugs = [device]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("select.smart_plug_none_state_after_power_outage") is None


async def test_state_after_power_outage_unknown_value_returns_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """current_option returns None when UNKNOWN (not in options)."""
    device = make_device("plug-ukn", "Smart Plug UKN", status="AVAILABLE")
    device.supports_power_switch_configuration = True
    device.state_after_power_outage = (
        PowerSwitchConfigurationService.StateAfterPowerOutage.UNKNOWN
    )

    mock_setup_dependencies.device_helper.smart_plugs = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.smart_plug_ukn_state_after_power_outage")
    assert state is not None
    assert state.state in ("unknown", "unavailable")


# ---------------------------------------------------------------------------
# SmokeSensitivitySelect — smoke_detectors / twinguards
# ---------------------------------------------------------------------------


async def test_smoke_sensitivity_select_smoke_detector(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """SmokeSensitivitySelect is created for smoke_detectors with the service."""
    device = make_device("sd-1", "Smoke Detector", status="AVAILABLE")
    device.supports_smoke_sensitivity = True
    device.smoke_sensitivity = SmokeSensitivityService.SmokeSensitivityLevel.MIDDLE

    mock_setup_dependencies.device_helper.smoke_detectors = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.smoke_detector_smoke_sensitivity")
    assert state is not None
    assert state.state == "MIDDLE"
    assert state.attributes["options"] == ["HIGH", "MIDDLE", "LOW"]


async def test_smoke_sensitivity_select_twinguard(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """SmokeSensitivitySelect is also created for twinguards."""
    device = make_device("tg-1", "Twinguard", status="AVAILABLE")
    device.supports_smoke_sensitivity = True
    device.smoke_sensitivity = SmokeSensitivityService.SmokeSensitivityLevel.LOW

    mock_setup_dependencies.device_helper.twinguards = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.twinguard_smoke_sensitivity")
    assert state is not None
    assert state.state == "LOW"


async def test_smoke_sensitivity_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """async_select_option sets smoke_sensitivity to the mapped enum."""
    device = make_device("sd-2", "Smoke Detector 2", status="AVAILABLE")
    device.supports_smoke_sensitivity = True
    device.smoke_sensitivity = SmokeSensitivityService.SmokeSensitivityLevel.HIGH
    device.async_set_smoke_sensitivity = AsyncMock()

    mock_setup_dependencies.device_helper.smoke_detectors = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.smoke_detector_2_smoke_sensitivity",
            "option": "LOW",
        },
        blocking=True,
    )
    device.async_set_smoke_sensitivity.assert_awaited_once_with(
        SmokeSensitivityService.SmokeSensitivityLevel.LOW
    )


async def test_smoke_sensitivity_skipped_when_not_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """SmokeSensitivitySelect is NOT created when supports_smoke_sensitivity is False."""
    device = make_device("sd-ns", "Smoke Detector NS", status="AVAILABLE")
    device.supports_smoke_sensitivity = False
    device.smoke_sensitivity = SmokeSensitivityService.SmokeSensitivityLevel.HIGH

    mock_setup_dependencies.device_helper.smoke_detectors = [device]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("select.smoke_detector_ns_smoke_sensitivity") is None


# ---------------------------------------------------------------------------
# DisplayDirectionSelect — thermostats / roomthermostats
# ---------------------------------------------------------------------------


async def test_display_direction_select_state_and_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """DisplayDirectionSelect is created for thermostats supporting display_direction."""
    device = make_device("therm-1", "Thermostat Gen2", status="AVAILABLE")
    device.supports_display_direction = True
    device.display_direction = DisplayDirection.Direction.NORMAL
    # Ensure other thermostat selects don't fire
    device.supports_displayed_temperature = False
    device.supports_wall_thermostat_configuration = False
    device.supports_terminal_configuration = False
    # number.py SHCNumber requires real numeric values (offset entity always created).
    device.min_offset = -5.0
    device.max_offset = 5.0
    device.step_size = 0.5
    device.offset = 0.0
    device.supports_display_configuration = False

    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.thermostat_gen2_display_direction")
    assert state is not None
    assert state.state == "NORMAL"
    assert state.attributes["options"] == ["NORMAL", "REVERSED"]


async def test_display_direction_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """async_select_option sets display_direction to the mapped enum."""
    device = make_device("therm-dd", "Thermostat DD", status="AVAILABLE")
    device.supports_display_direction = True
    device.display_direction = DisplayDirection.Direction.NORMAL
    device.async_set_display_direction = AsyncMock()
    device.supports_displayed_temperature = False
    device.supports_wall_thermostat_configuration = False
    device.supports_terminal_configuration = False
    device.min_offset = -5.0
    device.max_offset = 5.0
    device.step_size = 0.5
    device.offset = 0.0
    device.supports_display_configuration = False

    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.thermostat_dd_display_direction",
            "option": "REVERSED",
        },
        blocking=True,
    )
    device.async_set_display_direction.assert_awaited_once_with(
        DisplayDirection.Direction.REVERSED
    )


async def test_display_direction_skipped_when_not_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """DisplayDirectionSelect is NOT created when supports_display_direction is False."""
    device = make_device("therm-nodd", "Thermostat NoDD", status="AVAILABLE")
    device.supports_display_direction = False
    device.supports_displayed_temperature = False
    device.supports_wall_thermostat_configuration = False
    device.supports_terminal_configuration = False
    device.min_offset = -5.0
    device.max_offset = 5.0
    device.step_size = 0.5
    device.offset = 0.0
    device.supports_display_configuration = False

    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("select.thermostat_nodd_display_direction") is None


# ---------------------------------------------------------------------------
# DisplayedTemperatureSelect — thermostats / roomthermostats
# ---------------------------------------------------------------------------


async def test_displayed_temperature_select_state_and_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """DisplayedTemperatureSelect is created for thermostats supporting displayed_temperature."""
    device = make_device("therm-dt", "Thermostat DT", status="AVAILABLE")
    device.supports_display_direction = False
    device.supports_displayed_temperature = True
    device.displayed_temperature = (
        DisplayedTemperatureConfiguration.DisplayedTemperature.SETPOINT
    )
    device.supports_wall_thermostat_configuration = False
    device.supports_terminal_configuration = False
    device.min_offset = -5.0
    device.max_offset = 5.0
    device.step_size = 0.5
    device.offset = 0.0
    device.supports_display_configuration = False

    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.thermostat_dt_displayed_temperature")
    assert state is not None
    assert state.state == "SETPOINT"
    assert state.attributes["options"] == ["SETPOINT", "MEASURED"]


async def test_displayed_temperature_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """async_select_option sets displayed_temperature to the mapped enum."""
    device = make_device("therm-dt2", "Thermostat DT2", status="AVAILABLE")
    device.supports_display_direction = False
    device.supports_displayed_temperature = True
    device.displayed_temperature = (
        DisplayedTemperatureConfiguration.DisplayedTemperature.SETPOINT
    )
    device.async_set_displayed_temperature = AsyncMock()
    device.supports_wall_thermostat_configuration = False
    device.supports_terminal_configuration = False
    device.min_offset = -5.0
    device.max_offset = 5.0
    device.step_size = 0.5
    device.offset = 0.0
    device.supports_display_configuration = False

    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.thermostat_dt2_displayed_temperature",
            "option": "MEASURED",
        },
        blocking=True,
    )
    device.async_set_displayed_temperature.assert_awaited_once_with(
        DisplayedTemperatureConfiguration.DisplayedTemperature.MEASURED
    )


async def test_displayed_temperature_roomthermostat(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """DisplayedTemperatureSelect is also created for roomthermostats."""
    device = make_device("rth-1", "Room Thermostat", status="AVAILABLE")
    device.supports_display_direction = False
    device.supports_displayed_temperature = True
    device.displayed_temperature = (
        DisplayedTemperatureConfiguration.DisplayedTemperature.MEASURED
    )
    device.supports_wall_thermostat_configuration = False
    device.supports_terminal_configuration = False
    device.min_offset = -5.0
    device.max_offset = 5.0
    device.step_size = 0.5
    device.offset = 0.0
    device.supports_display_configuration = False

    mock_setup_dependencies.device_helper.roomthermostats = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.room_thermostat_displayed_temperature")
    assert state is not None
    assert state.state == "MEASURED"


# ---------------------------------------------------------------------------
# ValveTypeSelect — thermostats / roomthermostats
# ---------------------------------------------------------------------------


async def test_valve_type_select_state_and_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """ValveTypeSelect is created for thermostats with wall_thermostat_configuration + valve_type."""
    device = make_device("therm-vt", "Thermostat VT", status="AVAILABLE")
    device.supports_display_direction = False
    device.supports_displayed_temperature = False
    device.supports_wall_thermostat_configuration = True
    device.valve_type = WallThermostatConfiguration.ValveType.NORMALLY_CLOSE
    device.heater_type = None  # no heater entity
    device.supports_terminal_configuration = False
    device.min_offset = -5.0
    device.max_offset = 5.0
    device.step_size = 0.5
    device.offset = 0.0
    device.supports_display_configuration = False

    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.thermostat_vt_valve_type")
    assert state is not None
    assert state.state == "NORMALLY_CLOSE"
    assert state.attributes["options"] == ["NORMALLY_CLOSE", "NORMALLY_OPEN"]


async def test_valve_type_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """async_select_option sets valve_type to the mapped enum."""
    device = make_device("therm-vt2", "Thermostat VT2", status="AVAILABLE")
    device.supports_display_direction = False
    device.supports_displayed_temperature = False
    device.supports_wall_thermostat_configuration = True
    device.valve_type = WallThermostatConfiguration.ValveType.NORMALLY_CLOSE
    device.async_set_valve_type = AsyncMock()
    device.heater_type = None
    device.supports_terminal_configuration = False
    device.min_offset = -5.0
    device.max_offset = 5.0
    device.step_size = 0.5
    device.offset = 0.0
    device.supports_display_configuration = False

    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.thermostat_vt2_valve_type",
            "option": "NORMALLY_OPEN",
        },
        blocking=True,
    )
    device.async_set_valve_type.assert_awaited_once_with(
        WallThermostatConfiguration.ValveType.NORMALLY_OPEN
    )


# ---------------------------------------------------------------------------
# HeaterTypeSelect — thermostats / roomthermostats
# ---------------------------------------------------------------------------


async def test_heater_type_select_state_and_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """HeaterTypeSelect is created for thermostats with wall_thermostat_configuration + heater_type."""
    device = make_device("therm-ht", "Thermostat HT", status="AVAILABLE")
    device.supports_display_direction = False
    device.supports_displayed_temperature = False
    device.supports_wall_thermostat_configuration = True
    device.valve_type = None  # no valve entity
    device.heater_type = WallThermostatConfiguration.HeaterType.RADIATOR
    device.supports_terminal_configuration = False
    device.min_offset = -5.0
    device.max_offset = 5.0
    device.step_size = 0.5
    device.offset = 0.0
    device.supports_display_configuration = False

    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.thermostat_ht_heater_type")
    assert state is not None
    assert state.state == "RADIATOR"
    assert state.attributes["options"] == [
        "FLOOR_HEATING",
        "FLOOR_HEATING_LOW_ENERGY",
        "RADIATOR",
        "CONVECTOR_PASSIVE",
        "CONVECTOR_ACTIVE",
    ]


async def test_heater_type_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """async_select_option sets heater_type to the mapped enum."""
    device = make_device("therm-ht2", "Thermostat HT2", status="AVAILABLE")
    device.supports_display_direction = False
    device.supports_displayed_temperature = False
    device.supports_wall_thermostat_configuration = True
    device.valve_type = None
    device.heater_type = WallThermostatConfiguration.HeaterType.RADIATOR
    device.async_set_heater_type = AsyncMock()
    device.supports_terminal_configuration = False
    device.min_offset = -5.0
    device.max_offset = 5.0
    device.step_size = 0.5
    device.offset = 0.0
    device.supports_display_configuration = False

    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.thermostat_ht2_heater_type",
            "option": "FLOOR_HEATING",
        },
        blocking=True,
    )
    device.async_set_heater_type.assert_awaited_once_with(
        WallThermostatConfiguration.HeaterType.FLOOR_HEATING
    )


# ---------------------------------------------------------------------------
# TerminalTypeSelect — thermostats / roomthermostats
# ---------------------------------------------------------------------------


async def test_terminal_type_select_state_and_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """TerminalTypeSelect is created for roomthermostats with terminal_configuration."""
    device = make_device("rth-tt", "Room Thermostat TT", status="AVAILABLE")
    device.supports_display_direction = False
    device.supports_displayed_temperature = False
    device.supports_wall_thermostat_configuration = False
    device.supports_terminal_configuration = True
    device.terminal_type = TerminalConfiguration.Type.NOT_CONNECTED
    device.min_offset = -5.0
    device.max_offset = 5.0
    device.step_size = 0.5
    device.offset = 0.0
    device.supports_display_configuration = False

    mock_setup_dependencies.device_helper.roomthermostats = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.room_thermostat_tt_terminal_type")
    assert state is not None
    assert state.state == "NOT_CONNECTED"
    assert "FLOOR_SENSOR_CONNECTED" in state.attributes["options"]
    assert "OUTDOOR_SENSOR_CONNECTED" in state.attributes["options"]


async def test_terminal_type_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """async_select_option sets terminal_type to the mapped enum."""
    device = make_device("rth-tt2", "Room Thermostat TT2", status="AVAILABLE")
    device.supports_display_direction = False
    device.supports_displayed_temperature = False
    device.supports_wall_thermostat_configuration = False
    device.supports_terminal_configuration = True
    device.terminal_type = TerminalConfiguration.Type.NOT_CONNECTED
    device.async_set_terminal_type = AsyncMock()
    device.min_offset = -5.0
    device.max_offset = 5.0
    device.step_size = 0.5
    device.offset = 0.0
    device.supports_display_configuration = False

    mock_setup_dependencies.device_helper.roomthermostats = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.room_thermostat_tt2_terminal_type",
            "option": "FLOOR_SENSOR_CONNECTED",
        },
        blocking=True,
    )
    device.async_set_terminal_type.assert_awaited_once_with(
        TerminalConfiguration.Type.FLOOR_SENSOR_CONNECTED
    )


async def test_terminal_type_skipped_when_not_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """TerminalTypeSelect is NOT created when supports_terminal_configuration is False."""
    device = make_device("rth-nott", "Room Thermostat NoTT", status="AVAILABLE")
    device.supports_display_direction = False
    device.supports_displayed_temperature = False
    device.supports_wall_thermostat_configuration = False
    device.supports_terminal_configuration = False
    device.min_offset = -5.0
    device.max_offset = 5.0
    device.step_size = 0.5
    device.offset = 0.0
    device.supports_display_configuration = False

    mock_setup_dependencies.device_helper.roomthermostats = [device]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("select.room_thermostat_nott_terminal_type") is None


# ---------------------------------------------------------------------------
# SwitchTypeSelect — micromodule_relays / micromodule_light_controls
# ---------------------------------------------------------------------------


async def test_switch_type_select_state_and_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """SwitchTypeSelect is created for micromodule_relays with switch_type."""
    device = make_device("relay-st", "Micromodule Relay", status="AVAILABLE")
    device.supports_switch_configuration = True
    device.switch_type = SwitchConfiguration.SwitchType.PUSHBUTTON
    device.actuator_type = None  # suppress other entities
    device.output_mode = None

    mock_setup_dependencies.device_helper.micromodule_relays = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.micromodule_relay_switch_type")
    assert state is not None
    assert state.state == "PUSHBUTTON"
    assert state.attributes["options"] == ["NONE", "PUSHBUTTON", "SWITCH", "NO_SWITCH"]


async def test_switch_type_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """async_select_option sets switch_type to the mapped enum."""
    device = make_device("relay-st2", "Micromodule Relay 2", status="AVAILABLE")
    device.supports_switch_configuration = True
    device.switch_type = SwitchConfiguration.SwitchType.PUSHBUTTON
    device.async_set_switch_type = AsyncMock()
    device.actuator_type = None
    device.output_mode = None

    mock_setup_dependencies.device_helper.micromodule_relays = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.micromodule_relay_2_switch_type",
            "option": "SWITCH",
        },
        blocking=True,
    )
    device.async_set_switch_type.assert_awaited_once_with(
        SwitchConfiguration.SwitchType.SWITCH
    )


async def test_switch_type_light_control(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """SwitchTypeSelect is also created for micromodule_light_controls."""
    device = make_device("lc-st", "Light Control", status="AVAILABLE")
    device.supports_switch_configuration = True
    device.switch_type = SwitchConfiguration.SwitchType.SWITCH
    device.actuator_type = None
    device.output_mode = None

    mock_setup_dependencies.device_helper.micromodule_light_controls = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.light_control_switch_type")
    assert state is not None
    assert state.state == "SWITCH"


# ---------------------------------------------------------------------------
# ActuatorTypeSelect — micromodule_relays / micromodule_light_controls
# ---------------------------------------------------------------------------


async def test_actuator_type_select_state_and_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """ActuatorTypeSelect is created for micromodule_relays with actuator_type."""
    device = make_device("relay-at", "Micromodule Relay AT", status="AVAILABLE")
    device.supports_switch_configuration = True
    device.switch_type = None
    device.actuator_type = SwitchConfiguration.ActuatorType.NORMALLY_CLOSED
    device.output_mode = None

    mock_setup_dependencies.device_helper.micromodule_relays = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.micromodule_relay_at_actuator_type")
    assert state is not None
    assert state.state == "NORMALLY_CLOSED"
    assert state.attributes["options"] == [
        "NORMALLY_CLOSED",
        "NORMALLY_OPEN",
        "UNSUPPORTED",
    ]


async def test_actuator_type_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """async_select_option sets actuator_type to the mapped enum."""
    device = make_device("relay-at2", "Micromodule Relay AT2", status="AVAILABLE")
    device.supports_switch_configuration = True
    device.switch_type = None
    device.actuator_type = SwitchConfiguration.ActuatorType.NORMALLY_CLOSED
    device.async_set_actuator_type = AsyncMock()
    device.output_mode = None

    mock_setup_dependencies.device_helper.micromodule_relays = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.micromodule_relay_at2_actuator_type",
            "option": "NORMALLY_OPEN",
        },
        blocking=True,
    )
    device.async_set_actuator_type.assert_awaited_once_with(
        SwitchConfiguration.ActuatorType.NORMALLY_OPEN
    )


# ---------------------------------------------------------------------------
# OutputModeSelect — micromodule_relays / micromodule_light_controls
# ---------------------------------------------------------------------------


async def test_output_mode_select_state_and_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """OutputModeSelect is created for micromodule_relays with output_mode."""
    device = make_device("relay-om", "Micromodule Relay OM", status="AVAILABLE")
    device.supports_switch_configuration = True
    device.switch_type = None
    device.actuator_type = None
    device.output_mode = SwitchConfiguration.OutputMode.ATTACHED

    mock_setup_dependencies.device_helper.micromodule_relays = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.micromodule_relay_om_output_mode")
    assert state is not None
    assert state.state == "ATTACHED"
    assert state.attributes["options"] == [
        "ATTACHED",
        "DETACHED",
        "DETACHED_SHORT_PRESS",
        "DETACHED_LONG_PRESS",
        "UNSUPPORTED",
    ]


async def test_output_mode_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """async_select_option sets output_mode to the mapped enum."""
    device = make_device("relay-om2", "Micromodule Relay OM2", status="AVAILABLE")
    device.supports_switch_configuration = True
    device.switch_type = None
    device.actuator_type = None
    device.output_mode = SwitchConfiguration.OutputMode.ATTACHED
    device.async_set_output_mode = AsyncMock()

    mock_setup_dependencies.device_helper.micromodule_relays = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.micromodule_relay_om2_output_mode",
            "option": "DETACHED",
        },
        blocking=True,
    )
    device.async_set_output_mode.assert_awaited_once_with(
        SwitchConfiguration.OutputMode.DETACHED
    )


async def test_output_mode_skipped_when_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """OutputModeSelect is NOT created when output_mode is None."""
    device = make_device("relay-om-none", "Micromodule Relay OM None", status="AVAILABLE")
    device.supports_switch_configuration = True
    device.switch_type = None
    device.actuator_type = None
    device.output_mode = None

    mock_setup_dependencies.device_helper.micromodule_relays = [device]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("select.micromodule_relay_om_none_output_mode") is None


# ---------------------------------------------------------------------------
# SmartSensitivitySecurityLevelSelect — motion_detectors2
# ---------------------------------------------------------------------------


async def test_smart_sensitivity_security_select_state_and_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """SmartSensitivitySecurityLevelSelect is created for MD2 with supports_smart_sensitivity."""
    ctx_security = SmartSensitivityControlService.SmartSensitivityContext.SECURITY
    ctx_comfort = SmartSensitivityControlService.SmartSensitivityContext.COMFORT

    device = make_device("md2-ss", "Motion Detector 2 SS", status="AVAILABLE")
    device.supports_smart_sensitivity = True

    def get_smart_sensitivity(ctx):
        if ctx == ctx_security:
            return {
                "manualLevel": SmartSensitivityControlService.MotionSensitivity.HIGH
            }
        if ctx == ctx_comfort:
            return {
                "manualLevel": SmartSensitivityControlService.MotionSensitivity.LOW
            }
        return None

    device.get_smart_sensitivity = get_smart_sensitivity
    # long_poll_interval absent → no OrientationLight entity
    device.long_poll_interval = None
    # motion_sensitivity absent → no MotionSensitivity entity
    type(device).motion_sensitivity = property(
        lambda self: (_ for _ in ()).throw(AttributeError("absent"))
    )

    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(
        "select.motion_detector_2_ss_smart_sensitivity_security_level"
    )
    assert state is not None
    assert state.state == "HIGH"
    assert state.attributes["options"] == ["HIGH", "MIDDLE", "LOW"]


async def test_smart_sensitivity_security_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """async_select_option calls async_set_smart_sensitivity_manual_level for SECURITY."""
    ctx_security = SmartSensitivityControlService.SmartSensitivityContext.SECURITY
    ctx_comfort = SmartSensitivityControlService.SmartSensitivityContext.COMFORT

    device = make_device("md2-ss2", "Motion Detector 2 SS2", status="AVAILABLE")
    device.supports_smart_sensitivity = True

    def get_smart_sensitivity(ctx):
        if ctx == ctx_security:
            return {
                "manualLevel": SmartSensitivityControlService.MotionSensitivity.HIGH
            }
        if ctx == ctx_comfort:
            return {
                "manualLevel": SmartSensitivityControlService.MotionSensitivity.LOW
            }
        return None

    device.get_smart_sensitivity = get_smart_sensitivity
    device.async_set_smart_sensitivity_manual_level = AsyncMock()
    device.long_poll_interval = None
    type(device).motion_sensitivity = property(
        lambda self: (_ for _ in ()).throw(AttributeError("absent"))
    )

    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.motion_detector_2_ss2_smart_sensitivity_security_level",
            "option": "MIDDLE",
        },
        blocking=True,
    )
    device.async_set_smart_sensitivity_manual_level.assert_awaited_once_with(
        SmartSensitivityControlService.SmartSensitivityContext.SECURITY,
        SmartSensitivityControlService.MotionSensitivity.MIDDLE,
    )


# ---------------------------------------------------------------------------
# SmartSensitivityComfortLevelSelect — motion_detectors2
# ---------------------------------------------------------------------------


async def test_smart_sensitivity_comfort_select_state_and_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """SmartSensitivityComfortLevelSelect is created alongside the security entity."""
    ctx_security = SmartSensitivityControlService.SmartSensitivityContext.SECURITY
    ctx_comfort = SmartSensitivityControlService.SmartSensitivityContext.COMFORT

    device = make_device("md2-sc", "Motion Detector 2 SC", status="AVAILABLE")
    device.supports_smart_sensitivity = True

    def get_smart_sensitivity(ctx):
        if ctx == ctx_security:
            return {
                "manualLevel": SmartSensitivityControlService.MotionSensitivity.MIDDLE
            }
        if ctx == ctx_comfort:
            return {
                "manualLevel": SmartSensitivityControlService.MotionSensitivity.LOW
            }
        return None

    device.get_smart_sensitivity = get_smart_sensitivity
    device.long_poll_interval = None
    type(device).motion_sensitivity = property(
        lambda self: (_ for _ in ()).throw(AttributeError("absent"))
    )

    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(
        "select.motion_detector_2_sc_smart_sensitivity_comfort_level"
    )
    assert state is not None
    assert state.state == "LOW"
    assert state.attributes["options"] == ["HIGH", "MIDDLE", "LOW"]


async def test_smart_sensitivity_comfort_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """async_select_option calls async_set_smart_sensitivity_manual_level for COMFORT."""
    ctx_security = SmartSensitivityControlService.SmartSensitivityContext.SECURITY
    ctx_comfort = SmartSensitivityControlService.SmartSensitivityContext.COMFORT

    device = make_device("md2-sc2", "Motion Detector 2 SC2", status="AVAILABLE")
    device.supports_smart_sensitivity = True

    def get_smart_sensitivity(ctx):
        if ctx == ctx_security:
            return {
                "manualLevel": SmartSensitivityControlService.MotionSensitivity.HIGH
            }
        if ctx == ctx_comfort:
            return {
                "manualLevel": SmartSensitivityControlService.MotionSensitivity.HIGH
            }
        return None

    device.get_smart_sensitivity = get_smart_sensitivity
    device.async_set_smart_sensitivity_manual_level = AsyncMock()
    device.long_poll_interval = None
    type(device).motion_sensitivity = property(
        lambda self: (_ for _ in ()).throw(AttributeError("absent"))
    )

    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.motion_detector_2_sc2_smart_sensitivity_comfort_level",
            "option": "LOW",
        },
        blocking=True,
    )
    device.async_set_smart_sensitivity_manual_level.assert_awaited_once_with(
        SmartSensitivityControlService.SmartSensitivityContext.COMFORT,
        SmartSensitivityControlService.MotionSensitivity.LOW,
    )


async def test_smart_sensitivity_skipped_when_get_smart_sensitivity_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Smart sensitivity selects are NOT created when get_smart_sensitivity is None."""
    device = make_device("md2-noss", "Motion Detector 2 NoSS", status="AVAILABLE")
    device.supports_smart_sensitivity = False
    device.get_smart_sensitivity = None
    device.long_poll_interval = None
    type(device).motion_sensitivity = property(
        lambda self: (_ for _ in ()).throw(AttributeError("absent"))
    )

    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get(
            "select.motion_detector_2_noss_smart_sensitivity_security_level"
        )
        is None
    )
    assert (
        hass.states.get(
            "select.motion_detector_2_noss_smart_sensitivity_comfort_level"
        )
        is None
    )


async def test_smart_sensitivity_comfort_none_manualLevel(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """current_option returns None when manualLevel is None."""
    device = make_device("md2-scnone", "Motion Detector 2 SCNone", status="AVAILABLE")
    device.supports_smart_sensitivity = True

    def get_smart_sensitivity(ctx):
        return {"manualLevel": None}

    device.get_smart_sensitivity = get_smart_sensitivity
    device.long_poll_interval = None
    type(device).motion_sensitivity = property(
        lambda self: (_ for _ in ()).throw(AttributeError("absent"))
    )

    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(
        "select.motion_detector_2_scnone_smart_sensitivity_comfort_level"
    )
    assert state is not None
    assert state.state in ("unknown", "unavailable")


# ---------------------------------------------------------------------------
# Device excluded from integration
# ---------------------------------------------------------------------------


async def test_excluded_device_creates_no_select(
    hass: HomeAssistant,
    mock_setup_dependencies: MagicMock,
) -> None:
    """An excluded device must not produce any select entity."""
    device = make_device("plug-excl", "Excluded Plug", status="AVAILABLE")
    device.supports_power_switch_configuration = True
    device.state_after_power_outage = (
        PowerSwitchConfigurationService.StateAfterPowerOutage.OFF
    )

    mock_setup_dependencies.device_helper.smart_plugs = [device]

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="shc012345",
        unique_id="test-mac",
        entry_id="01JE69BM3MA48YE6RH05A4MDKQ",
        data={
            "host": "1.1.1.1",
            "ssl_certificate": "/etc/bosch_shc/test-cert.pem",
            "ssl_key": "/etc/bosch_shc/test-key.pem",
            "token": "abc:test-mac",
            "hostname": "test-mac",
        },
        options={"excluded_devices": ["plug-excl"]},
    )
    await setup_integration(hass, entry)

    assert hass.states.get("select.excluded_plug_state_after_power_outage") is None


# ---------------------------------------------------------------------------
# Multiple selects on a single thermostat device
# ---------------------------------------------------------------------------


async def test_thermostat_all_selects(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """A fully featured ThermostatGen2 creates DisplayDirection + ValveType + HeaterType."""
    device = make_device("therm-full", "Thermostat Full", status="AVAILABLE")
    device.supports_display_direction = True
    device.display_direction = DisplayDirection.Direction.NORMAL
    device.supports_displayed_temperature = True
    device.displayed_temperature = (
        DisplayedTemperatureConfiguration.DisplayedTemperature.SETPOINT
    )
    device.supports_wall_thermostat_configuration = True
    device.valve_type = WallThermostatConfiguration.ValveType.NORMALLY_CLOSE
    device.heater_type = WallThermostatConfiguration.HeaterType.RADIATOR
    device.supports_terminal_configuration = False
    device.min_offset = -5.0
    device.max_offset = 5.0
    device.step_size = 0.5
    device.offset = 0.0
    device.supports_display_configuration = False

    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("select.thermostat_full_display_direction") is not None
    assert hass.states.get("select.thermostat_full_displayed_temperature") is not None
    assert hass.states.get("select.thermostat_full_valve_type") is not None
    assert hass.states.get("select.thermostat_full_heater_type") is not None
