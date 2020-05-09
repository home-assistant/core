"""Sorting helpers for ISY994 device classifications."""
from typing import Any, List, Optional, Union

from pyisy.constants import (
    PROTO_GROUP,
    PROTO_INSTEON,
    PROTO_PROGRAM,
    PROTO_ZWAVE,
    TAG_FOLDER,
)
from pyisy.nodes import Group, Node, Nodes
from pyisy.programs import Programs

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR
from homeassistant.components.fan import DOMAIN as FAN
from homeassistant.components.light import DOMAIN as LIGHT
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.components.switch import DOMAIN as SWITCH
from homeassistant.helpers.entity_registry import async_get_registry
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    _LOGGER,
    DEFAULT_PROGRAM_STRING,
    DOMAIN,
    FILTER_INSTEON_TYPE,
    FILTER_NODE_DEF_ID,
    FILTER_STATES,
    FILTER_UOM,
    FILTER_ZWAVE_CAT,
    ISY994_NODES,
    ISY994_PROGRAMS,
    ISY_GROUP_PLATFORM,
    KEY_ACTIONS,
    KEY_STATUS,
    NODE_FILTERS,
    SUPPORTED_PLATFORMS,
    SUPPORTED_PROGRAM_PLATFORMS,
    TYPE_CATEGORY_SENSOR_ACTUATORS,
)

BINARY_SENSOR_UOMS = ["2", "78"]
BINARY_SENSOR_ISY_STATES = ["on", "off"]

TYPE_EZIO2X4 = "7.3.255."

SUBNODE_EZIO2X4_SENSORS = [9, 10, 11, 12]
SUBNODE_FANLINC_LIGHT = 1
SUBNODE_IOLINC_RELAY = 2


def _check_for_node_def(
    hass_isy_data: dict, node: Union[Group, Node], single_platform: str = None
) -> bool:
    """Check if the node matches the node_def_id for any platforms.

    This is only present on the 5.0 ISY firmware, and is the most reliable
    way to determine a device's type.
    """
    if not hasattr(node, "node_def_id") or node.node_def_id is None:
        # Node doesn't have a node_def (pre 5.0 firmware most likely)
        return False

    node_def_id = node.node_def_id

    platforms = SUPPORTED_PLATFORMS if not single_platform else [single_platform]
    for platform in platforms:
        if node_def_id in NODE_FILTERS[platform][FILTER_NODE_DEF_ID]:
            hass_isy_data[ISY994_NODES][platform].append(node)
            return True

    return False


def _check_for_insteon_type(
    hass_isy_data: dict, node: Union[Group, Node], single_platform: str = None
) -> bool:
    """Check if the node matches the Insteon type for any platforms.

    This is for (presumably) every version of the ISY firmware, but only
    works for Insteon device. "Node Server" (v5+) and Z-Wave and others will
    not have a type.
    """
    if not hasattr(node, "protocol") or node.protocol != PROTO_INSTEON:
        return False
    if not hasattr(node, "type") or node.type is None:
        # Node doesn't have a type (non-Insteon device most likely)
        return False

    device_type = node.type
    platforms = SUPPORTED_PLATFORMS if not single_platform else [single_platform]
    for platform in platforms:
        if any(
            [
                device_type.startswith(t)
                for t in set(NODE_FILTERS[platform][FILTER_INSTEON_TYPE])
            ]
        ):

            # Hacky special-cases for certain devices with different platforms
            # included as subnodes. Note that special-cases are not necessary
            # on ISY 5.x firmware as it uses the superior NodeDefs method
            subnode_id = int(node.address.split(" ")[-1], 16)

            # FanLinc, which has a light module as one of its nodes.
            if platform == FAN and subnode_id == SUBNODE_FANLINC_LIGHT:
                hass_isy_data[ISY994_NODES][LIGHT].append(node)
                return True

            # IOLincs which have a sensor and relay on 2 different nodes
            if (
                platform == BINARY_SENSOR
                and device_type.startswith(TYPE_CATEGORY_SENSOR_ACTUATORS)
                and subnode_id == SUBNODE_IOLINC_RELAY
            ):
                hass_isy_data[ISY994_NODES][SWITCH].append(node)
                return True

            # Smartenit EZIO2X4
            if (
                platform == SWITCH
                and device_type.startswith(TYPE_EZIO2X4)
                and subnode_id in SUBNODE_EZIO2X4_SENSORS
            ):
                hass_isy_data[ISY994_NODES][BINARY_SENSOR].append(node)
                return True

            hass_isy_data[ISY994_NODES][platform].append(node)
            return True

    return False


