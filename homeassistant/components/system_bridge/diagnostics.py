"""Diagnostics support for System Bridge."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant

from .coordinator import SystemBridgeConfigEntry

TO_REDACT = {
    CONF_API_KEY,
    CONF_HOST,
    CONF_TOKEN,
    "address",
    "broadcast",
    "fqdn",
    "hostname",
    "ip_address_4",
    "ip_address_6",
    "mac_address",
    "ssid",
    "title",
    "unique_id",
    "users",
    "uuid",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SystemBridgeConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    data = asdict(coordinator.data)
    # The process and connection lists are long and say a lot about the user
    data.pop("processes")
    if data["networks"] is not None:
        data["networks"].pop("connections")

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "data": async_redact_data(data, TO_REDACT),
    }
