"""Helper functions for Z-Wave JS integration."""

import asyncio
from collections import defaultdict
from collections.abc import Callable, Coroutine, Sequence
from dataclasses import astuple, dataclass
import logging
from typing import Any, cast, overload

import aiohttp
import probatio
from zwave_js_server.const import (
    LOG_LEVEL_MAP,
    CommandClass,
    ConfigurationValueType,
    LogLevel,
)
from zwave_js_server.const.command_class.notification import (
    CC_SPECIFIC_NOTIFICATION_TYPE,
    NotificationType,
)
from zwave_js_server.model.controller import Controller, ProvisioningEntry
from zwave_js_server.model.driver import Driver
from zwave_js_server.model.endpoint import Endpoint
from zwave_js_server.model.log_config import LogConfig
from zwave_js_server.model.node import EndpointGroup, Node as ZwaveNode
from zwave_js_server.model.value import (
    ConfigurationValue,
    Value as ZwaveValue,
    ValueDataType,
    get_value_id_str,
)
from zwave_js_server.version import VersionInfo, get_server_version

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_CONFIG_ENTRY_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    __version__ as HA_VERSION,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import ChildDeviceInfo, DeviceInfo
from homeassistant.helpers.group import expand_entity_ids
from homeassistant.helpers.typing import ConfigType, VolSchemaType

from .const import (
    ATTR_COMMAND_CLASS,
    ATTR_ENDPOINT,
    ATTR_PROPERTY,
    ATTR_PROPERTY_KEY,
    DOMAIN,
    LIB_LOGGER,
    LOGGER,
    NOTIFICATION_ACCESS_CONTROL_PROPERTY,
    OPENING_STATE_PROPERTY_KEY,
)
from .models import PlatformZwaveDiscoveryInfo, ZwaveJSConfigEntry

DRIVER_READY_EVENT_TIMEOUT = 60
SERVER_VERSION_TIMEOUT = 10


@dataclass
class ZwaveValueMatcher:
    """Class to allow matching a Z-Wave Value."""

    property_: str | int | None = None
    command_class: int | None = None
    endpoint: int | None = None
    property_key: str | int | None = None

    def __post_init__(self) -> None:
        """Post initialization check."""
        if all(val is None for val in astuple(self)):
            raise ValueError("At least one of the fields must be set.")


def value_matches_matcher(
    matcher: ZwaveValueMatcher, value_data: ValueDataType
) -> bool:
    """Return whether value matches matcher."""
    command_class = None
    if "commandClass" in value_data:
        command_class = CommandClass(value_data["commandClass"])
    zwave_value_id = ZwaveValueMatcher(
        property_=value_data.get("property"),
        command_class=command_class,
        endpoint=value_data.get("endpoint"),
        property_key=value_data.get("propertyKey"),
    )
    return all(
        redacted_field_val is None or redacted_field_val == zwave_value_field_val
        for redacted_field_val, zwave_value_field_val in zip(
            astuple(matcher), astuple(zwave_value_id), strict=False
        )
    )


def get_value_id_from_unique_id(unique_id: str) -> str | None:
    """Get the value ID and optional state key from a unique ID.

    Raises ValueError
    """
    split_unique_id = unique_id.split(".")
    # If the unique ID contains a `-` in its second part, the unique ID contains
    # a value ID and we can return it.
    if "-" in (value_id := split_unique_id[1]):
        return value_id
    return None


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


def get_value_of_zwave_value(value: ZwaveValue | None) -> Any | None:
    """Return the value of a ZwaveValue."""
    return value.value if value else None


def _get_notification_type(value: ZwaveValue) -> int | None:
    """Return the notification type for a value, if available."""
    return value.metadata.cc_specific.get(CC_SPECIFIC_NOTIFICATION_TYPE)


def is_opening_state_notification_value(value: ZwaveValue) -> bool:
    """Return if the value is the Access Control Opening state notification."""
    if (
        value.command_class != CommandClass.NOTIFICATION
        or _get_notification_type(value) != NotificationType.ACCESS_CONTROL
    ):
        return False

    return (
        value.property_ == NOTIFICATION_ACCESS_CONTROL_PROPERTY
        and value.property_key == OPENING_STATE_PROPERTY_KEY
    )


