"""Actions for the Meshtastic integration.

Everything here is registered from ``async_setup`` so that an automation that
calls one of these actions still validates while no config entry is loaded.

The actions cover the mesh operations that are not a *state* and therefore have
no entity: sending one message, asking a node for something it already knows,
and the node-database writes.  Node settings are configuration entities, not
actions, and there is deliberately no generic "send an admin message" escape
hatch.

Two rules shape every handler below:

* Nothing here talks to the ``meshtastic`` library.  Sends go through the
  client, which owns the executor, the send lock and the per-portnum pacing
  gates that keep us outside the firmware's client-side rate limits (2 s for
  text, 10 s for position and telemetry, 30 s for traceroute).
* Everything is validated before anything goes on the air, and every failure
  carries a ``translation_key``: ``ServiceValidationError`` when the user can
  fix it, ``HomeAssistantError`` when the mesh refused or never answered.
  :func:`~.client.raise_for_result` is the only thing that turns a failed
  request into an error, which is what maps every ``Routing.Error`` value onto
  its own translated message.
"""

import base64
from collections.abc import Mapping
from typing import Any, Final

import voluptuous as vol

from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    service,
)
from homeassistant.util.json import JsonValueType

from .client import MeshtasticRequestError, raise_for_result
from .config_entity import async_send_admin
from .const import (
    ATTR_CHANNEL,
    BROADCAST_ID,
    BROADCAST_NUM,
    DOMAIN,
    LOGGER,
    PORTNUM_POSITION_APP,
    PORTNUM_TELEMETRY_APP,
    PORTNUM_TRACEROUTE_APP,
    PORTNUM_UNKNOWN_APP,
    format_node_id,
    parse_node_id,
)
from .coordinator import MeshtasticConfigEntry
from .models import RequestKind, RequestResult, TelemetryFamily

SERVICE_EXPORT_CONFIG: Final = "export_config"
SERVICE_REBOOT: Final = "reboot"
SERVICE_REFRESH_NODES: Final = "refresh_nodes"
SERVICE_REMOVE_NODE: Final = "remove_node"
SERVICE_REQUEST_POSITION: Final = "request_position"
SERVICE_REQUEST_TELEMETRY: Final = "request_telemetry"
SERVICE_REQUEST_TRACEROUTE: Final = "request_traceroute"
SERVICE_SEND_MESSAGE: Final = "send_message"
SERVICE_SET_FAVORITE: Final = "set_favorite"
SERVICE_SET_IGNORED: Final = "set_ignored"

ATTR_CONFIRM: Final = "confirm"
ATTR_DELAY: Final = "delay"
ATTR_ENABLED: Final = "enabled"
ATTR_MESSAGE: Final = "message"
ATTR_NODE: Final = "node"
ATTR_TELEMETRY_TYPE: Final = "telemetry_type"
ATTR_WANT_ACK: Final = "want_ack"

#: The telemetry families a node answers a request for.  ``health`` and ``host``
#: are left out: the firmware only ever publishes those unsolicited.
TELEMETRY_TYPES: Final[tuple[str, ...]] = (
    str(TelemetryFamily.DEVICE),
    str(TelemetryFamily.ENVIRONMENT),
    str(TelemetryFamily.POWER),
    str(TelemetryFamily.AIR_QUALITY),
    str(TelemetryFamily.LOCAL_STATS),
)

#: Request payloads: a ``Telemetry`` message with the wanted variant present but
#: empty, which is what the firmware looks at to decide what to answer with.
#: Each is the two-byte header of an empty length-delimited field --
#: ``(field_number << 3) | 2`` followed by a zero length.
TELEMETRY_REQUESTS: Final[Mapping[str, bytes]] = {
    str(TelemetryFamily.DEVICE): b"\x12\x00",
    str(TelemetryFamily.ENVIRONMENT): b"\x1a\x00",
    str(TelemetryFamily.AIR_QUALITY): b'"\x00',
    str(TelemetryFamily.POWER): b"*\x00",
    str(TelemetryFamily.LOCAL_STATS): b"2\x00",
}

#: Traceroute SNR travels as ``int8`` decibels times four, with ``INT8_MIN``
#: meaning "not measured".
SNR_SCALE: Final = 4.0
SNR_UNKNOWN: Final = -128

