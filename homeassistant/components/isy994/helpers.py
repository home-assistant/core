"""Sorting helpers for ISY994 device classifications."""
from collections import namedtuple

from PyISY.Nodes import Group

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR
from homeassistant.components.fan import DOMAIN as FAN
from homeassistant.components.light import DOMAIN as LIGHT
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    _LOGGER,
    ISY994_NODES,
    ISY994_PROGRAMS,
    ISY994_WEATHER,
    ISY_GROUP_PLATFORM,
    KEY_ACTIONS,
    KEY_FOLDER,
    KEY_MY_PROGRAMS,
    KEY_STATUS,
    NODE_FILTERS,
    SUPPORTED_PLATFORMS,
    SUPPORTED_PROGRAM_PLATFORMS,
)

WeatherNode = namedtuple("WeatherNode", ("status", "name", "uom"))


def _check_for_node_def(
    hass: HomeAssistantType, node, single_platform: str = None
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

    _LOGGER.warning("Unsupported node: %s, type: %s", node.name, node.type)
    return False


def _check_for_insteon_type(
    hass: HomeAssistantType, node, single_platform: str = None
) -> bool:
    """Check if the node matches the Insteon type for any platforms.

    This is for (presumably) every version of the ISY firmware, but only
    works for Insteon device. "Node Server" (v5+) and Z-Wave and others will
    not have a type.
    """
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

            # Hacky special-case just for FanLinc, which has a light module
            # as one of its nodes. Note that this special-case is not necessary
            # on ISY 5.x firmware as it uses the superior NodeDefs method
            if platform == FAN and int(node.nid[-1]) == 1:
                hass.data[ISY994_NODES][LIGHT].append(node)
                return True

            hass.data[ISY994_NODES][platform].append(node)
            return True

    return False


def _check_for_uom_id(
    hass: HomeAssistantType, node, single_platform: str = None, uom_list: list = None
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
    hass: HomeAssistantType, node, single_platform: str = None, states_list: list = None
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


def _is_sensor_a_binary_sensor(hass: HomeAssistantType, node) -> bool:
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
    hass: HomeAssistantType, nodes, ignore_identifier: str, sensor_identifier: str
) -> None:
    """Sort the nodes to their proper platforms."""
    for (path, node) in nodes:
        ignored = ignore_identifier in path or ignore_identifier in node.name
        if ignored:
            # Don't import this node as a device at all
            continue

        if isinstance(node, Group):
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
        if _check_for_uom_id(hass, node):
            continue
        if _check_for_states_in_uom(hass, node):
            continue


def _categorize_programs(hass: HomeAssistantType, programs: dict) -> None:
    """Categorize the ISY994 programs."""
    for platform in SUPPORTED_PROGRAM_PLATFORMS:
        try:
            folder = programs[KEY_MY_PROGRAMS][f"HA.{platform}"]
        except KeyError:
            continue
        for dtype, _, node_id in folder.children:
            if dtype != KEY_FOLDER:
                continue
            entity_folder = folder[node_id]
            try:
                status = entity_folder[KEY_STATUS]
                assert status.dtype == "program", "Not a program"
                if platform != BINARY_SENSOR:
                    actions = entity_folder[KEY_ACTIONS]
                    assert actions.dtype == "program", "Not a program"
                else:
                    actions = None
            except (AttributeError, KeyError, AssertionError):
                _LOGGER.warning(
                    "Program entity '%s' not loaded due "
                    "to invalid folder structure.",
                    entity_folder.name,
                )
                continue

            entity = (entity_folder.name, status, actions)
            hass.data[ISY994_PROGRAMS][platform].append(entity)


def _categorize_weather(hass: HomeAssistantType, climate) -> None:
    """Categorize the ISY994 weather data."""
    climate_attrs = dir(climate)
    weather_nodes = [
        WeatherNode(
            getattr(climate, attr),
            attr.replace("_", " "),
            getattr(climate, f"{attr}_units"),
        )
        for attr in climate_attrs
        if f"{attr}_units" in climate_attrs
    ]
    hass.data[ISY994_WEATHER].extend(weather_nodes)