def get_opening_state_notification_value(
    node: ZwaveNode, endpoint: int | None = None
) -> ZwaveValue | None:
    """Return the Access Control Opening state value for a node."""
    value_id = get_value_id_str(
        node,
        CommandClass.NOTIFICATION,
        NOTIFICATION_ACCESS_CONTROL_PROPERTY,
        endpoint,
        OPENING_STATE_PROPERTY_KEY,
    )
    return node.values.get(value_id)


async def async_enable_statistics(driver: Driver) -> None:
    """Enable statistics on the driver."""
    await driver.async_enable_statistics("Home Assistant", HA_VERSION)


async def async_enable_server_logging_if_needed(
    hass: HomeAssistant, entry: ZwaveJSConfigEntry, driver: Driver
) -> None:
    """Enable logging of zwave-js-server in the lib."""
    # If lib log level is set to debug, we want to enable server logging. First we
    # check if server log level is less verbose than library logging, and if so, set it
    # to debug to match library logging. We will store the old server log level in
    # hass.data so we can reset it later
    if (
        not driver
        or not driver.client.connected
        or driver.client.server_logging_enabled
    ):
        return

    LOGGER.info("Enabling zwave-js-server logging")
    if (curr_server_log_level := driver.log_config.level) and (
        LOG_LEVEL_MAP[curr_server_log_level]
    ) > LIB_LOGGER.getEffectiveLevel():
        entry.runtime_data.old_server_log_level = curr_server_log_level
        await driver.async_update_log_config(LogConfig(level=LogLevel.DEBUG))
    await driver.client.enable_server_logging()
    LOGGER.info("Zwave-js-server logging is enabled")


async def async_disable_server_logging_if_needed(
    hass: HomeAssistant, entry: ZwaveJSConfigEntry, driver: Driver
) -> None:
    """Disable logging of zwave-js-server in the lib if still connected to server."""
    if (
        not driver
        or not driver.client.connected
        or not driver.client.server_logging_enabled
    ):
        return
    LOGGER.info("Disabling zwave_js server logging")
    if (
        old_server_log_level := entry.runtime_data.old_server_log_level
    ) is not None and old_server_log_level != driver.log_config.level:
        LOGGER.info(
            (
                "Server logging is currently set to %s as a result of server logging "
                "being enabled. It is now being reset to %s"
            ),
            driver.log_config.level,
            old_server_log_level,
        )
        await driver.async_update_log_config(LogConfig(level=old_server_log_level))
        entry.runtime_data.old_server_log_level = None
    driver.client.disable_server_logging()
    LOGGER.info("Zwave-js-server logging is enabled")


def format_home_id_for_display(home_id: int | None) -> str:
    """Format home ID as hexadecimal string for display."""
    if home_id is None:
        return "Unknown"
    return f"0x{home_id:08x}"


def get_valueless_base_unique_id(driver: Driver, node: ZwaveNode) -> str:
    """Return the base unique ID for an entity that is not based on a value."""
    return f"{driver.controller.home_id}.{node.node_id}"


def get_unique_id(driver: Driver, value_id: str) -> str:
    """Get unique ID from client and value ID."""
    return f"{driver.controller.home_id}.{value_id}"


def get_device_id(driver: Driver, node: ZwaveNode) -> tuple[str, str]:
    """Get device registry identifier for Z-Wave node."""
    return (DOMAIN, f"{driver.controller.home_id}-{node.node_id}")


def get_endpoint_device_id(
    driver: Driver, node: ZwaveNode, endpoint_device: Endpoint | EndpointGroup
) -> tuple[str, str]:
    """Get the device registry identifier for an endpoint child device.

    A child device is identified either by a single endpoint index or, when the
    device config groups several endpoints together, by ``g`` plus the group id.
    """
    domain, dev_id = get_device_id(driver, node)
    if isinstance(endpoint_device, EndpointGroup):
        return (domain, f"{dev_id}-g{endpoint_device.id}")
    return (domain, f"{dev_id}-{endpoint_device.index}")