#: ``Node.reboot()`` takes a delay in seconds; the firmware's own default is 10.
DEFAULT_REBOOT_DELAY: Final = 10
MAX_REBOOT_DELAY: Final = 300

#: Only ``security.public_key`` is safe to hand out; the private and admin keys
#: would let whoever reads the response take the node over.
REDACTED_CONFIG_FIELDS: Final[frozenset[tuple[str, str]]] = frozenset(
    {("security", "private_key"), ("security", "admin_key")}
)
REDACTED: Final = "**REDACTED**"


def _destination(value: Any) -> int | str:
    """Validate a destination given as a node id, node number or device id."""
    if isinstance(value, bool):
        raise vol.Invalid("Not a Meshtastic destination")
    if isinstance(value, int):
        return int(vol.Range(min=0, max=BROADCAST_NUM)(value))
    text = cv.string(value).strip()
    if not text:
        raise vol.Invalid("Not a Meshtastic destination")
    if text.isdigit():
        return int(vol.Range(min=0, max=BROADCAST_NUM)(int(text)))
    return text


_NODE_FIELDS = {
    vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
    vol.Required(ATTR_NODE): _destination,
}
_CONFIRM_FIELD = {vol.Required(ATTR_CONFIRM): cv.boolean}

SERVICE_SEND_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_MESSAGE): vol.All(cv.string, vol.Length(min=1)),
        vol.Optional(ATTR_NODE): _destination,
        vol.Optional(ATTR_CHANNEL): vol.All(vol.Coerce(int), vol.Range(min=0, max=7)),
        vol.Optional(ATTR_WANT_ACK, default=True): cv.boolean,
    }
)

SERVICE_REQUEST_TELEMETRY_SCHEMA = vol.Schema(
    {
        **_NODE_FIELDS,
        vol.Optional(ATTR_TELEMETRY_TYPE, default=str(TelemetryFamily.DEVICE)): vol.In(
            TELEMETRY_TYPES
        ),
    }
)

SERVICE_REQUEST_POSITION_SCHEMA = vol.Schema(dict(_NODE_FIELDS))

SERVICE_REQUEST_TRACEROUTE_SCHEMA = vol.Schema(dict(_NODE_FIELDS))

SERVICE_REFRESH_NODES_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string}
)

SERVICE_EXPORT_CONFIG_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string}
)

SERVICE_SET_FAVORITE_SCHEMA = vol.Schema(
    {**_NODE_FIELDS, vol.Optional(ATTR_ENABLED, default=True): cv.boolean}
)

SERVICE_SET_IGNORED_SCHEMA = vol.Schema(
    {**_NODE_FIELDS, vol.Optional(ATTR_ENABLED, default=True): cv.boolean}
)

SERVICE_REMOVE_NODE_SCHEMA = vol.Schema({**_NODE_FIELDS, **_CONFIRM_FIELD})

SERVICE_REBOOT_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Optional(ATTR_DELAY, default=DEFAULT_REBOOT_DELAY): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=MAX_REBOOT_DELAY)
        ),
        **_CONFIRM_FIELD,
    }
)


# ---------------------------------------------------------------------------
# Target resolution
# ---------------------------------------------------------------------------


@callback
def _async_node_num_from_device(device: dr.DeviceEntry) -> int | None:
    """Return the node number a Meshtastic device entry stands for.

    Device identifiers are ``!gateway`` for the gateway and ``!gateway_!node``
    for a mesh node, so the last segment is the node itself either way.
    """
    for domain, identifier in device.identifiers:
        if domain != DOMAIN:
            continue
        try:
            return parse_node_id(identifier.rsplit("_", 1)[-1])
        except ValueError:  # pragma: no cover - we build these identifiers
            continue
    return None


