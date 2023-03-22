"""Test basic initialization for the Legacy Nest API using mocks for the Nest python library."""
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from homeassistant.core import HomeAssistant

from .common import TEST_CONFIG_ENTRY_LEGACY, TEST_CONFIG_LEGACY

DOMAIN = "nest"


@pytest.fixture
def nest_test_config():
    """Fixture to specify the overall test fixture configuration."""
    return TEST_CONFIG_LEGACY


def make_thermostat():
    """Make a mock thermostat with dummy values."""
    device = MagicMock()
    type(device).device_id = PropertyMock(return_value="a.b.c.d.e.f.g")
    type(device).name = PropertyMock(return_value="My Thermostat")
    type(device).name_long = PropertyMock(return_value="My Thermostat")
    type(device).serial = PropertyMock(return_value="serial-number")
    type(device).mode = "off"
    type(device).hvac_state = "off"
    type(device).target = PropertyMock(return_value=31.0)
    type(device).temperature = PropertyMock(return_value=30.1)
    type(device).min_temperature = PropertyMock(return_value=10.0)
    type(device).max_temperature = PropertyMock(return_value=50.0)
    type(device).humidity = PropertyMock(return_value=40.4)
    type(device).software_version = PropertyMock(return_value="a.b.c")
    return device


@pytest.mark.parametrize(
    "nest_test_config", [TEST_CONFIG_LEGACY, TEST_CONFIG_ENTRY_LEGACY]
)
async def test_thermostat(hass: HomeAssistant, setup_base_platform) -> None:
    """Test simple initialization for thermostat entities."""

    thermostat = make_thermostat()

    structure = MagicMock()
    type(structure).name = PropertyMock(return_value="My Room")
    type(structure).thermostats = PropertyMock(return_value=[thermostat])
    type(structure).eta = PropertyMock(return_value="away")

    nest = MagicMock()
    type(nest).structures = PropertyMock(return_value=[structure])

    with patch("homeassistant.components.nest.legacy.Nest", return_value=nest), patch(
        "homeassistant.components.nest.legacy.sensor._VALID_SENSOR_TYPES",
        ["humidity", "temperature"],
    ), patch(
        "homeassistant.components.nest.legacy.binary_sensor._VALID_BINARY_SENSOR_TYPES",
        {"fan": None},
    ):
        await setup_base_platform()

    climate = hass.states.get("climate.my_thermostat")
    assert climate is not None
    assert climate.state == "off"

    temperature = hass.states.get("sensor.my_thermostat_temperature")
    assert temperature is not None
    assert temperature.state == "-1.1"

    humidity = hass.states.get("sensor.my_thermostat_humidity")
    assert humidity is not None
    assert humidity.state == "40.4"

    fan = hass.states.get("binary_sensor.my_thermostat_fan")
    assert fan is not None
    assert fan.state == "on"
