"""The tests for the Canary sensor platform."""
import copy
import unittest
from unittest.mock import patch, Mock, MagicMock, PropertyMock

from canary.api import SensorType, Reading
from homeassistant.components import canary as base_canary
from homeassistant.components.canary import DATA_CANARY
from homeassistant.components.sensor import canary
from homeassistant.components.sensor.canary import CanarySensor
from tests.common import (get_test_home_assistant)
from tests.components.test_canary import API_LOCATIONS

VALID_CONFIG = {
    "canary": {
        "username": "foo@bar.org",
        "password": "bar",
    }
}


def mock_device(device_id, name):
    device = MagicMock()
    type(device).device_id = PropertyMock(return_value=device_id)
    type(device).name = PropertyMock(return_value=name)
    return device


def mock_location(name, is_celsius=True):
    location = MagicMock()
    type(location).name = PropertyMock(return_value=name)
    type(location).is_celsius = PropertyMock(return_value=is_celsius)
    return location


class TestCanarySensorSetup(unittest.TestCase):
    """Test the Canary platform."""

    DEVICES = []

    def add_devices(self, devices, action):
        """Mock add devices."""
        for device in devices:
            self.DEVICES.append(device)

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.config = copy.deepcopy(VALID_CONFIG)

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch('homeassistant.components.canary.CanaryData')
    def test_setup_sensors(self, mock_canary):
        """Test the Canary senskor class and methods."""
        base_canary.setup(self.hass, self.config)

        self.hass.data[DATA_CANARY] = mock_canary()
        self.hass.data[DATA_CANARY].locations = API_LOCATIONS

        canary.setup_platform(self.hass, self.config, self.add_devices, None)

        self.assertEqual(6, len(self.DEVICES))

    def test_celsius_temperature_sensor(self):
        device = mock_device(10, "Family Room")
        location = mock_location("Home", True)

        data = Mock()
        data.get_readings.return_value = [Reading({
            "sensor_type": {"name": "temperature"},
            "value": 21.1234
        })]

        sensor = CanarySensor(data, SensorType.TEMPERATURE, location, device)
        sensor.update()

        self.assertEqual("Home Family Room Temperature", sensor.name)
        self.assertEqual("sensor_canary_10_temperature", sensor.unique_id)
        self.assertEqual("°C", sensor.unit_of_measurement)
        self.assertEqual(21.1, sensor.state)

    def test_fahrenheit_temperature_sensor(self):
        device = mock_device(10, "Family Room")
        location = mock_location("Home", False)

        data = Mock()
        data.get_readings.return_value = [Reading({
            "sensor_type": {"name": "temperature"},
            "value": 21.1567
        })]

        sensor = CanarySensor(data, SensorType.TEMPERATURE, location, device)
        sensor.update()

        self.assertEqual("Home Family Room Temperature", sensor.name)
        self.assertEqual("°F", sensor.unit_of_measurement)
        self.assertEqual(21.2, sensor.state)

    def test_humidity_sensor(self):
        device = mock_device(10, "Family Room")
        location = mock_location("Home")

        data = Mock()
        data.get_readings.return_value = [Reading({
            "sensor_type": {"name": "humidity"},
            "value": 50.4567
        })]

        sensor = CanarySensor(data, SensorType.HUMIDITY, location, device)
        sensor.update()

        self.assertEqual("Home Family Room Humidity", sensor.name)
        self.assertEqual("%", sensor.unit_of_measurement)
        self.assertEqual(50.5, sensor.state)

    def test_air_quality_sensor(self):
        device = mock_device(10, "Family Room")
        location = mock_location("Home")

        data = Mock()
        data.get_readings.return_value = [Reading({
            "sensor_type": {"name": "air_quality"},
            "value": 50.4567
        })]

        sensor = CanarySensor(data, SensorType.AIR_QUALITY, location, device)
        sensor.update()

        self.assertEqual("Home Family Room Air Quality", sensor.name)
        self.assertEqual("", sensor.unit_of_measurement)
        self.assertEqual(50.5, sensor.state)
