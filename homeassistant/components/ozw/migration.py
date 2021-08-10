"""Provide tools for migrating from the zwave integration."""
from homeassistant.helpers.device_registry import (
    async_get_registry as async_get_device_registry,
)
from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry,
    async_get_registry as async_get_entity_registry,
)

from .const import DOMAIN, MIGRATED, NODES_VALUES
from .entity import create_device_id, create_value_id

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
    "Smoke": "Smoke Alarm",
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


async def async_get_migration_data(hass):
    """Return dict with ozw side migration info."""
    data = {}
    nodes_values = hass.data[DOMAIN][NODES_VALUES]
    ozw_config_entries = hass.config_entries.async_entries(DOMAIN)
    config_entry = ozw_config_entries[0]  # ozw only has a single config entry
    ent_reg = await async_get_entity_registry(hass)
    entity_entries = async_entries_for_config_entry(ent_reg, config_entry.entry_id)
    unique_entries = {entry.unique_id: entry for entry in entity_entries}
    dev_reg = await async_get_device_registry(hass)

    for node_id, node_values in nodes_values.items():
        for entity_values in node_values:
            unique_id = create_value_id(entity_values.primary)
            if unique_id not in unique_entries:
                continue
            node = entity_values.primary.node
            device_identifier = (
                DOMAIN,
                create_device_id(node, entity_values.primary.instance),
            )
            device_entry = dev_reg.async_get_device({device_identifier}, set())
            data[unique_id] = {
                "node_id": node_id,
                "node_instance": entity_values.primary.instance,
                "device_id": device_entry.id,
                "command_class": entity_values.primary.command_class.value,
                "command_class_label": entity_values.primary.label,
                "value_index": entity_values.primary.index,
                "unique_id": unique_id,
                "entity_entry": unique_entries[unique_id],
            }

    return data


def map_node_values(zwave_data, ozw_data):
    """Map zwave node values onto ozw node values."""
    migration_map = {"device_entries": {}, "entity_entries": {}}

    for zwave_entry in zwave_data.values():
        node_id = zwave_entry["node_id"]
        node_instance = zwave_entry["node_instance"]
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
                    and entry["node_instance"] == node_instance
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
                    and entry["node_instance"] == node_instance
                    and entry["command_class"] == cc_id
                    and entry["value_index"] == value_index
                ),
                None,
            )

        if ozw_entry is None:
            continue

        # Save the zwave_entry under the ozw entity_id to create the map.
        # Check that the mapped entities have the same domain.
        if zwave_entry["entity_entry"].domain == ozw_entry["entity_entry"].domain:
            migration_map["entity_entries"][
                ozw_entry["entity_entry"].entity_id
            ] = zwave_entry
        migration_map["device_entries"][ozw_entry["device_id"]] = zwave_entry[
            "device_id"
        ]

    return migration_map


async def async_migrate(hass, migration_map):
    """Perform zwave to ozw migration."""
    dev_reg = await async_get_device_registry(hass)
    for ozw_device_id, zwave_device_id in migration_map["device_entries"].items():
        zwave_device_entry = dev_reg.async_get(zwave_device_id)
        dev_reg.async_update_device(
            ozw_device_id,
            area_id=zwave_device_entry.area_id,
            name_by_user=zwave_device_entry.name_by_user,
        )

    ent_reg = await async_get_entity_registry(hass)
    for zwave_entry in migration_map["entity_entries"].values():
        zwave_entity_id = zwave_entry["entity_entry"].entity_id
        ent_reg.async_remove(zwave_entity_id)

    for ozw_entity_id, zwave_entry in migration_map["entity_entries"].items():
        entity_entry = zwave_entry["entity_entry"]
        ent_reg.async_update_entity(
            ozw_entity_id,
            new_entity_id=entity_entry.entity_id,
            name=entity_entry.name,
            icon=entity_entry.icon,
        )

    zwave_config_entry = hass.config_entries.async_entries("zwave")[0]
    await hass.config_entries.async_remove(zwave_config_entry.entry_id)

    ozw_config_entry = hass.config_entries.async_entries("ozw")[0]
    updates = {
        **ozw_config_entry.data,
        MIGRATED: True,
    }
    hass.config_entries.async_update_entry(ozw_config_entry, data=updates)
