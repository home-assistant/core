"""Test Wallbox Switch component."""

import json
from unittest.mock import MagicMock

from homeassistant.components.wallbox import sensor
from homeassistant.components.wallbox.const import CONF_STATION, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.typing import HomeAssistantType

from tests.common import MockConfigEntry

entry = MockConfigEntry(
    domain=DOMAIN,
    data={
        CONF_USERNAME: "test_username",
        CONF_PASSWORD: "test_password",
        CONF_STATION: "12345",
    },
    entry_id="testEntry",
)

test_response = json.loads(
    '{"charging_power": 0,"max_available_power": 25,"charging_speed": 0,"added_range": 372,"added_energy": 44.697}'
)

test_response_rounding_error = json.loads(
    '{"charging_power": "XX","max_available_power": "xx","charging_speed": 0,"added_range": "xx","added_energy": "XX"}'
)


async def test_wallbox_sensor_class():
    """Test wallbox sensor class."""

    coordinator = MagicMock(return_value="connected")
    idx = 1
    ent = "charging_power"

    wallboxSensor = sensor.WallboxSensor(coordinator, idx, ent, entry)

    assert wallboxSensor.icon == "mdi:ev-station"
    assert wallboxSensor.unit_of_measurement == "kW"
    assert wallboxSensor.name == "Mock Title Charging Power"
    assert wallboxSensor.state


async def test_wallbox_updater(hass: HomeAssistantType):
    """Test wallbox updater."""
    wallbox = MagicMock(return_value=test_response)
    wallbox.get_data = MagicMock(return_value=test_response)
    await sensor.wallbox_updater(wallbox, hass)


async def test_wallbox_updater_rounding_error(hass: HomeAssistantType):
    """Test wallbox updater rounding error."""
    wallbox = MagicMock(return_value=test_response)
    wallbox.get_data = MagicMock(return_value=test_response_rounding_error)
    await sensor.wallbox_updater(wallbox, hass)
