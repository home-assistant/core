"""Create device without entities."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import DOMAIN


def async_create_device(
    hass: HomeAssistant,
    config_entry_id: str,
    device_name: str | None,
    unique_id: str,
) -> dr.DeviceEntry:
    """Create a device."""
    device_registry = dr.async_get(hass)
    return device_registry.async_get_or_create(
        config_entry_id=config_entry_id,
        name=device_name,
        identifiers={(DOMAIN, unique_id)},
    )
