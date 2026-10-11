"""Helpers for philips_js."""

from collections import deque
from collections.abc import Generator, Iterable

from haphilipsjs import PhilipsTV
from haphilipsjs.typing import MenuItemsSettingsNode

from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, TRIGGER_TYPE_TURN_ON


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
    """Yield a list with a the full path to all nodes."""
    stack: deque[tuple[MenuItemsSettingsNode, ...]] = deque([(root,)])
    while stack:
        node, *path = stack.pop()
        yield node, *path
        for child in reversed(node.get("data", {}).get("nodes", [])):
            stack.append((child, node, *path))


def get_node_paths(
    api: PhilipsTV,
) -> Generator[tuple[MenuItemsSettingsNode, ...]]:
    """Fetch node paths from api."""

    if not api.json_feature_supported("menuitems", "Setup_Menu"):
        return

    if not api.on:
        raise SettingsNotAvailable("Can't get descriptions if not turned on")

    if not api.settings:
        raise SettingsNotAvailable("Can't get descriptions if not turned on")

    if not (root := api.settings.get("node")):
        raise SettingsNotAvailable("No setting nodes available")

    yield from get_node_paths_from_node(root)


async def get_path_names(
    api: PhilipsTV, paths: Iterable[tuple[MenuItemsSettingsNode, ...]]
):
    """Calculate a node name based on it's path."""

    string_ids = {
        string_id
        for path in paths
        for node in path[:-1]
        if (string_id := node.get("string_id"))
    }
    strings = await api.getStringsCached(string_ids)
    assert strings

    def _get_node_name(node: MenuItemsSettingsNode):
        if string_id := node.get("string_id"):
            return strings.get(string_id, string_id)
        if context := node.get("context"):
            return context
        return str(node["node_id"])

    def _get_path_name(path: tuple[MenuItemsSettingsNode, ...]):
        return " / ".join(_get_node_name(node) for node in reversed(path))

    return [_get_path_name(path[:-1]) for path in paths]


def get_node_strings(node: MenuItemsSettingsNode) -> Generator[str]:
    """Return all translatable strings for a node."""
    if string_id := node.get("string_id"):
        yield string_id

    if enums := node["data"].get("enums"):
        for enum in enums:
            if string_id := enum.get("string_id"):
                yield string_id

    if sliders := node["data"].get("sliders"):
        for slider in sliders:
            yield slider["slider_id"]

    if nodes := node["data"].get("nodes"):
        for child in nodes:
            if string_id := child.get("string_id"):
                yield string_id
