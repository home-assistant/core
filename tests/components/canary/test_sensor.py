"""The tests for the Canary sensor platform."""
import copy
import unittest
from unittest.mock import Mock

from homeassistant.components.canary import DATA_CANARY, sensor as canary
from homeassistant.components.canary.sensor import (
    ATTR_AIR_QUALITY,
    SENSOR_TYPES,
    STATE_AIR_QUALITY_ABNORMAL,
    STATE_AIR_QUALITY_NORMAL,
    STATE_AIR_QUALITY_VERY_ABNORMAL,
    CanarySensor,
)
from homeassistant.const import TEMP_CELSIUS, UNIT_PERCENTAGE

from tests.common import get_test_home_assistant
from tests.components.canary.test_init import mock_device, mock_location

VALID_CONFIG = {"canary": {"username": "foo@bar.org", "password": "bar"}}


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
        online_device_at_home = mock_device(20, "Dining Room", True, "Canary Pro")
        offline_device_at_home = mock_device(21, "Front Yard", False, "Canary Pro")
        online_device_at_work = mock_device(22, "Office", True, "Canary Pro")

        self.hass.data[DATA_CANARY] = Mock()
        self.hass.data[DATA_CANARY].locations = [
            mock_location(
                "Home", True, devices=[online_device_at_home, offline_device_at_home]
            ),
            mock_location("Work", True, devices=[online_device_at_work]),
        ]

        canary.setup_platform(self.hass, self.config, self.add_entities, None)

        assert len(self.DEVICES) == 6

    def test_temperature_sensor(self):
        """Test temperature sensor with fahrenheit."""
        device = mock_device(10, "Family Room", "Canary Pro")
        location = mock_location("Home", False)

        data = Mock()
        data.get_reading.return_value = 21.1234

        sensor = CanarySensor(data, SENSOR_TYPES[0], location, device)
        sensor.update()

        assert sensor.name == "Home Family Room Temperature"
        assert sensor.unit_of_measurement == TEMP_CELSIUS
        assert sensor.state == 21.12
        assert sensor.icon == "mdi:thermometer"

    def test_temperature_sensor_with_none_sensor_value(self):
        """Test temperature sensor with fahrenheit."""
        device = mock_device(10, "Family Room", "Canary Pro")
        location = mock_location("Home", False)

        data = Mock()
        data.get_reading.return_value = None

        sensor = CanarySensor(data, SENSOR_TYPES[0], location, device)
        sensor.update()

        assert sensor.state is None

    def test_humidity_sensor(self):
        """Test humidity sensor."""
        device = mock_device(10, "Family Room", "Canary Pro")
        location = mock_location("Home")

        data = Mock()
        data.get_reading.return_value = 50.4567

        sensor = CanarySensor(data, SENSOR_TYPES[1], location, device)
        sensor.update()

        assert sensor.name == "Home Family Room Humidity"
        assert sensor.unit_of_measurement == UNIT_PERCENTAGE
        assert sensor.state == 50.46
        assert sensor.icon == "mdi:water-percent"

    def test_air_quality_sensor_with_very_abnormal_reading(self):
        """Test air quality sensor."""
        device = mock_device(10, "Family Room", "Canary Pro")
        location = mock_location("Home")

        data = Mock()
        data.get_reading.return_value = 0.4

        sensor = CanarySensor(data, SENSOR_TYPES[2], location, device)
        sensor.update()

        assert sensor.name == "Home Family Room Air Quality"
        assert sensor.unit_of_measurement is None
        assert sensor.state == 0.4
        assert sensor.icon == "mdi:weather-windy"

        air_quality = sensor.device_state_attributes[ATTR_AIR_QUALITY]
        assert air_quality == STATE_AIR_QUALITY_VERY_ABNORMAL

    def test_air_quality_sensor_with_abnormal_reading(self):
        """Test air quality sensor."""
        device = mock_device(10, "Family Room", "Canary Pro")
        location = mock_location("Home")

        data = Mock()
        data.get_reading.return_value = 0.59

        sensor = CanarySensor(data, SENSOR_TYPES[2], location, device)
        sensor.update()

        assert sensor.name == "Home Family Room Air Quality"
        assert sensor.unit_of_measurement is None
        assert sensor.state == 0.59
        assert sensor.icon == "mdi:weather-windy"

        air_quality = sensor.device_state_attributes[ATTR_AIR_QUALITY]
        assert air_quality == STATE_AIR_QUALITY_ABNORMAL

    def test_air_quality_sensor_with_normal_reading(self):
        """Test air quality sensor."""
        device = mock_device(10, "Family Room", "Canary Pro")
        location = mock_location("Home")

        data = Mock()
        data.get_reading.return_value = 1.0

        sensor = CanarySensor(data, SENSOR_TYPES[2], location, device)
        sensor.update()

        assert sensor.name == "Home Family Room Air Quality"
        assert sensor.unit_of_measurement is None
        assert sensor.state == 1.0
        assert sensor.icon == "mdi:weather-windy"

        air_quality = sensor.device_state_attributes[ATTR_AIR_QUALITY]
        assert air_quality == STATE_AIR_QUALITY_NORMAL

    def test_air_quality_sensor_with_none_sensor_value(self):
        """Test air quality sensor."""
        device = mock_device(10, "Family Room", "Canary Pro")
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

        assert sensor.name == "Home Family Room Battery"
        assert sensor.unit_of_measurement == UNIT_PERCENTAGE
        assert sensor.state == 70.46
        assert sensor.icon == "mdi:battery-70"

    def test_wifi_sensor(self):
        """Test battery sensor."""
        device = mock_device(10, "Family Room", "Canary Flex")
        location = mock_location("Home")

        data = Mock()
        data.get_reading.return_value = -57

        sensor = CanarySensor(data, SENSOR_TYPES[3], location, device)
        sensor.update()

        assert sensor.name == "Home Family Room Wifi"
        assert sensor.unit_of_measurement == "dBm"
        assert sensor.state == -57
        assert sensor.icon == "mdi:wifi"
