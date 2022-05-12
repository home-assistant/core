"""Test Airly system health."""
import asyncio
from unittest.mock import Mock

from aiohttp import ClientError

from homeassistant.components.airly.const import DOMAIN
from homeassistant.setup import async_setup_component

from tests.common import get_system_health_info


async def test_airly_system_health(hass, aioclient_mock):
    """Test Airly system health."""
    aioclient_mock.get("https://airapi.airly.eu/v2/", text="")
    hass.config.components.add(DOMAIN)
    assert await async_setup_component(hass, "system_health", {})

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN]["0123xyz"] = Mock(
        airly=Mock(
            AIRLY_API_URL="https://airapi.airly.eu/v2/",
            requests_remaining=42,
            requests_per_day=100,
        )
    )

    info = await get_system_health_info(hass, DOMAIN)

    for key, val in info.items():
        if asyncio.iscoroutine(val):
            info[key] = await val

    assert info["can_reach_server"] == "ok"
    assert info["requests_remaining"] == 42
    assert info["requests_per_day"] == 100


async def test_airly_system_health_fail(hass, aioclient_mock):
    """Test Airly system health."""
    aioclient_mock.get("https://airapi.airly.eu/v2/", exc=ClientError)
    hass.config.components.add(DOMAIN)
    assert await async_setup_component(hass, "system_health", {})

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN]["0123xyz"] = Mock(
        airly=Mock(
            AIRLY_API_URL="https://airapi.airly.eu/v2/",
            requests_remaining=0,
            requests_per_day=1000,
        )
    )

    info = await get_system_health_info(hass, DOMAIN)

    for key, val in info.items():
        if asyncio.iscoroutine(val):
            info[key] = await val

    assert info["can_reach_server"] == {"type": "failed", "error": "unreachable"}
    assert info["requests_remaining"] == 0
    assert info["requests_per_day"] == 1000
