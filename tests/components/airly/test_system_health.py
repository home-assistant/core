"""Test cloud system health."""
import asyncio

from aiohttp import ClientError

from homeassistant.components.airly.const import DOMAIN
from homeassistant.setup import async_setup_component

from tests.async_mock import Mock
from tests.common import get_system_health_info


async def test_airly_system_health(hass, aioclient_mock):
    """Test cloud system health."""
    aioclient_mock.get("https://airapi.airly.eu/v2/", text="")
    hass.config.components.add("airly")
    assert await async_setup_component(hass, "system_health", {})

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN]["0123xyz"] = Mock(
        airly=Mock(AIRLY_API_URL="https://airapi.airly.eu/v2/")
    )

    info = await get_system_health_info(hass, "airly")

    for key, val in info.items():
        if asyncio.iscoroutine(val):
            info[key] = await val

    assert info == {"can_reach_server": "ok"}


async def test_airly_system_health_fail(hass, aioclient_mock):
    """Test cloud system health."""
    aioclient_mock.get("https://airapi.airly.eu/v2/", exc=ClientError)
    hass.config.components.add("airly")
    assert await async_setup_component(hass, "system_health", {})

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN]["0123xyz"] = Mock(
        airly=Mock(AIRLY_API_URL="https://airapi.airly.eu/v2/")
    )

    info = await get_system_health_info(hass, "airly")

    for key, val in info.items():
        if asyncio.iscoroutine(val):
            info[key] = await val

    assert info == {"can_reach_server": {"type": "failed", "error": "unreachable"}}
