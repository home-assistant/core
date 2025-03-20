"""Test Airly system health."""

import asyncio

from aiohttp import ClientError

from homeassistant.components.airly.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import init_integration

from tests.common import get_system_health_info
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_airly_system_health(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test Airly system health."""
    aioclient_mock.get("https://airapi.airly.eu/v2/", text="")

    await init_integration(hass, aioclient_mock)
    assert await async_setup_component(hass, "system_health", {})
    await hass.async_block_till_done()

    info = await get_system_health_info(hass, DOMAIN)

    for key, val in info.items():
        if asyncio.iscoroutine(val):
            info[key] = await val

    assert info["can_reach_server"] == "ok"
    assert info["requests_remaining"] == 42
    assert info["requests_per_day"] == 100


async def test_airly_system_health_fail(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test Airly system health."""
    aioclient_mock.get("https://airapi.airly.eu/v2/", exc=ClientError)

    await init_integration(hass, aioclient_mock)
    assert await async_setup_component(hass, "system_health", {})
    await hass.async_block_till_done()

    info = await get_system_health_info(hass, DOMAIN)

    for key, val in info.items():
        if asyncio.iscoroutine(val):
            info[key] = await val

    assert info["can_reach_server"] == {"type": "failed", "error": "unreachable"}
    assert info["requests_remaining"] == 42
    assert info["requests_per_day"] == 100