@callback
def _async_resolve(call: ServiceCall) -> tuple[MeshtasticConfigEntry, int | None]:
    """Return the loaded config entry and destination node the call targets.

    The destination may be a ``!xxxxxxxx`` node id, a node number, or the
    Home Assistant device id of a gateway or node device.  A device id also says
    which config entry owns it, so ``config_entry_id`` is only needed when the
    destination is a bare node and more than one entry is set up.  The node is
    ``None`` only when the call did not name one at all.
    """
    hass = call.hass
    raw = call.data.get(ATTR_NODE)
    entry: MeshtasticConfigEntry | None = None
    node_num: int | None = None

    if isinstance(raw, str) and dr.async_get(hass).async_get(raw) is not None:
        device, entry = service.async_get_device_and_config_entry(hass, DOMAIN, raw)
        node_num = _async_node_num_from_device(device)

    entry_id = call.data.get(ATTR_CONFIG_ENTRY_ID)
    if entry is None or entry_id is not None:
        entry = service.async_get_config_entry(hass, DOMAIN, entry_id)

    if node_num is None and raw is not None:
        # Raises ServiceValidationError("unknown_node") for anything that is not
        # a node identifier; the library must never be handed a node name.
        node_num = entry.runtime_data.client.resolve_destination(raw)

    return entry, node_num


@callback
def _async_require_unicast(node_num: int | None, action: str) -> int:
    """Return a destination that is one node rather than the whole mesh."""
    if node_num is None or node_num == BROADCAST_NUM:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="broadcast_not_supported",
            translation_placeholders={"action": action},
        )
    return node_num


@callback
def _async_label(entry: MeshtasticConfigEntry, node_num: int) -> str:
    """Return the friendliest name we know for a node number."""
    if node_num == BROADCAST_NUM:
        return BROADCAST_ID
    node_id = format_node_id(node_num)
    if (node := entry.runtime_data.coordinator.get_node(node_id)) is not None:
        return node.name
    return node_id


@callback
def _async_require_confirmation(call: ServiceCall, action: str) -> None:
    """Refuse a destructive action that was not explicitly confirmed."""
    if not call.data[ATTR_CONFIRM]:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="confirmation_required",
            translation_placeholders={"action": action},
        )


def _delivery(result: RequestResult) -> dict[str, Any]:
    """Return the packet id and delivery verdict of one request."""
    return {
        "packet_id": result.packet_id,
        "state": str(result.state),
        "delivered": result.delivered,
        "destination": (
            BROADCAST_ID
            if result.destination == BROADCAST_NUM
            else format_node_id(result.destination)
        ),
    }


# ---------------------------------------------------------------------------
# Messaging
# ---------------------------------------------------------------------------


async def _async_send_message(call: ServiceCall) -> ServiceResponse:
    """Send one text message to a node, or broadcast it on a channel."""
    entry, node_num = _async_resolve(call)
    coordinator = entry.runtime_data.coordinator
    destination = BROADCAST_NUM if node_num is None else node_num
    channel = call.data.get(ATTR_CHANNEL, 0)

    if channel not in {slot.index for slot in coordinator.gateway.channels}:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_channel",
            translation_placeholders={"node": coordinator.gateway.name},
        )

    result = await coordinator.client.async_send_text(
        call.data[ATTR_MESSAGE],
        destination=destination,
        channel_index=channel,
        want_ack=call.data[ATTR_WANT_ACK],
    )
    raise_for_result(result, node=_async_label(entry, destination))
    if call.return_response:
        return _delivery(result)
    return None


# ---------------------------------------------------------------------------
# On-demand requests
# ---------------------------------------------------------------------------


async def _async_request_telemetry(call: ServiceCall) -> ServiceResponse:
    """Ask one node for a telemetry sample and wait for its answer."""
    entry, node_num = _async_resolve(call)
    node_num = _async_require_unicast(node_num, SERVICE_REQUEST_TELEMETRY)
    label = _async_label(entry, node_num)

    result = await entry.runtime_data.client.async_send_data(
        TELEMETRY_REQUESTS[call.data[ATTR_TELEMETRY_TYPE]],
        portnum=PORTNUM_TELEMETRY_APP,
        destination=node_num,
        kind=RequestKind.DIRECT_REQUEST,
        want_ack=True,
        want_response=True,
    )
    raise_for_result(result, node=label)
    response = result.response
    if response is None or response.telemetry is None:
        raise MeshtasticRequestError(
            translation_domain=DOMAIN,
            translation_key="no_response",
            translation_placeholders={"node": label},
        )
    if call.return_response:
        return {
            "node_id": format_node_id(node_num),
            "node": label,
            "telemetry": response.telemetry.as_dict(),
        }
    return None


