"""The generic_thermostat component."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device import (
    async_remove_stale_devices_links_keep_entity_device,
)

from .const import CONF_DUR_COOLDOWN, CONF_HEATER, CONF_MIN_DUR, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""

    async_remove_stale_devices_links_keep_entity_device(
        hass,
        entry.entry_id,
        entry.options[CONF_HEATER],
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config."""
    version = entry.version
    minor_version = entry.minor_version

    if version == 1 and minor_version == 1:
        data = {**entry.data}
        options = {**entry.options}

        _LOGGER.debug("Migrating from version %s.%s", version, minor_version)

        # Set `cycle_cooldown` to `min_cycle_duration` to mimic the old behavior
        options[CONF_DUR_COOLDOWN] = options[CONF_MIN_DUR]

        hass.config_entries.async_update_entry(
            entry, data=data, options=options, version=1, minor_version=2
        )

        _LOGGER.info(
            "Migration to version %s.%s successful", entry.version, entry.minor_version
        )
        return True

    return False


async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener, called when the config entry options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