def endpoint_devices(
    node: ZwaveNode,
    disc_infos: Sequence[PlatformZwaveDiscoveryInfo],
) -> dict[str, Endpoint | EndpointGroup]:
    """Map primary value IDs to the endpoint child device their entity belongs on.

    Values that belong on the main node device are absent from the result. Only
    endpoints that the device config explicitly describes produce child devices:

    - If the node defines endpoint groups, every value on an endpoint that belongs
      to a non-main group is placed on a single child device for that group (so, for
      example, the import and export endpoints of one meter clamp share one device).
      Values on endpoints in a main-device group, or in no group, stay on the node.
    - Otherwise, values on a labeled non-root endpoint are placed on a per-endpoint
      child device, but only when that endpoint has a value whose signature (command
      class, property, property key) also appears on another endpoint. The collision
      is determined from discovered (non-suppressed) values, so a suppressed endpoint
      value does not trigger a split.
    """
    result: dict[str, Endpoint | EndpointGroup] = {}

    if node.endpoint_groups:
        for info in disc_infos:
            endpoint_index = info.primary_value.endpoint
            if not endpoint_index:
                continue
            group = node.get_endpoint_group(endpoint_index)
            if group is not None and not group.is_main_device:
                result[info.primary_value.value_id] = group
        return result

    endpoints_by_signature: dict[tuple, set[int]] = defaultdict(set)
    for info in disc_infos:
        pv = info.primary_value
        # Root (endpoint 0) values always stay on the main device, so they are excluded
        # from the collision signatures: a non-root endpoint that merely duplicates a
        # root value is not a collision we split onto a child device.
        if pv.endpoint:
            sig = (pv.command_class, pv.property_, pv.property_key)
            endpoints_by_signature[sig].add(pv.endpoint)
    colliding_endpoints = {
        endpoint
        for endpoints in endpoints_by_signature.values()
        if len(endpoints) > 1
        for endpoint in endpoints
    }
    for info in disc_infos:
        endpoint_index = info.primary_value.endpoint
        if (
            endpoint_index
            and endpoint_index in colliding_endpoints
            and (endpoint := node.endpoints[endpoint_index]).endpoint_label
        ):
            result[info.primary_value.value_id] = endpoint
    return result


def endpoint_device_for_late_value(
    node: ZwaveNode,
    existing_placements: dict[str, Endpoint | EndpointGroup],
    primary_value: ZwaveValue,
) -> Endpoint | EndpointGroup | None:
    """Resolve the child device for a value discovered after node ready.

    Endpoints cannot be added after the node is ready, so placement is derived from the
    node's static endpoint structure and the placements already computed at node ready
    (``existing_placements``). A value on an endpoint group, or on an endpoint that is
    already a child endpoint, is placed on that child device. A value that would newly
    make a previously non-colliding endpoint collide is not handled here and stays on
    the main device.
    """
    endpoint_index = primary_value.endpoint
    if not endpoint_index:
        return None
    if node.endpoint_groups:
        group = node.get_endpoint_group(endpoint_index)
        if group is not None and not group.is_main_device:
            return group
        return None
    return next(
        (
            endpoint_device
            for endpoint_device in existing_placements.values()
            if isinstance(endpoint_device, Endpoint)
            and endpoint_device.index == endpoint_index
        ),
        None,
    )


def get_device_id_ext(driver: Driver, node: ZwaveNode) -> tuple[str, str] | None:
    """Get extended device registry identifier for Z-Wave node."""
    if None in (node.manufacturer_id, node.product_type, node.product_id):
        return None

    domain, dev_id = get_device_id(driver, node)
    return (
        domain,
        f"{dev_id}-{node.manufacturer_id}:{node.product_type}:{node.product_id}",
    )


