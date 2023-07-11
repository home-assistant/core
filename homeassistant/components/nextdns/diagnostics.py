"""Diagnostics support for NextDNS."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant

from .const import (
    ATTR_DNSSEC,
    ATTR_ENCRYPTION,
    ATTR_IP_VERSIONS,
    ATTR_PROTOCOLS,
    ATTR_SETTINGS,
    ATTR_STATUS,
    CONF_PROFILE_ID,
    DOMAIN,
)

TO_REDACT = {CONF_API_KEY, CONF_PROFILE_ID, CONF_UNIQUE_ID}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinators = hass.data[DOMAIN][config_entry.entry_id]

    dnssec_coordinator = coordinators[ATTR_DNSSEC]
    encryption_coordinator = coordinators[ATTR_ENCRYPTION]
    ip_versions_coordinator = coordinators[ATTR_IP_VERSIONS]
    protocols_coordinator = coordinators[ATTR_PROTOCOLS]
    settings_coordinator = coordinators[ATTR_SETTINGS]
    status_coordinator = coordinators[ATTR_STATUS]

    diagnostics_data = {
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT),
        "dnssec_coordinator_data": asdict(dnssec_coordinator.data),
        "encryption_coordinator_data": asdict(encryption_coordinator.data),
        "ip_versions_coordinator_data": asdict(ip_versions_coordinator.data),
        "protocols_coordinator_data": asdict(protocols_coordinator.data),
        "settings_coordinator_data": asdict(settings_coordinator.data),
        "status_coordinator_data": asdict(status_coordinator.data),
    }

    return diagnostics_data
