"""Tests for the Community store system health."""

import asyncio
from typing import Any

import pytest

from homeassistant.components.store.base import HacsBase
from homeassistant.components.store.const import DOMAIN
from homeassistant.components.store.enums import DisabledReason
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, get_system_health_info


async def _resolved_info(hass: HomeAssistant) -> dict[str, Any]:
    """Return the system health info with the reachability checks resolved."""
    info = await get_system_health_info(hass, DOMAIN)
    for key, value in info.items():
        if asyncio.iscoroutine(value):
            info[key] = await value
    return info


@pytest.mark.usefixtures("init_integration")
async def test_system_health(hass: HomeAssistant) -> None:
    """Test the system health of a set up store."""
    assert await async_setup_component(hass, "system_health", {})

    info = await _resolved_info(hass)

    assert info == {
        "GitHub API": "ok",
        "GitHub API Calls Remaining": 4999,
        "GitHub Content": "ok",
        "GitHub Web": "ok",
        "HACS Data": "ok",
        "Available Repositories": 5,
        "Downloaded Repositories": 0,
        "Installed Version": info["Installed Version"],
        "Stage": "running",
    }


async def test_system_health_when_disabled(
    hass: HomeAssistant, store: HacsBase
) -> None:
    """Test that a disabled store reports why."""
    assert await async_setup_component(hass, "system_health", {})
    store.disable_hacs(DisabledReason.RATE_LIMIT)

    info = await _resolved_info(hass)

    assert info["Disabled"] is DisabledReason.RATE_LIMIT


async def test_system_health_after_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, store: HacsBase
) -> None:
    """Test the system health after the store was unloaded."""
    assert await async_setup_component(hass, "system_health", {})
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    info = await _resolved_info(hass)

    assert info == {"Disabled": "The Community store is not loaded"}
