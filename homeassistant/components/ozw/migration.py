"""Provide tools for migrating from the zwave integration."""
import logging

from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry,
    async_get_registry as async_get_entity_registry,
)

from .const import DOMAIN
from .entity import create_value_id

_LOGGER = logging.getLogger(__name__)


async def async_get_own_migration_info(hass, nodes_values):
    """Return dict with ozw side migration info."""
    data = {}

    ozw_config_entries = hass.config_entries.async_entries(DOMAIN)
    if not ozw_config_entries:
        _LOGGER.error("Config entry not set up")
        return data

    config_entry = ozw_config_entries[0]  # ozw only has a single config entry
    ent_reg = await async_get_entity_registry(hass)
    entity_entries = async_entries_for_config_entry(ent_reg, config_entry.entry_id)
    unique_entries = {entry.unique_id: entry for entry in entity_entries}

    for node_id, node_values in nodes_values.items():
        for entity_values in node_values:
            unique_id = create_value_id(entity_values.primary)
            if unique_id not in unique_entries:
                continue
            data[unique_id] = {
                "node_id": node_id,
                "command_class": entity_values.primary.command_class.value,
                "command_class_label": entity_values.primary.label,
                "value_index": entity_values.primary.index.value,
                "unique_id": unique_id,
                "entity_entry": unique_entries[unique_id],
            }

    return data
