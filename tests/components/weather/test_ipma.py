"""The tests for the IPMA weather component."""
import re
import unittest
from unittest.mock import patch
from collections import namedtuple

import pyipma 

from homeassistant.components import weather
from homeassistant.components.weather import (
    ATTR_WEATHER_HUMIDITY, ATTR_WEATHER_PRESSURE, ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_WIND_BEARING, ATTR_WEATHER_WIND_SPEED)
from homeassistant.util.unit_system import METRIC_SYSTEM
from homeassistant.setup import setup_component

from tests.common import load_fixture, get_test_home_assistant, mock_coro

MockStation = namedtuple('Station', ['latitude', 'longitude',
                                         'idAreaAviso', 'idConselho',
                                         'idDistrito', 'idRegiao',
                                         'globalIdLocal', 'local'])

mockStation = MockStation(40.61, -8.64, 'AAA', 1, 1, 1, 100000, 'HomeTown')

Forecast = namedtuple('Forecast', ['precipitaProb', 'tMin', 'tMax',
                                   'predWindDir', 'idWeatherType',
                                   'classWindSpeed', 'longitude',
                                   'forecastDate', 'classPrecInt',
                                   'latitude', 'description'])

mockForecast = Forecast(73.0, 13.7, 18.7, 'NW', 6, 2, -8.64,
                        '2018-05-31', 2, 40.61,
                        'Aguaceiros, com vento Moderado de Noroeste')

Observation = namedtuple('Observation', ['temperature', 'humidity',
                                         'windspeed', 'winddirection',
                                         'precipitation', 'pressure',
                                         'description'])

Station = namedtuple('ObservationStation', ['latitude', 'longitude', 'stationID',
                                         'stationName', 'currentObs'])

mockObservation = Observation(18, 71.0, 3.94, 'NW', 0, 1000.0, '---')
mockObservationStation = Station(40.61, -8.64, 1, 'HomeTown', mockObservation)

class TestIPMA(unittest.TestCase):
    """Test the IPMA weather component."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.units = METRIC_SYSTEM
        self.lat = self.hass.config.latitude = 40.00 
        self.lon = self.hass.config.longitude = -8.00

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    @patch("pyipma.api.IPMA_API.stations", return_value=mock_coro([mockStation]))
    @patch("pyipma.api.IPMA_API.forecast", return_value=mock_coro([mockForecast]))
    @patch("pyipma.api.IPMA_API.observations", return_value=mock_coro([mockObservationStation]))
    def test_setup(self, mock_observation, mock_forecast, mock_stations):
        """Test for successfully setting up the IPMA platform."""

        self.assertTrue(setup_component(self.hass, weather.DOMAIN, {
            'weather': {
                'name': 'HomeTown',
                'platform': 'ipma',
            }
        }))

        state = self.hass.states.get('weather.hometown')
        self.assertEqual(state.state, 'rainy')

        data = state.attributes
        self.assertEqual(data.get(ATTR_WEATHER_TEMPERATURE), 18.0)
        self.assertEqual(data.get(ATTR_WEATHER_HUMIDITY), 71)
        self.assertEqual(data.get(ATTR_WEATHER_PRESSURE), 1000.0)
        self.assertEqual(data.get(ATTR_WEATHER_WIND_SPEED), 3.94)
        self.assertEqual(data.get(ATTR_WEATHER_WIND_BEARING), 'NW')
        self.assertEqual(state.attributes.get('friendly_name'), 'HomeTown')
