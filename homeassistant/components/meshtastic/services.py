"""Actions for the Meshtastic integration.

Everything here is registered from ``async_setup`` so that an automation that
calls one of these actions still validates while no config entry is loaded.

An action exists only where an entity cannot do the job.  Sending a message,
tracing a route and reading the configuration all take parameters or answer
with a payload, and the two node-database operations are maintenance rather
than state.  Everything else the mesh can be asked for is an entity -- the node
request buttons, the favourite and ignored switches and the gateway's restart
button -- so every operation has exactly one implementation and one
authorisation model.  Node settings are configuration entities, and there is
deliberately no generic "send an admin message" escape hatch.

``refresh_nodes``, ``remove_node`` and ``export_config`` are administrator-only:
the first two disturb or change the gateway, and the export answers with the
node's whole configuration, which lands in the trace of every automation that
captures the response.

Three rules shape every handler below:

* No module here imports the ``meshtastic`` library.  Sends go through the
  client, which owns the executor, the send lock and the per-portnum pacing
  gates that keep us outside the firmware's client-side rate limits (2 s for
  text, 10 s for position and telemetry, 30 s for traceroute).  The handlers
  that need the interface itself -- the traceroute's send and the configuration
  read -- are handed it by the client, in that executor and behind that lock.
* Everything is validated before anything goes on the air, and every failure
  carries a ``translation_key``: ``ServiceValidationError`` when the user can
  fix it, ``HomeAssistantError`` when the mesh refused or never answered.
  :func:`~.client.raise_for_result` is the only thing that turns a failed
  request into an error, which is what maps every ``Routing.Error`` value onto
  its own translated message.
* Nothing secret leaves in a response.  ``export_config`` redacts the node's
  credentials and never exports the channel URL, whose payload is the
  pre-shared key of every channel.
"""

import base64
import math
import time
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
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    service,
)
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.json import JsonValueType

from .client import MeshtasticRequestError, raise_for_result
from .config_entity import async_send_admin
from .const import (
    ATTR_CHANNEL,
    BROADCAST_ID,
    BROADCAST_NUM,
    CONF_INCLUDE_LOCATION,
    DEFAULT_INCLUDE_LOCATION,
    DOMAIN,
    LOGGER,
    PORTNUM_TRACEROUTE_APP,
    PORTNUM_UNKNOWN_APP,
    format_node_id,
    parse_node_id,
)
from .coordinator import MeshtasticConfigEntry
from .models import RequestKind, RequestResult

SERVICE_EXPORT_CONFIG: Final = "export_config"
SERVICE_REFRESH_NODES: Final = "refresh_nodes"
SERVICE_REMOVE_NODE: Final = "remove_node"
SERVICE_REQUEST_TRACEROUTE: Final = "request_traceroute"
SERVICE_SEND_MESSAGE: Final = "send_message"

ATTR_CONFIRM: Final = "confirm"
ATTR_MESSAGE: Final = "message"
ATTR_NODE: Final = "node"
ATTR_WANT_ACK: Final = "want_ack"

#: Traceroute SNR travels as ``int8`` decibels times four, with ``INT8_MIN``
#: meaning "not measured".
SNR_SCALE: Final = 4.0
SNR_UNKNOWN: Final = -128

#: A node-database refresh restarts the firmware's phone-API state machine, and
#: for as long as it streams, the node's eight-slot to-phone queue drops the
#: packets it receives.  Once a minute per entry is more than a person watching
#: for a node ever needs, and it stops an automation from turning the gateway
#: deaf by asking on a short interval.
REFRESH_NODES_SPACING: Final = 60.0
_REFRESH_NODES_GATE: HassKey[dict[str, float]] = HassKey(f"{DOMAIN}_refresh_nodes")

#: Field names the export replaces with :data:`REDACTED`, wherever they appear
#: and however deeply nested: the node's own credentials and the keys that would
#: let whoever reads the response take it over.  ``security.public_key`` is not
#: one of them -- it is what identifies the node and is meant to be shared.
REDACTED_CONFIG_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "admin_key",
        "fixed_pin",
        "password",
        "private_key",
        "psk",
        "username",
        "wifi_psk",
    }
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

SERVICE_SEND_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_MESSAGE): vol.All(cv.string, vol.Length(min=1)),
        vol.Optional(ATTR_NODE): _destination,
        vol.Optional(ATTR_CHANNEL): vol.All(vol.Coerce(int), vol.Range(min=0, max=7)),
        vol.Optional(ATTR_WANT_ACK, default=True): cv.boolean,
    }
)

SERVICE_REQUEST_TRACEROUTE_SCHEMA = vol.Schema(dict(_NODE_FIELDS))

SERVICE_REFRESH_NODES_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string}
)

SERVICE_EXPORT_CONFIG_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string}
)

