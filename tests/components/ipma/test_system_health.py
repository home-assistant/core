"""Test ipma system health."""
import asyncio

from homeassistant.setup import async_setup_component

from tests.common import get_system_health_info


async def test_ipma_system_health(hass, aioclient_mock):
    """Test ipma system health."""
    aioclient_mock.get("https://api.ipma.pt", json={"result": "ok", "data": {}})

    hass.config.components.add("ipma")
    assert await async_setup_component(hass, "system_health", {})

    info = await get_system_health_info(hass, "ipma")

    for key, val in info.items():
        if asyncio.iscoroutine(val):
            info[key] = await val

    assert info == {"api_endpoint_reachable": "ok"}
