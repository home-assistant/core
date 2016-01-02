"""
tests.components.sensor.test_yr
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests Yr sensor.
"""
from unittest.mock import patch

import pytest

import homeassistant.core as ha
import homeassistant.components.sensor as sensor


@pytest.mark.usefixtures('betamax_session')
class TestSensorYr:
    """ Test the Yr sensor. """

    def setup_method(self, method):
        self.hass = ha.HomeAssistant()
        self.hass.config.latitude = 32.87336
        self.hass.config.longitude = 117.22743

    def teardown_method(self, method):
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_default_setup(self, betamax_session):
        with patch('homeassistant.components.sensor.yr.requests.Session',
                   return_value=betamax_session):
            assert sensor.setup(self.hass, {
                'sensor': {
                    'platform': 'yr',
                    'elevation': 0,
                }
            })

        state = self.hass.states.get('sensor.yr_symbol')

        assert state.state.isnumeric()
        assert state.attributes.get('unit_of_measurement') is None

    def test_custom_setup(self, betamax_session):
        with patch('homeassistant.components.sensor.yr.requests.Session',
                   return_value=betamax_session):
            assert sensor.setup(self.hass, {
                'sensor': {
                    'platform': 'yr',
                    'elevation': 0,
                    'monitored_conditions': {
                        'pressure',
                        'windDirection',
                        'humidity',
                        'fog',
                        'windSpeed'
                    }
                }
            })

        state = self.hass.states.get('sensor.yr_pressure')
        assert 'hPa', state.attributes.get('unit_of_measurement')

        state = self.hass.states.get('sensor.yr_wind_direction')
        assert '°', state.attributes.get('unit_of_measurement')

        state = self.hass.states.get('sensor.yr_humidity')
        assert '%', state.attributes.get('unit_of_measurement')

        state = self.hass.states.get('sensor.yr_fog')
        assert '%', state.attributes.get('unit_of_measurement')

        state = self.hass.states.get('sensor.yr_wind_speed')
        assert 'm/s', state.attributes.get('unit_of_measurement')
