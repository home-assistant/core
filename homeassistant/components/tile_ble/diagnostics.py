"""Diagnostics support for the Tile BLE integration."""

from typing import Any

from homeassistant.components import bluetooth
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_AUTH_KEY
from .coordinator import TileBleConfigEntry

TO_REDACT = {CONF_AUTH_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TileBleConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    service_info = bluetooth.async_last_service_info(
        hass, coordinator.address, connectable=False
    )
    return {
        "config_entry_data": async_redact_data(entry.data, TO_REDACT),
        "available": coordinator.available,
        "connectable": bluetooth.async_address_present(
            hass, coordinator.address, connectable=True
        ),
        "service_info": {
            "rssi": service_info.rssi,
            "connectable": service_info.connectable,
            "time": service_info.time,
            "service_data": {
                uuid: data.hex() for uuid, data in service_info.service_data.items()
            },
            "service_uuids": service_info.service_uuids,
        }
        if service_info
        else None,
    }
