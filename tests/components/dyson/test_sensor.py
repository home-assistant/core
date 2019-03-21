"""Test the Dyson sensor(s) component."""
import unittest
from unittest import mock

from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT, \
    STATE_OFF
from homeassistant.components.dyson import sensor as dyson
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
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_component_with_no_devices(self):
        """Test setup component with no devices."""
        self.hass.data[dyson.DYSON_DEVICES] = []
        add_entities = mock.MagicMock()
        dyson.setup_platform(self.hass, None, add_entities)
        add_entities.assert_called_with([])

    def test_setup_component(self):
        """Test setup component with devices."""
        def _add_device(devices):
            assert len(devices) == 5
            assert devices[0].name == "Device_name Filter Life"
            assert devices[1].name == "Device_name Dust"
            assert devices[2].name == "Device_name Humidity"
            assert devices[3].name == "Device_name Temperature"
            assert devices[4].name == "Device_name AQI"

        device_fan = _get_device_without_state()
        device_non_fan = _get_with_state()
        self.hass.data[dyson.DYSON_DEVICES] = [device_fan, device_non_fan]
        dyson.setup_platform(self.hass, None, _add_device)

    def test_dyson_filter_life_sensor(self):
        """Test filter life sensor with no value."""
        sensor = dyson.DysonFilterLifeSensor(_get_device_without_state())
        sensor.hass = self.hass
        sensor.entity_id = "sensor.dyson_1"
        assert not sensor.should_poll
        assert sensor.state is None
        assert sensor.unit_of_measurement == "hours"
        assert sensor.name == "Device_name Filter Life"
        assert sensor.entity_id == "sensor.dyson_1"
        sensor.on_message('message')

    def test_dyson_filter_life_sensor_with_values(self):
        """Test filter sensor with values."""
        sensor = dyson.DysonFilterLifeSensor(_get_with_state())
        sensor.hass = self.hass
        sensor.entity_id = "sensor.dyson_1"
        assert not sensor.should_poll
        assert sensor.state == 100
        assert sensor.unit_of_measurement == "hours"
        assert sensor.name == "Device_name Filter Life"
        assert sensor.entity_id == "sensor.dyson_1"
        sensor.on_message('message')

    def test_dyson_dust_sensor(self):
        """Test dust sensor with no value."""
        sensor = dyson.DysonDustSensor(_get_device_without_state())
        sensor.hass = self.hass
        sensor.entity_id = "sensor.dyson_1"
        assert not sensor.should_poll
        assert sensor.state is None
        assert sensor.unit_of_measurement is None
        assert sensor.name == "Device_name Dust"
        assert sensor.entity_id == "sensor.dyson_1"

    def test_dyson_dust_sensor_with_values(self):
        """Test dust sensor with values."""
        sensor = dyson.DysonDustSensor(_get_with_state())
        sensor.hass = self.hass
        sensor.entity_id = "sensor.dyson_1"
        assert not sensor.should_poll
        assert sensor.state == 5
        assert sensor.unit_of_measurement is None
        assert sensor.name == "Device_name Dust"
        assert sensor.entity_id == "sensor.dyson_1"

    def test_dyson_humidity_sensor(self):
        """Test humidity sensor with no value."""
        sensor = dyson.DysonHumiditySensor(_get_device_without_state())
        sensor.hass = self.hass
        sensor.entity_id = "sensor.dyson_1"
        assert not sensor.should_poll
        assert sensor.state is None
        assert sensor.unit_of_measurement == '%'
        assert sensor.name == "Device_name Humidity"
        assert sensor.entity_id == "sensor.dyson_1"

    def test_dyson_humidity_sensor_with_values(self):
        """Test humidity sensor with values."""
        sensor = dyson.DysonHumiditySensor(_get_with_state())
        sensor.hass = self.hass
        sensor.entity_id = "sensor.dyson_1"
        assert not sensor.should_poll
        assert sensor.state == 45
        assert sensor.unit_of_measurement == '%'
        assert sensor.name == "Device_name Humidity"
        assert sensor.entity_id == "sensor.dyson_1"

    def test_dyson_humidity_standby_monitoring(self):
        """Test humidity sensor while device is in standby monitoring."""
        sensor = dyson.DysonHumiditySensor(_get_with_standby_monitoring())
        sensor.hass = self.hass
        sensor.entity_id = "sensor.dyson_1"
        assert not sensor.should_poll
        assert sensor.state == STATE_OFF
        assert sensor.unit_of_measurement == '%'
        assert sensor.name == "Device_name Humidity"
        assert sensor.entity_id == "sensor.dyson_1"

    def test_dyson_temperature_sensor(self):
        """Test temperature sensor with no value."""
        sensor = dyson.DysonTemperatureSensor(_get_device_without_state(),
                                              TEMP_CELSIUS)
        sensor.hass = self.hass
        sensor.entity_id = "sensor.dyson_1"
        assert not sensor.should_poll
        assert sensor.state is None
        assert sensor.unit_of_measurement == '°C'
        assert sensor.name == "Device_name Temperature"
        assert sensor.entity_id == "sensor.dyson_1"

    def test_dyson_temperature_sensor_with_values(self):
        """Test temperature sensor with values."""
        sensor = dyson.DysonTemperatureSensor(_get_with_state(),
                                              TEMP_CELSIUS)
        sensor.hass = self.hass
        sensor.entity_id = "sensor.dyson_1"
        assert not sensor.should_poll
        assert sensor.state == 21.9
        assert sensor.unit_of_measurement == '°C'
        assert sensor.name == "Device_name Temperature"
        assert sensor.entity_id == "sensor.dyson_1"

        sensor = dyson.DysonTemperatureSensor(_get_with_state(),
                                              TEMP_FAHRENHEIT)
        sensor.hass = self.hass
        sensor.entity_id = "sensor.dyson_1"
        assert not sensor.should_poll
        assert sensor.state == 71.3
        assert sensor.unit_of_measurement == '°F'
        assert sensor.name == "Device_name Temperature"
        assert sensor.entity_id == "sensor.dyson_1"

    def test_dyson_temperature_standby_monitoring(self):
        """Test temperature sensor while device is in standby monitoring."""
        sensor = dyson.DysonTemperatureSensor(_get_with_standby_monitoring(),
                                              TEMP_CELSIUS)
        sensor.hass = self.hass
        sensor.entity_id = "sensor.dyson_1"
        assert not sensor.should_poll
        assert sensor.state == STATE_OFF
        assert sensor.unit_of_measurement == '°C'
        assert sensor.name == "Device_name Temperature"
        assert sensor.entity_id == "sensor.dyson_1"

    def test_dyson_air_quality_sensor(self):
        """Test air quality sensor with no value."""
        sensor = dyson.DysonAirQualitySensor(_get_device_without_state())
        sensor.hass = self.hass
        sensor.entity_id = "sensor.dyson_1"
        assert not sensor.should_poll
        assert sensor.state is None
        assert sensor.unit_of_measurement is None
        assert sensor.name == "Device_name AQI"
        assert sensor.entity_id == "sensor.dyson_1"

    def test_dyson_air_quality_sensor_with_values(self):
        """Test air quality sensor with values."""
        sensor = dyson.DysonAirQualitySensor(_get_with_state())
        sensor.hass = self.hass
        sensor.entity_id = "sensor.dyson_1"
        assert not sensor.should_poll
        assert sensor.state == 2
        assert sensor.unit_of_measurement is None
        assert sensor.name == "Device_name AQI"
        assert sensor.entity_id == "sensor.dyson_1"
