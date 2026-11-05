"""Provide info to system health."""

from typing import Any

from aiogithubapi import GitHubException

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from .base import MarketplaceManager, async_get_marketplace
from .const import CATALOG_REPOSITORY, DOMAIN
from .profiles import Endpoint


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.domain = "Marketplace"
    register.async_register_info(system_health_info, "/marketplace")


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get info for the info page."""
    if not hass.config_entries.async_loaded_entries(DOMAIN):
        return {"disabled": "The Marketplace is not loaded"}

    marketplace = async_get_marketplace(hass)
    # The endpoints the downloads start with
    endpoints = marketplace.endpoints
    profile = endpoints.profile
    api = endpoints.bases(Endpoint.API)[0]
    raw = endpoints.bases(Endpoint.RAW)[0]
    github = endpoints.bases(Endpoint.GITHUB)[0]
    catalog = endpoints.bases(Endpoint.CATALOG)[0]

    data: dict[str, Any] = {
        "download_profile": profile.id,
        "github_api": system_health.async_check_can_reach_url(
            hass, api, profile.status_pages.get("api")
        ),
        "github_content": system_health.async_check_can_reach_url(
            hass, f"{raw}/{CATALOG_REPOSITORY}/main/integration"
        ),
        "github_web": system_health.async_check_can_reach_url(
            hass, f"{github}/", profile.status_pages.get(Endpoint.GITHUB)
        ),
        "catalog_data": system_health.async_check_can_reach_url(
            hass, f"{catalog}/data.json", profile.status_pages.get(Endpoint.CATALOG)
        ),
        "github_connected": marketplace.github_connected,
        "installed_version": marketplace.version,
        "stage": marketplace.stage,
        "available_repositories": len(marketplace.repositories.list_all),
        "installed_repositories": len(marketplace.repositories.list_installed),
    }

    # The anonymous rate limit is shared by every client on the address, it
    # says nothing about the Marketplace. Waited for like the checks above, a
    # slow answer can not hold up the rest.
    if marketplace.github_connected:
        data["github_api_calls_remaining"] = _async_calls_remaining(marketplace)

    if marketplace.system.disabled:
        data["disabled"] = marketplace.system.disabled_reason

    return data


async def _async_calls_remaining(marketplace: MarketplaceManager) -> int | str:
    """Return how many GitHub API calls the connected account has left."""
    try:
        response = await marketplace.githubapi.rate_limit()
    except GitHubException:
        # GitHub being out of reach is what the checks show already
        return "unknown"
    remaining: int = response.data.resources.core.remaining
    return remaining
