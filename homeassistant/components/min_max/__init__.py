"""The min_max component."""

import logging
from types import MappingProxyType

from homeassistant.components.group import (
    CONF_ENTITIES,
    CONF_HIDE_MEMBERS,
    CONF_IGNORE_NON_NUMERIC,
    DOMAIN as GROUP_DOMAIN,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_ENTITY_IDS, CONF_ROUND_DIGITS, DOMAIN

PLATFORMS = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Min/Max from a config entry."""

    # Create group config from entry options
    config = dict(entry.options)
    config[CONF_ENTITIES] = config.pop(CONF_ENTITY_IDS)
    config.pop(CONF_ROUND_DIGITS)
    config[CONF_HIDE_MEMBERS] = False
    config[CONF_IGNORE_NON_NUMERIC] = False

    # Create new config entry for group component and remove old entry
    new_config_entry = ConfigEntry(
        data={},
        discovery_keys=MappingProxyType({}),
        domain=GROUP_DOMAIN,
        minor_version=1,
        options=config,
        source=SOURCE_USER,
        subentries_data=[],
        title=entry.title,
        unique_id=None,
        version=1,
    )
    await hass.config_entries.async_add(new_config_entry)
    await hass.config_entries.async_remove(entry.entry_id)

    # Migrate entity from old entry to new entry
    entity_reg = er.async_get(hass)
    if old_entity := entity_reg.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, entry.entry_id
    ):
        entity_reg.async_update_entity(
            old_entity, config_entry_id=new_config_entry.entry_id
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
