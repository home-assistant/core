"""Tests for the Bosch SHC select platform."""

from unittest.mock import MagicMock

from boschshcpy.services_impl import OutdoorSirenService
import pytest

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_SELECT_OPTION
from homeassistant.core import HomeAssistant

from .conftest import outdoor_siren_device, setup_integration

from tests.common import MockConfigEntry

SOUND_LEVEL_ENTITY_ID = "select.outdoor_siren_siren_volume"


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
    device.siren.async_set_configuration.assert_awaited_once_with(
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
