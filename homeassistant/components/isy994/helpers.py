"""Sorting helpers for ISY device classifications."""

from __future__ import annotations

from typing import cast

from pyisy.constants import (
    BACKLIGHT_SUPPORT,
    CMD_BACKLIGHT,
    ISY_VALUE_UNKNOWN,
    PROP_BUSY,
    PROP_COMMS_ERROR,
    PROP_ON_LEVEL,
    PROP_RAMP_RATE,
    PROP_STATUS,
    PROTO_GROUP,
    PROTO_INSTEON,
    PROTO_PROGRAM,
    PROTO_ZWAVE,
    TAG_ENABLED,
    TAG_FOLDER,
    UOM_INDEX,
)
from pyisy.nodes import Group, Node, Nodes
from pyisy.programs import Programs

from homeassistant.const import ATTR_MANUFACTURER, ATTR_MODEL, Platform
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    _LOGGER,
    DEFAULT_PROGRAM_STRING,
    DOMAIN,
    FILTER_INSTEON_TYPE,
    FILTER_NODE_DEF_ID,
    FILTER_STATES,
    FILTER_UOM,
    FILTER_ZWAVE_CAT,
    ISY_GROUP_PLATFORM,
    KEY_ACTIONS,
    KEY_STATUS,
    NODE_AUX_FILTERS,
    NODE_FILTERS,
    NODE_PLATFORMS,
    PROGRAM_PLATFORMS,
    SUBNODE_CLIMATE_COOL,
    SUBNODE_CLIMATE_HEAT,
    SUBNODE_EZIO2X4_SENSORS,
    SUBNODE_FANLINC_LIGHT,
    SUBNODE_IOLINC_RELAY,
    TYPE_CATEGORY_SENSOR_ACTUATORS,
    TYPE_EZIO2X4,
    UOM_DOUBLE_TEMP,
    UOM_ISYV4_DEGREES,
)
from .models import IsyData

BINARY_SENSOR_UOMS = ["2", "78"]
BINARY_SENSOR_ISY_STATES = ["on", "off"]
ROOT_AUX_CONTROLS = {
    PROP_ON_LEVEL,
    PROP_RAMP_RATE,
}
SKIP_AUX_PROPS = {PROP_BUSY, PROP_COMMS_ERROR, PROP_STATUS, *ROOT_AUX_CONTROLS}


def _check_for_node_def(
    isy_data: IsyData, node: Group | Node, single_platform: Platform | None = None
) -> bool:
    """Check if the node matches the node_def_id for any platforms.

    This is only present on the 5.0 ISY firmware, and is the most reliable
    way to determine a device's type.
    """
    if not hasattr(node, "node_def_id") or node.node_def_id is None:
        # Node doesn't have a node_def (pre 5.0 firmware most likely)
        return False

    node_def_id = node.node_def_id

    platforms = NODE_PLATFORMS if not single_platform else [single_platform]
    for platform in platforms:
        if node_def_id in NODE_FILTERS[platform][FILTER_NODE_DEF_ID]:
            isy_data.nodes[platform].append(node)
            return True

    return False


