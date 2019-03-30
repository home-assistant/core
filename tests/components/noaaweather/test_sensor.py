"""The tests for the NOAA/NWS weather sensor component."""

import asyncio

from pytest import raises

import homeassistant.components.noaaweather.sensor as noaaweather

from homeassistant.setup import (async_setup_component)
from homeassistant.const import (TEMP_CELSIUS, TEMP_FAHRENHEIT,
                                 LENGTH_KILOMETERS, LENGTH_MILES,
                                 LENGTH_INCHES)
from homeassistant.util.unit_system import (IMPERIAL_SYSTEM)
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import (load_fixture, assert_setup_component)

VALID_CONFIG_MINIMAL = {
    'sensor': {
        'platform': 'noaaweather',
        'latitude': 40.6391,
        'longitude': -73.7639,
        'monitored_conditions': ['temperature'],
    }
}

VALID_CONFIG_FULL = {
    'sensor': {
        'platform': 'noaaweather',
        'latitude': 40.6391,
        'longitude': -73.7639,
        'monitored_conditions': [
            'temperature',
            'textDescription',
            'dewpoint',
            'windChill',
            'windSpeed',
            'windDirection',
            'windGust',
            'barometricPressure',
            'seaLevelPressure',
            'precipitationLastHour',
            'precipitationLast3Hours',
            'precipitationLast6Hours',
            'relativeHumidity',
            'heatIndex',
            'visibility',
            'cloudLayers',
        ],
    }
}

#
# Note that this is passed to async_setup_platform, so
# it does not have the "sensor" level.
#
BAD_CONF_LOCATION = {
    'platform': 'noaaweather',
    'latitude': 0,
    'longitude': 0,
    'monitored_conditions': [
        'temperature',
        ],
}

BAD_CONF_STATION = {
    'sensor': {
        'platform': 'noaaweather',
        'latitude': 40.6391,
        'longitude': -73.7639,
        'stationcode': 'KLGA',
        'monitored_conditions': [
            'temperature',
        ],
    }
}

STAURL = "https://api.weather.gov/points/40.6391,-73.7639/stations"
BADSTAURL = "https://api.weather.gov/points/0,0/stations"
OBSURL = "https://api.weather.gov/stations/KJFK/observations/"
BADOBSURL = "https://api.weather.gov/stations/KLGA/observations/"


@asyncio.coroutine
def test_setup_with_config(hass, aioclient_mock):
    """Test with the configuration."""
    aioclient_mock.get(STAURL, text=load_fixture('noaaweather-sta-valid.json'))
    aioclient_mock.get(
        OBSURL,
        text=load_fixture('noaaweather-obs-valid.json'),
        params={'limit': 5})

    with assert_setup_component(1, 'sensor'):
        yield from async_setup_component(hass, 'sensor', VALID_CONFIG_MINIMAL)


@asyncio.coroutine
def test_setup_minimal(hass, aioclient_mock):
    """Test for minimal weather sensor config.

    This test case is with default (metric) units.
    """
    aioclient_mock.get(STAURL, text=load_fixture('noaaweather-sta-valid.json'))
    aioclient_mock.get(
        OBSURL,
        text=load_fixture('noaaweather-obs-valid.json'),
        params={'limit': 5})

    with assert_setup_component(1, 'sensor'):
        yield from async_setup_component(hass, 'sensor', VALID_CONFIG_MINIMAL)

    print('test_setup_minimal')
    state = hass.states.get('sensor.noaa_weather_kjfk_temperature')
    assert state is not None

    assert state.state == '11.7'
    assert state.attributes.get('unit_of_measurement') == TEMP_CELSIUS
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Temperature"


@asyncio.coroutine
def test_setup_minimal_imperial(hass, aioclient_mock):
    """Test for minimal weather sensor config.

    This case is with imperial units.
    """
    aioclient_mock.get(STAURL, text=load_fixture('noaaweather-sta-valid.json'))
    aioclient_mock.get(
        OBSURL,
        text=load_fixture('noaaweather-obs-valid.json'),
        params={'limit': 5})

    hass.config.units = IMPERIAL_SYSTEM
    with assert_setup_component(1, 'sensor'):
        yield from async_setup_component(hass, 'sensor', VALID_CONFIG_MINIMAL)

    state = hass.states.get('sensor.noaa_weather_kjfk_temperature')
    assert state is not None

    assert state.state == '53.1'
    assert state.attributes.get('unit_of_measurement') == TEMP_FAHRENHEIT
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Temperature"


@asyncio.coroutine
def test_setup_badconflocation(hass, aioclient_mock):
    """Test for configuration with bad location."""
    aioclient_mock.get(BADSTAURL, status=404)
    aioclient_mock.get(
        OBSURL,
        text=load_fixture('noaaweather-obs-valid.json'),
        params={'limit': 5})

    with raises(ConfigEntryNotReady):
        yield from noaaweather.async_setup_platform(
            hass, BAD_CONF_LOCATION, lambda _: None)


