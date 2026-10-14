"""The Honeywell String Lights integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_TRANSMITTER

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Honeywell String Lights from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entries."""
    if entry.version == 1 and entry.minor_version < 2:
        # Minor version 1 stored the transmitter entity registry UUID.
        transmitter_entity_id = er.async_resolve_entity_id(
            er.async_get(hass), entry.data[CONF_TRANSMITTER]
        )
        if transmitter_entity_id is None:
            _LOGGER.error(
                "Unable to migrate config entry %s: transmitter %s not found",
                entry.entry_id,
                entry.data[CONF_TRANSMITTER],
            )
            return False
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_TRANSMITTER: transmitter_entity_id},
            minor_version=2,
        )

    return True
