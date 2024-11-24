"""The Stookwijzer integration."""

from __future__ import annotations

import logging

from stookwijzer import Stookwijzer

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import StookwijzerCoordinator

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

type StookwijzerConfigEntry = ConfigEntry[StookwijzerCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Stookwijzer from a config entry."""
    client = Stookwijzer(
        async_get_clientsession(hass),
        entry.data[CONF_LATITUDE],
        entry.data[CONF_LONGITUDE],
    )
    coordinator = StookwijzerCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Stookwijzer config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", entry.version)

    if entry.version == 1:
        session = async_get_clientsession(hass)
        x, y = await Stookwijzer.async_transform_coordinates(
            session,
            entry.data[CONF_LOCATION][CONF_LATITUDE],
            entry.data[CONF_LOCATION][CONF_LONGITUDE],
        )

        if not x or not y:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="location_migration_failed",
            )
        hass.config_entries.async_update_entry(
            entry, version=2, data={CONF_LATITUDE: x, CONF_LONGITUDE: y}
        )

        _LOGGER.debug("Migration to version %s successful", entry.version)

    return True
