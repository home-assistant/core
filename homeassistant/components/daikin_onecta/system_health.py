"""Provide system health information for Daikin Onecta."""

from typing import Any

from homeassistant.components import system_health
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback

from .const import DAIKIN_API_URL, DOMAIN, OAUTH2_AUTHORIZE
from .coordinator import DaikinOnectaConfigEntry


def _entry_label(config_entry: DaikinOnectaConfigEntry) -> str:
    """Return an unambiguous label for an account entry."""
    return f"{config_entry.title or config_entry.entry_id} ({config_entry.entry_id})"


def _entry_info(config_entry: DaikinOnectaConfigEntry) -> dict[str, Any]:
    """Return locally cached health data for an account entry."""
    coordinator = config_entry.runtime_data
    return {
        "max_minute": coordinator.rate_limits["minute"],
        "max_day": coordinator.rate_limits["day"],
        "remaining_minute": coordinator.rate_limits["remaining_minutes"],
        "remaining_day": coordinator.rate_limits["remaining_day"],
        "retry_after": coordinator.rate_limits["retry_after"],
        "ratelimit_reset": coordinator.rate_limits["ratelimit_reset"],
        "oauth2_token_valid": coordinator.session.valid_token,
    }


def _summarize_entries(
    entries: list[tuple[DaikinOnectaConfigEntry, dict[str, Any]]], key: str
) -> str:
    """Return one system-health value containing every configured account."""
    return "; ".join(
        f"{_entry_label(config_entry)}: {info[key]}" for config_entry, info in entries
    )


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Return system health information for every loaded account entry."""
    entries = [
        (config_entry, _entry_info(config_entry))
        for config_entry in hass.config_entries.async_entries(DOMAIN)
        if config_entry.state is ConfigEntryState.LOADED
        and config_entry.runtime_data is not None
    ]
    if not entries:
        return {}

    info: dict[str, Any] = {
        "api_status": system_health.async_check_can_reach_url(
            hass, f"{DAIKIN_API_URL}/gateway-devices"
        ),
        "oauth2_status": system_health.async_check_can_reach_url(
            hass, OAUTH2_AUTHORIZE
        ),
    }
    if len(entries) == 1:
        info.update(entries[0][1])
        return info

    for key in entries[0][1]:
        info[key] = _summarize_entries(entries, key)
    return info