def get_home_and_node_id_from_device_entry(
    device_entry: dr.AnyDeviceEntry,
) -> tuple[str, int] | None:
    """Get home ID and node ID for Z-Wave device registry entry.

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
    if device_id is None or device_id.startswith("provision_"):
        return None
    id_ = device_id.split("-")
    # A third segment, if present, identifies a child device (an endpoint index, or
    # ``g`` plus a group id) and is intentionally ignored here so that child devices
    # resolve to their node.
    return (id_[0], int(id_[1]))


def get_endpoint_indices_from_child_device(
    device_entry: dr.ChildDeviceEntry, node: ZwaveNode
) -> list[int]:
    """Return the endpoint indices an endpoint child device covers.

    A child device identifier is ``{home_id}-{node_id}-{endpoint}`` for a single
    endpoint or ``{home_id}-{node_id}-g{group_id}`` for an endpoint group.
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
        return []
    suffix = device_id.split("-")[-1]
    if suffix.startswith("g"):
        group = node.endpoint_groups.get(int(suffix[1:]))
        # group.endpoints filters to endpoints that actually exist on the node, unlike
        # the raw endpoint_indices which are taken as-is from the device config.
        return [endpoint.index for endpoint in group.endpoints] if group else []
    # A stale child device can outlive its endpoint (e.g. before a re-interview prunes
    # it), so only report the endpoint when it still exists on the node.
    endpoint = int(suffix)
    return [endpoint] if endpoint in node.endpoints else []


class DriverNotReadyError(ValueError):
    """Raised when the Z-Wave JS driver is not ready."""


@callback
def async_get_node_from_device_id(hass: HomeAssistant, device_id: str) -> ZwaveNode:
    """Get node from a device ID.

    Raises ValueError if device is invalid or node can't be found.
    """
    # Use the device config entry to validate that this is a valid zwave_js device
    # and to get the client
    device, config_entry = cast(
        tuple[dr.AnyDeviceEntry | None, ZwaveJSConfigEntry | None],
        dr.async_get_device_and_config_entry_for_domain(hass, device_id, domain=DOMAIN),
    )
    if device is None:
        raise ValueError(f"Device ID {device_id} is not valid")

    if config_entry is None:
        raise ValueError(
            f"Device {device_id} is not from an existing zwave_js config entry"
        )
    if config_entry.state is not ConfigEntryState.LOADED:
        raise ValueError(f"Device {device_id} config entry is not loaded")

    client = config_entry.runtime_data.client
    driver = client.driver

    if driver is None:
        raise DriverNotReadyError("Driver is not ready.")

    # Get node ID from device identifier, perform some validation, and then get the
    # node
    identifiers = get_home_and_node_id_from_device_entry(device)

    node_id = identifiers[1] if identifiers else None

    if node_id is None or node_id not in driver.controller.nodes:
        raise ValueError(f"Node for device {device_id} can't be found")

    return driver.controller.nodes[node_id]


@callback
def async_get_config_entry_from_node(
    hass: HomeAssistant, node: ZwaveNode
) -> ZwaveJSConfigEntry:
    """Get the config entry from a Z-Wave JS node."""
    return next(
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
        and entry.runtime_data.client is node.client
    )


async def async_get_provisioning_entry_from_device_id(
    hass: HomeAssistant, device_id: str
) -> ProvisioningEntry | None:
    """Get provisioning entry from a device ID.

    Raises ValueError if device is invalid
    """
    # Use the device config entry to validate that this is a valid zwave_js device
    # and to get the client
    device, config_entry = cast(
        tuple[dr.AnyDeviceEntry | None, ZwaveJSConfigEntry | None],
        dr.async_get_device_and_config_entry_for_domain(hass, device_id, domain=DOMAIN),
    )
    if device is None:
        raise ValueError(f"Device ID {device_id} is not valid")

    if config_entry is None:
        raise ValueError(
            f"Device {device_id} is not from an existing zwave_js config entry"
        )
    if config_entry.state is not ConfigEntryState.LOADED:
        raise ValueError(f"Device {device_id} config entry is not loaded")

    client = config_entry.runtime_data.client
    driver = client.driver

    if driver is None:
        raise DriverNotReadyError("Driver is not ready.")

    provisioning_entries = await driver.controller.async_get_provisioning_entries()
    for provisioning_entry in provisioning_entries:
        if (
            provisioning_entry.additional_properties
            and provisioning_entry.additional_properties.get("device_id") == device_id
        ):
            return provisioning_entry

    return None


