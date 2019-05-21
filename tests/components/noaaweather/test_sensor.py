"""The tests for the NOAA/NWS weather sensor component."""

import asyncio

from pytest import raises

import homeassistant.components.noaaweather.sensor as noaaweather

from homeassistant.setup import (async_setup_component)
from homeassistant.const import (TEMP_CELSIUS, TEMP_FAHRENHEIT,
                                 LENGTH_KILOMETERS, LENGTH_MILES,
                                 LENGTH_INCHES, CONF_LATITUDE,
                                 CONF_LONGITUDE)
from homeassistant.util.unit_system import (IMPERIAL_SYSTEM)
from homeassistant.exceptions import (ConfigEntryNotReady, PlatformNotReady)

from tests.common import (load_fixture, assert_setup_component)

#
# Configuration that just sets up one sensor.
#
VALID_CONFIG_KJFK_MINIMAL = {
    'sensor': {
        'platform': 'noaaweather',
        'latitude': 40.6391,
        'longitude': -73.7639,
        'monitored_conditions': ['temperature'],
        'useragent': 'x@example.com',
    }
}

#
# Configuration that just sets up to get textDescription, using
# the Home Assistant values.
#
VALID_CONFIG_KJFK_TEXT = {
    'sensor': {
        'platform': 'noaaweather',
        'latitude': 40.6391,
        'longitude': -73.7639,
        'monitored_conditions': ['textDescription'],
    }
}

