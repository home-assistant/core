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


async def _resolve(info: dict[str, Any]) -> dict[str, Any]:
    """Resolve the values system health waits for, in place."""
    for key, value in info.items():
        if asyncio.iscoroutine(value):
            info[key] = await value
    return info


async def _resolved_info(hass: HomeAssistant) -> dict[str, Any]:
    """Return the system health info with the reachability checks resolved."""
    return await _resolve(await get_system_health_info(hass, DOMAIN))


@pytest.mark.usefixtures("init_integration")
async def test_system_health(hass: HomeAssistant) -> None:
    """Test the system health of a set up Marketplace."""
    assert await async_setup_component(hass, "system_health", {})

    info = await _resolved_info(hass)

    assert info == {
        "github_api": "ok",
        "github_api_calls_remaining": 4999,
        "github_connected": True,
        "github_content": "ok",
        "github_web": "ok",
        "catalog_data": "ok",
        "available_repositories": 4,
        "installed_repositories": 0,
        "installed_version": info["installed_version"],
        "stage": "running",
    }


@pytest.mark.usefixtures("init_integration")
async def test_system_health_does_not_wait_for_the_rate_limit(
    hass: HomeAssistant,
) -> None:
    """Test a slow answer about the rate limit can not hold up the rest."""
    assert await async_setup_component(hass, "system_health", {})

    info = await get_system_health_info(hass, DOMAIN)

    calls_remaining = info.pop("github_api_calls_remaining")
    await _resolve(info)

    # Waited for like the reachability checks, each with its own timeout
    assert asyncio.iscoroutine(calls_remaining)
    assert await calls_remaining == 4999


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

    assert info["github_api_calls_remaining"] == "unknown"


@pytest.mark.parametrize("github_token", [None])
@pytest.mark.usefixtures("init_integration")
async def test_system_health_without_github(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the system health leaves the anonymous rate limit alone."""
    assert await async_setup_component(hass, "system_health", {})

    info = await _resolved_info(hass)

    assert info["github_connected"] is False
    assert "github_api_calls_remaining" not in info
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

    assert info["disabled"] is DisabledReason.RATE_LIMIT


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

    assert info == {"disabled": "The Marketplace is not loaded"}