async def _async_request_position(call: ServiceCall) -> ServiceResponse:
    """Ask one node for its position and wait for its answer."""
    entry, node_num = _async_resolve(call)
    node_num = _async_require_unicast(node_num, SERVICE_REQUEST_POSITION)
    label = _async_label(entry, node_num)

    # An empty payload is a valid empty Position message; the node answers with
    # its own because the packet asks for a response.
    result = await entry.runtime_data.client.async_send_data(
        b"",
        portnum=PORTNUM_POSITION_APP,
        destination=node_num,
        kind=RequestKind.DIRECT_REQUEST,
        want_ack=True,
        want_response=True,
    )
    raise_for_result(result, node=label)
    response = result.response
    if response is None or response.position is None:
        raise MeshtasticRequestError(
            translation_domain=DOMAIN,
            translation_key="no_response",
            translation_placeholders={"node": label},
        )
    if call.return_response:
        return {
            "node_id": format_node_id(node_num),
            "node": label,
            "position": response.position.as_dict(),
        }
    return None


def _snr_list(values: Any) -> list[JsonValueType]:
    """Return traceroute SNRs in decibels, with unmeasured hops as null."""
    if not isinstance(values, list):
        return []
    return [
        None if value == SNR_UNKNOWN else round(value / SNR_SCALE, 2)
        for value in values
        if isinstance(value, int) and not isinstance(value, bool)
    ]


def _route_list(values: Any, *, first: int, last: int) -> list[JsonValueType]:
    """Return a whole traceroute leg, endpoints included, as node ids."""
    relays = values if isinstance(values, list) else []
    hops = [first, *(hop for hop in relays if isinstance(hop, int)), last]
    return [format_node_id(hop) for hop in hops]


async def _async_request_traceroute(call: ServiceCall) -> ServiceResponse:
    """Trace the path to one node and back, with the SNR of every hop."""
    entry, node_num = _async_resolve(call)
    node_num = _async_require_unicast(node_num, SERVICE_REQUEST_TRACEROUTE)
    coordinator = entry.runtime_data.coordinator
    gateway_num = coordinator.gateway.node_num
    label = _async_label(entry, node_num)

    route: dict[str, Any] = {}

    def _on_traceroute(packet: dict[str, Any]) -> None:
        """Keep the route out of one traceroute answer.

        The library calls this on its reader thread while it decodes the
        packet, which is before it hands the same packet to pubsub and
        therefore before the request being awaited here can complete: the value
        is in place by the time the await returns.  Only plain numbers are
        copied out, so the protobuf the library parks beside them never leaves
        this function.  It must not raise -- an exception here would take the
        reader thread down with it.
        """
        try:
            decoded = packet.get("decoded") or {}
            raw = decoded.get("traceroute")
            if isinstance(raw, dict):
                route.update(
                    {
                        key: raw.get(key)
                        for key in ("route", "snrTowards", "routeBack", "snrBack")
                    }
                )
        except (AttributeError, TypeError) as err:  # pragma: no cover - defensive
            LOGGER.debug("Could not read the traceroute answer: %s", err)

    def _send(interface: Any) -> Any:
        # An empty payload is a valid empty RouteDiscovery.  The route itself is
        # only offered through this callback, which is why the request does not
        # go through the client's own send helper.  The library drops the
        # handler again as soon as it fires, and one belonging to an answer that
        # never came goes away with the interface on the next reconnect.
        return interface.sendData(
            b"",
            destinationId=node_num,
            portNum=PORTNUM_TRACEROUTE_APP,
            wantAck=True,
            wantResponse=True,
            onResponse=_on_traceroute,
            channelIndex=0,
        )

    result = await entry.runtime_data.client.async_request(
        kind=RequestKind.TRACEROUTE,
        portnum=PORTNUM_TRACEROUTE_APP,
        destination=node_num,
        send=_send,
        want_ack=True,
        want_response=True,
    )
    raise_for_result(result, node=label)
    if not route:
        raise MeshtasticRequestError(
            translation_domain=DOMAIN,
            translation_key="no_response",
            translation_placeholders={"node": label},
        )
    if call.return_response:
        return {
            "node_id": format_node_id(node_num),
            "node": label,
            "route_towards": _route_list(
                route.get("route"), first=gateway_num, last=node_num
            ),
            "snr_towards": _snr_list(route.get("snrTowards")),
            "route_back": _route_list(
                route.get("routeBack"), first=node_num, last=gateway_num
            ),
            "snr_back": _snr_list(route.get("snrBack")),
        }
    return None


