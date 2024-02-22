"""Test GIOS system health."""
import asyncio

from aiohttp import ClientError

from homeassistant.components.gios.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import get_system_health_info
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_gios_system_health(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test GIOS system health."""
    aioclient_mock.get("http://api.gios.gov.pl/", text="")
    hass.config.components.add(DOMAIN)
    assert await async_setup_component(hass, "system_health", {})

    info = await get_system_health_info(hass, DOMAIN)

    for key, val in info.items():
        if asyncio.iscoroutine(val):
            info[key] = await val

    assert info == {"can_reach_server": "ok"}


async def test_gios_system_health_fail(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test GIOS system health."""
    aioclient_mock.get("http://api.gios.gov.pl/", exc=ClientError)
    hass.config.components.add(DOMAIN)
    assert await async_setup_component(hass, "system_health", {})

    info = await get_system_health_info(hass, DOMAIN)

    for key, val in info.items():
        if asyncio.iscoroutine(val):
            info[key] = await val

    assert info == {"can_reach_server": {"type": "failed", "error": "unreachable"}}
