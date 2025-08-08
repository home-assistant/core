"""Diagnostics support for airOS."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .coordinator import AirOSConfigEntry

IP_REDACT = ["addr", "ipaddr", "ip6addr", "lastip"]  # IP related
HW_REDACT = ["apmac", "hwaddr", "mac"]  # MAC address
TO_REDACT_HA = [CONF_HOST, CONF_PASSWORD]
TO_REDACT_AIROS = [
    "hostname",  # Prevent leaking device naming
    "essid",  # Network SSID
    "lat",  # GPS latitude to prevent exposing location data.
    "lon",  # GPS longitude to prevent exposing location data.
    *HW_REDACT,
    *IP_REDACT,
]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AirOSConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT_HA),
        "data": async_redact_data(entry.runtime_data.data.to_dict(), TO_REDACT_AIROS),
    }
