"""Support for EQ3 devices."""

import logging
from typing import TYPE_CHECKING

from homeassistant.components import bluetooth
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import Eq3ConfigEntry, Eq3ConfigEntryData, Eq3Coordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: Eq3ConfigEntry) -> bool:
    """Handle config entry setup."""
    if TYPE_CHECKING:
        assert entry.unique_id is not None
    mac_address: str = entry.unique_id

    device = bluetooth.async_ble_device_from_address(
        hass, mac_address.upper(), connectable=True
    )

    if device is None:
        raise ConfigEntryNotReady(f"[{mac_address}] Device could not be found")

    coordinator = Eq3Coordinator(hass, entry, device)
    entry.runtime_data = Eq3ConfigEntryData(coordinator)

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: Eq3ConfigEntry) -> bool:
    """Handle config entry unload."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        if entry.runtime_data.coordinator.thermostat.is_connected:
            await entry.runtime_data.coordinator.thermostat.async_disconnect()

    return unload_ok
