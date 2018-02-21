"""Test different accessory types: Sensors."""
import unittest

from homeassistant.components.homekit.sensors import TemperatureSensor
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT, TEMP_CELSIUS, STATE_UNKNOWN)

from tests.common import get_test_home_assistant


class TestHomekitSensors(unittest.TestCase):
    """Test class for all accessory types regarding sensors."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop down everthing that was started."""
        self.hass.stop()

    def test_temperature_celsius(self):
        """Test if accessory is updated after state change."""
        temperature_sensor = 'sensor.temperature'

        acc = TemperatureSensor(self.hass, temperature_sensor, 'Temperature')
        acc.run()

        self.assertEqual(acc.char_temp.value, 0.0)

        self.hass.states.set(temperature_sensor, STATE_UNKNOWN,
                             {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()

        self.hass.states.set(temperature_sensor, '20')
        self.hass.block_till_done()
        self.assertEqual(acc.char_temp.value, 20)