SERVICE_REMOVE_NODE_SCHEMA = vol.Schema(
    {**_NODE_FIELDS, vol.Required(ATTR_CONFIRM): cv.boolean}
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


def _snr_list(values: tuple[int, ...]) -> list[JsonValueType]:
    """Return traceroute SNRs in decibels, with unmeasured hops as null."""
    return [
        None if value == SNR_UNKNOWN else round(value / SNR_SCALE, 2)
        for value in values
    ]


def _route_list(
    relays: tuple[int, ...], *, first: int, last: int
) -> list[JsonValueType]:
    """Return a whole traceroute leg, endpoints included, as node ids."""
    return [format_node_id(hop) for hop in (first, *relays, last)]


async def _async_request_traceroute(call: ServiceCall) -> ServiceResponse:
    """Trace the path to one node and back, with the SNR of every hop.

    The library offers the route through ``sendData(onResponse=...)``, a
    one-shot callback it files under the packet id and - by its own standing
    ``FIXME`` - only ever removes when it fires.  An answer that never came
    would leave the entry and everything its closure holds in the interface
    for the life of the connection, one per attempt.  It also runs on the
    reader thread, which nothing else in this integration does.  The answer is
    an ordinary packet on the traceroute port quoting our request id, so the
    client correlates it from pubsub like every other response and hands it
    back on the result.
    """
    entry, node_num = _async_resolve(call)
    node_num = _async_require_unicast(node_num, SERVICE_REQUEST_TRACEROUTE)
    coordinator = entry.runtime_data.coordinator
    gateway_num = coordinator.gateway.node_num
    label = _async_label(entry, node_num)

    def _send(interface: Any) -> Any:
        # An empty payload is a valid empty RouteDiscovery; the firmware fills
        # it in on the way and sends it back because the packet asks for a
        # response.
        return interface.sendData(
            b"",
            destinationId=node_num,
            portNum=PORTNUM_TRACEROUTE_APP,
            wantAck=True,
            wantResponse=True,
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
    route = None if result.response is None else result.response.traceroute
    if route is None:
        raise MeshtasticRequestError(
            translation_domain=DOMAIN,
            translation_key="no_response",
            translation_placeholders={"node": label},
        )
    if call.return_response:
        return {
            "node_id": format_node_id(node_num),
            "node": label,
            "route_towards": _route_list(route.route, first=gateway_num, last=node_num),
            "snr_towards": _snr_list(route.snr_towards),
            "route_back": _route_list(
                route.route_back, first=node_num, last=gateway_num
            ),
            "snr_back": _snr_list(route.snr_back),
        }
    return None


# ---------------------------------------------------------------------------
# Node database
# ---------------------------------------------------------------------------


async def _async_refresh_nodes(call: ServiceCall) -> None:
    """Ask the gateway to stream its node database again.

    The dump is the one operation a user can trigger that makes the firmware
    leave its packet-forwarding state, so it is paced per config entry and
    refused while the previous one is still recent.
    """
    entry: MeshtasticConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data.get(ATTR_CONFIG_ENTRY_ID)
    )
    gate = call.hass.data.setdefault(_REFRESH_NODES_GATE, {})
    now = time.monotonic()
    if now < (ready_at := gate.get(entry.entry_id, 0.0)):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="refresh_too_soon",
            translation_placeholders={"seconds": str(math.ceil(ready_at - now))},
        )
    gate[entry.entry_id] = now + REFRESH_NODES_SPACING

    client = entry.runtime_data.client
    if not client.download_node_db:
        # The option is off by default because a node without PSRAM can run out
        # of memory over a full dump.  The action is the user asking for that
        # dump anyway, so it runs -- but a crash right afterwards should be
        # explainable from the log.
        LOGGER.warning(
            "Refreshing the node database of %s although this entry has the"
            " node database download switched off: this is the same full dump,"
            " and a memory-constrained node can fail over it",
            entry.runtime_data.coordinator.gateway.name,
        )
    try:
        await client.async_refresh_nodes()
    except HomeAssistantError:
        # Nothing reached the node, so the next attempt need not sit out the
        # pause that is there to spare the node.
        gate.pop(entry.entry_id, None)
        raise


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


def _proto_dict(message: Any) -> dict[str, Any]:
    """Return the fields a protobuf message actually set, as a plain dict.

    ``ListFields`` skips defaults, which is what the CLI's ``--export-config``
    does too, and keeps the response to what the node really carries.  Keys are
    the protobuf field names, and a field named in
    :data:`REDACTED_CONFIG_FIELDS` is replaced at whatever depth it appears.
    """
    result: dict[str, Any] = {}
    for descriptor, value in message.ListFields():
        if descriptor.name in REDACTED_CONFIG_FIELDS:
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
        descriptor.name: _proto_dict(value)
        for descriptor, value in message.ListFields()
        if descriptor.type == descriptor.TYPE_MESSAGE
    }


async def _async_export_config(call: ServiceCall) -> ServiceResponse:
    """Return the gateway's configuration, in the shape the CLI exports it.

    Nothing is transmitted: the library downloaded the whole configuration when
    it connected, so this only reads back what it already holds.  The canned
    messages and the ringtone the CLI also exports are left out on purpose --
    the library only offers those through a helper that busy-waits on the reader
    thread with no timeout.

    The response is not a backup, and it is deliberately incomplete.  Every
    credential in it is redacted, and the channel URL the CLI prints is not part
    of it at all: that URL's payload is the pre-shared key of every channel, so
    whoever reads one can decrypt the mesh and transmit on it.  The gateway's
    own coordinates follow the same opt-in as the diagnostics download, because
    a response is kept in the trace of whatever asked for it.
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
        "config": export.get("config", {}),
        "module_config": export.get("module_config", {}),
    }
    position = response["config"].get("position", {})
    node = coordinator.get_node(gateway.node_id)
    if (
        entry.options.get(CONF_INCLUDE_LOCATION, DEFAULT_INCLUDE_LOCATION)
        and position.get("fixed_position")
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
        SERVICE_REQUEST_TRACEROUTE,
        _async_request_traceroute,
        schema=SERVICE_REQUEST_TRACEROUTE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    # Administrator-only, for three different reasons: the refresh makes the
    # gateway restart its node-info stream and drop packets while it runs,
    # removing a node changes the node database, and the export answers with
    # the whole configuration of the node.  The one that cannot be undone also
    # wants an explicit confirmation.
    service.async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_REFRESH_NODES,
        _async_refresh_nodes,
        schema=SERVICE_REFRESH_NODES_SCHEMA,
    )
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
        SERVICE_EXPORT_CONFIG,
        _async_export_config,
        schema=SERVICE_EXPORT_CONFIG_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
