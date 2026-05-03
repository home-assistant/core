"""Test Portainer system health."""

import asyncio

from aiohttp import ClientError

from homeassistant.components.portainer.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import MOCK_TEST_CONFIG, TEST_ENTRY, TEST_INSTANCE_ID

from tests.common import MockConfigEntry, get_system_health_info
from tests.test_util.aiohttp import AiohttpClientMocker

MOCK_HEALTH_URL = "https://127.0.0.1:9000/api/system/status"


async def test_system_health(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test system health when server is reachable."""
    aioclient_mock.get(MOCK_HEALTH_URL, text="ok")

    hass.config.components.add(DOMAIN)
    assert await async_setup_component(hass, "system_health", {})
    await hass.async_block_till_done()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_TEST_CONFIG,
        unique_id=TEST_INSTANCE_ID,
        entry_id=TEST_ENTRY,
        state=ConfigEntryState.LOADED,
    )
    entry.add_to_hass(hass)

    info = await get_system_health_info(hass, DOMAIN)

    for key, val in info.items():
        if asyncio.iscoroutine(val):
            info[key] = await val

    assert info["can_reach_server"] == "ok"


async def test_system_health_failed_connect(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test system health when server is unreachable."""
    aioclient_mock.get(MOCK_HEALTH_URL, exc=ClientError)

    hass.config.components.add(DOMAIN)
    assert await async_setup_component(hass, "system_health", {})
    await hass.async_block_till_done()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_TEST_CONFIG,
        unique_id=TEST_INSTANCE_ID,
        entry_id=TEST_ENTRY,
        state=ConfigEntryState.LOADED,
    )
    entry.add_to_hass(hass)

    info = await get_system_health_info(hass, DOMAIN)

    for key, val in info.items():
        if asyncio.iscoroutine(val):
            info[key] = await val

    assert info["can_reach_server"] == {"error": "unreachable", "type": "failed"}
