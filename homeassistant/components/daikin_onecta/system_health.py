"""Provide system health information for Daikin Onecta."""

from typing import Any

from homeassistant.components import system_health
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback

from .const import DAIKIN_API_URL, DOMAIN, OAUTH2_AUTHORIZE


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Return system health information for the first loaded entry."""
    for config_entry in hass.config_entries.async_entries(DOMAIN):
        if config_entry.state is not ConfigEntryState.LOADED:
            continue
        coordinator = config_entry.runtime_data
        if coordinator is None:
            continue

        api = coordinator.api
        return {
            "api_status": system_health.async_check_can_reach_url(
                hass, f"{DAIKIN_API_URL}/gateway-devices"
            ),
            "oauth2_status": system_health.async_check_can_reach_url(
                hass, OAUTH2_AUTHORIZE
            ),
            "max_minute": api.rate_limits["minute"],
            "max_day": api.rate_limits["day"],
            "remaining_minute": api.rate_limits["remaining_minutes"],
            "remaining_day": api.rate_limits["remaining_day"],
            "retry_after": api.rate_limits["retry_after"],
            "ratelimit_reset": api.rate_limits["ratelimit_reset"],
            "oauth2_token_valid": api.session.valid_token,
        }
    return {}