def _check_for_zwave_cat(
    hass_isy_data: dict, node: Union[Group, Node], single_platform: str = None
) -> bool:
    """Check if the node matches the ISY Z-Wave Category for any platforms.

    This is for (presumably) every version of the ISY firmware, but only
    works for Z-Wave Devices with the devtype.cat property.
    """
    if not hasattr(node, "protocol") or node.protocol != PROTO_ZWAVE:
        return False

    if not hasattr(node, "zwave_props") or node.zwave_props is None:
        # Node doesn't have a device type category (non-Z-Wave device)
        return False

    device_type = node.zwave_props.category
    platforms = SUPPORTED_PLATFORMS if not single_platform else [single_platform]
    for platform in platforms:
        if any(
            [
                device_type.startswith(t)
                for t in set(NODE_FILTERS[platform][FILTER_ZWAVE_CAT])
            ]
        ):

            hass_isy_data[ISY994_NODES][platform].append(node)
            return True

    return False


def _check_for_uom_id(
    hass_isy_data: dict,
    node: Union[Group, Node],
    single_platform: str = None,
    uom_list: list = None,
) -> bool:
    """Check if a node's uom matches any of the platforms uom filter.

    This is used for versions of the ISY firmware that report uoms as a single
    ID. We can often infer what type of device it is by that ID.
    """
    if not hasattr(node, "uom") or node.uom in [None, ""]:
        # Node doesn't have a uom (Scenes for example)
        return False

    # Backwards compatibility for ISYv4 Firmware:
    node_uom = node.uom
    if isinstance(node.uom, list):
        node_uom = node.uom[0]

    if uom_list:
        if node_uom in uom_list:
            hass_isy_data[ISY994_NODES][single_platform].append(node)
            return True
        return False

    platforms = SUPPORTED_PLATFORMS if not single_platform else [single_platform]
    for platform in platforms:
        if node_uom in NODE_FILTERS[platform][FILTER_UOM]:
            hass_isy_data[ISY994_NODES][platform].append(node)
            return True

    return False


def _check_for_states_in_uom(
    hass_isy_data: dict,
    node: Union[Group, Node],
    single_platform: str = None,
    states_list: list = None,
) -> bool:
    """Check if a list of uoms matches two possible filters.

    This is for versions of the ISY firmware that report uoms as a list of all
    possible "human readable" states. This filter passes if all of the possible
    states fit inside the given filter.
    """
    if not hasattr(node, "uom") or node.uom in [None, ""]:
        # Node doesn't have a uom (Scenes for example)
        return False

    # This only works for ISYv4 Firmware where uom is a list of states:
    if not isinstance(node.uom, list):
        return False

    node_uom = set(map(str.lower, node.uom))

    if states_list:
        if node_uom == set(states_list):
            hass_isy_data[ISY994_NODES][single_platform].append(node)
            return True
        return False

    platforms = SUPPORTED_PLATFORMS if not single_platform else [single_platform]
    for platform in platforms:
        if node_uom == set(NODE_FILTERS[platform][FILTER_STATES]):
            hass_isy_data[ISY994_NODES][platform].append(node)
            return True

    return False


def _is_sensor_a_binary_sensor(hass_isy_data: dict, node: Union[Group, Node]) -> bool:
    """Determine if the given sensor node should be a binary_sensor."""
    if _check_for_node_def(hass_isy_data, node, single_platform=BINARY_SENSOR):
        return True
    if _check_for_insteon_type(hass_isy_data, node, single_platform=BINARY_SENSOR):
        return True

    # For the next two checks, we're providing our own set of uoms that
    # represent on/off devices. This is because we can only depend on these
    # checks in the context of already knowing that this is definitely a
    # sensor device.
    if _check_for_uom_id(
        hass_isy_data, node, single_platform=BINARY_SENSOR, uom_list=BINARY_SENSOR_UOMS
    ):
        return True
    if _check_for_states_in_uom(
        hass_isy_data,
        node,
        single_platform=BINARY_SENSOR,
        states_list=BINARY_SENSOR_ISY_STATES,
    ):
        return True

    return False


