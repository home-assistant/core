"""Hue BLE integration."""

import logging

from HueBLE import HueBleLight

from homeassistant.components.bluetooth import (
    async_ble_device_from_address,
    async_scanner_count,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from a config entry."""

    address = str(entry.data.get(CONF_MAC))

    ble_device = async_ble_device_from_address(hass, address.upper(), connectable=True)

    if ble_device is None:
        count_scanners = async_scanner_count(hass, connectable=True)
        _LOGGER.debug("Count of BLE scanners: %i", count_scanners)

        if count_scanners < 1:
            raise ConfigEntryNotReady(
                "No Bluetooth scanners are available to search for the light."
            )
        raise ConfigEntryNotReady("The light was not found.")

    light = HueBleLight(ble_device)

    if not await light.connect() or not await light.poll_state():
        raise ConfigEntryNotReady("Device found but unable to connect.")

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = light

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "light")
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "light")

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
