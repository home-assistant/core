"""The tests for the IPMA weather component."""
import unittest
from unittest.mock import patch
from collections import namedtuple

from homeassistant.components import weather
from homeassistant.components.weather import (
    ATTR_WEATHER_HUMIDITY, ATTR_WEATHER_PRESSURE, ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_WIND_BEARING, ATTR_WEATHER_WIND_SPEED)
from homeassistant.util.unit_system import METRIC_SYSTEM
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant, MockDependency


class MockStation():
    """Mock Station from pyipma."""

    @classmethod
    async def get(cls, websession, lat, lon):
        """Mock Factory."""
        return MockStation()

    async def observation(self):
        """Mock Observation."""
        Observation = namedtuple('Observation', ['temperature', 'humidity',
                                                 'windspeed', 'winddirection',
                                                 'precipitation', 'pressure',
                                                 'description'])

        return Observation(18, 71.0, 3.94, 'NW', 0, 1000.0, '---')

    async def forecast(self):
        """Mock Forecast."""
        Forecast = namedtuple('Forecast', ['precipitaProb', 'tMin', 'tMax',
                                           'predWindDir', 'idWeatherType',
                                           'classWindSpeed', 'longitude',
                                           'forecastDate', 'classPrecInt',
                                           'latitude', 'description'])

        return [Forecast(73.0, 13.7, 18.7, 'NW', 6, 2, -8.64,
                         '2018-05-31', 2, 40.61,
                         'Aguaceiros, com vento Moderado de Noroeste')]

    @property
    def local(self):
        """Mock location."""
        return "HomeTown"


class TestIPMA(unittest.TestCase):
    """Test the IPMA weather component."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.units = METRIC_SYSTEM
        self.lat = self.hass.config.latitude = 40.00
        self.lon = self.hass.config.longitude = -8.00

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    @MockDependency("pyipma")
    @patch("pyipma.Station", new=MockStation)
    def test_setup(self, mock_pyipma):
        """Test for successfully setting up the IPMA platform."""
        assert setup_component(self.hass, weather.DOMAIN, {
            'weather': {
                'name': 'HomeTown',
                'platform': 'ipma',
            }
        })

        state = self.hass.states.get('weather.hometown')
        assert state.state == 'rainy'

        data = state.attributes
        assert data.get(ATTR_WEATHER_TEMPERATURE) == 18.0
        assert data.get(ATTR_WEATHER_HUMIDITY) == 71
        assert data.get(ATTR_WEATHER_PRESSURE) == 1000.0
        assert data.get(ATTR_WEATHER_WIND_SPEED) == 3.94
        assert data.get(ATTR_WEATHER_WIND_BEARING) == 'NW'
        assert state.attributes.get('friendly_name') == 'HomeTown'
