"""Sorting helpers for ISY994 device classifications."""
from typing import Union

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
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    _LOGGER,
    ISY994_NODES,
    ISY994_PROGRAMS,
    ISY_BIN_SENS_DEVICE_TYPES,
    ISY_GROUP_PLATFORM,
    KEY_ACTIONS,
    KEY_STATUS,
    NODE_FILTERS,
    SUPPORTED_PLATFORMS,
    SUPPORTED_PROGRAM_PLATFORMS,
    ZWAVE_BIN_SENS_DEVICE_TYPES,
)


def _check_for_node_def(
    hass: HomeAssistantType, node: Union[Group, Node], single_platform: str = None
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
        if node_def_id in NODE_FILTERS[platform]["node_def_id"]:
            hass.data[ISY994_NODES][platform].append(node)
            return True

    return False


def _check_for_insteon_type(
    hass: HomeAssistantType, node: Union[Group, Node], single_platform: str = None
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
                for t in set(NODE_FILTERS[platform]["insteon_type"])
            ]
        ):

            # Hacky special-cases for certain devices with different platforms
            # included as subnodes. Note that special-cases are not necessary
            # on ISY 5.x firmware as it uses the superior NodeDefs method

            # FanLinc, which has a light module as one of its nodes.
            if platform == FAN and str(node.address[-1]) in ["1"]:
                hass.data[ISY994_NODES][LIGHT].append(node)
                return True

            # IOLincs which have a sensor and relay on 2 different nodes
            if (
                platform == BINARY_SENSOR
                and device_type.startswith("7.")
                and str(node.address[-1]) in ["2"]
            ):
                hass.data[ISY994_NODES][SWITCH].append(node)
                return True

            # Smartenit EZIO2X4
            if (
                platform == SWITCH
                and device_type.startswith("7.3.255.")
                and str(node.address[-1]) in ["9", "A", "B", "C"]
            ):
                hass.data[ISY994_NODES][BINARY_SENSOR].append(node)
                return True

            hass.data[ISY994_NODES][platform].append(node)
            return True

    return False


def _check_for_zwave_cat(
    hass: HomeAssistantType, node: Union[Group, Node], single_platform: str = None
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
                for t in set(NODE_FILTERS[platform]["zwave_cat"])
            ]
        ):

            hass.data[ISY994_NODES][platform].append(node)
            return True

    return False


def _check_for_uom_id(
    hass: HomeAssistantType,
    node: Union[Group, Node],
    single_platform: str = None,
    uom_list: list = None,
) -> bool:
    """Check if a node's uom matches any of the platforms uom filter.

    This is used for versions of the ISY firmware that report uoms as a single
    ID. We can often infer what type of device it is by that ID.
    """
    if not hasattr(node, "uom") or node.uom is None:
        # Node doesn't have a uom (Scenes for example)
        return False

    node_uom = set(map(str.lower, node.uom))

    if uom_list:
        if node_uom.intersection(uom_list):
            hass.data[ISY994_NODES][single_platform].append(node)
            return True
    else:
        platforms = SUPPORTED_PLATFORMS if not single_platform else [single_platform]
        for platform in platforms:
            if node_uom.intersection(NODE_FILTERS[platform]["uom"]):
                hass.data[ISY994_NODES][platform].append(node)
                return True

    return False


def _check_for_states_in_uom(
    hass: HomeAssistantType,
    node: Union[Group, Node],
    single_platform: str = None,
    states_list: list = None,
) -> bool:
    """Check if a list of uoms matches two possible filters.

    This is for versions of the ISY firmware that report uoms as a list of all
    possible "human readable" states. This filter passes if all of the possible
    states fit inside the given filter.
    """
    if not hasattr(node, "uom") or node.uom is None:
        # Node doesn't have a uom (Scenes for example)
        return False

    node_uom = set(map(str.lower, node.uom))

    if states_list:
        if node_uom == set(states_list):
            hass.data[ISY994_NODES][single_platform].append(node)
            return True
    else:
        platforms = SUPPORTED_PLATFORMS if not single_platform else [single_platform]
        for platform in platforms:
            if node_uom == set(NODE_FILTERS[platform]["states"]):
                hass.data[ISY994_NODES][platform].append(node)
                return True

    return False


def _is_sensor_a_binary_sensor(
    hass: HomeAssistantType, node: Union[Group, Node]
) -> bool:
    """Determine if the given sensor node should be a binary_sensor."""
    if _check_for_node_def(hass, node, single_platform=BINARY_SENSOR):
        return True
    if _check_for_insteon_type(hass, node, single_platform=BINARY_SENSOR):
        return True

    # For the next two checks, we're providing our own set of uoms that
    # represent on/off devices. This is because we can only depend on these
    # checks in the context of already knowing that this is definitely a
    # sensor device.
    if _check_for_uom_id(
        hass, node, single_platform=BINARY_SENSOR, uom_list=["2", "78"]
    ):
        return True
    if _check_for_states_in_uom(
        hass, node, single_platform=BINARY_SENSOR, states_list=["on", "off"]
    ):
        return True

    return False


def _categorize_nodes(
    hass: HomeAssistantType,
    nodes: Nodes,
    ignore_identifier: str,
    sensor_identifier: str,
) -> None:
    """Sort the nodes to their proper platforms."""
    for (path, node) in nodes:
        ignored = ignore_identifier in path or ignore_identifier in node.name
        if ignored:
            # Don't import this node as a device at all
            continue

        if hasattr(node, "protocol") and node.protocol == PROTO_GROUP:
            hass.data[ISY994_NODES][ISY_GROUP_PLATFORM].append(node)
            continue

        if sensor_identifier in path or sensor_identifier in node.name:
            # User has specified to treat this as a sensor. First we need to
            # determine if it should be a binary_sensor.
            if _is_sensor_a_binary_sensor(hass, node):
                continue

            hass.data[ISY994_NODES][SENSOR].append(node)
            continue

        # We have a bunch of different methods for determining the device type,
        # each of which works with different ISY firmware versions or device
        # family. The order here is important, from most reliable to least.
        if _check_for_node_def(hass, node):
            continue
        if _check_for_insteon_type(hass, node):
            continue
        if _check_for_zwave_cat(hass, node):
            continue
        if _check_for_uom_id(hass, node):
            continue
        if _check_for_states_in_uom(hass, node):
            continue


def _categorize_programs(hass: HomeAssistantType, programs: Programs) -> None:
    """Categorize the ISY994 programs."""
    for platform in SUPPORTED_PROGRAM_PLATFORMS:
        folder = programs.get_by_name(f"HA.{platform}")
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
            hass.data[ISY994_PROGRAMS][platform].append(entity)


def _detect_device_type_and_class(node: Union[Group, Node]) -> (str, str):
    try:
        device_type = node.type
    except AttributeError:
        # The type attribute didn't exist in the ISY's API response
        return (None, None)

    # Z-Wave Devices:
    if node.protocol == PROTO_ZWAVE:
        device_type = f"Z{node.zwave_props.category}"
        for device_class in [*ZWAVE_BIN_SENS_DEVICE_TYPES]:
            if node.zwave_props.category in ZWAVE_BIN_SENS_DEVICE_TYPES[device_class]:
                return device_class, device_type
    else:  # Other devices (incl Insteon.)
        for device_class in [*ISY_BIN_SENS_DEVICE_TYPES]:
            if any(
                [
                    device_type.startswith(t)
                    for t in set(ISY_BIN_SENS_DEVICE_TYPES[device_class])
                ]
            ):
                return device_class, device_type

    return (None, device_type)
