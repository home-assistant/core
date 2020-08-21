"""Provide tools for migrating from the zwave integration."""
import logging

from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry,
    async_get_registry as async_get_entity_registry,
)

from .const import DOMAIN
from .entity import create_value_id

_LOGGER = logging.getLogger(__name__)

# The following dicts map labels between OpenZWave 1.4 and 1.6.
METER_CC_LABELS = {
    "Energy": "Electric - kWh",
    "Power": "Electric - W",
    "Count": "Electric - Pulses",
    "Voltage": "Electric - V",
    "Current": "Electric - A",
    "Power Factor": "Electric - PF",
}

NOTIFICATION_CC_LABELS = {
    "General": "Start",
    "Smoke": "Smoke_Alarm",
    "Carbon Monoxide": "Carbon Monoxide",
    "Carbon Dioxide": "Carbon Dioxide",
    "Heat": "Heat",
    "Flood": "Water",
    "Access Control": "Access Control",
    "Burglar": "Home Security",
    "Power Management": "Power Management",
    "System": "System",
    "Emergency": "Emergency",
    "Clock": "Clock",
    "Appliance": "Appliance",
    "HomeHealth": "Home Health",
}

CC_ID_LABELS = {
    50: METER_CC_LABELS,
    113: NOTIFICATION_CC_LABELS,
}


async def async_get_migration_data(hass, nodes_values):
    """Return dict with ozw side migration info."""
    data = {}
    ozw_config_entries = hass.config_entries.async_entries(DOMAIN)
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


def map_node_values(zwave_data, ozw_data):
    """Map zwave node values onto ozw node values."""
    can_migrate = {}

    for zwave_entry in zwave_data.values():
        node_id = zwave_entry["node_id"]
        cc_id = zwave_entry["command_class"]
        zwave_cc_label = zwave_entry["command_class_label"]

        if cc_id in CC_ID_LABELS:
            labels = CC_ID_LABELS[cc_id]
            ozw_cc_label = labels.get(zwave_cc_label, zwave_cc_label)

            ozw_entry = next(
                (
                    entry
                    for entry in ozw_data.values()
                    if entry["node_id"] == node_id
                    and entry["command_class"] == cc_id
                    and entry["command_class_label"] == ozw_cc_label
                ),
                None,
            )
        else:
            value_index = zwave_entry["value_index"]

            ozw_entry = next(
                (
                    entry
                    for entry in ozw_data.values()
                    if entry["node_id"] == node_id
                    and entry["command_class"] == cc_id
                    and entry["value_index"] == value_index
                ),
                None,
            )

        if ozw_entry is None:
            continue

        # Save the zwave_entry under the ozw entity_id to create the map.
        can_migrate[ozw_entry["entity_entry"].entity_id] = zwave_entry

    return can_migrate


async def async_migrate(hass, migration_map):
    """Perform zwave to ozw migration."""
    ent_reg = await async_get_entity_registry(hass)
    for zwave_entry in migration_map.values():
        zwave_entity_id = zwave_entry["entity_entry"].entity_id
        ent_reg.async_remove(zwave_entity_id)

    for ozw_entity_id, zwave_entry in migration_map.items():
        entity_entry = zwave_entry["entity_entry"]
        ent_reg.async_update_entity(
            ozw_entity_id,
            new_entity_id=entity_entry.entity_id,
            name=entity_entry.name,
            icon=entity_entry.icon,
        )
