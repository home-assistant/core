"""Diagnostics support for the Qingping integration."""

from typing import Any

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from . import QingpingConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: QingpingConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    address = entry.unique_id
    assert address is not None
    return {
        "entry": entry.as_dict(),
        "service_info": bluetooth.async_last_service_info(
            hass, address, connectable=False
        ),
    }
