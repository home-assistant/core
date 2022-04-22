"""The melnor integration."""


import logging

from melnor_bluetooth.device import Device

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .models import MelnorDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up melnor from a config entry."""
    hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})

    # Create the device and connect immediately so we can pull down
    # required attributes before building out our entities
    device = Device(mac=entry.data[CONF_MAC])

    await device.connect(timeout=10)
    if not device.is_connected:
        raise ConfigEntryNotReady(f"Failed to connect to: {device.mac}")

    coordinator = MelnorDataUpdateCoordinator(hass, device)

    hass.data[DOMAIN][entry.entry_id]["coordinator"] = coordinator

    await coordinator.async_config_entry_first_refresh()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    await hass.data[DOMAIN][entry.entry_id]["coordinator"].data.disconnect()

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
