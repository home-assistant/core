"""The tests for the TCP sensor platform."""
import logging

import homeassistant.components.ws980wifi.sensor as ws980wifi
from homeassistant.const import TEMP_CELSIUS

_LOGGER = logging.getLogger(__name__)


TEST_CONFIG = {
    "sensor": {
        "platform": "ws980wifi",
        "name": "test_name",
        "host": "test_host",
        "port": 12345,
        "timeout": 10,
        "monitored_conditions": {
            "inside_temperature",
            "outside_temperature",
            "inside_humidity",
        },
    }
}


def test_sensor_name(hass):
    """Check if name is set correct."""
    sensor = ws980wifi.WeatherSensor(
        "dummy", ["inside temperature", TEMP_CELSIUS, "°C", "7", "2", "10"]
    )
    assert sensor.name == "dummy inside temperature"


def test_sensor_unit_of_measurement(hass):
    """Check if unit of measurement is set correct."""
    sensor = ws980wifi.WeatherSensor(
        "dummy", ["inside temperature", TEMP_CELSIUS, "°C", "7", "2", "10"]
    )
    assert sensor.unit_of_measurement == "°C"


def test_sensor_state(hass):
    """Check if state is set correct, when update didn't triggert."""
    sensor = ws980wifi.WeatherSensor(
        "dummy", ["inside temperature", TEMP_CELSIUS, "°C", "7", "2", "10"]
    )
    assert sensor.state is None


def test_data_setup(hass):
    """Check if WeatherData is implement correltly."""
    sensor = ws980wifi.WeatherSensor(
        "dummy", ["inside temperature", TEMP_CELSIUS, "°C", "7", "2", "10"]
    )
    weather = ws980wifi.WeatherData(hass, [sensor], TEST_CONFIG["sensor"])
    assert isinstance(weather, ws980wifi.WeatherData)


async def test_data_updating_sensor(hass):
    """Check if updating sensor works correct."""
    sensor = ws980wifi.WeatherSensor(
        "dummy", ["inside temperature", TEMP_CELSIUS, "°C", "7", "2", "10"]
    )
    weather = ws980wifi.WeatherData(hass, [sensor], TEST_CONFIG["sensor"])
    await weather.updating_sensors(
        "ffff0b0050040100ef027fff037fff047fff057fff0607ff08aaaa0fff0bffff0cffff0e00000000100000000011000000001200000000130000000014000000001500ffffff16ffff17ffb2bf"
    )
    assert sensor.state == 23.9
