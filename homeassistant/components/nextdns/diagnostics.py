"""Diagnostics support for NextDNS."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant

from . import NextDnsConfigEntry
from .const import CONF_PROFILE_ID

TO_REDACT = {CONF_API_KEY, CONF_PROFILE_ID, CONF_UNIQUE_ID}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: NextDnsConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    profiles_data: list[dict[str, Any]] = []
    for subentry_id, profile_data in config_entry.runtime_data.profiles.items():
        subentry = config_entry.subentries[subentry_id]
        profiles_data.append(
            {
                "subentry_title": subentry.title,
                "dnssec_coordinator_data": asdict(profile_data.dnssec.data),
                "encryption_coordinator_data": asdict(profile_data.encryption.data),
                "ip_versions_coordinator_data": asdict(profile_data.ip_versions.data),
                "protocols_coordinator_data": asdict(profile_data.protocols.data),
                "settings_coordinator_data": asdict(profile_data.settings.data),
                "status_coordinator_data": asdict(profile_data.status.data),
            }
        )

    return {
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT),
        "profiles": profiles_data,
    }
