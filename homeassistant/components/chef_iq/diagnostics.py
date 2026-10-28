"""Diagnostics support for Chef iQ."""

from typing import Any

from homeassistant.components.bluetooth import async_last_service_info
from homeassistant.core import HomeAssistant

from . import ChefIqConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ChefIqConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    address = entry.unique_id
    assert address is not None
    service_info = async_last_service_info(hass, address, connectable=False)
    return {
        "entry": {
            "title": entry.title,
            "unique_id": address,
        },
        "advertisement": None
        if service_info is None
        else {
            "name": service_info.name,
            "rssi": service_info.rssi,
            "source": service_info.source,
            "manufacturer_data": {
                str(key): value.hex()
                for key, value in service_info.manufacturer_data.items()
            },
        },
    }
