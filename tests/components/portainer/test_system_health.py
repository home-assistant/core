"""Test Portainer system health."""

import asyncio
from unittest.mock import AsyncMock

from aiohttp import ClientError

from homeassistant.components.portainer.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import setup_integration

from tests.common import MockConfigEntry, get_system_health_info
from tests.test_util.aiohttp import AiohttpClientMocker

MOCK_HEALTH_URL = "https://127.0.0.1:9000/api/system/status"


async def test_system_health(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    mock_portainer_client: AsyncMock,
) -> None:
    """Test system health when server is reachable."""
    aioclient_mock.get(MOCK_HEALTH_URL, text="ok")

    assert await async_setup_component(hass, "system_health", {})
    await setup_integration(hass, mock_config_entry)

    info = await get_system_health_info(hass, DOMAIN)

    for key, val in info.items():
        if asyncio.iscoroutine(val):
            info[key] = await val

    assert info["can_reach_server"] == "ok"


async def test_system_health_failed_connect(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    mock_portainer_client: AsyncMock,
) -> None:
    """Test system health when server is unreachable."""
    aioclient_mock.get(MOCK_HEALTH_URL, exc=ClientError)

    assert await async_setup_component(hass, "system_health", {})
    await setup_integration(hass, mock_config_entry)

    info = await get_system_health_info(hass, DOMAIN)

    for key, val in info.items():
        if asyncio.iscoroutine(val):
            info[key] = await val

    assert info["can_reach_server"] == {"error": "unreachable", "type": "failed"}