def _check_for_insteon_type(
    isy_data: IsyData, node: Group | Node, single_platform: Platform | None = None
) -> bool:
    """Check if the node matches the Insteon type for any platforms.

    This is for (presumably) every version of the ISY firmware, but only
    works for Insteon device. "Node Server" (v5+) and Z-Wave and others will
    not have a type.
    """
    if node.protocol != PROTO_INSTEON:
        return False
    if not hasattr(node, "type") or node.type is None:
        # Node doesn't have a type (non-Insteon device most likely)
        return False

    device_type = node.type
    platforms = NODE_PLATFORMS if not single_platform else [single_platform]
    for platform in platforms:
        if any(
            device_type.startswith(t)
            for t in set(NODE_FILTERS[platform][FILTER_INSTEON_TYPE])
        ):
            # Hacky special-cases for certain devices with different platforms
            # included as subnodes. Note that special-cases are not necessary
            # on ISY 5.x firmware as it uses the superior NodeDefs method
            subnode_id = int(node.address.split(" ")[-1], 16)

            # FanLinc, which has a light module as one of its nodes.
            if platform == Platform.FAN and subnode_id == SUBNODE_FANLINC_LIGHT:
                isy_data.nodes[Platform.LIGHT].append(node)
                return True

            # Thermostats, which has a "Heat" and "Cool" sub-node on address 2 and 3
            if platform == Platform.CLIMATE and subnode_id in (
                SUBNODE_CLIMATE_COOL,
                SUBNODE_CLIMATE_HEAT,
            ):
                isy_data.nodes[Platform.BINARY_SENSOR].append(node)
                return True

            # IOLincs which have a sensor and relay on 2 different nodes
            if (
                platform == Platform.BINARY_SENSOR
                and device_type.startswith(TYPE_CATEGORY_SENSOR_ACTUATORS)
                and subnode_id == SUBNODE_IOLINC_RELAY
            ):
                isy_data.nodes[Platform.SWITCH].append(node)
                return True

            # Smartenit EZIO2X4
            if (
                platform == Platform.SWITCH
                and device_type.startswith(TYPE_EZIO2X4)
                and subnode_id in SUBNODE_EZIO2X4_SENSORS
            ):
                isy_data.nodes[Platform.BINARY_SENSOR].append(node)
                return True

            isy_data.nodes[platform].append(node)
            return True

    return False


def _check_for_zwave_cat(
    isy_data: IsyData, node: Group | Node, single_platform: Platform | None = None
) -> bool:
    """Check if the node matches the ISY Z-Wave Category for any platforms.

    This is for (presumably) every version of the ISY firmware, but only
    works for Z-Wave Devices with the devtype.cat property.
    """
    if node.protocol != PROTO_ZWAVE:
        return False

    if not hasattr(node, "zwave_props") or node.zwave_props is None:
        # Node doesn't have a device type category (non-Z-Wave device)
        return False

    device_type = node.zwave_props.category
    platforms = NODE_PLATFORMS if not single_platform else [single_platform]
    for platform in platforms:
        if any(
            device_type.startswith(t)
            for t in set(NODE_FILTERS[platform][FILTER_ZWAVE_CAT])
        ):
            isy_data.nodes[platform].append(node)
            return True

    return False


def _check_for_uom_id(
    isy_data: IsyData,
    node: Group | Node,
    single_platform: Platform | None = None,
    uom_list: list[str] | None = None,
) -> bool:
    """Check if a node's uom matches any of the platforms uom filter.

    This is used for versions of the ISY firmware that report uoms as a single
    ID. We can often infer what type of device it is by that ID.
    """
    if not hasattr(node, "uom") or node.uom in (None, ""):
        # Node doesn't have a uom (Scenes for example)
        return False

    # Backwards compatibility for ISYv4 Firmware:
    node_uom = node.uom
    if isinstance(node.uom, list):
        node_uom = node.uom[0]

    if uom_list and single_platform:
        if node_uom in uom_list:
            isy_data.nodes[single_platform].append(node)
            return True
        return False

    platforms = NODE_PLATFORMS if not single_platform else [single_platform]
    for platform in platforms:
        if node_uom in NODE_FILTERS[platform][FILTER_UOM]:
            isy_data.nodes[platform].append(node)
            return True

    return False


def _check_for_states_in_uom(
    isy_data: IsyData,
    node: Group | Node,
    single_platform: Platform | None = None,
    states_list: list[str] | None = None,
) -> bool:
    """Check if a list of uoms matches two possible filters.

    This is for versions of the ISY firmware that report uoms as a list of all
    possible "human readable" states. This filter passes if all of the possible
    states fit inside the given filter.
    """
    if not hasattr(node, "uom") or node.uom in (None, ""):
        # Node doesn't have a uom (Scenes for example)
        return False

    # This only works for ISYv4 Firmware where uom is a list of states:
    if not isinstance(node.uom, list):
        return False

    node_uom = set(map(str.lower, node.uom))

    if states_list and single_platform:
        if node_uom == set(states_list):
            isy_data.nodes[single_platform].append(node)
            return True
        return False

    platforms = NODE_PLATFORMS if not single_platform else [single_platform]
    for platform in platforms:
        if node_uom == set(NODE_FILTERS[platform][FILTER_STATES]):
            isy_data.nodes[platform].append(node)
            return True

    return False


