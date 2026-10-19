"""Helpers for philips_js."""

import logging
from typing import TypedDict

from haphilipsjs import PhilipsTV
from haphilipsjs.menu import (
    get_menu_node_name,
    get_menu_node_strings,
    is_menu_node_with_value,
    walk_menu_nodes,
)
from haphilipsjs.typing import MenuItemsSettingsNode

from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, MENU_NODE_TYPES, TRIGGER_TYPE_TURN_ON

_LOGGER = logging.getLogger(__name__)


class SettingsNotAvailable(HomeAssistantError):
    """Exceptions raised when we are unable to get settings."""


def async_get_turn_on_trigger(device_id: str) -> dict[str, str]:
    """Return trigger description for a turn on trigger."""

    return {
        CONF_PLATFORM: "device",
        CONF_DEVICE_ID: device_id,
        CONF_DOMAIN: DOMAIN,
        CONF_TYPE: TRIGGER_TYPE_TURN_ON,
    }


class EntitySetupNode(TypedDict):
    """Menu node with its name through the menu, to set up an entity for."""

    node: MenuItemsSettingsNode
    name: str


class MenuData(TypedDict):
    """Menu settings of the TV, as stored.

    nodes holds the named menu nodes with their name through the menu, except
    parent nodes that only group other nodes.
    """

    nodes: list[EntitySetupNode]
    strings: dict[str, str]


async def async_fetch_menu_data(api: PhilipsTV) -> MenuData:
    """Fetch the menu settings structure with names and translations from the TV."""
    if not api.settings or not (root := api.settings.get("node")):
        raise SettingsNotAvailable("No menu settings available")
    paths = list(walk_menu_nodes(root))

    string_ids = {
        string_id for node, *_ in paths for string_id in get_menu_node_strings(node)
    }
    if (strings := await api.getStringsCached(string_ids)) is None:
        raise SettingsNotAvailable("Unable to read menu strings")

    # Only parent nodes and nodes without string id are named or chosen by value
    node_ids = [
        node["node_id"]
        for node, *_ in paths
        if node["type"] == "PARENT_NODE" or not node.get("string_id")
    ]
    current = await api.getMenuItemsSettingsCurrentValue(node_ids)
    # A failed read is reported as no value for any node
    if node_ids and not any(current.values()):
        raise SettingsNotAvailable("Unable to read menu values")

    names = {
        node["node_id"]: name
        for node, *_ in paths
        if (name := get_menu_node_name(node, strings, current.get(node["node_id"])))
        is not None
    }

    nodes: list[EntitySetupNode] = []
    for path in paths:
        node = path[0]
        if not is_menu_node_with_value(node, current.get(node["node_id"])):
            continue
        try:
            name = " / ".join(names[part["node_id"]] for part in reversed(path))
        except KeyError:
            _LOGGER.debug(
                "Ignoring menu node %s, it or a parent has no name", node["node_id"]
            )
            continue
        nodes.append(EntitySetupNode(node=node, name=name))

    return MenuData(
        nodes=nodes,
        strings={string_id: strings[string_id] for string_id in string_ids},
    )


def get_menu_nodes(menu: MenuData) -> dict[int, EntitySetupNode]:
    """Return the menu nodes that can be exposed as entities."""
    return {
        data["node"]["node_id"]: data
        for data in menu["nodes"]
        if data["node"]["type"] in MENU_NODE_TYPES
    }
