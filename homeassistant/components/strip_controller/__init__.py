"""The Strip Controller integration.

Based on homeassistant/components/sun/sensor.py to associate entities to devices
Based on homeassistant/components/wled/button.py to create a configuration like WLED "Restart"
Based on homeassistant/components/wled/number.py to create a configuration like WLED "Intensity"

"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, LOGGER
from .device import async_create_sc_rpi_device

# TOD List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[str] = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Strip Controller from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    # TOD 1. Create API instance
    # TOD 2. Validate the API connection (and authentication)
    # TOD 3. Store an API object for your platforms to access
    # hass.data[DOMAIN][entry.entry_id] = MyApi()

    # TOD set name for device
    # Most code here is based on upnp integration

    try:
        device = await async_create_sc_rpi_device(hass, entry)
    except Exception as err:
        raise ConfigEntryNotReady(
            f"Error connecting to device at location: - , err: {err}"
        ) from err
    # identifiers = {(DOMAIN, device.usn)}
    identifiers = {(DOMAIN, entry.entry_id)}

    # connections = {(dr.CONNECTION_UPNP, device.udn)}

    dev_registry = dr.async_get(hass)
    device_entry = dev_registry.async_get_device(identifiers=identifiers)
    if device_entry:
        LOGGER.debug(
            "Found device using connections: - , device_entry: %s",
            device_entry,
        )
    if not device_entry:
        # No device found, create new device entry.
        device_entry = dev_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers=identifiers,
            manufacturer=device.manufacturer,
            model=device.model_name,
        )
        LOGGER.debug("Created device, device_entry: %s", device_entry)

    # This will trigger async_setup_entry function for all entities defined in PLATFORMS
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


# TOD: implement unloading device


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