def _is_sensor_a_binary_sensor(isy_data: IsyData, node: Group | Node) -> bool:
    """Determine if the given sensor node should be a binary_sensor."""
    if _check_for_node_def(isy_data, node, single_platform=Platform.BINARY_SENSOR):
        return True
    if _check_for_insteon_type(isy_data, node, single_platform=Platform.BINARY_SENSOR):
        return True

    # For the next two checks, we're providing our own set of uoms that
    # represent on/off devices. This is because we can only depend on these
    # checks in the context of already knowing that this is definitely a
    # sensor device.
    if _check_for_uom_id(
        isy_data,
        node,
        single_platform=Platform.BINARY_SENSOR,
        uom_list=BINARY_SENSOR_UOMS,
    ):
        return True
    if _check_for_states_in_uom(
        isy_data,
        node,
        single_platform=Platform.BINARY_SENSOR,
        states_list=BINARY_SENSOR_ISY_STATES,
    ):
        return True

    return False


def _add_backlight_if_supported(isy_data: IsyData, node: Node) -> None:
    """Check if a node supports setting a backlight and add entity."""
    if not getattr(node, "is_backlight_supported", False):
        return
    if BACKLIGHT_SUPPORT[node.node_def_id] == UOM_INDEX:
        isy_data.aux_properties[Platform.SELECT].append((node, CMD_BACKLIGHT))
        return
    isy_data.aux_properties[Platform.NUMBER].append((node, CMD_BACKLIGHT))


def _generate_device_info(node: Node) -> DeviceInfo:
    """Generate the device info for a root node device."""
    isy = node.isy
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{isy.uuid}_{node.address}")},
        manufacturer=node.protocol.title(),
        name=node.name,
        via_device=(DOMAIN, isy.uuid),
        configuration_url=isy.conn.url,
        suggested_area=node.folder,
    )

    # ISYv5 Device Types can provide model and manufacturer
    model: str = str(node.address).rpartition(" ")[0] or node.address
    if node.node_def_id is not None:
        model += f": {node.node_def_id}"

    # Numerical Device Type
    if node.type is not None:
        model += f" ({node.type})"

    # Get extra information for Z-Wave Devices
    if (
        node.protocol == PROTO_ZWAVE
        and node.zwave_props
        and node.zwave_props.mfr_id != "0"
    ):
        device_info[ATTR_MANUFACTURER] = (
            f"Z-Wave MfrID:{int(node.zwave_props.mfr_id):#0{6}x}"
        )
        model += (
            f"Type:{int(node.zwave_props.prod_type_id):#0{6}x} "
            f"Product:{int(node.zwave_props.product_id):#0{6}x}"
        )
    device_info[ATTR_MODEL] = model

    return device_info


