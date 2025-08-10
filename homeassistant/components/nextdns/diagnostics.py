"""Diagnostics support for NextDNS."""

from __future__ import annotations

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
    dnssec_coordinator = config_entry.runtime_data.dnssec
    encryption_coordinator = config_entry.runtime_data.encryption
    ip_versions_coordinator = config_entry.runtime_data.ip_versions
    protocols_coordinator = config_entry.runtime_data.protocols
    settings_coordinator = config_entry.runtime_data.settings
    status_coordinator = config_entry.runtime_data.status

    return {
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT),
        "dnssec_coordinator_data": asdict(dnssec_coordinator.data),
        "encryption_coordinator_data": asdict(encryption_coordinator.data),
        "ip_versions_coordinator_data": asdict(ip_versions_coordinator.data),
        "protocols_coordinator_data": asdict(protocols_coordinator.data),
        "settings_coordinator_data": asdict(settings_coordinator.data),
        "status_coordinator_data": asdict(status_coordinator.data),
    }
