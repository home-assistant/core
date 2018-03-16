"""The tests for the Foobot sensor platform."""

import re
import asyncio
from unittest.mock import MagicMock
import pytest


import homeassistant.components.sensor as sensor
from homeassistant.components.sensor import foobot
from homeassistant.const import (TEMP_CELSIUS)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.setup import async_setup_component
from tests.common import load_fixture

VALID_CONFIG = {
    'platform': 'foobot',
    'token': 'adfdsfasd',
    'username': 'example@example.com',
}


async def test_default_setup(hass, aioclient_mock):
    """Test the default setup."""
    aioclient_mock.get(re.compile('api.foobot.io/v2/owner/.*'),
                       text=load_fixture('foobot_devices.json'))
    aioclient_mock.get(re.compile('api.foobot.io/v2/device/.*'),
                       text=load_fixture('foobot_data.json'))
    assert await async_setup_component(hass, sensor.DOMAIN,
                                       {'sensor': VALID_CONFIG})

    metrics = {'co2': ['1232.0', 'ppm'],
               'temperature': ['21.1', TEMP_CELSIUS],
               'humidity': ['49.5', '%'],
               'pm25': ['144.8', 'µg/m3'],
               'voc': ['340.7', 'ppb'],
               'index': ['138.9', '%']}

    for name, value in metrics.items():
        state = hass.states.get('sensor.foobot_happybot_%s' % name)
        assert state.state == value[0]
        assert state.attributes.get('unit_of_measurement') == value[1]


async def test_setup_timeout_error(hass, aioclient_mock):
    """Expected failures caused by a timeout in API response."""
    fake_async_add_devices = MagicMock()

    aioclient_mock.get(re.compile('api.foobot.io/v2/owner/.*'),
                       exc=asyncio.TimeoutError())
    with pytest.raises(PlatformNotReady):
        await foobot.async_setup_platform(hass, {'sensor': VALID_CONFIG},
                                          fake_async_add_devices)


async def test_setup_permanent_error(hass, aioclient_mock):
    """Expected failures caused by permanent errors in API response."""
    fake_async_add_devices = MagicMock()

    errors = [400, 401, 403]
    for error in errors:
        aioclient_mock.get(re.compile('api.foobot.io/v2/owner/.*'),
                           status=error)
        result = await foobot.async_setup_platform(hass,
                                                   {'sensor': VALID_CONFIG},
                                                   fake_async_add_devices)
        assert result is None


async def test_setup_temporary_error(hass, aioclient_mock):
    """Expected failures caused by temporary errors in API response."""
    fake_async_add_devices = MagicMock()

    errors = [429, 500]
    for error in errors:
        aioclient_mock.get(re.compile('api.foobot.io/v2/owner/.*'),
                           status=error)
        with pytest.raises(PlatformNotReady):
            await foobot.async_setup_platform(hass,
                                              {'sensor': VALID_CONFIG},
                                              fake_async_add_devices)
