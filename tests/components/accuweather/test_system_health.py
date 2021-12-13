"""Test AccuWeather system health."""
import asyncio
from unittest.mock import Mock

from aiohttp import ClientError

from homeassistant.components.accuweather.const import DOMAIN
from homeassistant.setup import async_setup_component

from tests.common import get_system_health_info


async def test_accuweather_system_health(hass, aioclient_mock):
    """Test AccuWeather system health."""
    aioclient_mock.get("https://dataservice.accuweather.com/", text="")
    hass.config.components.add(DOMAIN)
    assert await async_setup_component(hass, "system_health", {})

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN]["0123xyz"] = {}
    hass.data[DOMAIN]["0123xyz"] = Mock(accuweather=Mock(requests_remaining="42"))

    info = await get_system_health_info(hass, DOMAIN)

    for key, val in info.items():
        if asyncio.iscoroutine(val):
            info[key] = await val

    assert info == {
        "can_reach_server": "ok",
        "remaining_requests": "42",
    }


async def test_accuweather_system_health_fail(hass, aioclient_mock):
    """Test AccuWeather system health."""
    aioclient_mock.get("https://dataservice.accuweather.com/", exc=ClientError)
    hass.config.components.add(DOMAIN)
    assert await async_setup_component(hass, "system_health", {})

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN]["0123xyz"] = {}
    hass.data[DOMAIN]["0123xyz"] = Mock(accuweather=Mock(requests_remaining="0"))

    info = await get_system_health_info(hass, DOMAIN)

    for key, val in info.items():
        if asyncio.iscoroutine(val):
            info[key] = await val

    assert info == {
        "can_reach_server": {"type": "failed", "error": "unreachable"},
        "remaining_requests": "0",
    }
