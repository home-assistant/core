"""Hue BLE integration."""

import logging

from HueBLE import HueBleLight

from homeassistant.components.bluetooth import (
    async_ble_device_from_address,
    async_scanner_count,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

_LOGGER = logging.getLogger(__name__)

type HueBLEConfigEntry = ConfigEntry[HueBleLight]


async def async_setup_entry(hass: HomeAssistant, entry: HueBLEConfigEntry) -> bool:
    """Set up the integration from a config entry."""

    assert entry.unique_id is not None
    address = entry.unique_id.upper()

    ble_device = async_ble_device_from_address(hass, address, connectable=True)

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

    entry.runtime_data = light

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setups(entry, ["light"])
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HueBLEConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_forward_entry_unload(entry, "light")
