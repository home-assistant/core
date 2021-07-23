"""Helper functions for Z-Wave JS integration."""
from __future__ import annotations

from typing import Any, cast

import voluptuous as vol
from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.model.node import Node as ZwaveNode
from zwave_js_server.model.value import Value as ZwaveValue, get_value_id

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import (
    DeviceRegistry,
    async_get as async_get_dev_reg,
)
from homeassistant.helpers.entity_registry import (
    EntityRegistry,
    async_get as async_get_ent_reg,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_COMMAND_CLASS,
    ATTR_ENDPOINT,
    ATTR_PROPERTY,
    ATTR_PROPERTY_KEY,
    CONF_DATA_COLLECTION_OPTED_IN,
    DATA_CLIENT,
    DOMAIN,
)


@callback
def get_value_of_zwave_value(value: ZwaveValue | None) -> Any | None:
    """Return the value of a ZwaveValue."""
    return value.value if value else None


async def async_enable_statistics(client: ZwaveClient) -> None:
    """Enable statistics on the driver."""
    await client.driver.async_enable_statistics("Home Assistant", HA_VERSION)


@callback
def update_data_collection_preference(
    hass: HomeAssistant, entry: ConfigEntry, preference: bool
) -> None:
    """Update data collection preference on config entry."""
    new_data = entry.data.copy()
    new_data[CONF_DATA_COLLECTION_OPTED_IN] = preference
    hass.config_entries.async_update_entry(entry, data=new_data)


@callback
def get_unique_id(home_id: str, value_id: str) -> str:
    """Get unique ID from home ID and value ID."""
    return f"{home_id}.{value_id}"


@callback
def get_device_id(client: ZwaveClient, node: ZwaveNode) -> tuple[str, str]:
    """Get device registry identifier for Z-Wave node."""
    return (DOMAIN, f"{client.driver.controller.home_id}-{node.node_id}")


@callback
def get_home_and_node_id_from_device_id(device_id: tuple[str, ...]) -> list[str]:
    """
    Get home ID and node ID for Z-Wave device registry entry.

    Returns [home_id, node_id]
    """
    return device_id[1].split("-")


@callback
def async_get_node_from_device_id(
    hass: HomeAssistant, device_id: str, dev_reg: DeviceRegistry | None = None
) -> ZwaveNode:
    """
    Get node from a device ID.

    Raises ValueError if device is invalid or node can't be found.
    """
    if not dev_reg:
        dev_reg = async_get_dev_reg(hass)
    device_entry = dev_reg.async_get(device_id)

    if not device_entry:
        raise ValueError(f"Device ID {device_id} is not valid")

    # Use device config entry ID's to validate that this is a valid zwave_js device
    # and to get the client
    config_entry_ids = device_entry.config_entries
    config_entry_id = next(
        (
            config_entry_id
            for config_entry_id in config_entry_ids
            if cast(
                ConfigEntry,
                hass.config_entries.async_get_entry(config_entry_id),
            ).domain
            == DOMAIN
        ),
        None,
    )
    if config_entry_id is None or config_entry_id not in hass.data[DOMAIN]:
        raise ValueError(
            f"Device {device_id} is not from an existing zwave_js config entry"
        )

    client = hass.data[DOMAIN][config_entry_id][DATA_CLIENT]

    # Get node ID from device identifier, perform some validation, and then get the
    # node
    identifier = next(
        (
            get_home_and_node_id_from_device_id(identifier)
            for identifier in device_entry.identifiers
            if identifier[0] == DOMAIN
        ),
        None,
    )

    node_id = int(identifier[1]) if identifier is not None else None

    if node_id is None or node_id not in client.driver.controller.nodes:
        raise ValueError(f"Node for device {device_id} can't be found")

    return client.driver.controller.nodes[node_id]


@callback
def async_get_node_from_entity_id(
    hass: HomeAssistant,
    entity_id: str,
    ent_reg: EntityRegistry | None = None,
    dev_reg: DeviceRegistry | None = None,
) -> ZwaveNode:
    """
    Get node from an entity ID.

    Raises ValueError if entity is invalid.
    """
    if not ent_reg:
        ent_reg = async_get_ent_reg(hass)
    entity_entry = ent_reg.async_get(entity_id)

    if entity_entry is None or entity_entry.platform != DOMAIN:
        raise ValueError(f"Entity {entity_id} is not a valid {DOMAIN} entity.")

    # Assert for mypy, safe because we know that zwave_js entities are always
    # tied to a device
    assert entity_entry.device_id
    return async_get_node_from_device_id(hass, entity_entry.device_id, dev_reg)


def get_zwave_value_from_config(node: ZwaveNode, config: ConfigType) -> ZwaveValue:
    """Get a Z-Wave JS Value from a config."""
    endpoint = None
    if config.get(ATTR_ENDPOINT):
        endpoint = config[ATTR_ENDPOINT]
    property_key = None
    if config.get(ATTR_PROPERTY_KEY):
        property_key = config[ATTR_PROPERTY_KEY]
    value_id = get_value_id(
        node,
        config[ATTR_COMMAND_CLASS],
        config[ATTR_PROPERTY],
        endpoint,
        property_key,
    )
    if value_id not in node.values:
        raise vol.Invalid(f"Value {value_id} can't be found on node {node}")
    return node.values[value_id]


@callback
def async_get_node_status_sensor_entity_id(
    hass: HomeAssistant,
    device_id: str,
    ent_reg: EntityRegistry | None = None,
    dev_reg: DeviceRegistry | None = None,
) -> str:
    """Get the node status sensor entity ID for a given Z-Wave JS device."""
    if not ent_reg:
        ent_reg = async_get_ent_reg(hass)
    if not dev_reg:
        dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get(device_id)
    if not device:
        raise HomeAssistantError("Invalid Device ID provided")

    entry_id = next(entry_id for entry_id in device.config_entries)
    client = hass.data[DOMAIN][entry_id][DATA_CLIENT]
    node = async_get_node_from_device_id(hass, device_id, dev_reg)
    entity_id = ent_reg.async_get_entity_id(
        SENSOR_DOMAIN,
        DOMAIN,
        f"{client.driver.controller.home_id}.{node.node_id}.node_status",
    )
    if not entity_id:
        raise HomeAssistantError(
            "Node status sensor entity not found. Device may not be a zwave_js device"
        )

    return entity_id
