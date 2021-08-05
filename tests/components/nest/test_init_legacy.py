"""Test basic initialization for the Legacy Nest API using mocks for the Nest python library."""

import time
from unittest.mock import MagicMock, PropertyMock, patch

from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

DOMAIN = "nest"

CONFIG = {
    "nest": {
        "client_id": "some-client-id",
        "client_secret": "some-client-secret",
    },
}

CONFIG_ENTRY_DATA = {
    "auth_implementation": "local",
    "tokens": {
        "expires_at": time.time() + 86400,
        "access_token": {
            "token": "some-token",
        },
    },
}


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


async def test_thermostat(hass):
    """Test simple initialization for thermostat entities."""

    thermostat = make_thermostat()

    structure = MagicMock()
    type(structure).name = PropertyMock(return_value="My Room")
    type(structure).thermostats = PropertyMock(return_value=[thermostat])
    type(structure).eta = PropertyMock(return_value="away")

    nest = MagicMock()
    type(nest).structures = PropertyMock(return_value=[structure])

    config_entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_ENTRY_DATA)
    config_entry.add_to_hass(hass)
    with patch("homeassistant.components.nest.legacy.Nest", return_value=nest), patch(
        "homeassistant.components.nest.legacy.sensor._VALID_SENSOR_TYPES",
        ["humidity", "temperature"],
    ), patch(
        "homeassistant.components.nest.legacy.binary_sensor._VALID_BINARY_SENSOR_TYPES",
        {"fan": None},
    ):
        assert await async_setup_component(hass, DOMAIN, CONFIG)
        await hass.async_block_till_done()

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
