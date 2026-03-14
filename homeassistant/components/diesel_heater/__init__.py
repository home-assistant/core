"""The Diesel Heater integration.

Supports Vevor, BYD, HeaterCC, Sunster and other Chinese diesel heaters via BLE.
"""
from __future__ import annotations

import asyncio
import logging

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import VevorHeaterCoordinator

type DieselHeaterConfigEntry = ConfigEntry[VevorHeaterCoordinator]

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: DieselHeaterConfigEntry) -> bool:
    """Set up Diesel Heater from a config entry."""
    address: str = entry.data[CONF_ADDRESS]

    _LOGGER.debug("Setting up Diesel Heater with address: %s", address)

    # Get BLE device from Home Assistant's bluetooth integration
    ble_device = bluetooth.async_ble_device_from_address(
        hass, address.upper(), connectable=True
    )

    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find Diesel Heater with address {address}"
        )

    # Create coordinator
    coordinator = VevorHeaterCoordinator(hass, ble_device, entry)

    # Initial data fetch with timeout
    try:
        await asyncio.wait_for(
            coordinator.async_config_entry_first_refresh(),
            timeout=30.0,
        )
    except asyncio.TimeoutError as err:
        raise ConfigEntryNotReady(
            f"Initial connection to Diesel Heater at {address} "
            "timed out after 30 seconds"
        ) from err

    # Store coordinator on the config entry
    entry.runtime_data = coordinator

    # Forward entry setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DieselHeaterConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: VevorHeaterCoordinator = entry.runtime_data
        await coordinator.async_shutdown()

    return unload_ok