# ---------------------------------------------------------------------------
# Node database
# ---------------------------------------------------------------------------


async def _async_refresh_nodes(call: ServiceCall) -> None:
    """Ask the gateway to stream its node database again."""
    entry: MeshtasticConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data.get(ATTR_CONFIG_ENTRY_ID)
    )
    await entry.runtime_data.client.async_refresh_nodes()


async def _async_set_flag(call: ServiceCall, *, set_to: str, clear_to: str) -> None:
    """Set or clear one per-node flag in the gateway's node database."""
    entry, node_num = _async_resolve(call)
    node_num = _async_require_unicast(node_num, call.service)
    method = set_to if call.data[ATTR_ENABLED] else clear_to

    def _send(interface: Any) -> Any:
        return getattr(interface.localNode, method)(node_num)

    await async_send_admin(entry.runtime_data.coordinator, _send)


async def _async_set_favorite(call: ServiceCall) -> None:
    """Mark a node as a favourite, or stop doing so."""
    await _async_set_flag(call, set_to="setFavorite", clear_to="removeFavorite")


async def _async_set_ignored(call: ServiceCall) -> None:
    """Drop every packet from a node, or stop doing so."""
    await _async_set_flag(call, set_to="setIgnored", clear_to="removeIgnored")


async def _async_remove_node(call: ServiceCall) -> None:
    """Delete one node from the gateway's node database."""
    _async_require_confirmation(call, SERVICE_REMOVE_NODE)
    entry, node_num = _async_resolve(call)
    node_num = _async_require_unicast(node_num, SERVICE_REMOVE_NODE)
    gateway = entry.runtime_data.coordinator.gateway
    if node_num == gateway.node_num:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="cannot_remove_gateway",
            translation_placeholders={"node": gateway.name},
        )

    def _send(interface: Any) -> Any:
        return interface.localNode.removeNode(node_num)

    await async_send_admin(entry.runtime_data.coordinator, _send)


async def _async_reboot(call: ServiceCall) -> None:
    """Reboot the gateway node."""
    _async_require_confirmation(call, SERVICE_REBOOT)
    entry: MeshtasticConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data.get(ATTR_CONFIG_ENTRY_ID)
    )
    client = entry.runtime_data.client
    gateway = entry.runtime_data.coordinator.gateway
    if client.reboot_grace_active:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="reboot_in_progress",
            translation_placeholders={"node": gateway.name},
        )
    delay = call.data[ATTR_DELAY]

    def _send(interface: Any) -> Any:
        return interface.localNode.reboot(delay)

    await async_send_admin(entry.runtime_data.coordinator, _send)
    # The acknowledgement means the reboot is scheduled, not done: the node
    # keeps talking for a few more seconds and then drops off without closing
    # the socket, so hold the entities available across the gap.
    client.async_note_reboot_expected()


# ---------------------------------------------------------------------------
# Configuration export
# ---------------------------------------------------------------------------


def _proto_scalar(descriptor: Any, value: Any) -> Any:
    """Return one protobuf value as something JSON can carry."""
    if descriptor.type == descriptor.TYPE_MESSAGE:
        return _proto_dict(value)
    if descriptor.type == descriptor.TYPE_ENUM:
        member = descriptor.enum_type.values_by_number.get(value)
        return value if member is None else member.name
    if descriptor.type == descriptor.TYPE_BYTES:
        return base64.b64encode(value).decode()
    return value


