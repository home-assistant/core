"""The Stookwijzer integration."""

from __future__ import annotations

from stookwijzer import Stookwijzer

from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER
from .coordinator import StookwijzerConfigEntry, StookwijzerCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: StookwijzerConfigEntry) -> bool:
    """Set up Stookwijzer from a config entry."""
    coordinator = StookwijzerCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: StookwijzerConfigEntry
) -> bool:
    """Unload Stookwijzer config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, entry: StookwijzerConfigEntry
) -> bool:
    """Migrate old entry."""
    LOGGER.debug("Migrating from version %s", entry.version)

    if entry.version == 1:
        latitude, longitude = await Stookwijzer.async_transform_coordinates(
            async_get_clientsession(hass),
            entry.data[CONF_LOCATION][CONF_LATITUDE],
            entry.data[CONF_LOCATION][CONF_LONGITUDE],
        )

        if not latitude or not longitude:
            ir.async_create_issue(
                hass,
                DOMAIN,
                "location_migration_failed",
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="location_migration_failed",
                translation_placeholders={
                    "entry_title": entry.title,
                },
            )
            return False

        hass.config_entries.async_update_entry(
            entry,
            version=2,
            data={
                CONF_LATITUDE: latitude,
                CONF_LONGITUDE: longitude,
            },
        )

        LOGGER.debug("Migration to version %s successful", entry.version)

    return True
