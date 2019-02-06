"""The tests for the IPMA weather component."""
from unittest.mock import patch
from collections import namedtuple

from homeassistant.components.weather import (
    ATTR_WEATHER_HUMIDITY, ATTR_WEATHER_PRESSURE, ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_WIND_BEARING, ATTR_WEATHER_WIND_SPEED,
    DOMAIN as WEATHER_DOMAIN)

from tests.common import MockConfigEntry, MockDependency

TEST_CONFIG = {
    "name": "HomeTown",
    "latitude": "40.00",
    "longitude": "-8.00",
}


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

    @property
    def latitude(self):
        """Mock latitude."""
        return 0

    @property
    def longitude(self):
        """Mock longitude."""
        return 0


@MockDependency("pyipma")
@patch("pyipma.Station", new=MockStation)
async def test_setup(hass):
    """Test for successfully setting up the IPMA platform."""
    entry = MockConfigEntry(domain='ipma', data=TEST_CONFIG)
    await hass.config_entries.async_forward_entry_setup(entry, WEATHER_DOMAIN)

    state = hass.states.get('weather.hometown')
    assert state.state == 'rainy'

    data = state.attributes
    assert data.get(ATTR_WEATHER_TEMPERATURE) == 18.0
    assert data.get(ATTR_WEATHER_HUMIDITY) == 71
    assert data.get(ATTR_WEATHER_PRESSURE) == 1000.0
    assert data.get(ATTR_WEATHER_WIND_SPEED) == 3.94
    assert data.get(ATTR_WEATHER_WIND_BEARING) == 'NW'
    assert state.attributes.get('friendly_name') == 'HomeTown'