@callback
def async_get_node_from_entity_id(
    hass: HomeAssistant,
    entity_id: str,
    ent_reg: er.EntityRegistry | None = None,
) -> ZwaveNode:
    """Get node from an entity ID.

    Raises ValueError if entity is invalid.
    """
    if not ent_reg:
        ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(entity_id)

    if entity_entry is None or entity_entry.platform != DOMAIN:
        raise ValueError(f"Entity {entity_id} is not a valid {DOMAIN} entity")

    # Assert for mypy, safe because we know that zwave_js entities are always
    # tied to a device
    assert entity_entry.device_id
    return async_get_node_from_device_id(hass, entity_entry.device_id)


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
            async_get_node_from_device_id(hass, entity.device_id)
            for entity in er.async_entries_for_area(ent_reg, area_id)
            if entity.platform == DOMAIN and entity.device_id is not None
        }
    )
    # Add devices in an area that are Z-Wave JS devices, including endpoint child devices
    # (async_get_node_from_device_id resolves a child device to its node).
    nodes.update(
        async_get_node_from_device_id(hass, device.id)
        for device in dr.async_entries_for_area(dev_reg, area_id)
        if (config_entry := hass.config_entries.async_get_entry(device.config_entry_id))
        is not None
        and config_entry.domain == DOMAIN
    )

    return nodes


@callback
def async_get_nodes_from_targets(
    hass: HomeAssistant,
    val: dict[str, Any],
    ent_reg: er.EntityRegistry | None = None,
    dev_reg: dr.DeviceRegistry | None = None,
    logger: logging.Logger = LOGGER,
    *,
    raise_on_driver_not_ready: bool = False,
) -> set[ZwaveNode]:
    """Get nodes for all targets.

    Supports entity_id with group expansion, area_id, and device_id.

    With raise_on_driver_not_ready, raises DriverNotReadyError when no node was
    found because a driver was not ready.
    """
    nodes: set[ZwaveNode] = set()
    driver_not_ready = False
    # Convert all entity IDs to nodes
    for entity_id in expand_entity_ids(hass, val.get(ATTR_ENTITY_ID, [])):
        try:
            nodes.add(async_get_node_from_entity_id(hass, entity_id, ent_reg))
        except DriverNotReadyError as err:
            driver_not_ready = True
            logger.warning(err.args[0])
        except ValueError as err:
            logger.warning(err.args[0])

    # Convert all area IDs to nodes
    for area_id in val.get(ATTR_AREA_ID, []):
        nodes.update(async_get_nodes_from_area_id(hass, area_id, ent_reg, dev_reg))

    # Convert all device IDs to nodes
    for device_id in val.get(ATTR_DEVICE_ID, []):
        try:
            nodes.add(async_get_node_from_device_id(hass, device_id))
        except DriverNotReadyError as err:
            driver_not_ready = True
            logger.warning(err.args[0])
        except ValueError as err:
            logger.warning(err.args[0])

    if raise_on_driver_not_ready and driver_not_ready and not nodes:
        raise DriverNotReadyError("Driver is not ready.")

    return nodes


def get_zwave_value_from_config(node: ZwaveNode, config: ConfigType) -> ZwaveValue:
    """Get a Z-Wave JS Value from a config."""
    endpoint = None
    if config.get(ATTR_ENDPOINT):
        endpoint = config[ATTR_ENDPOINT]
    property_key = config.get(ATTR_PROPERTY_KEY)
    if property_key == "":
        property_key = None
    value_id = get_value_id_str(
        node,
        config[ATTR_COMMAND_CLASS],
        config[ATTR_PROPERTY],
        endpoint,
        property_key,
    )
    if value_id not in node.values:
        raise probatio.Invalid(f"Value {value_id} can't be found on node {node}")
    return node.values[value_id]


