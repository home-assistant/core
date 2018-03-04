"""The tests for the Canary sensor platform."""
import copy
import unittest
from unittest.mock import Mock

from homeassistant.components.canary import DATA_CANARY
from homeassistant.components.sensor import canary
from homeassistant.components.sensor.canary import CanarySensor, \
    SENSOR_TYPES, ATTR_AIR_QUALITY, STATE_AIR_QUALITY_NORMAL, \
    STATE_AIR_QUALITY_ABNORMAL, STATE_AIR_QUALITY_VERY_ABNORMAL
from tests.common import (get_test_home_assistant)
from tests.components.test_canary import mock_device, mock_location

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

    def test_setup_sensors(self):
        """Test the sensor setup."""
        online_device_at_home = mock_device(20, "Dining Room", True)
        offline_device_at_home = mock_device(21, "Front Yard", False)
        online_device_at_work = mock_device(22, "Office", True)

        self.hass.data[DATA_CANARY] = Mock()
        self.hass.data[DATA_CANARY].locations = [
            mock_location("Home", True, devices=[online_device_at_home,
                                                 offline_device_at_home]),
            mock_location("Work", True, devices=[online_device_at_work]),
        ]

        canary.setup_platform(self.hass, self.config, self.add_devices, None)

        self.assertEqual(6, len(self.DEVICES))

    def test_temperature_sensor(self):
        """Test temperature sensor with fahrenheit."""
        device = mock_device(10, "Family Room")
        location = mock_location("Home", False)

        data = Mock()
        data.get_reading.return_value = 21.1234

        sensor = CanarySensor(data, SENSOR_TYPES[0], location, device)
        sensor.update()

        self.assertEqual("Home Family Room Temperature", sensor.name)
        self.assertEqual("°C", sensor.unit_of_measurement)
        self.assertEqual(21.12, sensor.state)

    def test_temperature_sensor_with_none_sensor_value(self):
        """Test temperature sensor with fahrenheit."""
        device = mock_device(10, "Family Room")
        location = mock_location("Home", False)

        data = Mock()
        data.get_reading.return_value = None

        sensor = CanarySensor(data, SENSOR_TYPES[0], location, device)
        sensor.update()

        self.assertEqual(None, sensor.state)

    def test_humidity_sensor(self):
        """Test humidity sensor."""
        device = mock_device(10, "Family Room")
        location = mock_location("Home")

        data = Mock()
        data.get_reading.return_value = 50.4567

        sensor = CanarySensor(data, SENSOR_TYPES[1], location, device)
        sensor.update()

        self.assertEqual("Home Family Room Humidity", sensor.name)
        self.assertEqual("%", sensor.unit_of_measurement)
        self.assertEqual(50.46, sensor.state)

    def test_air_quality_sensor_with_very_abnormal_reading(self):
        """Test air quality sensor."""
        device = mock_device(10, "Family Room")
        location = mock_location("Home")

        data = Mock()
        data.get_reading.return_value = 0.4

        sensor = CanarySensor(data, SENSOR_TYPES[2], location, device)
        sensor.update()

        self.assertEqual("Home Family Room Air Quality", sensor.name)
        self.assertEqual(None, sensor.unit_of_measurement)
        self.assertEqual(0.4, sensor.state)

        air_quality = sensor.device_state_attributes[ATTR_AIR_QUALITY]
        self.assertEqual(STATE_AIR_QUALITY_VERY_ABNORMAL, air_quality)

    def test_air_quality_sensor_with_abnormal_reading(self):
        """Test air quality sensor."""
        device = mock_device(10, "Family Room")
        location = mock_location("Home")

        data = Mock()
        data.get_reading.return_value = 0.59

        sensor = CanarySensor(data, SENSOR_TYPES[2], location, device)
        sensor.update()

        self.assertEqual("Home Family Room Air Quality", sensor.name)
        self.assertEqual(None, sensor.unit_of_measurement)
        self.assertEqual(0.59, sensor.state)

        air_quality = sensor.device_state_attributes[ATTR_AIR_QUALITY]
        self.assertEqual(STATE_AIR_QUALITY_ABNORMAL, air_quality)

    def test_air_quality_sensor_with_normal_reading(self):
        """Test air quality sensor."""
        device = mock_device(10, "Family Room")
        location = mock_location("Home")

        data = Mock()
        data.get_reading.return_value = 1.0

        sensor = CanarySensor(data, SENSOR_TYPES[2], location, device)
        sensor.update()

        self.assertEqual("Home Family Room Air Quality", sensor.name)
        self.assertEqual(None, sensor.unit_of_measurement)
        self.assertEqual(1.0, sensor.state)

        air_quality = sensor.device_state_attributes[ATTR_AIR_QUALITY]
        self.assertEqual(STATE_AIR_QUALITY_NORMAL, air_quality)

    def test_air_quality_sensor_with_none_sensor_value(self):
        """Test air quality sensor."""
        device = mock_device(10, "Family Room")
        location = mock_location("Home")

        data = Mock()
        data.get_reading.return_value = None

        sensor = CanarySensor(data, SENSOR_TYPES[2], location, device)
        sensor.update()

        self.assertEqual(None, sensor.state)
        self.assertEqual(None, sensor.device_state_attributes)
