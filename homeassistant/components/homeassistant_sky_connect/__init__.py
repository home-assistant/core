"""The Home Assistant SkyConnect integration."""

from __future__ import annotations

import logging

from homeassistant.components.homeassistant_hardware.util import guess_firmware_type
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Home Assistant SkyConnect config entry."""
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""

    _LOGGER.debug(
        "Migrating from version %s:%s", config_entry.version, config_entry.minor_version
    )

    if config_entry.version == 1:
        if config_entry.minor_version == 1:
            # Add-on startup with type service get started before Core, always (e.g. the
            # Multi-Protocol add-on). Probing the firmware would interfere with the add-on,
            # so we can't safely probe here. Instead, we must make an educated guess!
            firmware_guess = await guess_firmware_type(
                hass, config_entry.data["device"]
            )

            new_data = {**config_entry.data}
            new_data["firmware"] = firmware_guess.firmware_type.value

            # Copy `description` to `product`
            new_data["product"] = new_data["description"]

            hass.config_entries.async_update_entry(
                config_entry,
                data=new_data,
                version=1,
                minor_version=2,
            )

        _LOGGER.debug(
            "Migration to version %s.%s successful",
            config_entry.version,
            config_entry.minor_version,
        )

        return True

    # This means the user has downgraded from a future version
    return False
