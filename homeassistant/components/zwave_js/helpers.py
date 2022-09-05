"""Helper functions for Z-Wave JS integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, cast

import voluptuous as vol
from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import ConfigurationValueType
from zwave_js_server.model.driver import Driver
from zwave_js_server.model.node import Node as ZwaveNode
from zwave_js_server.model.value import (
    ConfigurationValue,
    Value as ZwaveValue,
    get_value_id,
)

from homeassistant.components.group import expand_entity_ids
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    CONF_TYPE,
    __version__ as HA_VERSION,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_COMMAND_CLASS,
    ATTR_ENDPOINT,
    ATTR_PROPERTY,
    ATTR_PROPERTY_KEY,
    CONF_DATA_COLLECTION_OPTED_IN,
    DATA_CLIENT,
    DOMAIN,
    LOGGER,
)


@dataclass
class ZwaveValueID:
    """Class to represent a value ID."""

    property_: str | int
    command_class: int
    endpoint: int | None = None
    property_key: str | int | None = None


@callback
def get_value_id_from_unique_id(unique_id: str) -> str | None:
    """
    Get the value ID and optional state key from a unique ID.

    Raises ValueError
    """
    split_unique_id = unique_id.split(".")
    # If the unique ID contains a `-` in its second part, the unique ID contains
    # a value ID and we can return it.
    if "-" in (value_id := split_unique_id[1]):
        return value_id
    return None


@callback
def get_state_key_from_unique_id(unique_id: str) -> int | None:
    """Get the state key from a unique ID."""
    # If the unique ID has more than two parts, it's a special unique ID. If the last
    # part of the unique ID is an int, then it's a state key and we return it.
    if len(split_unique_id := unique_id.split(".")) > 2:
        try:
            return int(split_unique_id[-1])
        except ValueError:
            pass
    return None


@callback
def get_value_of_zwave_value(value: ZwaveValue | None) -> Any | None:
    """Return the value of a ZwaveValue."""
    return value.value if value else None


async def async_enable_statistics(driver: Driver) -> None:
    """Enable statistics on the driver."""
    await driver.async_enable_statistics("Home Assistant", HA_VERSION)
    await driver.async_enable_error_reporting()


@callback
def update_data_collection_preference(
    hass: HomeAssistant, entry: ConfigEntry, preference: bool
) -> None:
    """Update data collection preference on config entry."""
    new_data = entry.data.copy()
    new_data[CONF_DATA_COLLECTION_OPTED_IN] = preference
    hass.config_entries.async_update_entry(entry, data=new_data)


@callback
def get_valueless_base_unique_id(driver: Driver, node: ZwaveNode) -> str:
    """Return the base unique ID for an entity that is not based on a value."""
    return f"{driver.controller.home_id}.{node.node_id}"


def get_unique_id(driver: Driver, value_id: str) -> str:
    """Get unique ID from client and value ID."""
    return f"{driver.controller.home_id}.{value_id}"


@callback
def get_device_id(driver: Driver, node: ZwaveNode) -> tuple[str, str]:
    """Get device registry identifier for Z-Wave node."""
    return (DOMAIN, f"{driver.controller.home_id}-{node.node_id}")


@callback
def get_device_id_ext(driver: Driver, node: ZwaveNode) -> tuple[str, str] | None:
    """Get extended device registry identifier for Z-Wave node."""
    if None in (node.manufacturer_id, node.product_type, node.product_id):
        return None

    domain, dev_id = get_device_id(driver, node)
    return (
        domain,
        f"{dev_id}-{node.manufacturer_id}:{node.product_type}:{node.product_id}",
    )


@callback
def get_home_and_node_id_from_device_entry(
    device_entry: dr.DeviceEntry,
) -> tuple[str, int] | None:
    """
    Get home ID and node ID for Z-Wave device registry entry.

    Returns (home_id, node_id) or None if not found.
    """
    device_id = next(
        (
            identifier[1]
            for identifier in device_entry.identifiers
            if identifier[0] == DOMAIN
        ),
        None,
    )
    if device_id is None:
        return None
    id_ = device_id.split("-")
    return (id_[0], int(id_[1]))


@callback
def async_get_node_from_device_id(
    hass: HomeAssistant, device_id: str, dev_reg: dr.DeviceRegistry | None = None
) -> ZwaveNode:
    """
    Get node from a device ID.

    Raises ValueError if device is invalid or node can't be found.
    """
    if not dev_reg:
        dev_reg = dr.async_get(hass)

    if not (device_entry := dev_reg.async_get(device_id)):
        raise ValueError(f"Device ID {device_id} is not valid")

    # Use device config entry ID's to validate that this is a valid zwave_js device
    # and to get the client
    config_entry_ids = device_entry.config_entries
    entry = next(
        (
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.entry_id in config_entry_ids
        ),
        None,
    )
    if entry and entry.state != ConfigEntryState.LOADED:
        raise ValueError(f"Device {device_id} config entry is not loaded")
    if entry is None or entry.entry_id not in hass.data[DOMAIN]:
        raise ValueError(
            f"Device {device_id} is not from an existing zwave_js config entry"
        )

    client: ZwaveClient = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    driver = client.driver

    if driver is None:
        raise ValueError("Driver is not ready.")

    # Get node ID from device identifier, perform some validation, and then get the
    # node
    identifiers = get_home_and_node_id_from_device_entry(device_entry)

    node_id = identifiers[1] if identifiers else None

    if node_id is None or node_id not in driver.controller.nodes:
        raise ValueError(f"Node for device {device_id} can't be found")

    return driver.controller.nodes[node_id]


@callback
def async_get_node_from_entity_id(
    hass: HomeAssistant,
    entity_id: str,
    ent_reg: er.EntityRegistry | None = None,
    dev_reg: dr.DeviceRegistry | None = None,
) -> ZwaveNode:
    """
    Get node from an entity ID.

    Raises ValueError if entity is invalid.
    """
    if not ent_reg:
        ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(entity_id)

    if entity_entry is None or entity_entry.platform != DOMAIN:
        raise ValueError(f"Entity {entity_id} is not a valid {DOMAIN} entity.")

    # Assert for mypy, safe because we know that zwave_js entities are always
    # tied to a device
    assert entity_entry.device_id
    return async_get_node_from_device_id(hass, entity_entry.device_id, dev_reg)


@callback
def async_get_nodes_from_area_id(
    hass: HomeAssistant,
    area_id: str,
    ent_reg: er.EntityRegistry | None = None,
    dev_reg: dr.DeviceRegistry | None = None,
) -> set[ZwaveNode]:
    """Get nodes for all Z-Wave JS devices and entities that are in an area."""
    nodes: set[ZwaveNode] = set()
    if ent_reg is None:
        ent_reg = er.async_get(hass)
    if dev_reg is None:
        dev_reg = dr.async_get(hass)
    # Add devices for all entities in an area that are Z-Wave JS entities
    nodes.update(
        {
            async_get_node_from_device_id(hass, entity.device_id, dev_reg)
            for entity in er.async_entries_for_area(ent_reg, area_id)
            if entity.platform == DOMAIN and entity.device_id is not None
        }
    )
    # Add devices in an area that are Z-Wave JS devices
    for device in dr.async_entries_for_area(dev_reg, area_id):
        if next(
            (
                config_entry_id
                for config_entry_id in device.config_entries
                if cast(
                    ConfigEntry,
                    hass.config_entries.async_get_entry(config_entry_id),
                ).domain
                == DOMAIN
            ),
            None,
        ):
            nodes.add(async_get_node_from_device_id(hass, device.id, dev_reg))

    return nodes


@callback
def async_get_nodes_from_targets(
    hass: HomeAssistant,
    val: dict[str, Any],
    ent_reg: er.EntityRegistry | None = None,
    dev_reg: dr.DeviceRegistry | None = None,
    logger: logging.Logger = LOGGER,
) -> set[ZwaveNode]:
    """
    Get nodes for all targets.

    Supports entity_id with group expansion, area_id, and device_id.
    """
    nodes: set[ZwaveNode] = set()
    # Convert all entity IDs to nodes
    for entity_id in expand_entity_ids(hass, val.get(ATTR_ENTITY_ID, [])):
        try:
            nodes.add(async_get_node_from_entity_id(hass, entity_id, ent_reg, dev_reg))
        except ValueError as err:
            logger.warning(err.args[0])

    # Convert all area IDs to nodes
    for area_id in val.get(ATTR_AREA_ID, []):
        nodes.update(async_get_nodes_from_area_id(hass, area_id, ent_reg, dev_reg))

    # Convert all device IDs to nodes
    for device_id in val.get(ATTR_DEVICE_ID, []):
        try:
            nodes.add(async_get_node_from_device_id(hass, device_id, dev_reg))
        except ValueError as err:
            logger.warning(err.args[0])

    return nodes


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


def _zwave_js_config_entry(hass: HomeAssistant, device: dr.DeviceEntry) -> str | None:
    """Find zwave_js config entry from a device."""
    for entry_id in device.config_entries:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry and entry.domain == DOMAIN:
            return entry_id
    return None


@callback
def async_get_node_status_sensor_entity_id(
    hass: HomeAssistant,
    device_id: str,
    ent_reg: er.EntityRegistry | None = None,
    dev_reg: dr.DeviceRegistry | None = None,
) -> str | None:
    """Get the node status sensor entity ID for a given Z-Wave JS device."""
    if not ent_reg:
        ent_reg = er.async_get(hass)
    if not dev_reg:
        dev_reg = dr.async_get(hass)
    if not (device := dev_reg.async_get(device_id)):
        raise HomeAssistantError("Invalid Device ID provided")

    if not (entry_id := _zwave_js_config_entry(hass, device)):
        return None

    client = hass.data[DOMAIN][entry_id][DATA_CLIENT]
    node = async_get_node_from_device_id(hass, device_id, dev_reg)
    return ent_reg.async_get_entity_id(
        SENSOR_DOMAIN,
        DOMAIN,
        f"{client.driver.controller.home_id}.{node.node_id}.node_status",
    )


def remove_keys_with_empty_values(config: ConfigType) -> ConfigType:
    """Remove keys from config where the value is an empty string or None."""
    return {key: value for key, value in config.items() if value not in ("", None)}


def check_type_schema_map(schema_map: dict[str, vol.Schema]) -> Callable:
    """Check type specific schema against config."""

    def _check_type_schema(config: ConfigType) -> ConfigType:
        """Check type specific schema against config."""
        return cast(ConfigType, schema_map[str(config[CONF_TYPE])](config))

    return _check_type_schema


def copy_available_params(
    input_dict: dict[str, Any], output_dict: dict[str, Any], params: list[str]
) -> None:
    """Copy available params from input into output."""
    output_dict.update(
        {param: input_dict[param] for param in params if param in input_dict}
    )


def get_value_state_schema(
    value: ZwaveValue,
) -> vol.Schema | None:
    """Return device automation schema for a config entry."""
    if isinstance(value, ConfigurationValue):
        min_ = value.metadata.min
        max_ = value.metadata.max
        if value.configuration_value_type in (
            ConfigurationValueType.RANGE,
            ConfigurationValueType.MANUAL_ENTRY,
        ):
            return vol.All(vol.Coerce(int), vol.Range(min=min_, max=max_))

        if value.configuration_value_type == ConfigurationValueType.ENUMERATED:
            return vol.In({int(k): v for k, v in value.metadata.states.items()})

        return None

    if value.metadata.states:
        return vol.In({int(k): v for k, v in value.metadata.states.items()})

    return vol.All(
        vol.Coerce(int),
        vol.Range(min=value.metadata.min, max=value.metadata.max),
    )


def get_device_info(driver: Driver, node: ZwaveNode) -> DeviceInfo:
    """Get DeviceInfo for node."""
    return DeviceInfo(
        identifiers={get_device_id(driver, node)},
        sw_version=node.firmware_version,
        name=node.name or node.device_config.description or f"Node {node.node_id}",
        model=node.device_config.label,
        manufacturer=node.device_config.manufacturer,
        suggested_area=node.location if node.location else None,
    )
