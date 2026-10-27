"""Tests for the Bosch SHC select platform."""

from unittest.mock import MagicMock

from boschshcpy import SHCRoomThermostat2
from boschshcpy.services_impl import (
    DisplayDirection,
    DisplayedTemperatureConfiguration,
    OutdoorSirenService,
    PirSensorConfigurationService,
    PowerSwitchConfigurationService,
    SmartSensitivityControlService,
    SmokeSensitivityService,
    SwitchConfiguration,
    TerminalConfiguration,
    VibrationSensorService,
    WallThermostatConfiguration,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_SELECT_OPTION, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .conftest import (
    micromodule_relay_device,
    motion_detector2_device,
    outdoor_siren_device,
    setup_integration,
    shutter_contact2_device,
    shutter_contact2_plus_device,
    smart_plug_compact_device,
    smart_plug_device,
    smoke_detector_device,
    thermostat_gen2_device,
)

SOUND_LEVEL_ENTITY_ID = "select.outdoor_siren_siren_volume"
MOTION_SENSITIVITY_ENTITY_ID = "select.motion_detector_motion_sensitivity"
DISPLAY_DIRECTION_ENTITY_ID = "select.thermostat_gen2_display_orientation"
DISPLAYED_TEMPERATURE_ENTITY_ID = "select.thermostat_gen2_displayed_temperature"
STATE_AFTER_OUTAGE_ENTITY_ID = "select.smart_plug_state_after_power_outage"
VALVE_TYPE_ENTITY_ID = "select.thermostat_gen2_valve_type"
HEATER_TYPE_ENTITY_ID = "select.thermostat_gen2_heater_type"
TERMINAL_TYPE_ENTITY_ID = "select.thermostat_gen2_sensor_connection"
SMOKE_SENSITIVITY_ENTITY_ID = "select.smoke_detector_smoke_sensitivity"
VIBRATION_SENSITIVITY_ENTITY_ID = "select.shutter_contact_vibration_sensitivity"


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "outdoor_sirens": [
                outdoor_siren_device(sound_level=OutdoorSirenService.SoundLevel.MEDIUM)
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_outdoor_siren_sound_level_current_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The Outdoor Siren's current sound level is reported."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(SOUND_LEVEL_ENTITY_ID)
    assert state is not None
    assert state.state == "medium"


@pytest.mark.parametrize(
    "device_buckets",
    [{"outdoor_sirens": [outdoor_siren_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_outdoor_siren_sound_level_select_option(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Selecting a sound level writes it to the device."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.outdoor_sirens[0]

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: SOUND_LEVEL_ENTITY_ID, "option": "high"},
        blocking=True,
    )
    device.siren.set_configuration.assert_called_once_with(
        sound_level=OutdoorSirenService.SoundLevel.HIGH
    )


@pytest.mark.parametrize(
    "device_buckets",
    [{"outdoor_sirens": [outdoor_siren_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_outdoor_siren_no_siren_service(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No select entity is created for a siren without the siren service."""
    mock_session.device_helper.outdoor_sirens[0].siren = None
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(SOUND_LEVEL_ENTITY_ID) is None


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "motion_detectors2": [
                motion_detector2_device(
                    motion_sensitivity=PirSensorConfigurationService.MotionSensitivity.LOW
                )
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_motion_sensitivity_current_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The Motion Detector II's current motion sensitivity is reported."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(MOTION_SENSITIVITY_ENTITY_ID)
    assert state is not None
    assert state.state == "low"


@pytest.mark.parametrize(
    "device_buckets",
    [{"motion_detectors2": [motion_detector2_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_motion_sensitivity_select_option(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Selecting a motion sensitivity writes it to the device."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.motion_detectors2[0]

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: MOTION_SENSITIVITY_ENTITY_ID, "option": "high"},
        blocking=True,
    )
    assert (
        device.motion_sensitivity
        == PirSensorConfigurationService.MotionSensitivity.HIGH
    )


@pytest.mark.parametrize(
    "device_buckets",
    [{"motion_detectors2": [motion_detector2_device(motion_sensitivity=None)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_motion_sensitivity_not_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No select entity is created without the motion sensitivity service."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(MOTION_SENSITIVITY_ENTITY_ID) is None


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "shutter_contacts2": [
                shutter_contact2_plus_device(
                    sensitivity=VibrationSensorService.SensitivityState.VERY_LOW
                )
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_vibration_sensitivity_current_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The contact's current vibration sensitivity is reported."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(VIBRATION_SENSITIVITY_ENTITY_ID)
    assert state is not None
    assert state.state == "very_low"


@pytest.mark.parametrize(
    "device_buckets",
    [{"shutter_contacts2": [shutter_contact2_plus_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_vibration_sensitivity_select_option(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Selecting a vibration sensitivity writes it to the device."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.shutter_contacts2[0]

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: VIBRATION_SENSITIVITY_ENTITY_ID, "option": "very_high"},
        blocking=True,
    )
    assert device.sensitivity == VibrationSensorService.SensitivityState.VERY_HIGH


@pytest.mark.parametrize(
    "device_buckets",
    [{"shutter_contacts2": [shutter_contact2_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_vibration_sensitivity_not_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No select entity is created for a contact without a vibration sensor."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(VIBRATION_SENSITIVITY_ENTITY_ID) is None


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "smoke_detectors": [
                smoke_detector_device(
                    smoke_sensitivity=SmokeSensitivityService.SmokeSensitivityLevel.LOW
                )
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_smoke_sensitivity_current_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The Smoke Detector's current smoke sensitivity is reported."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(SMOKE_SENSITIVITY_ENTITY_ID)
    assert state is not None
    assert state.state == "low"


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "smoke_detectors": [
                smoke_detector_device(
                    smoke_sensitivity=SmokeSensitivityService.SmokeSensitivityLevel.LOW
                )
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_smoke_sensitivity_select_option(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Selecting a smoke sensitivity writes it to the device."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.smoke_detectors[0]

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: SMOKE_SENSITIVITY_ENTITY_ID, "option": "high"},
        blocking=True,
    )
    assert (
        device.smoke_sensitivity == SmokeSensitivityService.SmokeSensitivityLevel.HIGH
    )


@pytest.mark.parametrize(
    "device_buckets",
    [{"smoke_detectors": [smoke_detector_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_smoke_sensitivity_unsupported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No select is created without smoke sensitivity support."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(SMOKE_SENSITIVITY_ENTITY_ID) is None


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "thermostats": [
                thermostat_gen2_device(
                    display_direction=DisplayDirection.Direction.REVERSED,
                    displayed_temperature=DisplayedTemperatureConfiguration.DisplayedTemperature.MEASURED,
                )
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_thermostat_display_current_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The thermostat's display direction and shown temperature are reported."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(DISPLAY_DIRECTION_ENTITY_ID)
    assert state is not None
    assert state.state == "reversed"
    state = hass.states.get(DISPLAYED_TEMPERATURE_ENTITY_ID)
    assert state is not None
    assert state.state == "measured"


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "thermostats": [
                thermostat_gen2_device(
                    display_direction=DisplayDirection.Direction.NORMAL,
                    displayed_temperature=DisplayedTemperatureConfiguration.DisplayedTemperature.MEASURED,
                )
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_thermostat_display_select_options(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Selecting options writes them to the thermostat."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.thermostats[0]

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: DISPLAY_DIRECTION_ENTITY_ID, "option": "reversed"},
        blocking=True,
    )
    assert device.display_direction == DisplayDirection.Direction.REVERSED

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: DISPLAYED_TEMPERATURE_ENTITY_ID, "option": "setpoint"},
        blocking=True,
    )
    assert (
        device.displayed_temperature
        == DisplayedTemperatureConfiguration.DisplayedTemperature.SETPOINT
    )


@pytest.mark.parametrize(
    "device_buckets",
    [{"thermostats": [thermostat_gen2_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_thermostat_display_unsupported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No selects are created without display support."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(DISPLAY_DIRECTION_ENTITY_ID) is None
    assert hass.states.get(DISPLAYED_TEMPERATURE_ENTITY_ID) is None


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "thermostats": [
                thermostat_gen2_device(
                    supports_display_direction=True,
                    supports_displayed_temperature=True,
                )
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_thermostat_display_unknown_initial_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Supported display selects are created even without an initial value."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(DISPLAY_DIRECTION_ENTITY_ID).state == STATE_UNKNOWN
    assert hass.states.get(DISPLAYED_TEMPERATURE_ENTITY_ID).state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "roomthermostats": [
                thermostat_gen2_device(
                    spec=SHCRoomThermostat2,
                    display_direction=DisplayDirection.Direction.NORMAL,
                    displayed_temperature=DisplayedTemperatureConfiguration.DisplayedTemperature.SETPOINT,
                )
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_room_thermostat_2_display_selects(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Room Thermostat II gets the display selects and writes to the device."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.roomthermostats[0]
    entity_id = "select.thermostat_gen2_display_orientation"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "normal"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, "option": "reversed"},
        blocking=True,
    )
    assert device.display_direction == DisplayDirection.Direction.REVERSED
    assert hass.states.get(DISPLAYED_TEMPERATURE_ENTITY_ID) is not None


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "smart_plugs": [
                smart_plug_device(
                    state_after_power_outage=PowerSwitchConfigurationService.StateAfterPowerOutage.LAST_STATE
                )
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_state_after_power_outage_current_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The Smart Plug's state after a power outage is reported."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(STATE_AFTER_OUTAGE_ENTITY_ID)
    assert state is not None
    assert state.state == "last_state"


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "smart_plugs": [
                smart_plug_device(
                    state_after_power_outage=PowerSwitchConfigurationService.StateAfterPowerOutage.OFF
                )
            ],
            "smart_plugs_compact": [
                smart_plug_compact_device(
                    name="Smart Plug Compact",
                    state_after_power_outage=PowerSwitchConfigurationService.StateAfterPowerOutage.OFF,
                )
            ],
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_state_after_power_outage_select_option(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Selecting an option writes it to the plug and the compact plug."""
    await setup_integration(hass, mock_config_entry)

    for entity_id, device in (
        (STATE_AFTER_OUTAGE_ENTITY_ID, mock_session.device_helper.smart_plugs[0]),
        (
            "select.smart_plug_compact_state_after_power_outage",
            mock_session.device_helper.smart_plugs_compact[0],
        ),
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, "option": "on"},
            blocking=True,
        )
        assert (
            device.state_after_power_outage
            == PowerSwitchConfigurationService.StateAfterPowerOutage.ON
        )


@pytest.mark.parametrize(
    "device_buckets",
    [{"smart_plugs": [smart_plug_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_state_after_power_outage_unsupported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No select is created without power switch configuration support."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(STATE_AFTER_OUTAGE_ENTITY_ID) is None


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "thermostats": [
                thermostat_gen2_device(
                    valve_type=WallThermostatConfiguration.ValveType.NORMALLY_OPEN,
                    heater_type=WallThermostatConfiguration.HeaterType.RADIATOR,
                )
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_thermostat_valve_and_heater_type(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The valve and heater type are reported and written to the thermostat."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.thermostats[0]

    assert hass.states.get(VALVE_TYPE_ENTITY_ID).state == "normally_open"
    assert hass.states.get(HEATER_TYPE_ENTITY_ID).state == "radiator"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: VALVE_TYPE_ENTITY_ID, "option": "normally_close"},
        blocking=True,
    )
    assert device.valve_type == WallThermostatConfiguration.ValveType.NORMALLY_CLOSE

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: HEATER_TYPE_ENTITY_ID, "option": "floor_heating"},
        blocking=True,
    )
    assert device.heater_type == WallThermostatConfiguration.HeaterType.FLOOR_HEATING


@pytest.mark.parametrize(
    "device_buckets",
    [{"thermostats": [thermostat_gen2_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_thermostat_valve_and_heater_type_unsupported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No valve or heater type selects are created without wall thermostat support."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(VALVE_TYPE_ENTITY_ID) is None
    assert hass.states.get(HEATER_TYPE_ENTITY_ID) is None


SWITCH_TYPE_ENTITY_ID = "select.relay_switch_type"


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "micromodule_relays": [
                micromodule_relay_device(
                    supports_switch_configuration=True,
                    switch_type=SwitchConfiguration.SwitchType.PUSHBUTTON,
                )
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_relay_switch_type(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The relay switch type is reported and written to the device."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.micromodule_relays[0]

    assert hass.states.get(SWITCH_TYPE_ENTITY_ID).state == "pushbutton"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: SWITCH_TYPE_ENTITY_ID, "option": "switch"},
        blocking=True,
    )
    assert device.switch_type == SwitchConfiguration.SwitchType.SWITCH


@pytest.mark.parametrize(
    "device_buckets",
    [{"micromodule_relays": [micromodule_relay_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_relay_switch_type_unsupported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No switch type select is created without switch configuration support."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(SWITCH_TYPE_ENTITY_ID) is None


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "roomthermostats": [
                thermostat_gen2_device(
                    spec=SHCRoomThermostat2,
                    terminal_type=TerminalConfiguration.Type.NOT_CONNECTED,
                )
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_room_thermostat_terminal_type(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The terminal type is reported and written to the Room Thermostat II."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.roomthermostats[0]

    assert hass.states.get(TERMINAL_TYPE_ENTITY_ID).state == "not_connected"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: TERMINAL_TYPE_ENTITY_ID, "option": "outdoor_sensor_connected"},
        blocking=True,
    )
    assert device.terminal_type == TerminalConfiguration.Type.OUTDOOR_SENSOR_CONNECTED


@pytest.mark.parametrize(
    "device_buckets",
    [{"roomthermostats": [thermostat_gen2_device(spec=SHCRoomThermostat2)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_room_thermostat_terminal_type_unsupported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No terminal type select is created without terminal configuration support."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(TERMINAL_TYPE_ENTITY_ID) is None


ACTUATOR_TYPE_ENTITY_ID = "select.relay_actuator_type"


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "micromodule_relays": [
                micromodule_relay_device(
                    supports_switch_configuration=True,
                    actuator_type=SwitchConfiguration.ActuatorType.NORMALLY_CLOSED,
                )
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_relay_actuator_type(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The relay actuator type is reported and written to the device."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.micromodule_relays[0]

    assert hass.states.get(ACTUATOR_TYPE_ENTITY_ID).state == "normally_closed"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ACTUATOR_TYPE_ENTITY_ID, "option": "normally_open"},
        blocking=True,
    )
    assert device.actuator_type == SwitchConfiguration.ActuatorType.NORMALLY_OPEN


@pytest.mark.parametrize(
    "device_buckets",
    [{"micromodule_relays": [micromodule_relay_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_relay_actuator_type_unsupported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No actuator type select is created without switch configuration support."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ACTUATOR_TYPE_ENTITY_ID) is None


OUTPUT_MODE_ENTITY_ID = "select.relay_output_mode"


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "micromodule_relays": [
                micromodule_relay_device(
                    supports_switch_configuration=True,
                    output_mode=SwitchConfiguration.OutputMode.ATTACHED,
                )
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_relay_output_mode(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The relay output mode is reported and written to the device."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.micromodule_relays[0]

    assert hass.states.get(OUTPUT_MODE_ENTITY_ID).state == "attached"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: OUTPUT_MODE_ENTITY_ID, "option": "detached"},
        blocking=True,
    )
    assert device.output_mode == SwitchConfiguration.OutputMode.DETACHED


@pytest.mark.parametrize(
    "device_buckets",
    [{"micromodule_relays": [micromodule_relay_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_relay_output_mode_unsupported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No output mode select is created without switch configuration support."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(OUTPUT_MODE_ENTITY_ID) is None


SECURITY_LEVEL_ENTITY_ID = "select.motion_detector_sensitivity_for_alarm_system"
COMFORT_LEVEL_ENTITY_ID = "select.motion_detector_sensitivity_for_other_cases"


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "motion_detectors2": [
                motion_detector2_device(
                    supports_smart_sensitivity=True,
                    smart_sensitivity={"SECURITY": "HIGH", "COMFORT": "LOW"},
                )
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_smart_sensitivity_levels(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The smart sensitivity levels are reported and written per context."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.motion_detectors2[0]

    assert hass.states.get(SECURITY_LEVEL_ENTITY_ID).state == "high"
    assert hass.states.get(COMFORT_LEVEL_ENTITY_ID).state == "low"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: COMFORT_LEVEL_ENTITY_ID, "option": "middle"},
        blocking=True,
    )
    device.set_smart_sensitivity_manual_level.assert_called_once_with(
        SmartSensitivityControlService.SmartSensitivityContext.COMFORT,
        SmartSensitivityControlService.MotionSensitivity.MIDDLE,
    )


@pytest.mark.parametrize(
    "device_buckets",
    [{"motion_detectors2": [motion_detector2_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_smart_sensitivity_levels_unsupported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No smart sensitivity selects are created without support."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(SECURITY_LEVEL_ENTITY_ID) is None
    assert hass.states.get(COMFORT_LEVEL_ENTITY_ID) is None


@pytest.mark.parametrize(
    "device_buckets",
    [{"motion_detectors2": [motion_detector2_device(supports_smart_sensitivity=True)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_smart_sensitivity_levels_not_reported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The levels stay unknown while the controller reports none."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(SECURITY_LEVEL_ENTITY_ID).state == STATE_UNKNOWN
    assert hass.states.get(COMFORT_LEVEL_ENTITY_ID).state == STATE_UNKNOWN