def node_status_matches(node: ZwaveNode, status: str) -> bool:
    """Return whether the node has the given status name."""
    return node.status.name.lower() == status


def value_matches_state(value: ZwaveValue, expected: Any) -> bool:
    """Return whether a value matches the expected raw value, string form or label."""
    current = value.value
    return expected in (
        current,
        str(current),
        value.metadata.states.get(str(current), current),
    )


def get_zwave_js_config_entry_id(
    hass: HomeAssistant, device: dr.DeviceEntry
) -> str | None:
    """Find zwave_js config entry from a device."""
    _, config_entry = dr.async_get_device_and_config_entry_for_domain(
        hass, device.id, domain=DOMAIN
    )
    return config_entry.entry_id if config_entry else None


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
    if not (device := dev_reg.async_get(device_id, include_child_devices=False)):
        raise HomeAssistantError("Invalid Device ID provided")

    if not (entry_id := get_zwave_js_config_entry_id(hass, device)):
        return None

    entry = hass.config_entries.async_get_entry(entry_id)
    assert entry
    client = entry.runtime_data.client
    node = async_get_node_from_device_id(hass, device_id)
    return ent_reg.async_get_entity_id(
        SENSOR_DOMAIN,
        DOMAIN,
        f"{client.driver.controller.home_id}.{node.node_id}.node_status",
    )


def remove_keys_with_empty_values(config: ConfigType) -> ConfigType:
    """Remove keys from config where the value is an empty string or None."""
    return {key: value for key, value in config.items() if value not in ("", None)}


def copy_available_params(
    input_dict: dict[str, Any], output_dict: dict[str, Any], params: list[str]
) -> None:
    """Copy available params from input into output."""
    output_dict.update(
        {param: input_dict[param] for param in params if param in input_dict}
    )


def get_value_state_schema(
    value: ZwaveValue,
) -> VolSchemaType | probatio.Coerce | probatio.In | None:
    """Return device automation schema for a config entry."""
    if isinstance(value, ConfigurationValue):
        min_ = value.metadata.min
        max_ = value.metadata.max
        if value.configuration_value_type in (
            ConfigurationValueType.RANGE,
            ConfigurationValueType.MANUAL_ENTRY,
        ):
            return probatio.All(
                probatio.Coerce(int), probatio.Range(min=min_, max=max_)
            )

        if value.configuration_value_type == ConfigurationValueType.BOOLEAN:
            return probatio.Coerce(bool)

        if value.configuration_value_type == ConfigurationValueType.ENUMERATED:
            return probatio.In(
                {str(int(k)): v for k, v in value.metadata.states.items()}
            )

        return None

    if value.metadata.states:
        return probatio.In({str(int(k)): v for k, v in value.metadata.states.items()})

    return probatio.All(
        probatio.Coerce(int),
        probatio.Range(min=value.metadata.min, max=value.metadata.max),
    )


@overload
def get_device_info(
    driver: Driver,
    node: ZwaveNode,
) -> DeviceInfo: ...


@overload
def get_device_info(
    driver: Driver,
    node: ZwaveNode,
    endpoint_device: Endpoint | EndpointGroup,
    parent_device_id: str,
) -> ChildDeviceInfo: ...


def get_device_info(
    driver: Driver,
    node: ZwaveNode,
    endpoint_device: Endpoint | EndpointGroup | None = None,
    parent_device_id: str | None = None,
) -> DeviceInfo | ChildDeviceInfo:
    """Get DeviceInfo for a node or one of its endpoint child devices."""
    node_name = node.name or node.device_config.description or f"Node {node.node_id}"
    if endpoint_device is None:
        return DeviceInfo(
            identifiers={get_device_id(driver, node)},
            sw_version=node.firmware_version,
            name=node_name,
            model=node.device_config.label,
            manufacturer=node.device_config.manufacturer,
            suggested_area=node.location or None,
        )

    assert parent_device_id is not None
    name: str | None
    if isinstance(endpoint_device, EndpointGroup):
        name = endpoint_device.label
    else:
        # A value is only placed on a per-endpoint child device when the endpoint has a
        # label (see endpoint_devices), so endpoint_label is always set here.
        name = endpoint_device.endpoint_label
    return ChildDeviceInfo(
        identifiers={get_endpoint_device_id(driver, node, endpoint_device)},
        name=name,
        parent_device_id=parent_device_id,
    )


