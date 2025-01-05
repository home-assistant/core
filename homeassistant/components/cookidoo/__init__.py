"""The Cookidoo integration."""

from __future__ import annotations

import logging

from cookidoo_api import CookidooAuthException, CookidooRequestException

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import CookidooConfigEntry, CookidooDataUpdateCoordinator
from .helpers import cookidoo_from_config_entry

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.TODO]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: CookidooConfigEntry) -> bool:
    """Set up Cookidoo from a config entry."""

    coordinator = CookidooDataUpdateCoordinator(
        hass, await cookidoo_from_config_entry(hass, entry), entry
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CookidooConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: CookidooConfigEntry
) -> bool:
    """Migrate config entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 1 and config_entry.minor_version == 1:
        # Add the unique uuid
        cookidoo = await cookidoo_from_config_entry(hass, config_entry)

        try:
            auth_data = await cookidoo.login()
        except (CookidooRequestException, CookidooAuthException) as e:
            _LOGGER.error(
                "Could not migrate config config_entry: %s",
                str(e),
            )
            return False

        hass.config_entries.async_update_entry(
            config_entry, unique_id=auth_data.sub, minor_version=2
        )

    _LOGGER.debug(
        "Migration to version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True
