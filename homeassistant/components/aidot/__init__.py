"""The aidot integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aidot.discover import Discover

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up aidot from a config entry."""

    hass.data.setdefault(DOMAIN, {})["device_list"] = entry.data["device_list"]
    hass.data.setdefault(DOMAIN, {})["login_response"] = entry.data["login_response"]
    hass.data.setdefault(DOMAIN, {})["products"] = entry.data["product_list"]

    def discover(devId, event: Mapping[str, Any]):
        hass.bus.async_fire(devId, event)

    await Discover().broadcast_message(
        discover, hass.data[DOMAIN]["login_response"]["id"]
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def cleanup_device_registry(hass: HomeAssistant) -> None:
    """Remove deleted device registry entry if there are no remaining entities."""
    device_registry = dr.async_get(hass)
    for dev_id, device_entry in list(device_registry.devices.items()):
        for item in device_entry.identifiers:
            _LOGGER.info(item)
            _LOGGER.info(dev_id)
            device_registry.async_remove_device(dev_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # This is called when an entry/configured device is to be removed. The class
    # needs to unload itself, and remove callbacks. See the classes for further
    # details
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop("device_list", None)
        hass.data[DOMAIN].pop("login_response", None)
        hass.data[DOMAIN].pop("products", None)

    return unload_ok
