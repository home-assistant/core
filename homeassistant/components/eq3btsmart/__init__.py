"""Support for EQ3 devices."""

import logging

from eq3btsmart import Thermostat

from homeassistant.components import bluetooth
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_MAC_ADDRESS
from .coordinator import Eq3Coordinator
from .models import Eq3ConfigEntry, Eq3ConfigEntryData

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
    mac_address: str = entry.data.get(CONF_MAC_ADDRESS, entry.unique_id)

    device = bluetooth.async_ble_device_from_address(
        hass, mac_address.upper(), connectable=True
    )

    if device is None:
        raise ConfigEntryNotReady(f"[{mac_address}] Device could not be found")

    if not entry.data:
        hass.config_entries.async_update_entry(
            entry,
            data={CONF_MAC_ADDRESS: mac_address},
        )

    thermostat = Thermostat(device)
    coordinator = Eq3Coordinator(hass, entry, mac_address)
    entry.runtime_data = Eq3ConfigEntryData(thermostat, coordinator)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.async_update_listeners()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: Eq3ConfigEntry) -> bool:
    """Handle config entry unload."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.thermostat.async_disconnect()

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: Eq3ConfigEntry) -> None:
    """Handle config entry update."""
    await hass.config_entries.async_reload(entry.entry_id)
