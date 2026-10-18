"""Tests for the Bosch SHC select platform."""

from unittest.mock import MagicMock

from boschshcpy import SHCRoomThermostat2
from boschshcpy.services_impl import (
    DisplayDirection,
    DisplayedTemperatureConfiguration,
    OutdoorSirenService,
    PirSensorConfigurationService,
    SmokeSensitivityService,
    VibrationSensorService,
)
import pytest

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_SELECT_OPTION, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .conftest import (
    motion_detector2_device,
    outdoor_siren_device,
    setup_integration,
    shutter_contact2_device,
    shutter_contact2_plus_device,
    smoke_detector_device,
    thermostat_gen2_device,
)

from tests.common import MockConfigEntry

SOUND_LEVEL_ENTITY_ID = "select.outdoor_siren_siren_volume"
MOTION_SENSITIVITY_ENTITY_ID = "select.motion_detector_motion_sensitivity"
DISPLAY_DIRECTION_ENTITY_ID = "select.thermostat_gen2_display_orientation"
DISPLAYED_TEMPERATURE_ENTITY_ID = "select.thermostat_gen2_displayed_temperature"
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
