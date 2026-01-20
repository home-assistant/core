"""Solarwatt integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import SolarwattDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

# Typed ConfigEntry with runtime_data pointing to the coordinator
type SolarwattConfigEntry = ConfigEntry[SolarwattDataUpdateCoordinator]

# No YAML configuration; config entries only
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Solarwatt integration from YAML (not used, kept for compatibility)."""
    # No YAML setup; everything is config entry based.
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SolarwattConfigEntry) -> bool:
    """Set up Solarwatt from a config entry."""
    _LOGGER.debug("Setting up Solarwatt config entry: %s", entry.data)

    coordinator = SolarwattDataUpdateCoordinator(hass, entry)

    try:
        # Initial refresh; may raise ConfigEntryNotReady if the device is not reachable
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady as err:
        _LOGGER.warning(
            "Solarwatt device %s not ready yet: %s",
            entry.data.get("host"),
            err,
        )
        raise ConfigEntryNotReady from err

    # Store coordinator on the entry for typed access in platforms
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload entry when options / data change
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SolarwattConfigEntry) -> bool:
    """Unload a Solarwatt config entry."""
    _LOGGER.debug("Unloading config entry for Solarwatt: %s", entry.entry_id)
    # No need to clean up hass.data; we rely on entry.runtime_data
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: SolarwattConfigEntry) -> None:
    """Reload a Solarwatt config entry."""
    _LOGGER.debug("Reloading Solarwatt config entry: %s", entry.entry_id)
    await hass.config_entries.async_reload(entry.entry_id)
