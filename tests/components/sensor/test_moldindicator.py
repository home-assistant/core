"""The tests for the MoldIndicator sensor"""
import unittest

import homeassistant.components.sensor as sensor
from homeassistant.const import (ATTR_UNIT_OF_MEASUREMENT,
                                 TEMP_CELCIUS)

from tests.common import get_test_home_assistant


class TestSensorMoldIndicator(unittest.TestCase):
    """Test the MoldIndicator sensor."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.states.set('test.indoortemp', '20',
                             {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELCIUS})
        self.hass.states.set('test.outdoortemp', '10',
                             {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELCIUS})
        self.hass.states.set('test.indoorhumidity', '50',
                             {ATTR_UNIT_OF_MEASUREMENT: '%'})

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_calculation(self):
        """Test the mold indicator sensor"""
        self.assertTrue(sensor.setup(self.hass, {
            'sensor': {
                'platform': 'mold_indicator',
                'indoor_temp_sensor': 'test.indoortemp',
                'outdoor_temp_sensor': 'test.outdoortemp',
                'indoor_humidity_sensor': 'test.indoorhumidity',
                'calibration_factor': '2.0'
            }
        }))

        moldind = self.hass.states.get('sensor.moldindicator')
