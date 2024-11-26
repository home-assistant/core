"""The Aseko Pool Live integration."""

from __future__ import annotations

import logging

from aioaseko import Aseko, AsekoNotLoggedIn

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .coordinator import AsekoConfigEntry, AsekoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: AsekoConfigEntry) -> bool:
    """Set up Aseko Pool Live from a config entry."""
    aseko = Aseko(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])

    try:
        await aseko.login()
    except AsekoNotLoggedIn as err:
        raise ConfigEntryAuthFailed from err

    coordinator = AsekoDataUpdateCoordinator(hass, aseko)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AsekoConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: AsekoConfigEntry
) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        new = {
            CONF_EMAIL: config_entry.title,
            CONF_PASSWORD: "",
        }

        hass.config_entries.async_update_entry(config_entry, data=new, version=2)

        _LOGGER.debug("Migration to version %s successful", config_entry.version)
        return True

    _LOGGER.error("Attempt to migrate from unknown version %s", config_entry.version)
    return False
