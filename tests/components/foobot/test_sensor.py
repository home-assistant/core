"""The tests for the Foobot sensor platform."""
import asyncio
from http import HTTPStatus
import re
from unittest.mock import MagicMock

import pytest

from homeassistant.components.foobot import sensor as foobot
import homeassistant.components.sensor as sensor
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.setup import async_setup_component

from tests.common import load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

VALID_CONFIG = {
    "platform": "foobot",
    "token": "adfdsfasd",
    "username": "example@example.com",
}


async def test_default_setup(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the default setup."""
    aioclient_mock.get(
        re.compile("api.foobot.io/v2/owner/.*"),
        text=load_fixture("devices.json", "foobot"),
    )
    aioclient_mock.get(
        re.compile("api.foobot.io/v2/device/.*"),
        text=load_fixture("data.json", "foobot"),
    )
    assert await async_setup_component(hass, sensor.DOMAIN, {"sensor": VALID_CONFIG})
    await hass.async_block_till_done()

    metrics = {
        "co2": ["1232.0", CONCENTRATION_PARTS_PER_MILLION],
        "temperature": ["21.1", UnitOfTemperature.CELSIUS],
        "humidity": ["49.5", PERCENTAGE],
        "pm2_5": ["144.8", CONCENTRATION_MICROGRAMS_PER_CUBIC_METER],
        "voc": ["340.7", CONCENTRATION_PARTS_PER_BILLION],
        "index": ["138.9", PERCENTAGE],
    }

    for name, value in metrics.items():
        state = hass.states.get(f"sensor.foobot_happybot_{name}")
        assert state.state == value[0]
        assert state.attributes.get("unit_of_measurement") == value[1]


async def test_setup_timeout_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Expected failures caused by a timeout in API response."""
    fake_async_add_entities = MagicMock()

    aioclient_mock.get(
        re.compile("api.foobot.io/v2/owner/.*"), exc=asyncio.TimeoutError()
    )
    with pytest.raises(PlatformNotReady):
        await foobot.async_setup_platform(hass, VALID_CONFIG, fake_async_add_entities)


async def test_setup_permanent_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Expected failures caused by permanent errors in API response."""
    fake_async_add_entities = MagicMock()

    errors = [HTTPStatus.BAD_REQUEST, HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN]
    for error in errors:
        aioclient_mock.get(re.compile("api.foobot.io/v2/owner/.*"), status=error)
        result = await foobot.async_setup_platform(
            hass, VALID_CONFIG, fake_async_add_entities
        )
        assert result is None


async def test_setup_temporary_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Expected failures caused by temporary errors in API response."""
    fake_async_add_entities = MagicMock()

    errors = [HTTPStatus.TOO_MANY_REQUESTS, HTTPStatus.INTERNAL_SERVER_ERROR]
    for error in errors:
        aioclient_mock.get(re.compile("api.foobot.io/v2/owner/.*"), status=error)
        with pytest.raises(PlatformNotReady):
            await foobot.async_setup_platform(
                hass, VALID_CONFIG, fake_async_add_entities
            )
