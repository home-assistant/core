"""
tests.components.binary_sensor.test_binary_sensor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Test the binary_sensor base class
"""
import unittest
from unittest import mock

from homeassistant.components import binary_sensor
from homeassistant.const import STATE_ON, STATE_OFF


class TestBinarySensor(unittest.TestCase):
    def test_state(self):
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
        sensor = binary_sensor.BinarySensorDevice()
        self.assertEqual({'sensor_class': None},
                         sensor.device_state_attributes)
        with mock.patch('homeassistant.components.binary_sensor.'
                        'BinarySensorDevice.sensor_class',
                        new='motion'):
            self.assertEqual({'sensor_class': 'motion'},
                             sensor.device_state_attributes)