def _categorize_nodes(
    isy_data: IsyData, nodes: Nodes, ignore_identifier: str, sensor_identifier: str
) -> None:
    """Sort the nodes to their proper platforms."""
    for path, node in nodes:
        ignored = ignore_identifier in path or ignore_identifier in node.name
        if ignored:
            # Don't import this node as a device at all
            continue

        if hasattr(node, "parent_node") and node.parent_node is None:
            # This is a physical device / parent node
            isy_data.devices[node.address] = _generate_device_info(node)
            isy_data.root_nodes[Platform.BUTTON].append(node)
            # Any parent node can have communication errors:
            isy_data.aux_properties[Platform.SENSOR].append((node, PROP_COMMS_ERROR))
            # Add Ramp Rate and On Levels for Dimmable Load devices
            if getattr(node, "is_dimmable", False):
                aux_controls = ROOT_AUX_CONTROLS.intersection(node.aux_properties)
                for control in aux_controls:
                    platform = NODE_AUX_FILTERS[control]
                    isy_data.aux_properties[platform].append((node, control))
            if hasattr(node, TAG_ENABLED):
                isy_data.aux_properties[Platform.SWITCH].append((node, TAG_ENABLED))
            _add_backlight_if_supported(isy_data, node)

        if node.protocol == PROTO_GROUP:
            isy_data.nodes[ISY_GROUP_PLATFORM].append(node)
            continue

        if node.protocol == PROTO_INSTEON:
            for control in node.aux_properties:
                if control in SKIP_AUX_PROPS:
                    continue
                isy_data.aux_properties[Platform.SENSOR].append((node, control))

        if sensor_identifier in path or sensor_identifier in node.name:
            # User has specified to treat this as a sensor. First we need to
            # determine if it should be a binary_sensor.
            if _is_sensor_a_binary_sensor(isy_data, node):
                continue
            isy_data.nodes[Platform.SENSOR].append(node)
            continue

        # We have a bunch of different methods for determining the device type,
        # each of which works with different ISY firmware versions or device
        # family. The order here is important, from most reliable to least.
        if _check_for_node_def(isy_data, node):
            continue
        if _check_for_insteon_type(isy_data, node):
            continue
        if _check_for_zwave_cat(isy_data, node):
            continue
        if _check_for_uom_id(isy_data, node):
            continue
        if _check_for_states_in_uom(isy_data, node):
            continue

        # Fallback as as sensor, e.g. for un-sortable items like NodeServer nodes.
        isy_data.nodes[Platform.SENSOR].append(node)


def _categorize_programs(isy_data: IsyData, programs: Programs) -> None:
    """Categorize the ISY programs."""
    for platform in PROGRAM_PLATFORMS:
        folder = programs.get_by_name(f"{DEFAULT_PROGRAM_STRING}{platform}")
        if not folder:
            continue

        for dtype, _, node_id in folder.children:
            if dtype != TAG_FOLDER:
                continue
            entity_folder: Programs = folder[node_id]
            actions = None
            status = entity_folder.get_by_name(KEY_STATUS)
            if not status or status.protocol != PROTO_PROGRAM:
                _LOGGER.warning(
                    "Program %s entity '%s' not loaded, invalid/missing status program",
                    platform,
                    entity_folder.name,
                )
                continue

            if platform != Platform.BINARY_SENSOR:
                actions = entity_folder.get_by_name(KEY_ACTIONS)
                if not actions or actions.protocol != PROTO_PROGRAM:
                    _LOGGER.warning(
                        (
                            "Program %s entity '%s' not loaded, invalid/missing actions"
                            " program"
                        ),
                        platform,
                        entity_folder.name,
                    )
                    continue

            entity = (entity_folder.name, status, actions)
            isy_data.programs[platform].append(entity)


def convert_isy_value_to_hass(
    value: float | None,
    uom: str | None,
    precision: int | str,
    fallback_precision: int | None = None,
) -> float | int | None:
    """Fix ISY Reported Values.

    ISY provides float values as an integer and precision component.
    Correct by shifting the decimal place left by the value of precision.
    (e.g. value=2345, prec="2" == 23.45)

    Insteon Thermostats report temperature in 0.5-deg precision as an int
    by sending a value of 2 times the Temp. Correct by dividing by 2 here.
    """
    if value is None or value == ISY_VALUE_UNKNOWN:
        return None
    if uom in (UOM_DOUBLE_TEMP, UOM_ISYV4_DEGREES):
        return round(float(value) / 2.0, 1)
    if precision not in ("0", 0):
        return cast(float, round(float(value) / 10 ** int(precision), int(precision)))
    if fallback_precision:
        return round(float(value), fallback_precision)
    return value
