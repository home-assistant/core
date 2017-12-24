"""The tests for the Canary sensor platform."""
import copy
import unittest
from unittest.mock import patch, Mock

from canary.api import SensorType
from homeassistant.components import canary as base_canary
from homeassistant.components.canary import DATA_CANARY
from homeassistant.components.sensor import canary
from homeassistant.components.sensor.canary import CanarySensor
from tests.common import (get_test_home_assistant)
from tests.components.test_canary import mock_device, mock_reading, \
    mock_location

VALID_CONFIG = {
    "canary": {
        "username": "foo@bar.org",
        "password": "bar",
    }
}


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
        """Test the sensor setup."""
        base_canary.setup(self.hass, self.config)

        online_device_at_home = mock_device(20, "Dining Room", True)
        offline_device_at_home = mock_device(21, "Front Yard", False)
        online_device_at_work = mock_device(22, "Office", True)

        self.hass.data[DATA_CANARY] = mock_canary()
        self.hass.data[DATA_CANARY].locations = [
            mock_location("Home", True, devices=[online_device_at_home,
                                                 offline_device_at_home]),
            mock_location("Work", True, devices=[online_device_at_work]),
        ]

        canary.setup_platform(self.hass, self.config, self.add_devices, None)

        self.assertEqual(6, len(self.DEVICES))

    def test_celsius_temperature_sensor(self):
        """Test temperature sensor with celsius."""
        device = mock_device(10, "Family Room")
        location = mock_location("Home", True)

        data = Mock()
        data.get_readings.return_value = [
            mock_reading(SensorType.TEMPERATURE, 21.1234)]

        sensor = CanarySensor(data, SensorType.TEMPERATURE, location, device)
        sensor.update()

        self.assertEqual("Home Family Room Temperature", sensor.name)
        self.assertEqual("sensor_canary_10_temperature", sensor.unique_id)
        self.assertEqual("°C", sensor.unit_of_measurement)
        self.assertEqual(21.1, sensor.state)

    def test_fahrenheit_temperature_sensor(self):
        """Test temperature sensor with fahrenheit."""
        device = mock_device(10, "Family Room")
        location = mock_location("Home", False)

        data = Mock()
        data.get_readings.return_value = [
            mock_reading(SensorType.TEMPERATURE, 21.1567)]

        sensor = CanarySensor(data, SensorType.TEMPERATURE, location, device)
        sensor.update()

        self.assertEqual("Home Family Room Temperature", sensor.name)
        self.assertEqual("°F", sensor.unit_of_measurement)
        self.assertEqual(21.2, sensor.state)

    def test_humidity_sensor(self):
        """Test humidity sensor."""
        device = mock_device(10, "Family Room")
        location = mock_location("Home")

        data = Mock()
        data.get_readings.return_value = [
            mock_reading(SensorType.HUMIDITY, 50.4567)]

        sensor = CanarySensor(data, SensorType.HUMIDITY, location, device)
        sensor.update()

        self.assertEqual("Home Family Room Humidity", sensor.name)
        self.assertEqual("%", sensor.unit_of_measurement)
        self.assertEqual(50.5, sensor.state)

    def test_air_quality_sensor(self):
        """Test air quality sensor."""
        device = mock_device(10, "Family Room")
        location = mock_location("Home")

        data = Mock()
        data.get_readings.return_value = [
            mock_reading(SensorType.AIR_QUALITY, 50.4567)]

        sensor = CanarySensor(data, SensorType.AIR_QUALITY, location, device)
        sensor.update()

        self.assertEqual("Home Family Room Air Quality", sensor.name)
        self.assertEqual("", sensor.unit_of_measurement)
        self.assertEqual(50.5, sensor.state)
