"""Tests for the Bosch SHC binary_sensor platform."""

from boschshcpy import ShutterContactService
import pytest

from homeassistant.core import HomeAssistant

from .conftest import setup_integration, shutter_contact_device

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "shutter_contacts": [
                shutter_contact_device(state=ShutterContactService.State.CLOSED)
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_shutter_contact_closed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A closed Shutter Contact is reported as off."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.shutter_contact")
    assert state is not None
    assert state.state == "off"


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "shutter_contacts": [
                shutter_contact_device(state=ShutterContactService.State.OPEN)
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_shutter_contact_open(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """An open Shutter Contact is reported as on."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.shutter_contact")
    assert state is not None
    assert state.state == "on"


@pytest.mark.parametrize(
    "device_buckets",
    [{"shutter_contacts": [shutter_contact_device(device_class="ENTRANCE_DOOR")]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_shutter_contact_device_class(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A Shutter Contact's device_class maps to the binary_sensor device class."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.shutter_contact")
    assert state is not None
    assert state.attributes["device_class"] == "door"
