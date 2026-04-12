"""The Avea integration."""

from __future__ import annotations

import avea

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

type AveaConfigEntry = ConfigEntry[avea.Bulb]

PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: AveaConfigEntry) -> bool:
    """Set up Avea from a config entry."""
    if not (
        ble_device := async_ble_device_from_address(
            hass, entry.data[CONF_ADDRESS], connectable=True
        )
    ):
        raise ConfigEntryNotReady(
            f"Could not find Avea device with address {entry.data[CONF_ADDRESS]}"
        )

    entry.runtime_data = avea.Bulb(ble_device)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AveaConfigEntry) -> bool:
    """Unload an Avea config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await hass.async_add_executor_job(entry.runtime_data.close)

    return unload_ok
