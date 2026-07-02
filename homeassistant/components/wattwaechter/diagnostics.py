"""Diagnostics support for the WattWächter Plus integration."""

from dataclasses import asdict
from typing import Any

from aio_wattwaechter.models import SystemInfo

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_MAC, CONF_TOKEN
from homeassistant.core import HomeAssistant

from .coordinator import WattwaechterConfigEntry

# The device exposes network identifiers as system info values; redact the
# credential and hardware/network identifiers. Local IPs are kept for support.
TO_REDACT = {CONF_TOKEN, CONF_MAC, "ssid", "mac_address", "mdns_name"}


def _flatten_system(system: SystemInfo) -> dict[str, dict[str, Any]]:
    """Flatten system info sections into {section: {name: value}} mappings."""
    return {
        section: {entry["name"]: entry["value"] for entry in entries}
        for section, entries in asdict(system).items()
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: WattwaechterConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return async_redact_data(
        {
            "config_entry": dict(entry.data),
            "meter": asdict(coordinator.data.meter),
            "system": _flatten_system(coordinator.data.system),
        },
        TO_REDACT,
    )
