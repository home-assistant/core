"""The tests for the Yr sensor platform."""
from datetime import datetime
from unittest import TestCase
from unittest.mock import patch

import requests_mock

from homeassistant.bootstrap import _setup_component
import homeassistant.util.dt as dt_util
from tests.common import get_test_home_assistant, load_fixture


class TestSensorYr(TestCase):
    """Test the Yr sensor."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.latitude = 32.87336
        self.hass.config.longitude = 117.22743

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @requests_mock.Mocker()
    def test_default_setup(self, m):
        """Test the default setup."""
        m.get('http://api.yr.no/weatherapi/locationforecast/1.9/',
              text=load_fixture('yr.no.json'))
        now = datetime(2016, 6, 9, 1, tzinfo=dt_util.UTC)

        with patch('homeassistant.components.sensor.yr.dt_util.utcnow',
                   return_value=now):
                assert _setup_component(self.hass, 'sensor', {
                                'sensor': {'platform': 'yr',
                                           'elevation': 0}})

        state = self.hass.states.get('sensor.yr_symbol')

        assert '3' == state.state
        assert state.state.isnumeric()
        assert state.attributes.get('unit_of_measurement') is None

    @requests_mock.Mocker()
    def test_custom_setup(self, m):
        """Test a custom setup."""
        m.get('http://api.yr.no/weatherapi/locationforecast/1.9/',
              text=load_fixture('yr.no.json'))
        now = datetime(2016, 6, 9, 1, tzinfo=dt_util.UTC)

        with patch('homeassistant.components.sensor.yr.dt_util.utcnow',
                   return_value=now):
            assert _setup_component(self.hass, 'sensor', {
                                    'sensor': {'platform': 'yr',
                                               'elevation': 0,
                                               'monitored_conditions': [
                                                   'pressure',
                                                   'windDirection',
                                                   'humidity',
                                                   'fog',
                                                   'windSpeed']}})

        state = self.hass.states.get('sensor.yr_pressure')
        assert 'hPa' == state.attributes.get('unit_of_measurement')
        assert '1009.3' == state.state

        state = self.hass.states.get('sensor.yr_wind_direction')
        assert '°' == state.attributes.get('unit_of_measurement')
        assert '103.6' == state.state

        state = self.hass.states.get('sensor.yr_humidity')
        assert '%' == state.attributes.get('unit_of_measurement')
        assert '55.5' == state.state

        state = self.hass.states.get('sensor.yr_fog')
        assert '%' == state.attributes.get('unit_of_measurement')
        assert '0.0' == state.state

        state = self.hass.states.get('sensor.yr_wind_speed')
        assert 'm/s', state.attributes.get('unit_of_measurement')
        assert '3.5' == state.state