@asyncio.coroutine
def test_setup_badconfstation(hass, aioclient_mock):
    """Test for configuration with bad station.

    This is the case where the station code was in the list for the
    location, but retrieving observation data failed.  This should
    be a transient error, so the sensor will still exist. However,
    without any data being received, no conditions are available.
    """
    aioclient_mock.get(STAURL, text=load_fixture('noaaweather-sta-valid.json'))
    aioclient_mock.get(BADOBSURL, status=505)

    with assert_setup_component(1, 'sensor'):
        yield from async_setup_component(hass, 'sensor', BAD_CONF_STATION)

    state = hass.states.get('sensor.noaa_weather_klga_temperature')
    assert state is None


@asyncio.coroutine
def test_setup_badobs(hass, aioclient_mock):
    """Test for configuration with bad station."""
    aioclient_mock.get(STAURL, text=load_fixture('noaaweather-sta-valid.json'))
    aioclient_mock.get(
        BADOBSURL,
        text=load_fixture('noaaweather-obs-empty.json'),
        params={'limit': 5})

    with assert_setup_component(1, 'sensor'):
        yield from async_setup_component(hass, 'sensor', BAD_CONF_STATION)

    state = hass.states.get('sensor.noaa_weather_klga_temperature')
    assert state is None


@asyncio.coroutine
def test_setup_full(hass, aioclient_mock):
    """Test for full weather sensor config.

    This test case is with default (metric) units.
    """
    aioclient_mock.get(STAURL, text=load_fixture('noaaweather-sta-valid.json'))
    aioclient_mock.get(
        OBSURL,
        text=load_fixture('noaaweather-obs-valid.json'),
        params={'limit': 5})

    with assert_setup_component(1, 'sensor'):
        yield from async_setup_component(hass, 'sensor', VALID_CONFIG_FULL)

    state = hass.states.get('sensor.noaa_weather_kjfk_temperature')
    assert state is not None

    assert state.state == '11.7'
    assert state.attributes.get('unit_of_measurement') == TEMP_CELSIUS
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Temperature"

    state = hass.states.get('sensor.noaa_weather_kjfk_textDescription')
    assert state is not None

    assert state.state == 'Mostly Cloudy and Windy'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Weather"

    state = hass.states.get('sensor.noaa_weather_kjfk_dewpoint')
    assert state is not None

    assert state.state == '-1.5'
    assert state.attributes.get('unit_of_measurement') == TEMP_CELSIUS
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather dewpoint"

    state = hass.states.get('sensor.noaa_weather_kjfk_windChill')
    assert state is not None

    assert state.state == '4.4'
    assert state.attributes.get('unit_of_measurement') == TEMP_CELSIUS
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Wind Chill"

    state = hass.states.get('sensor.noaa_weather_kjfk_heatIndex')
    assert state is not None

    assert state.state == '11.1'
    assert state.attributes.get('unit_of_measurement') == TEMP_CELSIUS
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Heat Index"

    state = hass.states.get('sensor.noaa_weather_kjfk_windSpeed')
    assert state is not None

    assert state.state == '16.6'
    assert state.attributes.get('unit_of_measurement') == 'km/h'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Wind Speed"

    state = hass.states.get('sensor.noaa_weather_kjfk_windDirection')
    assert state is not None

    assert state.state == '200'
    assert state.attributes.get('unit_of_measurement') == '°'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Wind Bearing"

    state = hass.states.get('sensor.noaa_weather_kjfk_windGust')
    assert state is not None

    assert state.state == '33.5'
    assert state.attributes.get('unit_of_measurement') == 'km/h'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Wind Gust"

    state = hass.states.get('sensor.noaa_weather_kjfk_barometricPressure')
    assert state is not None

    assert state.state == '1016.9'
    assert state.attributes.get('unit_of_measurement') == 'mbar'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Pressure"

    state = hass.states.get('sensor.noaa_weather_kjfk_seaLevelPressure')
    assert state is not None

    assert state.state == '1016.8'
    assert state.attributes.get('unit_of_measurement') == 'mbar'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Sea Level Pressure"

    state = hass.states.get(
        'sensor.noaa_weather_kjfk_precipitationLastHour')
    assert state is not None

    assert state.state == '10.0'
    assert state.attributes.get('unit_of_measurement') == 'mm'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Precipitation in last hour"

    state = hass.states.get(
        'sensor.noaa_weather_kjfk_precipitationLast3Hours')
    assert state is not None

    assert state.state == '11.0'
    assert state.attributes.get('unit_of_measurement') == 'mm'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Precipitation in last 3 hours"

    state = hass.states.get(
        'sensor.noaa_weather_kjfk_precipitationLast6Hours')
    assert state is not None

    assert state.state == '15.0'
    assert state.attributes.get('unit_of_measurement') == 'mm'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Precipitation in last 6 hours"

    state = hass.states.get('sensor.noaa_weather_kjfk_relativeHumidity')
    assert state is not None

    assert state.state == '63.0'
    assert state.attributes.get('unit_of_measurement') == '%'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Humidity"

    state = hass.states.get('sensor.noaa_weather_kjfk_visibility')
    assert state is not None

    assert state.state == '16.1'
    assert state.attributes.get('unit_of_measurement') == \
        LENGTH_KILOMETERS
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Visibility"

    state = hass.states.get('sensor.noaa_weather_kjfk_cloudLayers')
    assert state is not None

    assert state.state == 'FEW'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Cloud Layers"


