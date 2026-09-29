"""Tests for the Marketplace system health."""

import asyncio
from typing import Any
from unittest.mock import patch

from aiogithubapi import GitHubAuthenticationException
import pytest

from homeassistant.components.marketplace.base import MarketplaceManager
from homeassistant.components.marketplace.const import DOMAIN
from homeassistant.components.marketplace.enums import DisabledReason
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, get_system_health_info
from tests.test_util.aiohttp import AiohttpClientMocker


async def _resolved_info(hass: HomeAssistant) -> dict[str, Any]:
    """Return the system health info with the reachability checks resolved."""
    info = await get_system_health_info(hass, DOMAIN)
    for key, value in info.items():
        if asyncio.iscoroutine(value):
            info[key] = await value
    return info


@pytest.mark.usefixtures("init_integration")
async def test_system_health(hass: HomeAssistant) -> None:
    """Test the system health of a set up Marketplace."""
    assert await async_setup_component(hass, "system_health", {})

    info = await _resolved_info(hass)

    assert info == {
        "GitHub API": "ok",
        "GitHub API Calls Remaining": 4999,
        "GitHub Connected": True,
        "GitHub Content": "ok",
        "GitHub Web": "ok",
        "Catalog Data": "ok",
        "Available Repositories": 4,
        "Installed Repositories": 0,
        "Installed Version": info["Installed Version"],
        "Stage": "running",
    }


@pytest.mark.usefixtures("init_integration")
async def test_system_health_when_github_fails(
    hass: HomeAssistant, marketplace: MarketplaceManager
) -> None:
    """Test a failing rate limit call does not take the section down."""
    assert await async_setup_component(hass, "system_health", {})

    with patch.object(
        marketplace.githubapi,
        "rate_limit",
        side_effect=GitHubAuthenticationException("Bad credentials"),
    ):
        info = await _resolved_info(hass)

    assert info["GitHub API Calls Remaining"] == "unknown"


@pytest.mark.parametrize("github_token", [None])
@pytest.mark.usefixtures("init_integration")
async def test_system_health_without_github(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the system health leaves the anonymous rate limit alone."""
    assert await async_setup_component(hass, "system_health", {})

    info = await _resolved_info(hass)

    assert info["GitHub Connected"] is False
    assert "GitHub API Calls Remaining" not in info
    assert not [
        url for _, url, _, _ in aioclient_mock.mock_calls if url.path == "/rate_limit"
    ]


async def test_system_health_when_disabled(
    hass: HomeAssistant, marketplace: MarketplaceManager
) -> None:
    """Test that a disabled Marketplace reports why."""
    assert await async_setup_component(hass, "system_health", {})
    marketplace.disable(DisabledReason.RATE_LIMIT)

    info = await _resolved_info(hass)

    assert info["Disabled"] is DisabledReason.RATE_LIMIT


async def test_system_health_after_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    marketplace: MarketplaceManager,
) -> None:
    """Test the system health after the Marketplace was unloaded."""
    assert await async_setup_component(hass, "system_health", {})
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    info = await _resolved_info(hass)

    assert info == {"Disabled": "The Marketplace is not loaded"}
