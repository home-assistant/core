"""Test the Dyson sensor(s) component."""
import unittest
from unittest import mock

from homeassistant.const import STATE_UNKNOWN
from homeassistant.components.sensor import dyson
from tests.common import get_test_home_assistant


def _get_device_without_state():
    """Return a valid device provide by Dyson web services."""
    device = mock.Mock()
    device.name = "Device_name"
    device.state = None
    return device


def _get_with_state():
    """Return a valid device with state values."""
    device = mock.Mock()
    device.name = "Device_name"
    device.state = mock.Mock()
    device.state.filter_life = 100
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
            assert len(devices) == 1
            assert devices[0].name == "Device_name filter life"

        device = _get_device_without_state()
        self.hass.data[dyson.DYSON_DEVICES] = [device]
        dyson.setup_platform(self.hass, None, _add_device)

    def test_dyson_filter_life_sensor(self):
        """Test sensor with no value."""
        sensor = dyson.DysonFilterLifeSensor(self.hass,
                                             _get_device_without_state())
        sensor.entity_id = "sensor.dyson_1"
        self.assertFalse(sensor.should_poll)
        self.assertEqual(sensor.state, STATE_UNKNOWN)
        self.assertEqual(sensor.unit_of_measurement, "hours")
        self.assertEqual(sensor.name, "Device_name filter life")
        self.assertEqual(sensor.entity_id, "sensor.dyson_1")
        sensor.on_message('message')

    def test_dyson_filter_life_sensor_with_values(self):
        """Test sensor with values."""
        sensor = dyson.DysonFilterLifeSensor(self.hass, _get_with_state())
        sensor.entity_id = "sensor.dyson_1"
        self.assertFalse(sensor.should_poll)
        self.assertEqual(sensor.state, 100)
        self.assertEqual(sensor.unit_of_measurement, "hours")
        self.assertEqual(sensor.name, "Device_name filter life")
        self.assertEqual(sensor.entity_id, "sensor.dyson_1")
        sensor.on_message('message')
