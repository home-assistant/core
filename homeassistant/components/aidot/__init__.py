"""The aidot integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aidot.discover import Discover
from aidot.login_const import CONF_DEVICE_LIST, CONF_LOGIN_RESPONSE, CONF_PRODUCT_LIST

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr

from .coordinator import AidotConfigEntry, AidotCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: AidotConfigEntry) -> bool:
    """Set up aidot from a config entry."""

    coordinator = AidotCoordinator(
        hass,
        entry,
        entry.data[CONF_DEVICE_LIST],
        entry.data[CONF_LOGIN_RESPONSE],
        entry.data[CONF_PRODUCT_LIST],
    )
    entry.runtime_data = coordinator

    def discover(dev_id, event: Mapping[str, Any]):
        hass.bus.async_fire(dev_id, event)

    try:
        await Discover().broadcast_message(discover, coordinator.login_response["id"])
    except OSError as err:
        raise ConfigEntryError from err

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def cleanup_device_registry(hass: HomeAssistant) -> None:
    """Remove deleted device registry entry if there are no remaining entities."""
    device_registry = dr.async_get(hass)
    for dev_id, device_entry in list(device_registry.devices.items()):
        for _ in device_entry.identifiers:
            device_registry.async_remove_device(dev_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # This is called when an entry/configured device is to be removed. The class
    # needs to unload itself, and remove callbacks. See the classes for further
    # details
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
