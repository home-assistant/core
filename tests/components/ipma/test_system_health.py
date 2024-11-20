"""Test ipma system health."""

import asyncio

from homeassistant.components.ipma.system_health import IPMA_API_URL
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import get_system_health_info
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_ipma_system_health(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test ipma system health."""
    aioclient_mock.get(IPMA_API_URL, json={"result": "ok", "data": {}})

    hass.config.components.add("ipma")
    assert await async_setup_component(hass, "system_health", {})
    await hass.async_block_till_done()

    info = await get_system_health_info(hass, "ipma")

    for key, val in info.items():
        if asyncio.iscoroutine(val):
            info[key] = await val

    assert info == {"api_endpoint_reachable": "ok"}
