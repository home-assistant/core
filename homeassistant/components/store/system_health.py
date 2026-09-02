"""Provide info to system health."""

from typing import Any

from aiogithubapi.common.const import BASE_API_URL
from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from .base import HacsBase
from .const import DOMAIN

GITHUB_STATUS = "https://www.githubstatus.com/"
CLOUDFLARE_STATUS = "https://www.cloudflarestatus.com/"


@callback
def async_register(hass: HomeAssistant, register: system_health.SystemHealthRegistration) -> None:
    """Register system health callbacks."""
    register.domain = "Home Assistant Community Store"
    register.async_register_info(system_health_info, "/hacs")


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get info for the info page."""
    if DOMAIN not in hass.data:
        return {"Disabled": "HACS is not loaded, but HA still requests this information..."}

    hacs: HacsBase = hass.data[DOMAIN]
    response = await hacs.githubapi.rate_limit()

    data = {
        "GitHub API": system_health.async_check_can_reach_url(hass, BASE_API_URL, GITHUB_STATUS),
        "GitHub Content": system_health.async_check_can_reach_url(
            hass, "https://raw.githubusercontent.com/hacs/integration/main/hacs.json"
        ),
        "GitHub Web": system_health.async_check_can_reach_url(
            hass, "https://github.com/", GITHUB_STATUS
        ),
        "HACS Data": system_health.async_check_can_reach_url(
            hass, "https://data-v2.hacs.xyz/data.json", CLOUDFLARE_STATUS
        ),
        "GitHub API Calls Remaining": response.data.resources.core.remaining,
        "Installed Version": hacs.version,
        "Stage": hacs.stage,
        "Available Repositories": len(hacs.repositories.list_all),
        "Downloaded Repositories": len(hacs.repositories.list_downloaded),
    }

    if hacs.system.disabled:
        data["Disabled"] = hacs.system.disabled_reason

    return data
