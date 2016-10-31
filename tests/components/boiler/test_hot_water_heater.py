"""The tests for the hot water heater (geyser) component."""
import unittest
from unittest import mock

from homeassistant.components import hot_water_heater
from homeassistant.const import STATE_ON, STATE_OFF


class TestGeyserDevice(unittest.TestCase):
    """Test the hot_water_heater base class."""

    def test_state(self):
        """Test binary sensor state."""
        sensor = hot_water_heater.BinarySensorDevice()
        self.assertEqual(STATE_OFF, sensor.state)
        with mock.patch('homeassistant.components.hot_water_heater.'
                        'BinarySensorDevice.is_on',
                        new=False):
            self.assertEqual(STATE_OFF,
                             hot_water_heater.BinarySensorDevice().state)
        with mock.patch('homeassistant.components.hot_water_heater.'
                        'BinarySensorDevice.is_on',
                        new=True):
            self.assertEqual(STATE_ON,
                             hot_water_heater.BinarySensorDevice().state)

    def test_attributes(self):
        """Test binary sensor attributes."""
        sensor = hot_water_heater.BinarySensorDevice()
        self.assertEqual({}, sensor.state_attributes)
        with mock.patch('homeassistant.components.hot_water_heater.'
                        'BinarySensorDevice.sensor_class',
                        new='motion'):
            self.assertEqual({'sensor_class': 'motion'},
                             sensor.state_attributes)
