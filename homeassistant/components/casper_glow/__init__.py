"""The Casper Glow integration."""

from __future__ import annotations

from pycasperglow import CasperGlow

from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import CasperGlowConfigEntry, CasperGlowCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: CasperGlowConfigEntry) -> bool:
    """Set up Casper Glow from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    ble_device = bluetooth.async_ble_device_from_address(hass, address.upper(), True)
    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find Casper Glow device with address {address}"
        )

    glow = CasperGlow(ble_device)
    coordinator = CasperGlowCoordinator(hass, glow, entry.title)
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(coordinator.async_start())

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CasperGlowConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
