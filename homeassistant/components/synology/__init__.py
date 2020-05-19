"""The synology component."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN

PLATFORMS = ["camera"]


async def async_setup(hass: HomeAssistantType, config: dict) -> bool:
    """Set up platform."""
    # TODO: import
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up config entry."""
    # Register device
    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="Synology",
        name="Synology Surveillance Station",
    )

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )
    return True
