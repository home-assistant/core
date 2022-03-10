"""Component to wrap switch entities in entities of other domains."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_entity_registry_updated_event

from .light import LightSwitch

__all__ = ["LightSwitch"]

DOMAIN = "switch_as_x"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    registry = er.async_get(hass)
    try:
        entity_id = er.async_validate_entity_id(registry, entry.options[CONF_ENTITY_ID])
    except vol.Invalid:
        # The entity is identified by an unknown entity registry ID
        _LOGGER.error(
            "Failed to setup switch_as_x for unknown entity %s",
            entry.options[CONF_ENTITY_ID],
        )
        return False

    async def async_registry_updated(event: Event) -> None:
        """Handle entity registry update."""
        data = event.data
        if data["action"] == "remove":
            await hass.config_entries.async_remove(entry.entry_id)

        if data["action"] != "update" or "entity_id" not in data["changes"]:
            return

        # Entity_id changed, reload the config entry
        await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(
        async_track_entity_registry_updated_event(
            hass, entity_id, async_registry_updated
        )
    )

    hass.config_entries.async_setup_platforms(entry, (entry.options["target_domain"],))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(
        entry, (entry.options["target_domain"],)
    )
