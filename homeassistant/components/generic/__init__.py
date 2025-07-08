"""The generic component."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.stream import (
    CONF_RTSP_TRANSPORT,
    CONF_USE_WALLCLOCK_AS_TIMESTAMPS,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_AUTHENTICATION, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import CONF_FRAMERATE, CONF_LIMIT_REFETCH_TO_URL_CHANGE, SECTION_ADVANCED

DOMAIN = "generic"
PLATFORMS = [Platform.CAMERA]
_LOGGER = logging.getLogger(__name__)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_migrate_unique_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate entities to the new unique id."""

    @callback
    def _async_migrator(entity_entry: er.RegistryEntry) -> dict[str, Any] | None:
        if entity_entry.unique_id == entry.entry_id:
            # Already correct, nothing to do
            return None
        # There is only one entity, and its unique id
        # should always be the same as the config entry entry_id
        return {"new_unique_id": entry.entry_id}

    await er.async_migrate_entries(hass, entry.entry_id, _async_migrator)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up generic IP camera from a config entry."""

    await _async_migrate_unique_ids(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate entry."""
    _LOGGER.debug("Migrating from version %s:%s", entry.version, entry.minor_version)

    if entry.version > 2:
        # This means the user has downgraded from a future version
        return False

    if entry.version == 1:
        # Migrate to advanced section
        new_options = {**entry.options}
        advanced = new_options[SECTION_ADVANCED] = {
            CONF_FRAMERATE: new_options.pop(CONF_FRAMERATE),
            CONF_VERIFY_SSL: new_options.pop(CONF_VERIFY_SSL),
        }

        # migrate optional fields
        for key in (
            CONF_RTSP_TRANSPORT,
            CONF_USE_WALLCLOCK_AS_TIMESTAMPS,
            CONF_AUTHENTICATION,
            CONF_LIMIT_REFETCH_TO_URL_CHANGE,
        ):
            if key in new_options:
                advanced[key] = new_options.pop(key)

        hass.config_entries.async_update_entry(entry, options=new_options, version=2)

    _LOGGER.debug(
        "Migration to version %s:%s successful", entry.version, entry.minor_version
    )

    return True
