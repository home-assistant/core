"""Tests for the comfoconnect sensor platform."""
# import json
from unittest.mock import patch

import pytest

from homeassistant.components.sensor import DOMAIN
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component

COMPONENT = "comfoconnect"
VALID_CONFIG = {
    COMPONENT: {"host": "1.2.3.4"},
    DOMAIN: {
        "platform": COMPONENT,
        "resources": [
            "current_humidity",
            "current_temperature",
            "supply_fan_duty",
            "power_usage",
            "preheater_power_total",
        ],
    },
}


@pytest.fixture
def mock_bridge_discover():
    """Mock the bridge discover method."""
    with patch("pycomfoconnect.bridge.Bridge.discover") as mock_bridge_discover:
        mock_bridge_discover.return_value[0].uuid.hex.return_value = "00"
        yield mock_bridge_discover


@pytest.fixture
def mock_comfoconnect_command():
    """Mock the ComfoConnect connect method."""
    with patch(
        "pycomfoconnect.comfoconnect.ComfoConnect._command"
    ) as mock_comfoconnect_command:
        yield mock_comfoconnect_command


@pytest.fixture
async def setup_sensor(hass, mock_bridge_discover, mock_comfoconnect_command):
    """Set up demo sensor component."""
    with assert_setup_component(1, DOMAIN):
        await async_setup_component(hass, DOMAIN, VALID_CONFIG)
        await hass.async_block_till_done()


async def test_sensors(hass, setup_sensor):
    """Test the sensors."""
    state = hass.states.get("sensor.comfoairq_inside_humidity")
    assert state is not None

    assert state.name == "ComfoAirQ Inside Humidity"
    assert state.attributes.get("unit_of_measurement") == "%"
    assert state.attributes.get("device_class") == "humidity"
    assert state.attributes.get("icon") is None

    state = hass.states.get("sensor.comfoairq_inside_temperature")
    assert state is not None

    assert state.name == "ComfoAirQ Inside Temperature"
    assert state.attributes.get("unit_of_measurement") == "°C"
    assert state.attributes.get("device_class") == "temperature"
    assert state.attributes.get("icon") is None

    state = hass.states.get("sensor.comfoairq_supply_fan_duty")
    assert state is not None

    assert state.name == "ComfoAirQ Supply Fan Duty"
    assert state.attributes.get("unit_of_measurement") == "%"
    assert state.attributes.get("device_class") is None
    assert state.attributes.get("icon") == "mdi:fan"

    state = hass.states.get("sensor.comfoairq_power_usage")
    assert state is not None

    assert state.name == "ComfoAirQ Power usage"
    assert state.attributes.get("unit_of_measurement") == "W"
    assert state.attributes.get("device_class") == "power"
    assert state.attributes.get("icon") is None

    state = hass.states.get("sensor.comfoairq_preheater_power_total")
    assert state is not None

    assert state.name == "ComfoAirQ Preheater power total"
    assert state.attributes.get("unit_of_measurement") == "kWh"
    assert state.attributes.get("device_class") == "energy"
    assert state.attributes.get("icon") is None