def get_network_identifier_for_notification(
    hass: HomeAssistant, config_entry: ZwaveJSConfigEntry, controller: Controller
) -> str:
    """Return the network identifier string for persistent notifications."""
    home_id = format_home_id_for_display(controller.home_id)
    if len(hass.config_entries.async_entries(DOMAIN)) > 1:
        if home_id != config_entry.title:
            return f"`{config_entry.title}`, with the home ID `{home_id}`,"
        return f"with the home ID `{home_id}`"
    return ""


async def async_get_version_info(hass: HomeAssistant, ws_address: str) -> VersionInfo:
    """Return Z-Wave JS version info."""
    try:
        async with asyncio.timeout(SERVER_VERSION_TIMEOUT):
            version_info: VersionInfo = await get_server_version(
                ws_address, async_get_clientsession(hass)
            )
    except (TimeoutError, aiohttp.ClientError) as err:
        # We don't want to spam the log if the add-on isn't started
        # or takes a long time to start.
        LOGGER.debug("Failed to connect to Z-Wave JS server: %s", err)
        raise CannotConnect from err

    return version_info


@callback
def async_wait_for_driver_ready_event(
    config_entry: ZwaveJSConfigEntry,
    driver: Driver,
) -> Callable[[], Coroutine[Any, Any, None]]:
    """Wait for the driver ready event and the config entry reload.

    When the driver ready event is received
    the config entry will be reloaded by the integration.
    This function helps wait for that to happen
    before proceeding with further actions.

    If the config entry is reloaded for another reason,
    this function will not wait for it to be reloaded again.

    Raises TimeoutError if the driver ready event and reload
    is not received within the specified timeout.
    """
    driver_ready_event_received = asyncio.Event()
    config_entry_reloaded = asyncio.Event()
    unsubscribers: list[Callable[[], None]] = []

    @callback
    def driver_ready_received(event: dict) -> None:
        """Receive the driver ready event."""
        driver_ready_event_received.set()

    unsubscribers.append(driver.once("driver ready", driver_ready_received))

    @callback
    def on_config_entry_state_change() -> None:
        """Check config entry was loaded after driver ready event."""
        if config_entry.state is ConfigEntryState.LOADED:
            config_entry_reloaded.set()

    unsubscribers.append(
        config_entry.async_on_state_change(on_config_entry_state_change)
    )

    async def wait_for_events() -> None:
        try:
            async with asyncio.timeout(DRIVER_READY_EVENT_TIMEOUT):
                await asyncio.gather(
                    driver_ready_event_received.wait(), config_entry_reloaded.wait()
                )
        finally:
            for unsubscribe in unsubscribers:
                unsubscribe()

    return wait_for_events


class CannotConnect(HomeAssistantError):
    """Indicate connection error."""


@callback
def async_bypass_dynamic_config_validation(
    hass: HomeAssistant, config: ConfigType
) -> bool:
    """Return whether a referenced zwave_js config entry is not loaded or ready."""
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    devices = config.get(ATTR_DEVICE_ID, [])
    entities = config.get(ATTR_ENTITY_ID, [])
    for entry in hass.config_entries.async_entries(DOMAIN):
        if not (
            entry.entry_id == config.get(ATTR_CONFIG_ENTRY_ID)
            or any(
                device.id in devices
                for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
            )
            or any(
                device.id in devices
                for device in dr.async_child_entries_for_config_entry(
                    dev_reg, entry.entry_id
                )
            )
            or any(
                entity.entity_id in entities
                for entity in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
            )
        ):
            continue
        if entry.state is not ConfigEntryState.LOADED:
            return True
        # The driver may not be ready when the config entry is loaded.
        if entry.runtime_data.client.driver is None:
            return True

    return False
