"""The tests for the Binary sensor component."""
import unittest
from unittest import mock

from homeassistant.components import binary_sensor
from homeassistant.const import STATE_ON, STATE_OFF


class TestBinarySensor(unittest.TestCase):
    """Test the binary_sensor base class."""

    def test_state(self):
        """Test binary sensor state."""
        sensor = binary_sensor.BinarySensorDevice()
        self.assertEqual(STATE_OFF, sensor.state)
        with mock.patch('homeassistant.components.binary_sensor.'
                        'BinarySensorDevice.is_on',
                        new=False):
            self.assertEqual(STATE_OFF,
                             binary_sensor.BinarySensorDevice().state)
        with mock.patch('homeassistant.components.binary_sensor.'
                        'BinarySensorDevice.is_on',
                        new=True):
            self.assertEqual(STATE_ON,
                             binary_sensor.BinarySensorDevice().state)

    def test_attributes(self):
        """Test binary sensor attributes."""
        sensor = binary_sensor.BinarySensorDevice()
        self.assertEqual({}, sensor.state_attributes)
        with mock.patch('homeassistant.components.binary_sensor.'
                        'BinarySensorDevice.sensor_class',
                        new='motion'):
            self.assertEqual({'sensor_class': 'motion'},
                             sensor.state_attributes)
