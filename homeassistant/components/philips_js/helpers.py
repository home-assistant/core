"""Helpers for philips_js."""

from collections import Counter, deque
from collections.abc import Generator
import logging
from typing import TypedDict

from haphilipsjs import PhilipsTV
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


def get_node_paths_from_node(
    root: MenuItemsSettingsNode,
) -> Generator[tuple[MenuItemsSettingsNode, ...]]:
    """Yield each node with its parents up to the root, starting with the node."""
    stack: deque[tuple[MenuItemsSettingsNode, ...]] = deque([(root,)])
    while stack:
        node, *path = stack.pop()
        yield node, *path
        for child in reversed(node.get("data", {}).get("nodes", [])):
            stack.append((child, node, *path))


class MenuData(TypedDict):
    """Menu settings structure with what is needed to resolve it offline."""

    structure: MenuItemsSettingsNode
    strings: dict[str, str]
    parent_node_ids: list[int]
    # Keyed by node id as string, since the data is stored as JSON
    names: dict[str, str]


class EntitySetupData(TypedDict):
    """Description structure for setup."""

    node: MenuItemsSettingsNode
    name: str


async def async_fetch_menu_data(api: PhilipsTV) -> MenuData:
    """Fetch the menu settings structure from the TV."""
    if not api.settings or not (root := api.settings.get("node")):
        raise SettingsNotAvailable("No settings structure available")

    nodes = [node for node, *_ in get_node_paths_from_node(root)]

    # Only parent nodes with an active node can be exposed as a select
    parent_node_ids = {
        node["node_id"]
        for node in nodes
        if node["type"] == "PARENT_NODE" and node["data"].get("nodes")
    }
    # The current value of a node without string id holds its translated name
    unnamed_node_ids = {node["node_id"] for node in nodes if not node.get("string_id")}
    current = await api.getMenuItemsSettingsCurrentValue(
        list(parent_node_ids | unnamed_node_ids)
    )
    active_parent_node_ids = [
        node_id
        for node_id in parent_node_ids
        if (value := current.get(node_id))
        and value.get("data", {}).get("activenode_id")
    ]
    names = {
        str(node_id): name
        for node_id in unnamed_node_ids
        if (value := current.get(node_id)) and (name := value.get("string_id"))
    }
    for node_id in unnamed_node_ids:
        if str(node_id) not in names:
            _LOGGER.debug(
                "Ignoring menu node %s and its children without name", node_id
            )

    string_ids = {string_id for node in nodes for string_id in get_node_strings(node)}
    if (strings := await api.getStringsCached(string_ids)) is None:
        raise SettingsNotAvailable("Unable to fetch setting names")

    return MenuData(
        structure=root,
        strings={string_id: strings[string_id] for string_id in string_ids},
        parent_node_ids=sorted(active_parent_node_ids),
        names=names,
    )


def get_menu_nodes(menu: MenuData) -> dict[int, EntitySetupData]:
    """Return the menu nodes that can be exposed as entities."""
    strings = menu["strings"]
    names = menu["names"]
    parent_node_ids = set(menu["parent_node_ids"])

    def _accepted(node: MenuItemsSettingsNode) -> bool:
        if node["type"] not in MENU_NODE_TYPES:
            return False
        if node["type"] == "PARENT_NODE":
            return node["node_id"] in parent_node_ids
        return True

    def _get_node_name(node: MenuItemsSettingsNode) -> str | None:
        if string_id := node.get("string_id"):
            return strings[string_id]
        return names.get(str(node["node_id"]))

    def _get_distinct_suffix(node: MenuItemsSettingsNode) -> str:
        """Return a suffix for nodes sharing a name, like per country time zones."""
        if node["type"] == "LIST_NODE" and (enums := node["data"].get("enums")):
            string_id = enums[0]["string_id"]
            return f"{strings[string_id]} ..."
        return str(node["node_id"])

    paths = list(get_node_paths_from_node(menu["structure"]))
    node_names = {
        path[0]["node_id"]: name for path in paths if (name := _get_node_name(path[0]))
    }

    # The root node is left out of the names, it is the same for all nodes.
    # Paths with an unnamed node are skipped, those are logged when fetched.
    menu_nodes = {
        path[0]["node_id"]: EntitySetupData(
            node=path[0],
            name=" / ".join(
                node_names[node["node_id"]] for node in reversed(path[:-1])
            ),
        )
        for path in paths
        if _accepted(path[0])
        and all(node["node_id"] in node_names for node in path[:-1])
    }

    name_count = Counter(data["name"] for data in menu_nodes.values())
    suffixed_names = {
        node_id: f"{data['name']} ({_get_distinct_suffix(data['node'])})"
        for node_id, data in menu_nodes.items()
        if name_count[data["name"]] > 1
    }
    # Nodes can also share their first enum, the node id is unique
    suffixed_count = Counter(suffixed_names.values())
    for node_id, name in suffixed_names.items():
        data = menu_nodes[node_id]
        if suffixed_count[name] > 1:
            name = f"{data['name']} ({node_id})"
        data["name"] = name
    return menu_nodes


def get_node_strings(node: MenuItemsSettingsNode) -> Generator[str]:
    """Return all translatable strings for a node."""
    if string_id := node.get("string_id"):
        yield string_id

    if enums := node["data"].get("enums"):
        for enum in enums:
            yield enum["string_id"]

    if sliders := node["data"].get("sliders"):
        for slider in sliders:
            yield slider["slider_id"]

    if nodes := node["data"].get("nodes"):
        for child in nodes:
            if string_id := child.get("string_id"):
                yield string_id
