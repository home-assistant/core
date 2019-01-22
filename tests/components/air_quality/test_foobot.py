"""The tests for the Foobot air_quality platform."""

import re
import asyncio
from unittest.mock import MagicMock
import pytest


import homeassistant.components.air_quality as air_quality
from homeassistant.components.air_quality import (
    foobot, ATTR_AQI, ATTR_ATTRIBUTION, ATTR_CO2, ATTR_PM_2_5)
from homeassistant.components.air_quality.foobot import (
    ATTR_HUMIDITY, ATTR_FOOBOT_INDEX, ATTR_VOC)
from homeassistant.const import (ATTR_TIME, ATTR_TEMPERATURE)
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
    assert await async_setup_component(hass, air_quality.DOMAIN,
                                       {'air_quality': VALID_CONFIG})

    metrics = {ATTR_CO2: 1232.0,
               ATTR_TEMPERATURE: 21.1,
               ATTR_HUMIDITY: 49.5,
               ATTR_PM_2_5: 144.8,
               ATTR_VOC: 340.7,
               ATTR_FOOBOT_INDEX: 138.9,
               ATTR_ATTRIBUTION: 'Foobot®—Airboxlab S.A.S.',
               ATTR_AQI: 197,
               ATTR_TIME: '2018-02-09T00:09:23Z'}

    state = hass.states.get('air_quality.foobot_happybot')
    assert state.state == '144.8'
    for name, value in metrics.items():
        assert state.attributes.get(name) == value


async def test_setup_timeout_error(hass, aioclient_mock):
    """Expected failures caused by a timeout in API response."""
    fake_async_add_entities = MagicMock()

    aioclient_mock.get(re.compile('api.foobot.io/v2/owner/.*'),
                       exc=asyncio.TimeoutError())
    with pytest.raises(PlatformNotReady):
        await foobot.async_setup_platform(hass, {'air_quality': VALID_CONFIG},
                                          fake_async_add_entities)


async def test_setup_permanent_error(hass, aioclient_mock):
    """Expected failures caused by permanent errors in API response."""
    fake_async_add_entities = MagicMock()

    errors = [400, 401, 403]
    for error in errors:
        aioclient_mock.get(re.compile('api.foobot.io/v2/owner/.*'),
                           status=error)
        result = await foobot.async_setup_platform(hass,
                                                   {'air_quality':
                                                    VALID_CONFIG},
                                                   fake_async_add_entities)
        assert result is None


async def test_setup_temporary_error(hass, aioclient_mock):
    """Expected failures caused by temporary errors in API response."""
    fake_async_add_entities = MagicMock()

    errors = [429, 500]
    for error in errors:
        aioclient_mock.get(re.compile('api.foobot.io/v2/owner/.*'),
                           status=error)
        with pytest.raises(PlatformNotReady):
            await foobot.async_setup_platform(hass,
                                              {'air_quality': VALID_CONFIG},
                                              fake_async_add_entities)


async def test_pm_to_aqi_conversion(hass):
    """Test the PM 2.5 to AQI conversion using values from EPA calculator."""
    values = {0: 0,
              12: 50,
              24: 76,
              55.5: 151,
              144.8: 197,
              320: 369,
              500.4: 500,
              9999999999: 500}

    for pm, aqi in values.items():
        assert foobot.FoobotQuality.pm_2_5_to_aqi(pm) == aqi