@asyncio.coroutine
def test_setup_full_imperial(hass, aioclient_mock):
    """Test for full weather sensor config.

    This test case is with imperial units.
    """
    aioclient_mock.get(STAURL, text=load_fixture('noaaweather-sta-valid.json'))
    aioclient_mock.get(
        OBSURL,
        text=load_fixture('noaaweather-obs-valid.json'),
        params={'limit': 5})

    hass.config.units = IMPERIAL_SYSTEM
    with assert_setup_component(1, 'sensor'):
        yield from async_setup_component(hass, 'sensor', VALID_CONFIG_FULL)

    state = hass.states.get('sensor.noaa_weather_kjfk_temperature')
    assert state is not None

    assert state.state == '53.1'
    assert state.attributes.get('unit_of_measurement') == TEMP_FAHRENHEIT
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Temperature"

    state = hass.states.get('sensor.noaa_weather_kjfk_textDescription')
    assert state is not None

    assert state.state == 'Mostly Cloudy and Windy'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Weather"

    state = hass.states.get('sensor.noaa_weather_kjfk_dewpoint')
    assert state is not None

    assert state.state == '29.3'
    assert state.attributes.get('unit_of_measurement') == TEMP_FAHRENHEIT
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather dewpoint"

    state = hass.states.get('sensor.noaa_weather_kjfk_windChill')
    assert state is not None

    assert state.state == '39.9'
    assert state.attributes.get('unit_of_measurement') == TEMP_FAHRENHEIT
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Wind Chill"

    state = hass.states.get('sensor.noaa_weather_kjfk_heatIndex')
    assert state is not None

    assert state.state == '52.0'
    assert state.attributes.get('unit_of_measurement') == TEMP_FAHRENHEIT
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Heat Index"

    state = hass.states.get('sensor.noaa_weather_kjfk_windSpeed')
    assert state is not None

    assert state.state == '10.3'
    assert state.attributes.get('unit_of_measurement') == 'mph'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Wind Speed"

    state = hass.states.get('sensor.noaa_weather_kjfk_windDirection')
    assert state is not None

    assert state.state == '200'
    assert state.attributes.get('unit_of_measurement') == '°'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Wind Bearing"

    state = hass.states.get('sensor.noaa_weather_kjfk_windGust')
    assert state is not None

    assert state.state == '20.8'
    assert state.attributes.get('unit_of_measurement') == 'mph'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Wind Gust"

    state = hass.states.get('sensor.noaa_weather_kjfk_barometricPressure')
    assert state is not None

    assert state.state == '1016.9'
    assert state.attributes.get('unit_of_measurement') == 'mbar'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Pressure"

    state = hass.states.get('sensor.noaa_weather_kjfk_seaLevelPressure')
    assert state is not None

    assert state.state == '1016.8'
    assert state.attributes.get('unit_of_measurement') == 'mbar'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Sea Level Pressure"

    state = hass.states.get(
        'sensor.noaa_weather_kjfk_precipitationLastHour')
    assert state is not None

    assert state.state == '0.4'
    assert state.attributes.get('unit_of_measurement') == LENGTH_INCHES
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Precipitation in last hour"

    state = hass.states.get(
        'sensor.noaa_weather_kjfk_precipitationLast3Hours')
    assert state is not None

    assert state.state == '0.4'
    assert state.attributes.get('unit_of_measurement') == LENGTH_INCHES
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Precipitation in last 3 hours"

    state = hass.states.get(
        'sensor.noaa_weather_kjfk_precipitationLast6Hours')
    assert state is not None

    assert state.state == '0.6'
    assert state.attributes.get('unit_of_measurement') == LENGTH_INCHES
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Precipitation in last 6 hours"

    state = hass.states.get('sensor.noaa_weather_kjfk_relativeHumidity')
    assert state is not None

    assert state.state == '63.0'
    assert state.attributes.get('unit_of_measurement') == '%'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Humidity"

    state = hass.states.get('sensor.noaa_weather_kjfk_visibility')
    assert state is not None

    assert state.state == '10.0'
    assert state.attributes.get('unit_of_measurement') == LENGTH_MILES
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Visibility"

    state = hass.states.get('sensor.noaa_weather_kjfk_cloudLayers')
    assert state is not None

    assert state.state == 'FEW'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Cloud Layers"
