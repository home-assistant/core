"""Provide info to system health."""

from typing import Any

from aiogithubapi import GitHubException
from aiogithubapi.common.const import BASE_API_URL

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from .base import async_get_marketplace
from .const import CATALOG_REPOSITORY, DOMAIN

GITHUB_STATUS = "https://www.githubstatus.com/"
CLOUDFLARE_STATUS = "https://www.cloudflarestatus.com/"


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
        return {"Disabled": "The Marketplace is not loaded"}

    marketplace = async_get_marketplace(hass)

    data: dict[str, Any] = {
        "GitHub API": system_health.async_check_can_reach_url(
            hass, BASE_API_URL, GITHUB_STATUS
        ),
        "GitHub Content": system_health.async_check_can_reach_url(
            hass,
            f"https://raw.githubusercontent.com/{CATALOG_REPOSITORY}/main/integration",
        ),
        "GitHub Web": system_health.async_check_can_reach_url(
            hass, "https://github.com/", GITHUB_STATUS
        ),
        "Catalog Data": system_health.async_check_can_reach_url(
            hass, "https://data-v2.hacs.xyz/data.json", CLOUDFLARE_STATUS
        ),
        "GitHub Connected": marketplace.github_connected,
        "Installed Version": marketplace.version,
        "Stage": marketplace.stage,
        "Available Repositories": len(marketplace.repositories.list_all),
        "Downloaded Repositories": len(marketplace.repositories.list_downloaded),
    }

    # The anonymous rate limit is shared by every client on the address, it
    # says nothing about the Marketplace.
    if marketplace.github_connected:
        try:
            response = await marketplace.githubapi.rate_limit()
        except GitHubException:
            # GitHub being out of reach is what the checks above show already
            data["GitHub API Calls Remaining"] = "unknown"
        else:
            data["GitHub API Calls Remaining"] = response.data.resources.core.remaining

    if marketplace.system.disabled:
        data["Disabled"] = marketplace.system.disabled_reason

    return data
