"""Shared helpers for SVS Subwoofer integration."""

from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN

if TYPE_CHECKING:
    from . import SVSConfigEntry
    from .coordinator import SVSSubwooferCoordinator


def get_coordinator_for_device(
    hass: HomeAssistant, device_id: str
) -> SVSSubwooferCoordinator | None:
    """Return the coordinator owning the given device registry entry."""
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        return None

    address = next(
        (ident[1] for ident in device.identifiers if ident[0] == DOMAIN),
        None,
    )
    if address is None:
        return None

    entries: list[SVSConfigEntry] = hass.config_entries.async_loaded_entries(DOMAIN)
    for entry in entries:
        coordinator = entry.runtime_data
        if coordinator.address == address:
            return coordinator
    return None