def _categorize_nodes(
    hass_isy_data: dict, nodes: Nodes, ignore_identifier: str, sensor_identifier: str
) -> None:
    """Sort the nodes to their proper platforms."""
    for (path, node) in nodes:
        ignored = ignore_identifier in path or ignore_identifier in node.name
        if ignored:
            # Don't import this node as a device at all
            continue

        if hasattr(node, "protocol") and node.protocol == PROTO_GROUP:
            hass_isy_data[ISY994_NODES][ISY_GROUP_PLATFORM].append(node)
            continue

        if sensor_identifier in path or sensor_identifier in node.name:
            # User has specified to treat this as a sensor. First we need to
            # determine if it should be a binary_sensor.
            if _is_sensor_a_binary_sensor(hass_isy_data, node):
                continue
            hass_isy_data[ISY994_NODES][SENSOR].append(node)
            continue

        # We have a bunch of different methods for determining the device type,
        # each of which works with different ISY firmware versions or device
        # family. The order here is important, from most reliable to least.
        if _check_for_node_def(hass_isy_data, node):
            continue
        if _check_for_insteon_type(hass_isy_data, node):
            continue
        if _check_for_zwave_cat(hass_isy_data, node):
            continue
        if _check_for_uom_id(hass_isy_data, node):
            continue
        if _check_for_states_in_uom(hass_isy_data, node):
            continue

        # Fallback as as sensor, e.g. for un-sortable items like NodeServer nodes.
        hass_isy_data[ISY994_NODES][SENSOR].append(node)


def _categorize_programs(hass_isy_data: dict, programs: Programs) -> None:
    """Categorize the ISY994 programs."""
    for platform in SUPPORTED_PROGRAM_PLATFORMS:
        folder = programs.get_by_name(f"{DEFAULT_PROGRAM_STRING}{platform}")
        if not folder:
            continue

        for dtype, _, node_id in folder.children:
            if dtype != TAG_FOLDER:
                continue
            entity_folder = folder[node_id]

            actions = None
            status = entity_folder.get_by_name(KEY_STATUS)
            if not status or not status.protocol == PROTO_PROGRAM:
                _LOGGER.warning(
                    "Program %s entity '%s' not loaded, invalid/missing status program.",
                    platform,
                    entity_folder.name,
                )
                continue

            if platform != BINARY_SENSOR:
                actions = entity_folder.get_by_name(KEY_ACTIONS)
                if not actions or not actions.protocol == PROTO_PROGRAM:
                    _LOGGER.warning(
                        "Program %s entity '%s' not loaded, invalid/missing actions program.",
                        platform,
                        entity_folder.name,
                    )
                    continue

            entity = (entity_folder.name, status, actions)
            hass_isy_data[ISY994_PROGRAMS][platform].append(entity)


async def migrate_old_unique_ids(
    hass: HomeAssistantType, platform: str, devices: Optional[List[Any]]
) -> None:
    """Migrate to new controller-specific unique ids."""
    registry = await async_get_registry(hass)

    for device in devices:
        old_entity_id = registry.async_get_entity_id(
            platform, DOMAIN, device.old_unique_id
        )
        if old_entity_id is not None:
            _LOGGER.debug(
                "Migrating unique_id from [%s] to [%s]",
                device.old_unique_id,
                device.unique_id,
            )
            registry.async_update_entity(old_entity_id, new_unique_id=device.unique_id)

        old_entity_id_2 = registry.async_get_entity_id(
            platform, DOMAIN, device.unique_id.replace(":", "")
        )
        if old_entity_id_2 is not None:
            _LOGGER.debug(
                "Migrating unique_id from [%s] to [%s]",
                device.unique_id.replace(":", ""),
                device.unique_id,
            )
            registry.async_update_entity(
                old_entity_id_2, new_unique_id=device.unique_id
            )
