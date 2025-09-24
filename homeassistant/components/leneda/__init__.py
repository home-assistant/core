"""The Leneda integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import CONF_API_TOKEN, CONF_ENERGY_ID
from .coordinator import LenedaCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type LenedaConfigEntry = ConfigEntry[LenedaCoordinator]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: LenedaConfigEntry) -> bool:
    """Set up Leneda from a config entry or subentry."""
    _LOGGER.debug("Setting up entry %s", entry.entry_id)

    api_token, energy_id = entry.data[CONF_API_TOKEN], entry.data[CONF_ENERGY_ID]
    coordinator = LenedaCoordinator(hass, entry, api_token, energy_id)
    entry.runtime_data = coordinator

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Set up a listener for subentry changes
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a metering point device (only relevant for subentries)."""
    return True
