"""Diagnostics support for Chef iQ."""

from typing import TYPE_CHECKING, Any

from homeassistant.components import bluetooth
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import ChefIqConfigEntry

SERVICE_INFO_TO_REDACT = frozenset(
    {"address", "advertisement", "device", "name", "source"}
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ChefIqConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    address = entry.unique_id
    if TYPE_CHECKING:
        assert address is not None
    service_info = bluetooth.async_last_service_info(hass, address, connectable=False)
    return {
        "service_info": async_redact_data(
            service_info.as_dict() if service_info else None,
            SERVICE_INFO_TO_REDACT,
        ),
    }
