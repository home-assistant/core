"""Test the Dyson sensor(s) component."""
import unittest
from unittest import mock

from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT, \
    STATE_OFF
from homeassistant.components.sensor import dyson
from tests.common import get_test_home_assistant
from libpurecoollink.dyson_pure_cool_link import DysonPureCoolLink


def _get_device_without_state():
    """Return a valid device provide by Dyson web services."""
    device = mock.Mock(spec=DysonPureCoolLink)
    device.name = "Device_name"
    device.state = None
    device.environmental_state = None
    return device


def _get_with_state():
    """Return a valid device with state values."""
    device = mock.Mock()
    device.name = "Device_name"
    device.state = mock.Mock()
    device.state.filter_life = 100
    device.environmental_state = mock.Mock()
    device.environmental_state.dust = 5
    device.environmental_state.humidity = 45
    device.environmental_state.temperature = 295
    device.environmental_state.volatil_organic_compounds = 2

    return device


def _get_with_standby_monitoring():
    """Return a valid device with state but with standby monitoring disable."""
    device = mock.Mock()
    device.name = "Device_name"
    device.state = mock.Mock()
    device.state.filter_life = 100
    device.environmental_state = mock.Mock()
    device.environmental_state.dust = 5
    device.environmental_state.humidity = 0
    device.environmental_state.temperature = 0
    device.environmental_state.volatil_organic_compounds = 2

    return device


