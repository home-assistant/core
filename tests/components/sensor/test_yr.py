"""
tests.components.sensor.test_yr
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests Yr sensor.
"""
import unittest

import homeassistant.core as ha
import homeassistant.components.sensor as sensor


class TestSensorYr(unittest.TestCase):
    """ Test the Yr sensor. """

    def setUp(self):  # pylint: disable=invalid-name
        self.hass = ha.HomeAssistant()
        latitude = 32.87336
        longitude = 117.22743

        # Compare it with the real data
        self.hass.config.latitude = latitude
        self.hass.config.longitude = longitude

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_default_setup(self):
        self.assertTrue(sensor.setup(self.hass, {
            'sensor': {
                'platform': 'yr',
            }
        }))
        state = self.hass.states.get('sensor.yr_symbol')

        self.assertTrue(state.state.isnumeric())
        self.assertEqual(None,
                         state.attributes.get('unit_of_measurement'))

    def test_custom_setup(self):
        self.assertTrue(sensor.setup(self.hass, {
            'sensor': {
                'platform': 'yr',
                'monitored_conditions': {'pressure', 'windDirection', 'humidity', 'fog', 'windSpeed'}
            }
        }))
        state = self.hass.states.get('sensor.yr_symbol')
        self.assertEqual(None, state)

        state = self.hass.states.get('sensor.yr_pressure')
        self.assertEqual('hPa',
                         state.attributes.get('unit_of_measurement'))

        state = self.hass.states.get('sensor.yr_wind_direction')
        self.assertEqual('°',
                         state.attributes.get('unit_of_measurement'))

        state = self.hass.states.get('sensor.yr_humidity')
        self.assertEqual('%',
                         state.attributes.get('unit_of_measurement'))

        state = self.hass.states.get('sensor.yr_fog')
        self.assertEqual('%',
                         state.attributes.get('unit_of_measurement'))

        state = self.hass.states.get('sensor.yr_wind_speed')
        self.assertEqual('m/s',
                         state.attributes.get('unit_of_measurement'))
