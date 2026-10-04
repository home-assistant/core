"""Diagnostics platform for the Netis Router integration.

Supports downloading a redacted snapshot of the router state via
Settings > Devices & Services > Netis > Download diagnostics. Used for
troubleshooting; all identifying fields (passwords, MACs, IPs, IMEI) are
masked by :func:`async_redact_data`.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import NetisConfigEntry

# Keys masked in the diagnostic download. Keys map to both the config
# entry data dict and the NetisDevice / NetisData field names.
TO_REDACT = {
    # credentials
    "password",
    # device identifiers
    "mac",
    "ip",
    "ip_address",
    "mac_address",
    # LTE / modem identifiers
    "imei",
    "lte_imei",
    "lte_imsi",
    "lte_ip",
    # host name aliases (user-set, potentially identifying)
    "name",
    "alias",
    "hostname",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NetisConfigEntry
) -> dict[str, Any]:
    """Return redacted diagnostics for a config entry."""
    coordinator = entry.runtime_data
    snapshot = coordinator.data
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "data": asdict(snapshot) if snapshot else None,
    }
