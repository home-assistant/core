"""Tests for the Duco system health."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from homeassistant.components.duco.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, get_system_health_info


async def test_system_health(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_duco_client: AsyncMock,
) -> None:
    """Test Duco system health."""
    assert await async_setup_component(hass, "system_health", {})
    await hass.async_block_till_done()

    info = await get_system_health_info(hass, DOMAIN)

    for key, val in info.items():
        if asyncio.iscoroutine(val):
            info[key] = await val

    assert info == {
        "write_requests_remaining": 100,
    }
