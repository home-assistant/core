"""Handle MySensors messages."""

from collections.abc import Callable

from mysensors import Message
from mysensors.const import SYSTEM_CHILD_ID

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import decorator

from .const import CHILD_CALLBACK, NODE_CALLBACK, DevId
from .helpers import (
    discover_mysensors_node,
    discover_mysensors_platform,
    validate_set_msg,
)
from .models import MySensorsConfigEntry

HANDLERS: decorator.Registry[
    str, Callable[[HomeAssistant, MySensorsConfigEntry, Message], None]
] = decorator.Registry()


@HANDLERS.register("set")
@callback
def handle_set(hass: HomeAssistant, entry: MySensorsConfigEntry, msg: Message) -> None:
    """Handle a mysensors set message."""
    validated = validate_set_msg(entry.entry_id, msg)
    _handle_child_update(hass, entry, validated)


@HANDLERS.register("internal")
@callback
def handle_internal(
    hass: HomeAssistant, entry: MySensorsConfigEntry, msg: Message
) -> None:
    """Handle a mysensors internal message."""
    internal = msg.gateway.const.Internal(msg.sub_type)
    if (handler := HANDLERS.get(internal.name)) is None:
        return
    handler(hass, entry, msg)


@HANDLERS.register("I_BATTERY_LEVEL")
@callback
def handle_battery_level(
    hass: HomeAssistant, entry: MySensorsConfigEntry, msg: Message
) -> None:
    """Handle an internal battery level message."""
    _handle_node_update(hass, entry, msg)


@HANDLERS.register("I_HEARTBEAT_RESPONSE")
@callback
def handle_heartbeat(
    hass: HomeAssistant, entry: MySensorsConfigEntry, msg: Message
) -> None:
    """Handle an heartbeat."""
    _handle_node_update(hass, entry, msg)


@HANDLERS.register("I_SKETCH_NAME")
@callback
def handle_sketch_name(
    hass: HomeAssistant, entry: MySensorsConfigEntry, msg: Message
) -> None:
    """Handle an internal sketch name message."""
    _handle_node_update(hass, entry, msg)


@HANDLERS.register("I_SKETCH_VERSION")
@callback
def handle_sketch_version(
    hass: HomeAssistant, entry: MySensorsConfigEntry, msg: Message
) -> None:
    """Handle an internal sketch version message."""
    _handle_node_update(hass, entry, msg)


@HANDLERS.register("presentation")
@callback
def handle_presentation(
    hass: HomeAssistant, entry: MySensorsConfigEntry, msg: Message
) -> None:
    """Handle an internal presentation message."""
    if msg.child_id == SYSTEM_CHILD_ID:
        discover_mysensors_node(hass, entry, msg.node_id)


@callback
def _handle_child_update(
    hass: HomeAssistant,
    entry: MySensorsConfigEntry,
    validated: dict[Platform, list[DevId]],
) -> None:
    """Handle a child update."""
    signals: list[str] = []

    # Update all platforms for the device via dispatcher.
    # Add/update entity for validated children.
    for platform, dev_ids in validated.items():
        discovered_dev_ids = entry.runtime_data.discovered_dev_ids[platform]
        new_dev_ids: list[DevId] = []
        for dev_id in dev_ids:
            if dev_id in discovered_dev_ids:
                signals.append(CHILD_CALLBACK.format(*dev_id))
            else:
                new_dev_ids.append(dev_id)
        if new_dev_ids:
            discover_mysensors_platform(hass, entry.entry_id, platform, new_dev_ids)
    for signal in set(signals):
        # Only one signal per device is needed.
        # A device can have multiple platforms, ie multiple schemas.
        async_dispatcher_send(hass, signal)


@callback
def _handle_node_update(
    hass: HomeAssistant, entry: MySensorsConfigEntry, msg: Message
) -> None:
    """Handle a node update."""
    signal = NODE_CALLBACK.format(entry.entry_id, msg.node_id)
    async_dispatcher_send(hass, signal)