class DysonTest(unittest.TestCase):
    """Dyson Sensor component test class."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_component_with_no_devices(self):
        """Test setup component with no devices."""
        self.hass.data[dyson.DYSON_DEVICES] = []
        add_devices = mock.MagicMock()
        dyson.setup_platform(self.hass, None, add_devices)
        add_devices.assert_called_with([])

    def test_setup_component(self):
        """Test setup component with devices."""
        def _add_device(devices):
            assert len(devices) == 5
            assert devices[0].name == "Device_name filter life"
            assert devices[1].name == "Device_name dust"
            assert devices[2].name == "Device_name humidity"
            assert devices[3].name == "Device_name temperature"
            assert devices[4].name == "Device_name air quality"

        device_fan = _get_device_without_state()
        device_non_fan = _get_with_state()
        self.hass.data[dyson.DYSON_DEVICES] = [device_fan, device_non_fan]
        dyson.setup_platform(self.hass, None, _add_device)

    def test_dyson_filter_life_sensor(self):
        """Test filter life sensor with no value."""
        sensor = dyson.DysonFilterLifeSensor(self.hass,
                                             _get_device_without_state())
        sensor.entity_id = "sensor.dyson_1"
        self.assertFalse(sensor.should_poll)
        self.assertIsNone(sensor.state)
        self.assertEqual(sensor.unit_of_measurement, "hours")
        self.assertEqual(sensor.name, "Device_name filter life")
        self.assertEqual(sensor.entity_id, "sensor.dyson_1")
        sensor.on_message('message')

    def test_dyson_filter_life_sensor_with_values(self):
        """Test filter sensor with values."""
        sensor = dyson.DysonFilterLifeSensor(self.hass, _get_with_state())
        sensor.entity_id = "sensor.dyson_1"
        self.assertFalse(sensor.should_poll)
        self.assertEqual(sensor.state, 100)
        self.assertEqual(sensor.unit_of_measurement, "hours")
        self.assertEqual(sensor.name, "Device_name filter life")
        self.assertEqual(sensor.entity_id, "sensor.dyson_1")
        sensor.on_message('message')

    def test_dyson_dust_sensor(self):
        """Test dust sensor with no value."""
        sensor = dyson.DysonDustSensor(self.hass,
                                       _get_device_without_state())
        sensor.entity_id = "sensor.dyson_1"
        self.assertFalse(sensor.should_poll)
        self.assertIsNone(sensor.state)
        self.assertEqual(sensor.unit_of_measurement, 'level')
        self.assertEqual(sensor.name, "Device_name dust")
        self.assertEqual(sensor.entity_id, "sensor.dyson_1")

    def test_dyson_dust_sensor_with_values(self):
        """Test dust sensor with values."""
        sensor = dyson.DysonDustSensor(self.hass, _get_with_state())
        sensor.entity_id = "sensor.dyson_1"
        self.assertFalse(sensor.should_poll)
        self.assertEqual(sensor.state, 5)
        self.assertEqual(sensor.unit_of_measurement, 'level')
        self.assertEqual(sensor.name, "Device_name dust")
        self.assertEqual(sensor.entity_id, "sensor.dyson_1")

    def test_dyson_humidity_sensor(self):
        """Test humidity sensor with no value."""
        sensor = dyson.DysonHumiditySensor(self.hass,
                                           _get_device_without_state())
        sensor.entity_id = "sensor.dyson_1"
        self.assertFalse(sensor.should_poll)
        self.assertIsNone(sensor.state)
        self.assertEqual(sensor.unit_of_measurement, '%')
        self.assertEqual(sensor.name, "Device_name humidity")
        self.assertEqual(sensor.entity_id, "sensor.dyson_1")

    def test_dyson_humidity_sensor_with_values(self):
        """Test humidity sensor with values."""
        sensor = dyson.DysonHumiditySensor(self.hass, _get_with_state())
        sensor.entity_id = "sensor.dyson_1"
        self.assertFalse(sensor.should_poll)
        self.assertEqual(sensor.state, 45)
        self.assertEqual(sensor.unit_of_measurement, '%')
        self.assertEqual(sensor.name, "Device_name humidity")
        self.assertEqual(sensor.entity_id, "sensor.dyson_1")

    def test_dyson_humidity_standby_monitoring(self):
        """Test humidity sensor while device is in standby monitoring."""
        sensor = dyson.DysonHumiditySensor(self.hass,
                                           _get_with_standby_monitoring())
        sensor.entity_id = "sensor.dyson_1"
        self.assertFalse(sensor.should_poll)
        self.assertEqual(sensor.state, STATE_OFF)
        self.assertEqual(sensor.unit_of_measurement, '%')
        self.assertEqual(sensor.name, "Device_name humidity")
        self.assertEqual(sensor.entity_id, "sensor.dyson_1")

    def test_dyson_temperature_sensor(self):
        """Test temperature sensor with no value."""
        sensor = dyson.DysonTemperatureSensor(self.hass,
                                              _get_device_without_state(),
                                              TEMP_CELSIUS)
        sensor.entity_id = "sensor.dyson_1"
        self.assertFalse(sensor.should_poll)
        self.assertIsNone(sensor.state)
        self.assertEqual(sensor.unit_of_measurement, '°C')
        self.assertEqual(sensor.name, "Device_name temperature")
        self.assertEqual(sensor.entity_id, "sensor.dyson_1")

    def test_dyson_temperature_sensor_with_values(self):
        """Test temperature sensor with values."""
        sensor = dyson.DysonTemperatureSensor(self.hass,
                                              _get_with_state(),
                                              TEMP_CELSIUS)
        sensor.entity_id = "sensor.dyson_1"
        self.assertFalse(sensor.should_poll)
        self.assertEqual(sensor.state, 21.9)
        self.assertEqual(sensor.unit_of_measurement, '°C')
        self.assertEqual(sensor.name, "Device_name temperature")
        self.assertEqual(sensor.entity_id, "sensor.dyson_1")

        sensor = dyson.DysonTemperatureSensor(self.hass,
                                              _get_with_state(),
                                              TEMP_FAHRENHEIT)
        sensor.entity_id = "sensor.dyson_1"
        self.assertFalse(sensor.should_poll)
        self.assertEqual(sensor.state, 71.3)
        self.assertEqual(sensor.unit_of_measurement, '°F')
        self.assertEqual(sensor.name, "Device_name temperature")
        self.assertEqual(sensor.entity_id, "sensor.dyson_1")

    def test_dyson_temperature_standby_monitoring(self):
        """Test temperature sensor while device is in standby monitoring."""
        sensor = dyson.DysonTemperatureSensor(self.hass,
                                              _get_with_standby_monitoring(),
                                              TEMP_CELSIUS)
        sensor.entity_id = "sensor.dyson_1"
        self.assertFalse(sensor.should_poll)
        self.assertEqual(sensor.state, STATE_OFF)
        self.assertEqual(sensor.unit_of_measurement, '°C')
        self.assertEqual(sensor.name, "Device_name temperature")
        self.assertEqual(sensor.entity_id, "sensor.dyson_1")

    def test_dyson_air_quality_sensor(self):
        """Test air quality sensor with no value."""
        sensor = dyson.DysonAirQualitySensor(self.hass,
                                             _get_device_without_state())
        sensor.entity_id = "sensor.dyson_1"
        self.assertFalse(sensor.should_poll)
        self.assertIsNone(sensor.state)
        self.assertEqual(sensor.unit_of_measurement, 'level')
        self.assertEqual(sensor.name, "Device_name air quality")
        self.assertEqual(sensor.entity_id, "sensor.dyson_1")

    def test_dyson_air_quality_sensor_with_values(self):
        """Test air quality sensor with values."""
        sensor = dyson.DysonAirQualitySensor(self.hass, _get_with_state())
        sensor.entity_id = "sensor.dyson_1"
        self.assertFalse(sensor.should_poll)
        self.assertEqual(sensor.state, 2)
        self.assertEqual(sensor.unit_of_measurement, 'level')
        self.assertEqual(sensor.name, "Device_name air quality")
        self.assertEqual(sensor.entity_id, "sensor.dyson_1")
