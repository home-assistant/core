"""The tests for the WUnderground platform."""
import asyncio

import aiohttp
from homeassistant.core import callback
from homeassistant.components.sensor import wunderground
from homeassistant.const import TEMP_CELSIUS, LENGTH_INCHES, STATE_UNKNOWN
from homeassistant.exceptions import PlatformNotReady
from pytest import raises

from tests.common import load_fixture

VALID_CONFIG_PWS = {
    'platform': 'wunderground',
    'api_key': 'foo',
    'pws_id': 'bar',
    'monitored_conditions': [
        'weather', 'feelslike_c', 'alerts', 'elevation', 'location'
    ]
}

VALID_CONFIG = {
    'platform': 'wunderground',
    'api_key': 'foo',
    'monitored_conditions': [
        'weather', 'feelslike_c', 'alerts', 'elevation', 'location',
        'weather_1d_metric', 'precip_1d_in'
    ]
}

INVALID_CONFIG = {
    'platform': 'wunderground',
    'api_key': 'BOB',
    'pws_id': 'bar',
    'lang': 'foo',
    'monitored_conditions': [
        'weather', 'feelslike_c', 'alerts'
    ]
}

URL = 'http://api.wunderground.com/api/foo/alerts/conditions/forecast/lang' \
      ':None/q/32.87336,-117.22743.json'
PWS_URL = 'http://api.wunderground.com/api/foo/alerts/conditions/' \
          'lang:None/q/pws:bar.json'
INVALID_URL = 'http://api.wunderground.com/api/BOB/alerts/conditions/' \
              'lang:foo/q/pws:bar.json'


@asyncio.coroutine
def test_setup(hass, aioclient_mock):
    """Test that the component is loaded if passed in PWS Id."""
    aioclient_mock.get(URL, text=load_fixture('wunderground-valid.json'))
    aioclient_mock.get(PWS_URL, text=load_fixture('wunderground-valid.json'))
    aioclient_mock.get(INVALID_URL, text=load_fixture('wunderground-error.json'))

    result = yield from wunderground.async_setup_platform(
        hass, VALID_CONFIG_PWS, lambda _: None)
    assert result

    aioclient_mock.get(URL, text=load_fixture('wunderground-valid.json'))

    result = yield from wunderground.async_setup_platform(
        hass, VALID_CONFIG, lambda _: None)
    assert result

    with raises(PlatformNotReady):
        yield from wunderground.async_setup_platform(hass, INVALID_CONFIG,
                                                     lambda _: None)


@asyncio.coroutine
def test_sensor(hass, aioclient_mock):
    """Test the WUnderground sensor class and methods."""
    aioclient_mock.get(URL, text=load_fixture('wunderground-valid.json'))

    devices = []

    @callback
    def async_add_devices(new_devices):
        """Mock add devices."""
        for device in new_devices:
            devices.append(device)

    result = yield from wunderground.async_setup_platform(hass, VALID_CONFIG,
                                                          async_add_devices)
    assert result

    for device in devices:
        yield from device.async_update()
        entity_id = device.entity_id
        assert entity_id.startswith('sensor.pws_')
        friendly_name = device.name

        if entity_id == 'sensor.pws_weather':
            assert 'https://icons.wxug.com/i/c/k/clear.gif' == device.entity_picture
            assert 'Clear' == device.state
            assert device.unit_of_measurement is None
            assert "Weather Summary" == friendly_name
        elif entity_id == 'sensor.pws_alerts':
            assert 1 == device.state
            assert 'This is a test alert message' == device.device_state_attributes['Message']
            assert 'mdi:alert-circle-outline' == device.icon
            assert device.entity_picture is None
            assert 'Alerts' == friendly_name
        elif entity_id == 'sensor.pws_location':
            assert 'Holly Springs, NC' == device.state
            assert 'Location' == friendly_name
        elif entity_id == 'sensor.pws_elevation':
            assert '413' == device.state
            assert 'Elevation' == friendly_name
        elif entity_id == 'sensor.pws_feelslike_c':
            assert device.entity_picture is None
            assert '40' == device.state
            assert TEMP_CELSIUS == device.unit_of_measurement
            assert "Feels Like" == friendly_name
        elif entity_id == 'sensor.pws_weather_1d_metric':
            assert 'Mostly Cloudy. Fog overnight.' == device.state
            assert 'Tuesday' == friendly_name
        else:
            assert 'sensor.pws_precip_1d_in' == entity_id
            assert 0.03 == device.state
            assert LENGTH_INCHES == device.unit_of_measurement
            assert 'Precipitation Intensity Today' == friendly_name


@asyncio.coroutine
def test_connect_failed(hass, aioclient_mock):
    """Test the WUnderground connection error."""
    aioclient_mock.get(URL, exc=aiohttp.ClientError())
    with raises(PlatformNotReady):
        yield from wunderground.async_setup_platform(hass, VALID_CONFIG,
                                                     lambda _: None)


@asyncio.coroutine
def test_invalid_data(hass, aioclient_mock):
    """Test the WUnderground invalid data."""
    aioclient_mock.get(PWS_URL, text=load_fixture('wunderground-invalid.json'))
    devices = []

    @callback
    def async_add_devices(new_devices):
        """Mock add devices."""
        for device in new_devices:
            devices.append(device)

    result = yield from wunderground.async_setup_platform(
        hass, VALID_CONFIG_PWS, async_add_devices)
    assert result

    for device in devices:
        yield from device.async_update()
        assert STATE_UNKNOWN == device.state
