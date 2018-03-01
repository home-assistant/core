"""Test different accessory types: Sensors."""
import unittest
from unittest.mock import patch

from homeassistant.components.homekit.const import PROP_CELSIUS
from homeassistant.components.homekit.sensors import (
    TemperatureSensor, calc_temperature)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT, TEMP_CELSIUS, TEMP_FAHRENHEIT, STATE_UNKNOWN)

from tests.common import get_test_home_assistant
from tests.mock.homekit import get_patch_paths, mock_preload_service

PATH_ACC, PATH_FILE = get_patch_paths('sensors')


def test_calc_temperature():
    """Test if temperature in Celsius is calculated correctly."""
    assert calc_temperature(STATE_UNKNOWN) is None
    assert calc_temperature('test') is None

    assert calc_temperature('20') == 20
    assert calc_temperature('20.12', TEMP_CELSIUS) == 20.12

    assert calc_temperature('75.2', TEMP_FAHRENHEIT) == 24
    assert calc_temperature('-20.6', TEMP_FAHRENHEIT) == -29.22


class TestHomekitSensors(unittest.TestCase):
    """Test class for all accessory types regarding sensors."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        get_patch_paths('sensors')

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    def test_temperature(self):
        """Test if accessory is updated after state change."""
        temperature_sensor = 'sensor.temperature'

        with patch(PATH_ACC, side_effect=mock_preload_service):
            with patch(PATH_FILE, side_effect=mock_preload_service):
                acc = TemperatureSensor(self.hass, temperature_sensor,
                                        'Temperature')
                acc.run()

        self.assertEqual(acc.char_temp.value, 0.0)
        self.assertEqual(acc.char_temp.properties, PROP_CELSIUS)

        self.hass.states.set(temperature_sensor, STATE_UNKNOWN,
                             {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()

        self.hass.states.set(temperature_sensor, '20',
                             {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()
        self.assertEqual(acc.char_temp.value, 20)

        self.hass.states.set(temperature_sensor, '75.2',
                             {ATTR_UNIT_OF_MEASUREMENT: TEMP_FAHRENHEIT})
        self.hass.block_till_done()
        self.assertEqual(acc.char_temp.value, 24)
