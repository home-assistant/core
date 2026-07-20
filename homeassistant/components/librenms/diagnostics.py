"""Diagnostics support for LibreNMS."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import LibrenmsConfigEntry

TO_REDACT_ENTRY = {CONF_API_KEY, CONF_HOST}
TO_REDACT_DATA = {
    "authname",
    "authpass",
    "community",
    "cryptopass",
    "dependency_parent_hostname",
    "display",
    "hostname",
    "ip",
    "lat",
    "lng",
    "location",
    "notes",
    "overwrite_ip",
    "serial",
    "sys_contact",
    "sys_name",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LibrenmsConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT_ENTRY),
        "data": async_redact_data(asdict(coordinator.data), TO_REDACT_DATA),
    }