#
# Configuration that sets up all sensors.
#
VALID_CONFIG_KJFK_FULL = {
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
# Configuration for a different station with all sensors.
# The data for this station has many observations with missing values
# that need to be replaced by information from the METAR record that
# is included in the "rawMessage" entry returned in all responses.
#
VALID_CONFIG_PHNG_FULL = {
    'sensor': {
        'platform': 'noaaweather',
        'latitude': 21.4131,
        'longitude': -157.7574,
        'stationcode': 'PHNG',
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
# Configuration that is out of the service area.  This tests the handling
# of an HTTP 404 error when trying to get information for the location.
#
BAD_CONF_LOCATION = {
    'sensor': {
        'platform': 'noaaweather',
        'latitude': 0.0,
        'longitude': 0.0,
        'monitored_conditions': [
            'temperature',
        ],
    }
}

#
# Configuration to test getting no observation data returned.
#
CONF_STATION_KLGA = {
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

#
# Configuration with an invalid station name for the location.
#
BAD_CONF_STATION = {
    'sensor': {
        'platform': 'noaaweather',
        'latitude': 40.6391,
        'longitude': -73.7639,
        'stationcode': 'XXXX',
        'monitored_conditions': [
            'temperature',
        ],
    }
}
#
# Configuration with no location information.
#
BAD_CONF_NOLOCATION = {
    'sensor': {
        'platform': 'noaaweather',
        'monitored_conditions': [
            'temperature',
        ],
    }
}

STAURL = "https://api.weather.gov/points/{},{}/stations"
OBSURL = "https://api.weather.gov/stations/{}/observations/"


@asyncio.coroutine
def test_setup_with_config(hass, aioclient_mock):
    """Test with the configuration."""
    aioclient_mock.get(
        STAURL.format(VALID_CONFIG_KJFK_MINIMAL['sensor']['latitude'],
                      VALID_CONFIG_KJFK_MINIMAL['sensor']['longitude']),
        text=load_fixture('noaaweather-sta-valid.json'))
    aioclient_mock.get(
        OBSURL.format("KJFK"),
        text=load_fixture('noaaweather-obs-valid.json'),
        params={'limit': 5})

    with assert_setup_component(1, 'sensor'):
        yield from async_setup_component(
            hass, 'sensor', VALID_CONFIG_KJFK_MINIMAL)


@asyncio.coroutine
def test_setup_with_nostation(hass, aioclient_mock):
    """Test with the configuration."""
    aioclient_mock.get(
        STAURL.format(VALID_CONFIG_KJFK_MINIMAL['sensor']['latitude'],
                      VALID_CONFIG_KJFK_MINIMAL['sensor']['longitude']),
        text=load_fixture('noaaweather-sta-nosta.json'))
    aioclient_mock.get(
        OBSURL.format("KJFK"),
        text=load_fixture('noaaweather-obs-valid.json'),
        params={'limit': 5})

    with raises(ConfigEntryNotReady):
        yield from noaaweather.async_setup_platform(
            hass, VALID_CONFIG_KJFK_MINIMAL['sensor'], lambda _: None)


@asyncio.coroutine
def test_setup_minimal(hass, aioclient_mock):
    """Test for minimal weather sensor config.

    This test case is with default (metric) units.
    """
    aioclient_mock.get(
        STAURL.format(VALID_CONFIG_KJFK_MINIMAL['sensor']['latitude'],
                      VALID_CONFIG_KJFK_MINIMAL['sensor']['longitude']),
        text=load_fixture('noaaweather-sta-valid.json'))
    aioclient_mock.get(
        OBSURL.format("KJFK"),
        text=load_fixture('noaaweather-obs-valid.json'),
        params={'limit': 5})

    with assert_setup_component(1, 'sensor'):
        yield from async_setup_component(
            hass, 'sensor', VALID_CONFIG_KJFK_MINIMAL)

    state = hass.states.get('sensor.noaa_weather_kjfk_temperature')
    assert state is not None
    assert state.state == '11.7'
    assert state.attributes.get('unit_of_measurement') == TEMP_CELSIUS
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Temperature"


@asyncio.coroutine
def test_sta_badjson(hass, aioclient_mock):
    """Test for minimal weather sensor config.

    This test case uses a station response with bad JSON syntax.
    """
    aioclient_mock.get(
        STAURL.format(VALID_CONFIG_KJFK_MINIMAL['sensor']['latitude'],
                      VALID_CONFIG_KJFK_MINIMAL['sensor']['longitude']),
        text=load_fixture('noaaweather-sta-badjson.json'))
    aioclient_mock.get(
        OBSURL.format("KJFK"),
        text=load_fixture('noaaweather-obs-valid.json'),
        params={'limit': 5})

    with raises(PlatformNotReady):
        yield from noaaweather.async_setup_platform(
            hass, VALID_CONFIG_KJFK_MINIMAL['sensor'], lambda _: None)


@asyncio.coroutine
def test_obs_badjson(hass, aioclient_mock):
    """Test for minimal weather sensor config.

    This test case uses a observation response with bad JSON syntax.
    """
    aioclient_mock.get(
        STAURL.format(VALID_CONFIG_KJFK_MINIMAL['sensor']['latitude'],
                      VALID_CONFIG_KJFK_MINIMAL['sensor']['longitude']),
        text=load_fixture('noaaweather-sta-valid.json'))
    aioclient_mock.get(
        OBSURL.format("KJFK"),
        text=load_fixture('noaaweather-obs-badjson.json'),
        params={'limit': 5})

    with raises(PlatformNotReady):
        yield from noaaweather.async_setup_platform(
            hass, VALID_CONFIG_KJFK_MINIMAL['sensor'], lambda _: None)


@asyncio.coroutine
def test_setup_mintext(hass, aioclient_mock):
    """Test for minimal weather sensor config, getting text description.

    This test case is with default (metric) units.
    The test data for this case has multiple observations with
    the same timestamp.
    """
    aioclient_mock.get(
        STAURL.format(VALID_CONFIG_KJFK_TEXT['sensor']['latitude'],
                      VALID_CONFIG_KJFK_TEXT['sensor']['longitude']),
        text=load_fixture('noaaweather-sta-valid.json'))
    aioclient_mock.get(
        OBSURL.format("KJFK"),
        text=load_fixture('noaaweather-obs-valid-night.json'),
        params={'limit': 5})

    with assert_setup_component(1, 'sensor'):
        yield from async_setup_component(
            hass, 'sensor', VALID_CONFIG_KJFK_TEXT)

    state = hass.states.get('sensor.noaa_weather_kjfk_textdescription')
    assert state is not None
    assert state.state == 'Clear'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Weather"


@asyncio.coroutine
def test_setup_minimal_imperial(hass, aioclient_mock):
    """Test for minimal weather sensor config.

    This case is with imperial units.
    """
    aioclient_mock.get(
        STAURL.format(VALID_CONFIG_KJFK_MINIMAL['sensor']['latitude'],
                      VALID_CONFIG_KJFK_MINIMAL['sensor']['longitude']),
        text=load_fixture('noaaweather-sta-valid.json'))
    aioclient_mock.get(
        OBSURL.format("KJFK"),
        text=load_fixture('noaaweather-obs-valid.json'),
        params={'limit': 5})

    hass.config.units = IMPERIAL_SYSTEM
    with assert_setup_component(1, 'sensor'):
        yield from async_setup_component(
            hass, 'sensor', VALID_CONFIG_KJFK_MINIMAL)

    state = hass.states.get('sensor.noaa_weather_kjfk_temperature')
    assert state is not None
    assert state.state == '53.1'
    assert state.attributes.get('unit_of_measurement') == TEMP_FAHRENHEIT
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Temperature"


@asyncio.coroutine
def test_setup_badconflocation(hass, aioclient_mock):
    """Test for configuration with bad location."""
    aioclient_mock.get(
        STAURL.format(BAD_CONF_LOCATION['sensor']['latitude'],
                      BAD_CONF_LOCATION['sensor']['longitude']),
        status=404)
    aioclient_mock.get(
        OBSURL.format("KJFK"),
        text=load_fixture('noaaweather-obs-valid.json'),
        params={'limit': 5})

    with raises(ConfigEntryNotReady):
        yield from noaaweather.async_setup_platform(
            hass, BAD_CONF_LOCATION['sensor'], lambda _: None)


@asyncio.coroutine
def test_setup_badconfresponse(hass, aioclient_mock):
    """Test for configuration with bad response from web server."""
    aioclient_mock.get(
        STAURL.format(BAD_CONF_LOCATION['sensor']['latitude'],
                      BAD_CONF_LOCATION['sensor']['longitude']),
        status=503)
    aioclient_mock.get(
        OBSURL.format("KJFK"),
        text=load_fixture('noaaweather-obs-valid.json'),
        params={'limit': 5})

    with raises(PlatformNotReady):
        yield from noaaweather.async_setup_platform(
            hass, BAD_CONF_LOCATION['sensor'], lambda _: None)


@asyncio.coroutine
def test_setup_badconfnoloc(hass, aioclient_mock):
    """Test for configuration with no location provided.

    This tests getting a correct ConfigEntryNotReady exception
    when no latitude and longitude values are configured.
    """
    setattr(hass.config, CONF_LATITUDE, None)
    setattr(hass.config, CONF_LONGITUDE, None)

    with raises(ConfigEntryNotReady):
        yield from noaaweather.async_setup_platform(
            hass, BAD_CONF_NOLOCATION['sensor'], lambda _: None)


@asyncio.coroutine
def test_setup_bad_conf_station(hass, aioclient_mock):
    """Test for case where the web server returns an error (other than 404).

    This is the case where the configuration is valid, but
    retrieving observation data failed.  This should
    be a transient error, so the sensor will still exist. However,
    without any data being received, no conditions are available.
    """
    aioclient_mock.get(
        STAURL.format(BAD_CONF_STATION['sensor']['latitude'],
                      BAD_CONF_STATION['sensor']['longitude']),
        text=load_fixture('noaaweather-sta-valid.json'))

    with raises(ConfigEntryNotReady):
        yield from noaaweather.async_setup_platform(
            hass, BAD_CONF_STATION['sensor'], lambda _: None)


@asyncio.coroutine
def test_setup_http505response(hass, aioclient_mock):
    """Test for case where the web server returns an error (other than 404).

    This is the case where the configuration is valid, but
    retrieving observation data failed.  This should
    be a transient error, so the sensor will still exist. However,
    without any data being received, no conditions are available.
    """
    aioclient_mock.get(
        STAURL.format(CONF_STATION_KLGA['sensor']['latitude'],
                      CONF_STATION_KLGA['sensor']['longitude']),
        text=load_fixture('noaaweather-sta-valid.json'))
    aioclient_mock.get(OBSURL.format("KLGA"), status=505)

    with assert_setup_component(1, 'sensor'):
        yield from async_setup_component(hass, 'sensor', CONF_STATION_KLGA)

    state = hass.states.get('sensor.noaa_weather_klga_temperature')
    assert state is None


@asyncio.coroutine
def test_setup_badobs(hass, aioclient_mock):
    """Test for configuration with bad station.

    In this case, a request for station observations returns valid json
    but with no data values.  The result will be a sensor with no
    conditions available.
    """
    aioclient_mock.get(
        STAURL.format(CONF_STATION_KLGA['sensor']['latitude'],
                      CONF_STATION_KLGA['sensor']['longitude']),
        text=load_fixture('noaaweather-sta-valid.json'))
    aioclient_mock.get(
        OBSURL.format("KLGA"),
        text=load_fixture('noaaweather-obs-empty.json'),
        params={'limit': 5})

    with assert_setup_component(1, 'sensor'):
        yield from async_setup_component(hass, 'sensor', CONF_STATION_KLGA)

    state = hass.states.get('sensor.noaa_weather_klga_temperature')
    assert state is None


@asyncio.coroutine
def test_setup_badtextdesc(hass, aioclient_mock):
    """Test for no valid text in textDescription response.

    In this we should get back the unrecognized text for the description.
    """
    aioclient_mock.get(
        STAURL.format(VALID_CONFIG_KJFK_TEXT['sensor']['latitude'],
                      VALID_CONFIG_KJFK_TEXT['sensor']['longitude']),
        text=load_fixture('noaaweather-sta-valid.json'))
    aioclient_mock.get(
        OBSURL.format("KJFK"),
        text=load_fixture('noaaweather-obs-badtext.json'),
        params={'limit': 5})

    with assert_setup_component(1, 'sensor'):
        yield from async_setup_component(hass, 'sensor',
                                         VALID_CONFIG_KJFK_TEXT)

    state = hass.states.get('sensor.noaa_weather_kjfk_textdescription')
    assert state is not None
    assert state.state == 'Strange Description'


@asyncio.coroutine
def test_setup_badunits(hass, aioclient_mock):
    """Test for unknown unitCode value or missing value.

    The data has a temperature value set with an unknown unit code (degK
    instead of degC or degF), degF set for heatIndex, and
    no unit code for dewpoint.

    """
    aioclient_mock.get(
        STAURL.format(VALID_CONFIG_KJFK_FULL['sensor']['latitude'],
                      VALID_CONFIG_KJFK_FULL['sensor']['longitude']),
        text=load_fixture('noaaweather-sta-valid.json'))
    aioclient_mock.get(
        OBSURL.format("KJFK"),
        text=load_fixture('noaaweather-obs-badunits.json'),
        params={'limit': 5})

    with assert_setup_component(1, 'sensor'):
        yield from async_setup_component(hass, 'sensor',
                                         VALID_CONFIG_KJFK_FULL)

    state = hass.states.get('sensor.noaa_weather_kjfk_temperature')
    assert state is not None
    assert state.state == 'unknown'

    state = hass.states.get('sensor.noaa_weather_kjfk_dewpoint')
    assert state is not None
    assert state.state == 'unknown'

    state = hass.states.get('sensor.noaa_weather_kjfk_heatindex')
    assert state is not None
    assert state.state == '32.8'


@asyncio.coroutine
def test_setup_full(hass, aioclient_mock):
    """Test for full weather sensor config.

    This test case is with default (metric) units.
    """
    aioclient_mock.get(
        STAURL.format(VALID_CONFIG_KJFK_FULL['sensor']['latitude'],
                      VALID_CONFIG_KJFK_FULL['sensor']['longitude']),
        text=load_fixture('noaaweather-sta-valid.json'))
    aioclient_mock.get(
        OBSURL.format("KJFK"),
        text=load_fixture('noaaweather-obs-valid.json'),
        params={'limit': 5})

    with assert_setup_component(1, 'sensor'):
        yield from async_setup_component(
            hass, 'sensor', VALID_CONFIG_KJFK_FULL)

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
        "NOAA Weather Dew Point"

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
        "NOAA Weather Precipitation in Last Hour"

    state = hass.states.get(
        'sensor.noaa_weather_kjfk_precipitationLast3Hours')
    assert state is not None
    assert state.state == '11.0'
    assert state.attributes.get('unit_of_measurement') == 'mm'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Precipitation in Last 3 Hours"

    state = hass.states.get(
        'sensor.noaa_weather_kjfk_precipitationLast6Hours')
    assert state is not None
    assert state.state == '15.0'
    assert state.attributes.get('unit_of_measurement') == 'mm'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Precipitation in Last 6 Hours"

    state = hass.states.get('sensor.noaa_weather_kjfk_relativeHumidity')
    assert state is not None
    assert state.state == '63.0'
    assert state.attributes.get('unit_of_measurement') == '%'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Humidity"

    state = hass.states.get('sensor.noaa_weather_kjfk_visibility')
    assert state is not None
    assert state.state == '16.0'
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
def test_setup_full_metar(hass, aioclient_mock):
    """Test for full weather sensor config.

    This test case is with default (metric) units.
    The observation data includes entries with missing data
    in the normal json observation record, but with the data
    available in the rawMessage METAR record.
    """
    aioclient_mock.get(
        STAURL.format(VALID_CONFIG_PHNG_FULL['sensor']['latitude'],
                      VALID_CONFIG_PHNG_FULL['sensor']['longitude']),
        text=load_fixture('noaaweather-sta-phng.json'))
    aioclient_mock.get(
        OBSURL.format("PHNG"),
        text=load_fixture('noaaweather-obs-phng-metar.json'),
        params={'limit': 5})

    with assert_setup_component(1, 'sensor'):
        yield from async_setup_component(
            hass, 'sensor', VALID_CONFIG_PHNG_FULL)

    state = hass.states.get('sensor.noaa_weather_phng_temperature')
    assert state is not None
    assert state.state == '24.4'
    assert state.attributes.get('unit_of_measurement') == TEMP_CELSIUS
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Temperature"

    state = hass.states.get('sensor.noaa_weather_phng_textDescription')
    assert state is not None
    assert state.state == 'Mostly Clear'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Weather"

    state = hass.states.get('sensor.noaa_weather_phng_dewpoint')
    assert state is not None
    assert state.state == '17.8'
    assert state.attributes.get('unit_of_measurement') == TEMP_CELSIUS
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Dew Point"

    state = hass.states.get('sensor.noaa_weather_phng_windChill')
    assert state is not None
    assert state.state == 'unknown'
    assert state.attributes.get('unit_of_measurement') == TEMP_CELSIUS
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Wind Chill"

    state = hass.states.get('sensor.noaa_weather_phng_heatIndex')
    assert state is not None
    assert state.state == '24.6'
    assert state.attributes.get('unit_of_measurement') == TEMP_CELSIUS
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Heat Index"

    state = hass.states.get('sensor.noaa_weather_phng_windSpeed')
    assert state is not None
    assert state.state == '20.4'
    assert state.attributes.get('unit_of_measurement') == 'km/h'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Wind Speed"

    state = hass.states.get('sensor.noaa_weather_phng_windDirection')
    assert state is not None
    assert state.state == '60.0'
    assert state.attributes.get('unit_of_measurement') == '°'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Wind Bearing"

    state = hass.states.get('sensor.noaa_weather_phng_windGust')
    assert state is not None
    assert state.state == 'unknown'
    assert state.attributes.get('unit_of_measurement') == 'km/h'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Wind Gust"

    state = hass.states.get('sensor.noaa_weather_phng_barometricPressure')
    assert state is not None
    assert state.state == '1019.98'
    assert state.attributes.get('unit_of_measurement') == 'mbar'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Pressure"

    state = hass.states.get('sensor.noaa_weather_phng_seaLevelPressure')
    assert state is not None
    assert state.state == '1019.5'
    assert state.attributes.get('unit_of_measurement') == 'mbar'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Sea Level Pressure"

    state = hass.states.get(
        'sensor.noaa_weather_phng_precipitationLastHour')
    assert state is not None
    assert state.state == '0'
    assert state.attributes.get('unit_of_measurement') == 'mm'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Precipitation in Last Hour"

    state = hass.states.get(
        'sensor.noaa_weather_phng_precipitationLast3Hours')
    assert state is not None
    assert state.state == 'unknown'
    assert state.attributes.get('unit_of_measurement') == 'mm'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Precipitation in Last 3 Hours"

    state = hass.states.get(
        'sensor.noaa_weather_phng_precipitationLast6Hours')
    assert state is not None
    assert state.state == '0'
    assert state.attributes.get('unit_of_measurement') == 'mm'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Precipitation in Last 6 Hours"

    state = hass.states.get('sensor.noaa_weather_phng_relativeHumidity')
    assert state is not None
    assert state.state == 'unknown'
    assert state.attributes.get('unit_of_measurement') == '%'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Humidity"

    state = hass.states.get('sensor.noaa_weather_phng_visibility')
    assert state is not None
    assert state.state == '16.0'
    assert state.attributes.get('unit_of_measurement') == \
        LENGTH_KILOMETERS
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Visibility"

    state = hass.states.get('sensor.noaa_weather_phng_cloudLayers')
    assert state is not None
    assert state.state == 'FEW'
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Cloud Layers"


@asyncio.coroutine
def test_setup_full_imperial(hass, aioclient_mock):
    """Test for full weather sensor config.

    This test case is with imperial units.
    """
    aioclient_mock.get(
        STAURL.format(VALID_CONFIG_KJFK_FULL['sensor']['latitude'],
                      VALID_CONFIG_KJFK_FULL['sensor']['longitude']),
        text=load_fixture('noaaweather-sta-valid.json'))
    aioclient_mock.get(
        OBSURL.format("KJFK"),
        text=load_fixture('noaaweather-obs-valid.json'),
        params={'limit': 5})

    hass.config.units = IMPERIAL_SYSTEM
    with assert_setup_component(1, 'sensor'):
        yield from async_setup_component(
            hass, 'sensor', VALID_CONFIG_KJFK_FULL)

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
        "NOAA Weather Dew Point"

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
    assert state.state == '0.394'
    assert state.attributes.get('unit_of_measurement') == LENGTH_INCHES
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Precipitation in Last Hour"

    state = hass.states.get(
        'sensor.noaa_weather_kjfk_precipitationLast3Hours')
    assert state is not None
    assert state.state == '0.433'
    assert state.attributes.get('unit_of_measurement') == LENGTH_INCHES
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Precipitation in Last 3 Hours"

    state = hass.states.get(
        'sensor.noaa_weather_kjfk_precipitationLast6Hours')
    assert state is not None
    assert state.state == '0.591'
    assert state.attributes.get('unit_of_measurement') == LENGTH_INCHES
    assert state.attributes.get('friendly_name') == \
        "NOAA Weather Precipitation in Last 6 Hours"

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
