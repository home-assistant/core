"""Tests for the Bosch SHC select platform."""

from unittest.mock import MagicMock

from boschshcpy.services_impl import OutdoorSirenService, PirSensorConfigurationService
import pytest

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_SELECT_OPTION
from homeassistant.core import HomeAssistant

from .conftest import motion_detector2_device, outdoor_siren_device, setup_integration

from tests.common import MockConfigEntry

SOUND_LEVEL_ENTITY_ID = "select.outdoor_siren_siren_volume"
MOTION_SENSITIVITY_ENTITY_ID = "select.motion_detector_motion_sensitivity"


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
    device.siren.put_state_element.assert_called_once()
    key, config = device.siren.put_state_element.call_args.args
    assert key == "outdoorSirenConfiguration"
    assert config["soundLevel"] == OutdoorSirenService.SoundLevel.HIGH.value


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
