"""Support for Imou camera."""

import asyncio
import logging

from pyimouapi.device import ImouDeviceManager
from pyimouapi.ha_device import ImouHaDeviceManager
from pyimouapi.openapi import ImouOpenApiClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN, PARAM_API_URL, PARAM_APP_ID, PARAM_APP_SECRET, PLATFORMS
from .coordinator import ImouDataUpdateCoordinator

LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """Set up entry."""
    LOGGER.info("starting setup imou")
    imou_client = ImouOpenApiClient(
        config.data.get(PARAM_APP_ID),
        config.data.get(PARAM_APP_SECRET),
        config.data.get(PARAM_API_URL),
    )
    device_manager = ImouDeviceManager(imou_client)
    imou_device_manager = ImouHaDeviceManager(device_manager)
    imou_coordinator = ImouDataUpdateCoordinator(hass, imou_device_manager)
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config.entry_id] = imou_coordinator
    await imou_coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(config, PLATFORMS)
    config.add_update_listener(async_reload_entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    LOGGER.info("Unloading entry %s", entry.entry_id)
    unloaded = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ],
            async_remove_devices(hass, entry.entry_id),
        )
    )
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def async_remove_devices(hass: HomeAssistant, config_entry_id: str):
    """Remove device."""
    device_registry_object = dr.async_get(hass)
    for device_entry in device_registry_object.devices.get_devices_for_config_entry_id(
        config_entry_id
    ):
        LOGGER.info("remove device %s", device_entry.id)
        device_registry_object.async_remove_device(device_entry.id)
    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
):
    """Remove device."""
    device_registry_object = dr.async_get(hass)
    device_registry_object.async_remove_device(device_entry.id)
    return True
