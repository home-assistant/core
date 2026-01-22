"""Support for Imou devices."""

from __future__ import annotations

import logging

from pyimouapi.device import ImouDeviceManager
from pyimouapi.ha_device import ImouHaDeviceManager
from pyimouapi.openapi import ImouOpenApiClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry

from .const import PARAM_API_URL, PARAM_APP_ID, PARAM_APP_SECRET, PLATFORMS
from .coordinator import ImouDataUpdateCoordinator

_LOGGER: logging.Logger = logging.getLogger(__package__)

type ImouConfigEntry = ConfigEntry[ImouDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: ImouConfigEntry) -> bool:
    """Set up Imou integration from a config entry.

    Args:
        hass: Home Assistant core object
        entry: Configuration entry

    Returns:
        True if setup was successful, False otherwise
    """
    _LOGGER.debug("Starting setup")
    imou_client = ImouOpenApiClient(
        entry.data[PARAM_APP_ID],
        entry.data[PARAM_APP_SECRET],
        entry.data[PARAM_API_URL],
    )
    device_manager = ImouDeviceManager(imou_client)
    imou_device_manager = ImouHaDeviceManager(device_manager)
    imou_coordinator = ImouDataUpdateCoordinator(hass, imou_device_manager, entry)
    await imou_coordinator.async_config_entry_first_refresh()
    entry.runtime_data = imou_coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ImouConfigEntry) -> bool:
    """Handle removal of an entry.

    Args:
        hass: Home Assistant core object
        entry: Configuration entry to unload

    Returns:
        True if unload was successful, False otherwise
    """
    _LOGGER.debug("Unloading entry %s", entry.entry_id)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await async_remove_devices(hass, entry.entry_id)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ImouConfigEntry) -> None:
    """Reload config entry.

    Args:
        hass: Home Assistant core object
        entry: Configuration entry to reload
    """
    _LOGGER.debug("Reloading entry %s", entry.entry_id)
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_devices(hass: HomeAssistant, config_entry_id: str) -> None:
    """Remove all devices of a config entry.

    Args:
        hass: Home Assistant core object
        config_entry_id: Configuration entry ID
    """
    device_registry_object = dr.async_get(hass)
    for device_entry in device_registry_object.devices.get_devices_for_config_entry_id(
        config_entry_id
    ):
        _LOGGER.debug("Removing device %s", device_entry.name)
        device_registry_object.async_remove_device(device_entry.id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ImouConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a single device.

    Args:
        hass: Home Assistant core object
        config_entry: Configuration entry
        device_entry: Device entry to remove
    """
    _LOGGER.debug("Removing device %s", device_entry.name)
    device_registry_object = dr.async_get(hass)
    device_registry_object.async_remove_device(device_entry.id)
    return True
