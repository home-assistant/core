"""Describe Meshtastic logbook events.

Every packet the gateway hears is published on the bus as a ``meshtastic_event``.
The logbook turns those into one readable line each: who was heard, what they
sent, and over which channel.  The describer is deliberately forgiving about
the payload - a packet from an unknown application still produces a sensible
line rather than a ``KeyError`` in the recorder.
"""

from collections.abc import Callable, Mapping
from typing import Any

from homeassistant.components.logbook import (
    LOGBOOK_ENTRY_ICON,
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import (
    ATTR_CHANNEL,
    ATTR_EVENT_TYPE,
    ATTR_FROM_ID,
    ATTR_FROM_NUM,
    ATTR_GATEWAY_ID,
    ATTR_NODE_ID,
    ATTR_NODE_NUM,
    ATTR_PORTNUM,
    ATTR_TEXT,
    ATTR_TO_NUM,
    ATTR_VIA_MQTT,
    BROADCAST_NUM,
    DOMAIN,
    EVENT_MESHTASTIC,
    PORTNUM_ALERT_APP,
    PORTNUM_DETECTION_SENSOR_APP,
    PORTNUM_MAP_REPORT_APP,
    PORTNUM_NAMES,
    PORTNUM_NEIGHBORINFO_APP,
    PORTNUM_NODEINFO_APP,
    PORTNUM_PAXCOUNTER_APP,
    PORTNUM_POSITION_APP,
    PORTNUM_ROUTING_APP,
    PORTNUM_TELEMETRY_APP,
    PORTNUM_TRACEROUTE_APP,
    PORTNUM_UNKNOWN_APP,
    PORTNUM_WAYPOINT_APP,
    format_node_id,
    gateway_device_id,
    node_device_id,
    parse_node_id,
)

#: A logbook line is a one-liner; long messages are cut rather than wrapped.
MAX_TEXT_LENGTH = 80

#: What a packet on a given port means, in words.
PORTNUM_MESSAGES: dict[str, str] = {
    PORTNUM_NAMES[PORTNUM_ALERT_APP]: "raised an alert",
    PORTNUM_NAMES[PORTNUM_DETECTION_SENSOR_APP]: "reported a detection",
    PORTNUM_NAMES[PORTNUM_MAP_REPORT_APP]: "sent a map report",
    PORTNUM_NAMES[PORTNUM_NEIGHBORINFO_APP]: "reported its neighbours",
    PORTNUM_NAMES[PORTNUM_NODEINFO_APP]: "announced itself",
    PORTNUM_NAMES[PORTNUM_PAXCOUNTER_APP]: "reported a device count",
    PORTNUM_NAMES[PORTNUM_POSITION_APP]: "reported its position",
    PORTNUM_NAMES[PORTNUM_ROUTING_APP]: "acknowledged a packet",
    PORTNUM_NAMES[PORTNUM_TELEMETRY_APP]: "reported telemetry",
    PORTNUM_NAMES[PORTNUM_TRACEROUTE_APP]: "answered a traceroute",
    PORTNUM_NAMES[PORTNUM_UNKNOWN_APP]: "sent a packet this channel cannot decrypt",
    PORTNUM_NAMES[PORTNUM_WAYPOINT_APP]: "shared a waypoint",
}

ICON_MESSAGE = "mdi:message-text"
ICON_PACKET = "mdi:radio-tower"


def _node_number(data: Mapping[str, Any]) -> int | None:
    """Return the node number the event came from, however it is spelled."""
    for key in (ATTR_FROM_NUM, ATTR_NODE_NUM):
        if isinstance(value := data.get(key), int):
            return value
    for key in (ATTR_FROM_ID, ATTR_NODE_ID):
        if isinstance(value := data.get(key), str):
            try:
                return parse_node_id(value)
            except ValueError:
                continue
    return None


def _device_identifier(data: Mapping[str, Any]) -> str | None:
    """Return the device-registry identifier of the node behind an event."""
    gateway_id = data.get(ATTR_GATEWAY_ID)
    node_num = _node_number(data)
    if not isinstance(gateway_id, str) or node_num is None:
        return None
    try:
        gateway_num = parse_node_id(gateway_id)
    except ValueError:
        return None
    # The gateway is a device in its own right, not a sub-device of itself.
    if gateway_num == node_num:
        return gateway_device_id(gateway_num)
    return node_device_id(gateway_num, node_num)


def _fallback_name(data: Mapping[str, Any]) -> str:
    """Return the best name available without the device registry."""
    for key in (ATTR_FROM_ID, ATTR_NODE_ID):
        if isinstance(value := data.get(key), str) and value:
            return value
    if (node_num := _node_number(data)) is not None:
        return format_node_id(node_num)
    return "Meshtastic"


def _where(data: Mapping[str, Any]) -> str:
    """Return how a text message was addressed."""
    to_num = data.get(ATTR_TO_NUM)
    if isinstance(to_num, int) and to_num != BROADCAST_NUM:
        return "as a direct message"
    channel = data.get(ATTR_CHANNEL)
    return f"on channel {channel}" if isinstance(channel, int) else "to everyone"


def _message(data: Mapping[str, Any]) -> tuple[str, str]:
    """Return the logbook message and icon for one event."""
    text = data.get(ATTR_TEXT)
    if isinstance(text, str) and text:
        if len(text) > MAX_TEXT_LENGTH:
            text = f"{text[: MAX_TEXT_LENGTH - 1]}…"
        return f'sent "{text}" {_where(data)}', ICON_MESSAGE

    portnum = data.get(ATTR_PORTNUM)
    if isinstance(portnum, str) and (described := PORTNUM_MESSAGES.get(portnum)):
        return described, ICON_PACKET
    event_type = data.get(ATTR_EVENT_TYPE)
    if isinstance(event_type, str) and event_type:
        return f"sent a {event_type.replace('_', ' ')} event", ICON_PACKET
    return "was heard by the mesh", ICON_PACKET


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict[str, str]]], None],
) -> None:
    """Describe logbook events."""
    device_registry = dr.async_get(hass)

    @callback
    def _device_name(data: Mapping[str, Any]) -> str | None:
        """Return the name the device registry has for the node, if any.

        The identifier is already scoped to the gateway, and a gateway is a
        config entry's unique id, so at most one device can ever match.
        """
        if (identifier := _device_identifier(data)) is None:
            return None
        for device in device_registry.async_get_devices(
            identifiers={(DOMAIN, identifier)}
        ):
            return device.name_by_user or device.name
        return None

    @callback
    def async_describe_meshtastic_event(event: Event) -> dict[str, str]:
        """Describe one meshtastic_event bus event."""
        data = event.data
        name = _device_name(data) or _fallback_name(data)

        message, icon = _message(data)
        if data.get(ATTR_VIA_MQTT):
            message = f"{message}, via MQTT"

        return {
            LOGBOOK_ENTRY_NAME: name,
            LOGBOOK_ENTRY_MESSAGE: message,
            LOGBOOK_ENTRY_ICON: icon,
        }

    async_describe_event(DOMAIN, EVENT_MESHTASTIC, async_describe_meshtastic_event)
