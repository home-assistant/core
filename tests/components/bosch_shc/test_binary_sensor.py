"""Tests for the Bosch SHC binary_sensor platform."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from boschshcpy import ShutterContactService
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant

from .conftest import climate_control_device, setup_integration, shutter_contact_device


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Restrict bosch_shc setup to the binary sensor platform."""
    with patch(
        "homeassistant.components.bosch_shc.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        yield


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


@pytest.mark.parametrize(
    ("device_kwargs", "entity_id", "expected"),
    [
        ({"has_demand": True}, "binary_sensor.room_climate_call_for_heat", STATE_ON),
        ({}, "binary_sensor.room_climate_call_for_heat", STATE_OFF),
        (
            {"has_demand": True, "supports_cooling": True, "cooling_mode": True},
            "binary_sensor.room_climate_call_for_heat",
            STATE_OFF,
        ),
        (
            {"setpoint_temperature_offset_active": True},
            "binary_sensor.room_climate_schedule_override_active",
            STATE_ON,
        ),
        ({"summer_mode": True}, "binary_sensor.room_climate_heating_break", STATE_ON),
        (
            {"ventilation_mode": True},
            "binary_sensor.room_climate_sustainable_ventilation",
            STATE_ON,
        ),
    ],
)
@pytest.mark.usefixtures("mock_session")
async def test_climate_control_binary_sensors(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_kwargs: dict[str, bool],
    entity_id: str,
    expected: str,
) -> None:
    """A room climate control exposes its demand and mode flags."""
    mock_session.device_helper.climate_controls = [
        climate_control_device(**device_kwargs)
    ]
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected
