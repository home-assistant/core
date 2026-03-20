"""The PJLink integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME, CONF_PLATFORM, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .media_player import PLATFORM_SCHEMA  # noqa: F401 Needed for async_setup

_LOGGER = logging.getLogger(__name__)
_PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]


# Deprecated: Will get removed with next release
async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Create config entry from YAML."""
    if Platform.MEDIA_PLAYER not in config:
        return True

    for entry in config[Platform.MEDIA_PLAYER]:
        if entry[CONF_PLATFORM] == DOMAIN:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=entry
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PJLink from a config entry."""

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    # Temporary to take over the given name from yaml
    if CONF_NAME not in entry.data:
        return True
    ent_reg = er.async_get(hass)
    entity = next(
        (
            ent
            for ent in ent_reg.entities.values()
            if ent.config_entry_id == entry.entry_id
        ),
        None,
    )
    if entity and entity.name is None:
        ent_reg.async_update_entity(entity.entity_id, name=entry.data[CONF_NAME])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
