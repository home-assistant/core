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

    def add_entities(self, devices, action):
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
        online_device_at_home = mock_device(20, "Dining Room", True, "Canary")
        offline_device_at_home = mock_device(21, "Front Yard", False, "Canary")
        online_device_at_work = mock_device(22, "Office", True, "Canary")

        self.hass.data[DATA_CANARY] = Mock()
        self.hass.data[DATA_CANARY].locations = [
            mock_location("Home", True, devices=[online_device_at_home,
                                                 offline_device_at_home]),
            mock_location("Work", True, devices=[online_device_at_work]),
        ]

        canary.setup_platform(self.hass, self.config, self.add_entities, None)

        assert 6 == len(self.DEVICES)

    def test_temperature_sensor(self):
        """Test temperature sensor with fahrenheit."""
        device = mock_device(10, "Family Room", "Canary")
        location = mock_location("Home", False)

        data = Mock()
        data.get_reading.return_value = 21.1234

        sensor = CanarySensor(data, SENSOR_TYPES[0], location, device)
        sensor.update()

        assert "Home Family Room Temperature" == sensor.name
        assert "°C" == sensor.unit_of_measurement
        assert 21.12 == sensor.state
        assert "mdi:thermometer" == sensor.icon

    def test_temperature_sensor_with_none_sensor_value(self):
        """Test temperature sensor with fahrenheit."""
        device = mock_device(10, "Family Room", "Canary")
        location = mock_location("Home", False)

        data = Mock()
        data.get_reading.return_value = None

        sensor = CanarySensor(data, SENSOR_TYPES[0], location, device)
        sensor.update()

        assert sensor.state is None

    def test_humidity_sensor(self):
        """Test humidity sensor."""
        device = mock_device(10, "Family Room", "Canary")
        location = mock_location("Home")

        data = Mock()
        data.get_reading.return_value = 50.4567

        sensor = CanarySensor(data, SENSOR_TYPES[1], location, device)
        sensor.update()

        assert "Home Family Room Humidity" == sensor.name
        assert "%" == sensor.unit_of_measurement
        assert 50.46 == sensor.state
        assert "mdi:water-percent" == sensor.icon

    def test_air_quality_sensor_with_very_abnormal_reading(self):
        """Test air quality sensor."""
        device = mock_device(10, "Family Room", "Canary")
        location = mock_location("Home")

        data = Mock()
        data.get_reading.return_value = 0.4

        sensor = CanarySensor(data, SENSOR_TYPES[2], location, device)
        sensor.update()

        assert "Home Family Room Air Quality" == sensor.name
        assert sensor.unit_of_measurement is None
        assert 0.4 == sensor.state
        assert "mdi:weather-windy" == sensor.icon

        air_quality = sensor.device_state_attributes[ATTR_AIR_QUALITY]
        assert STATE_AIR_QUALITY_VERY_ABNORMAL == air_quality

    def test_air_quality_sensor_with_abnormal_reading(self):
        """Test air quality sensor."""
        device = mock_device(10, "Family Room", "Canary")
        location = mock_location("Home")

        data = Mock()
        data.get_reading.return_value = 0.59

        sensor = CanarySensor(data, SENSOR_TYPES[2], location, device)
        sensor.update()

        assert "Home Family Room Air Quality" == sensor.name
        assert sensor.unit_of_measurement is None
        assert 0.59 == sensor.state
        assert "mdi:weather-windy" == sensor.icon

        air_quality = sensor.device_state_attributes[ATTR_AIR_QUALITY]
        assert STATE_AIR_QUALITY_ABNORMAL == air_quality

    def test_air_quality_sensor_with_normal_reading(self):
        """Test air quality sensor."""
        device = mock_device(10, "Family Room", "Canary")
        location = mock_location("Home")

        data = Mock()
        data.get_reading.return_value = 1.0

        sensor = CanarySensor(data, SENSOR_TYPES[2], location, device)
        sensor.update()

        assert "Home Family Room Air Quality" == sensor.name
        assert sensor.unit_of_measurement is None
        assert 1.0 == sensor.state
        assert "mdi:weather-windy" == sensor.icon

        air_quality = sensor.device_state_attributes[ATTR_AIR_QUALITY]
        assert STATE_AIR_QUALITY_NORMAL == air_quality

    def test_air_quality_sensor_with_none_sensor_value(self):
        """Test air quality sensor."""
        device = mock_device(10, "Family Room", "Canary")
        location = mock_location("Home")

        data = Mock()
        data.get_reading.return_value = None

        sensor = CanarySensor(data, SENSOR_TYPES[2], location, device)
        sensor.update()

        assert sensor.state is None
        assert sensor.device_state_attributes is None

    def test_battery_sensor(self):
        """Test battery sensor."""
        device = mock_device(10, "Family Room", "Canary Flex")
        location = mock_location("Home")

        data = Mock()
        data.get_reading.return_value = 70.4567

        sensor = CanarySensor(data, SENSOR_TYPES[4], location, device)
        sensor.update()

        assert "Home Family Room Battery" == sensor.name
        assert "%" == sensor.unit_of_measurement
        assert 70.46 == sensor.state
        assert "mdi:battery-70" == sensor.icon

    def test_wifi_sensor(self):
        """Test battery sensor."""
        device = mock_device(10, "Family Room", "Canary Flex")
        location = mock_location("Home")

        data = Mock()
        data.get_reading.return_value = -57

        sensor = CanarySensor(data, SENSOR_TYPES[3], location, device)
        sensor.update()

        assert "Home Family Room Wifi" == sensor.name
        assert "dBm" == sensor.unit_of_measurement
        assert -57 == sensor.state
        assert "mdi:wifi" == sensor.icon
