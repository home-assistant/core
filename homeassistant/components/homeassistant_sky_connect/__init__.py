"""The Home Assistant SkyConnect integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .util import guess_firmware_type

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Home Assistant SkyConnect config entry."""
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""

    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        # Core cannot stall addon startup so we can't probe the real firmware running on
        # the stick. Instead, we must make an educated guess!
        firmware = await guess_firmware_type(hass, config_entry.data["device"])

        new_data = {**config_entry.data}
        new_data["firmware"] = firmware

        # Rename `description` to `product`
        new_data["product"] = new_data.pop("description")

        hass.config_entries.async_update_entry(
            config_entry,
            data=new_data,
            version=2,
            minor_version=1,
        )

    _LOGGER.debug(
        "Migration to version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True
