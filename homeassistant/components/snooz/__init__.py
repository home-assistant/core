"""The Snooz component."""

from __future__ import annotations

import logging

from pysnooz.device import SnoozDevice

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.const import CONF_ADDRESS, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import PLATFORMS
from .models import SnoozConfigEntry, SnoozConfigurationData


async def async_setup_entry(hass: HomeAssistant, entry: SnoozConfigEntry) -> bool:
    """Set up Snooz device from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    token: str = entry.data[CONF_TOKEN]

    # transitions info logs are verbose. Only enable warnings
    logging.getLogger("transitions.core").setLevel(logging.WARNING)

    if not (ble_device := async_ble_device_from_address(hass, address)):
        raise ConfigEntryNotReady(
            f"Could not find Snooz with address {address}. Try power cycling the device"
        )

    device = SnoozDevice(ble_device, token)

    entry.runtime_data = SnoozConfigurationData(ble_device, device, entry.title)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: SnoozConfigEntry) -> None:
    """Handle options update."""
    if entry.title != entry.runtime_data.title:
        await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SnoozConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # also called by fan entities, but do it here too for good measure
        await entry.runtime_data.device.async_disconnect()

    return unload_ok
