"""ISY utils."""

from __future__ import annotations

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import _LOGGER, DOMAIN


@callback
def _async_cleanup_registry_entries(hass: HomeAssistant, entry_id: str) -> None:
    """Remove extra entities that are no longer part of the integration."""
    entity_registry = er.async_get(hass)
    isy_data = hass.data[DOMAIN][entry_id]

    existing_entries = er.async_entries_for_config_entry(entity_registry, entry_id)
    entities = {
        (entity.domain, entity.unique_id): entity.entity_id
        for entity in existing_entries
    }

    extra_entities = set(entities.keys()).difference(isy_data.unique_ids)
    if not extra_entities:
        return

    for entity in extra_entities:
        if entity_registry.async_is_registered(entities[entity]):
            entity_registry.async_remove(entities[entity])

    _LOGGER.debug(
        ("Cleaning up ISY entities: removed %s extra entities for config entry %s"),
        len(extra_entities),
        entry_id,
    )