def _proto_dict(message: Any, *, section: str | None = None) -> dict[str, Any]:
    """Return the fields a protobuf message actually set, as a plain dict.

    ``ListFields`` skips defaults, which is what the CLI's ``--export-config``
    does too, and keeps the response to what the node really carries.  Keys are
    the protobuf field names.
    """
    result: dict[str, Any] = {}
    for descriptor, value in message.ListFields():
        if section is not None and (section, descriptor.name) in REDACTED_CONFIG_FIELDS:
            result[descriptor.name] = REDACTED
        elif descriptor.is_repeated:
            result[descriptor.name] = [
                _proto_scalar(descriptor, item) for item in value
            ]
        else:
            result[descriptor.name] = _proto_scalar(descriptor, value)
    return result


def _proto_sections(message: Any) -> dict[str, Any]:
    """Return a ``LocalConfig``/``LocalModuleConfig`` as one dict per section."""
    if message is None:
        return {}
    return {
        descriptor.name: _proto_dict(value, section=descriptor.name)
        for descriptor, value in message.ListFields()
        if descriptor.type == descriptor.TYPE_MESSAGE
    }


async def _async_export_config(call: ServiceCall) -> ServiceResponse:
    """Return the gateway's configuration, in the shape the CLI exports.

    Nothing is transmitted: the library downloaded the whole configuration when
    it connected, so this only reads back what it already holds.  The canned
    messages and the ringtone the CLI also exports are left out on purpose --
    the library only offers those through a helper that busy-waits on the reader
    thread with no timeout.
    """
    entry: MeshtasticConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data.get(ATTR_CONFIG_ENTRY_ID)
    )
    coordinator = entry.runtime_data.coordinator
    gateway = coordinator.gateway
    export: dict[str, Any] = {}

    def _read(interface: Any) -> None:
        local_node = getattr(interface, "localNode", None)
        local_config = getattr(local_node, "localConfig", None)
        if local_config is None:
            raise MeshtasticRequestError(
                translation_domain=DOMAIN, translation_key="no_config"
            )
        export["config"] = _proto_sections(local_config)
        export["module_config"] = _proto_sections(
            getattr(local_node, "moduleConfig", None)
        )
        if (get_url := getattr(local_node, "getURL", None)) is not None:
            export["channel_url"] = get_url()

    await coordinator.client.async_request(
        kind=RequestKind.ADMIN_LOCAL_GET,
        # Nothing goes on the air, so no port owes the firmware any pacing; the
        # unknown port is the one with no send spacing.
        portnum=PORTNUM_UNKNOWN_APP,
        destination=gateway.node_num,
        send=_read,
        want_ack=False,
    )

    response: dict[str, Any] = {
        "owner": gateway.long_name,
        "owner_short": gateway.short_name,
        "channel_url": export.get("channel_url"),
        "config": export.get("config", {}),
        "module_config": export.get("module_config", {}),
    }
    position = response["config"].get("position", {})
    node = coordinator.get_node(gateway.node_id)
    if (
        position.get("fixed_position")
        and node is not None
        and node.position is not None
        and node.position.valid
    ):
        response["location"] = {
            "latitude": node.position.latitude,
            "longitude": node.position.longitude,
            "altitude": node.position.altitude,
        }
    return response


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Meshtastic actions."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        _async_send_message,
        schema=SERVICE_SEND_MESSAGE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REQUEST_TELEMETRY,
        _async_request_telemetry,
        schema=SERVICE_REQUEST_TELEMETRY_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REQUEST_POSITION,
        _async_request_position,
        schema=SERVICE_REQUEST_POSITION_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REQUEST_TRACEROUTE,
        _async_request_traceroute,
        schema=SERVICE_REQUEST_TRACEROUTE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_NODES,
        _async_refresh_nodes,
        schema=SERVICE_REFRESH_NODES_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_EXPORT_CONFIG,
        _async_export_config,
        schema=SERVICE_EXPORT_CONFIG_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_FAVORITE,
        _async_set_favorite,
        schema=SERVICE_SET_FAVORITE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_IGNORED,
        _async_set_ignored,
        schema=SERVICE_SET_IGNORED_SCHEMA,
    )
    # Removing a node and rebooting the radio are destructive, so they are
    # offered to administrators only, on top of the explicit confirmation field.
    service.async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_REMOVE_NODE,
        _async_remove_node,
        schema=SERVICE_REMOVE_NODE_SCHEMA,
    )
    service.async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_REBOOT,
        _async_reboot,
        schema=SERVICE_REBOOT_SCHEMA,
    )
