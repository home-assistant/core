"""The tests for the WUnderground platform."""
import asyncio
import aiohttp

from pytest import raises

from homeassistant.core import callback
from homeassistant.components.sensor import wunderground
from homeassistant.const import TEMP_CELSIUS, LENGTH_INCHES, STATE_UNKNOWN
from homeassistant.exceptions import PlatformNotReady
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
    aioclient_mock.get(INVALID_URL,
                       text=load_fixture('wunderground-error.json'))

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
            assert device.entity_picture == \
                'https://icons.wxug.com/i/c/k/clear.gif'
            assert device.state == 'Clear'
            assert device.unit_of_measurement is None
            assert friendly_name == "Weather Summary"
        elif entity_id == 'sensor.pws_alerts':
            assert device.state == 1
            assert device.device_state_attributes['Message'] == \
                'This is a test alert message'
            assert device.icon == 'mdi:alert-circle-outline'
            assert device.entity_picture is None
            assert friendly_name == 'Alerts'
        elif entity_id == 'sensor.pws_location':
            assert device.state == 'Holly Springs, NC'
            assert friendly_name == 'Location'
        elif entity_id == 'sensor.pws_elevation':
            assert device.state == '413'
            assert friendly_name == 'Elevation'
        elif entity_id == 'sensor.pws_feelslike_c':
            assert device.entity_picture is None
            assert device.state == '40'
            assert device.unit_of_measurement == TEMP_CELSIUS
            assert friendly_name == "Feels Like"
        elif entity_id == 'sensor.pws_weather_1d_metric':
            assert device.state == 'Mostly Cloudy. Fog overnight.'
            assert friendly_name == 'Tuesday'
        else:
            assert entity_id == 'sensor.pws_precip_1d_in'
            assert device.state == 0.03
            assert device.unit_of_measurement == LENGTH_INCHES
            assert friendly_name == 'Precipitation Intensity Today'


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
