"""The tests for the Yr sensor platform."""
import asyncio
from datetime import datetime
from unittest.mock import patch

from homeassistant.bootstrap import setup_component
import homeassistant.util.dt as dt_util
from tests.common import assert_setup_component, load_fixture


NOW = datetime(2016, 6, 9, 1, tzinfo=dt_util.UTC)


def _setup_platform(hass, config):
    """Setup a yr platform."""
    hass.allow_pool = True

    def _setup():
        """Setup the platform."""
        with patch('homeassistant.components.sensor.yr.dt_util.utcnow',
                   return_value=NOW), assert_setup_component(1):
            setup_component(hass, 'sensor', {'sensor': config})
    return _setup


@asyncio.coroutine
def test_default_setup(hass, aioclient_mock):
    """Test the default setup."""
    aioclient_mock.get('http://api.yr.no/weatherapi/locationforecast/1.9/',
                       text=load_fixture('yr.no.json'))
    config = {'platform': 'yr',
              'elevation': 0}
    yield from hass.loop.run_in_executor(None, _setup_platform(hass, config))

    state = hass.states.get('sensor.yr_symbol')

    assert state.state == '3'
    assert state.state.isnumeric()
    assert state.attributes.get('unit_of_measurement') is None


@asyncio.coroutine
def test_custom_setup(hass, aioclient_mock):
    """Test a custom setup."""
    aioclient_mock.get('http://api.yr.no/weatherapi/locationforecast/1.9/',
                       text=load_fixture('yr.no.json'))

    config = {'platform': 'yr',
              'elevation': 0,
              'monitored_conditions': [
                  'pressure',
                  'windDirection',
                  'humidity',
                  'fog',
                  'windSpeed']}
    yield from hass.loop.run_in_executor(None, _setup_platform(hass, config))

    state = hass.states.get('sensor.yr_pressure')
    assert state.attributes.get('unit_of_measurement') == 'hPa'
    assert state.state == '1009.3'

    state = hass.states.get('sensor.yr_wind_direction')
    assert state.attributes.get('unit_of_measurement') == '°'
    assert state.state == '103.6'

    state = hass.states.get('sensor.yr_humidity')
    assert state.attributes.get('unit_of_measurement') == '%'
    assert state.state == '55.5'

    state = hass.states.get('sensor.yr_fog')
    assert state.attributes.get('unit_of_measurement') == '%'
    assert state.state == '0.0'

    state = hass.states.get('sensor.yr_wind_speed')
    assert state.attributes.get('unit_of_measurement') == 'm/s'
    assert state.state == '3.5'
