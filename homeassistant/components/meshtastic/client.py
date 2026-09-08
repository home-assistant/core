"""Meshtastic radio client.

This is the only module in the integration that imports or touches the
``meshtastic`` library.  Everything it hands out is one of the frozen models in
:mod:`.models`.

Rules this module keeps, and that the rest of the integration relies on:

* Every library call runs in the executor, behind one asyncio lock per client,
  with a bounded timeout and a guard that turns a stray ``SystemExit`` (the
  library uses ``sys.exit()`` for input validation) into a
  :class:`MeshtasticError`.
* Only the library's public API is used.  None of the blocking helpers that can
  call ``our_exit()`` on the reader thread are ever called: no
  ``waitForAckNak``, ``sendTelemetry``, ``sendPosition(wantResponse=True)``,
  ``sendTraceRoute``, ``getNode`` for remote nodes.  Answers are correlated from
  pubsub by ``decoded.requestId`` instead.
* pubsub listeners are bound methods, filter on interface identity, never raise
  and do nothing but hop to the event loop with ``call_soon_threadsafe``.
* Reconnection is owned here: jittered exponential backoff, a circuit breaker
  for the firmware's "one API client at a time" kick, and a reboot grace window.
"""

import asyncio
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import functools
import random
import time
from typing import Any, Final

from meshtastic.mesh_interface import MeshInterface
from meshtastic.protobuf import mesh_pb2
from meshtastic.tcp_interface import TCPInterface
from pubsub import pub

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from .const import (
    BACKLOG_CONNECT_WINDOW,
    BACKLOG_MAX_AGE,
    BROADCAST_ID,
    BROADCAST_NUM,
    CIRCUIT_BREAKER_COOLDOWN,
    CIRCUIT_BREAKER_TRIPS,
    CLOSE_TIMEOUT,
    CONNECT_TIMEOUT,
    CONNECTION_STABLE_AFTER,
    DEFAULT_ERROR_TRANSLATION_KEY,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_SEND_SPACING,
    DOMAIN,
    EXECUTOR_JOB_TIMEOUT,
    FAST_PROBE_INTERVAL,
    HEARTBEAT_INTERVAL,
    HEARTBEAT_RESPONSE_TIMEOUT,
    LIBRARY_TIMEOUT,
    LIVENESS_TIMEOUT,
    LOGGER,
    MAX_DIRECT_TEXT_PAYLOAD_BYTES,
    MAX_MISSED_HEARTBEATS,
    MAX_SEND_GATE_WAIT,
    MAX_TEXT_PAYLOAD_BYTES,
    NOTIFICATION_REJECTED,
    PORTNUM_TEXT_MESSAGE_APP,
    REBOOT_GRACE,
    RECONNECT_BACKOFF_FACTOR,
    RECONNECT_MAX_DELAY,
    RECONNECT_MAX_INITIAL_DELAY,
    RECONNECT_MIN_DELAY,
    REQUEST_TIMEOUTS,
    ROUTING_ERROR_NONE,
    ROUTING_ERROR_TRANSLATION_KEYS,
    ROUTING_ERROR_VALIDATION,
    SEND_SPACING,
    TIMEOUT_TRANSLATION_KEYS,
    format_node_id,
    parse_node_id,
)
from .models import (
    ConnectionState,
    GatewayInfo,
    MeshtasticChannel,
    MeshtasticNode,
    MeshtasticNotification,
    MeshtasticPacket,
    NodeUser,
    Position,
    PositionSource,
    RequestKind,
    RequestResult,
    RequestState,
    TelemetryFamily,
    TelemetrySample,
    TelemetryValue,
)

# pubsub topics published by meshtastic 2.7.11.
TOPIC_CONNECTION_ESTABLISHED: Final = "meshtastic.connection.established"
TOPIC_CONNECTION_LOST: Final = "meshtastic.connection.lost"
TOPIC_RECEIVE: Final = "meshtastic.receive"
TOPIC_NODE_UPDATED: Final = "meshtastic.node.updated"
TOPIC_CLIENT_NOTIFICATION: Final = "meshtastic.clientNotification"

#: ``PhoneAPI.h`` ``SPECIAL_NONCE_ONLY_NODES``.  A ``want_config_id`` with this
#: value makes the firmware stream only its node database and then return to
#: normal packet flow, skipping the channels, config and file-manifest phases
#: of a full handshake.  The library does not expose it.
NODES_ONLY_WANT_CONFIG_ID: Final = 69421

_TERMINAL_STATES: Final = frozenset(
    {RequestState.RESPONDED, RequestState.NACKED, RequestState.TIMED_OUT}
)
_ORPHAN_LIMIT: Final = 64

#: camelCase telemetry oneof names as they appear in packet dicts.
_TELEMETRY_FAMILIES: Final[dict[str, TelemetryFamily]] = {
    "deviceMetrics": TelemetryFamily.DEVICE,
    "environmentMetrics": TelemetryFamily.ENVIRONMENT,
    "airQualityMetrics": TelemetryFamily.AIR_QUALITY,
    "powerMetrics": TelemetryFamily.POWER,
    "localStats": TelemetryFamily.LOCAL_STATS,
    "healthMetrics": TelemetryFamily.HEALTH,
    "hostMetrics": TelemetryFamily.HOST,
}


class MeshtasticError(HomeAssistantError):
    """Base error raised by the Meshtastic client."""


class MeshtasticConnectionError(MeshtasticError):
    """The radio link is down, or could not be established."""


class MeshtasticRequestError(MeshtasticError):
    """A request was sent but the mesh refused it or never answered."""


# ---------------------------------------------------------------------------
# Conversion helpers: library dict -> models
# ---------------------------------------------------------------------------


def _snake(name: str) -> str:
    """Convert a protobuf camelCase dict key to snake_case."""
    out: list[str] = []
    for index, char in enumerate(name):
        if char.isupper():
            if index:
                out.append("_")
            out.append(char.lower())
        else:
            out.append(char)
    return "".join(out)


def _json_safe(value: Any) -> TelemetryValue | None:
    """Return the value when it is safe to publish, otherwise None."""
    if isinstance(value, bool | int | float | str):
        return value
    return None


def _int(value: Any) -> int | None:
    """Coerce to int or None."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except TypeError, ValueError:
        return None


def _float(value: Any) -> float | None:
    """Coerce to float or None."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except TypeError, ValueError:
        return None


def parse_user(raw: dict[str, Any]) -> NodeUser | None:
    """Build a :class:`NodeUser` from a library ``user`` dict."""
    node_id = raw.get("id")
    if not isinstance(node_id, str):
        return None
    public_key = raw.get("publicKey")
    return NodeUser(
        node_id=node_id,
        long_name=raw.get("longName") or None,
        short_name=raw.get("shortName") or None,
        hardware_model=raw.get("hwModel")
        if isinstance(raw.get("hwModel"), str)
        else None,
        role=raw.get("role") if isinstance(raw.get("role"), str) else None,
        is_licensed=bool(raw.get("isLicensed", False)),
        is_unmessagable=raw.get("isUnmessagable"),
        has_public_key=bool(public_key),
    )


def parse_position(
    raw: dict[str, Any],
    *,
    now: datetime,
    source: PositionSource = PositionSource.PACKET,
) -> Position | None:
    """Build a :class:`Position` from a library ``position`` dict."""
    latitude = _float(raw.get("latitude"))
    longitude = _float(raw.get("longitude"))
    if latitude is None and (latitude_i := _int(raw.get("latitudeI"))) is not None:
        latitude = latitude_i * 1e-7
    if longitude is None and (longitude_i := _int(raw.get("longitudeI"))) is not None:
        longitude = longitude_i * 1e-7
    if latitude is None or longitude is None:
        return None
    return Position(
        latitude=latitude,
        longitude=longitude,
        altitude=_int(raw.get("altitude")),
        precision_bits=_int(raw.get("precisionBits")),
        location_source=(
            raw.get("locationSource")
            if isinstance(raw.get("locationSource"), str)
            else None
        ),
        sats_in_view=_int(raw.get("satsInView")),
        ground_speed=_int(raw.get("groundSpeed")),
        ground_track=_float(raw.get("groundTrack")),
        device_time=_int(raw.get("time")),
        reported_at=now,
        source=source,
    )


def parse_telemetry(raw: dict[str, Any], *, now: datetime) -> TelemetrySample | None:
    """Build a :class:`TelemetrySample` from a library ``telemetry`` dict."""
    for key, family in _TELEMETRY_FAMILIES.items():
        metrics = raw.get(key)
        if not isinstance(metrics, dict):
            continue
        values: dict[str, TelemetryValue] = {}
        for name, value in metrics.items():
            if name == "raw":
                continue
            if (safe := _json_safe(value)) is not None:
                values[_snake(name)] = safe
        return TelemetrySample(
            family=family,
            values=values,
            device_time=_int(raw.get("time")),
            reported_at=now,
        )
    return None


def parse_packet(
    raw: dict[str, Any], *, now: datetime, backlog: bool = False
) -> MeshtasticPacket | None:
    """Build a :class:`MeshtasticPacket` from a library packet dict.

    Returns ``None`` when the dict is not a packet we can make sense of.  The
    protobuf ``raw`` members and the ``payload`` bytes are dropped here and
    never leave this module.
    """
    from_num = _int(raw.get("from"))
    if from_num is None:
        return None
    decoded = raw.get("decoded")
    decoded = decoded if isinstance(decoded, dict) else {}
    portnum = decoded.get("portnum")
    routing = decoded.get("routing")
    routing_error: str | None = None
    if isinstance(routing, dict):
        routing_error = routing.get("errorReason") or ROUTING_ERROR_NONE
    user_raw = decoded.get("user")
    position_raw = decoded.get("position")
    telemetry_raw = decoded.get("telemetry")
    return MeshtasticPacket(
        packet_id=_int(raw.get("id")) or 0,
        from_num=from_num,
        from_id=raw.get("fromId") if isinstance(raw.get("fromId"), str) else None,
        to_num=_int(raw.get("to")) or 0,
        to_id=raw.get("toId") if isinstance(raw.get("toId"), str) else None,
        portnum=portnum if isinstance(portnum, str) else "UNKNOWN_APP",
        channel=_int(raw.get("channel")) or 0,
        want_ack=bool(raw.get("wantAck", False)),
        via_mqtt=bool(raw.get("viaMqtt", False)),
        priority=raw.get("priority") if isinstance(raw.get("priority"), str) else None,
        hop_limit=_int(raw.get("hopLimit")),
        hop_start=_int(raw.get("hopStart")),
        rx_time=_int(raw.get("rxTime")),
        rx_snr=_float(raw.get("rxSnr")),
        rx_rssi=_int(raw.get("rxRssi")),
        request_id=_int(decoded.get("requestId")),
        reply_id=_int(decoded.get("replyId")),
        routing_error=routing_error,
        text=decoded.get("text") if isinstance(decoded.get("text"), str) else None,
        user=parse_user(user_raw) if isinstance(user_raw, dict) else None,
        position=(
            parse_position(position_raw, now=now)
            if isinstance(position_raw, dict)
            else None
        ),
        telemetry=(
            parse_telemetry(telemetry_raw, now=now)
            if isinstance(telemetry_raw, dict)
            else None
        ),
        received_at=now,
        backlog=backlog,
    )


def parse_node_info(raw: dict[str, Any], *, now: datetime) -> MeshtasticNode | None:
    """Build a :class:`MeshtasticNode` from a library node-DB entry."""
    num = _int(raw.get("num"))
    if num is None:
        return None
    user_raw = raw.get("user")
    user = parse_user(user_raw) if isinstance(user_raw, dict) else None
    position_raw = raw.get("position")
    position = (
        parse_position(position_raw, now=now, source=PositionSource.NODE_INFO)
        if isinstance(position_raw, dict)
        else None
    )
    telemetry: dict[str, TelemetrySample] = {}
    for key, family in _TELEMETRY_FAMILIES.items():
        metrics = raw.get(key)
        if not isinstance(metrics, dict):
            continue
        values: dict[str, TelemetryValue] = {}
        for name, value in metrics.items():
            if name == "raw":
                continue
            if (safe := _json_safe(value)) is not None:
                values[_snake(name)] = safe
        telemetry[str(family)] = TelemetrySample(
            family=family, values=values, reported_at=now
        )
    last_heard_device = _int(raw.get("lastHeard"))
    return MeshtasticNode(
        num=num,
        node_id=user.node_id if user else format_node_id(num),
        long_name=user.long_name if user else None,
        short_name=user.short_name if user else None,
        hardware_model=user.hardware_model if user else None,
        role=user.role if user else None,
        hops_away=_int(raw.get("hopsAway")),
        snr=_float(raw.get("snr")),
        channel=_int(raw.get("channel")) or 0,
        via_mqtt=bool(raw.get("viaMqtt", False)),
        first_seen=now,
        last_heard=(
            dt_util.utc_from_timestamp(last_heard_device) if last_heard_device else None
        ),
        last_heard_device=last_heard_device,
        position=position,
        telemetry=telemetry,
        is_favorite=bool(raw.get("isFavorite", False)),
        is_ignored=bool(raw.get("isIgnored", False)),
        is_muted=bool(raw.get("isMuted", False)),
        is_key_manually_verified=bool(raw.get("isKeyManuallyVerified", False)),
        is_licensed=user.is_licensed if user else False,
        is_unmessagable=user.is_unmessagable if user else None,
        has_public_key=user.has_public_key if user else False,
        presumptive=user is None,
    )


def _enum_name(message: Any, field_name: str) -> str | None:
    """Return the name of an enum field of a protobuf message."""
    try:
        descriptor = message.DESCRIPTOR.fields_by_name[field_name]
        value = getattr(message, field_name)
    except AttributeError, KeyError:
        return None
    if descriptor.enum_type is None:
        return None
    entry = descriptor.enum_type.values_by_number.get(value)
    return entry.name if entry is not None else str(value)


def build_gateway_info(interface: TCPInterface) -> GatewayInfo:
    """Read the gateway identity off a connected interface.

    Runs in the executor: it touches protobuf members of the library object.
    """
    my_info = interface.myInfo
    if my_info is None:
        raise MeshtasticConnectionError(
            translation_domain=DOMAIN, translation_key="no_node_info"
        )
    node_num = int(my_info.my_node_num)
    metadata = interface.metadata
    local_node = interface.localNode
    local_config = getattr(local_node, "localConfig", None)
    lora = getattr(local_config, "lora", None)
    device = getattr(local_config, "device", None)

    channels: list[MeshtasticChannel] = []
    for channel in getattr(local_node, "channels", None) or []:
        role = _enum_name(channel, "role")
        if role == "DISABLED":
            continue
        settings = channel.settings
        channels.append(
            MeshtasticChannel(
                index=int(channel.index),
                name=str(settings.name),
                role=role or "PRIMARY",
                encrypted=bool(settings.psk) and settings.psk != b"\x00",
                uplink_enabled=bool(settings.uplink_enabled),
                downlink_enabled=bool(settings.downlink_enabled),
            )
        )

    user = interface.getMyNodeInfo() or {}
    user_info = user.get("user") if isinstance(user, dict) else None
    user_info = user_info if isinstance(user_info, dict) else {}

    return GatewayInfo(
        node_num=node_num,
        node_id=user_info.get("id") or format_node_id(node_num),
        long_name=user_info.get("longName") or None,
        short_name=user_info.get("shortName") or None,
        hardware_model=(
            _enum_name(metadata, "hw_model") if metadata is not None else None
        ),
        firmware_version=(
            str(metadata.firmware_version) if metadata is not None else None
        ),
        role=(
            _enum_name(metadata, "role")
            if metadata is not None
            else (_enum_name(device, "role") if device is not None else None)
        ),
        region=_enum_name(lora, "region") if lora is not None else None,
        modem_preset=_enum_name(lora, "modem_preset") if lora is not None else None,
        has_bluetooth=bool(getattr(metadata, "hasBluetooth", False)),
        has_wifi=bool(getattr(metadata, "hasWifi", False)),
        reboot_count=int(getattr(my_info, "reboot_count", 0)) or None,
        nodedb_count=int(getattr(my_info, "nodedb_count", 0)) or None,
        channels=tuple(channels),
    )


# ---------------------------------------------------------------------------
# Request tracking
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class PendingRequest:
    """One packet we sent and are waiting for the mesh to answer."""

    packet_id: int
    kind: RequestKind
    destination: int
    want_ack: bool = True
    want_response: bool = False
    state: RequestState = RequestState.SENT
    reached: RequestState = RequestState.SENT
    error_reason: str | None = None
    notification: str | None = None
    response: MeshtasticPacket | None = None
    future: asyncio.Future[None] | None = None

    @property
    def done(self) -> bool:
        """Return True when nothing further can change the outcome."""
        if self.state in _TERMINAL_STATES:
            return True
        if self.want_response:
            return False
        if self.state is RequestState.ACKED:
            return True
        return (
            self.state is RequestState.ACKED_IMPLICIT
            and self.destination == BROADCAST_NUM
        )

    def result(self) -> RequestResult:
        """Freeze this request into a :class:`RequestResult`."""
        return RequestResult(
            packet_id=self.packet_id,
            kind=self.kind,
            state=self.state,
            reached=self.reached,
            destination=self.destination,
            error_reason=self.error_reason,
            notification=self.notification,
            response=self.response,
        )


class RequestTracker:
    """Correlate ACK/NAK/response packets back to the packets we sent.

    Everything here runs on the event loop: the pubsub listeners hop across
    with ``call_soon_threadsafe`` before anything is handed to the tracker, so
    no locking is needed.  A short orphan buffer covers the race where the
    answer is processed before the send call has returned from the executor.
    """

    def __init__(self) -> None:
        """Initialise an empty tracker."""
        self.my_node_num: int | None = None
        self._pending: dict[int, PendingRequest] = {}
        self._orphans: OrderedDict[int, list[MeshtasticPacket]] = OrderedDict()

    @property
    def pending_count(self) -> int:
        """Return how many requests are currently in flight."""
        return len(self._pending)

    @callback
    def async_register(self, request: PendingRequest) -> None:
        """Register a request and replay any answer that arrived early."""
        self._pending[request.packet_id] = request
        for packet in self._orphans.pop(request.packet_id, []):
            self.async_handle_packet(packet)

    @callback
    def async_handle_packet(self, packet: MeshtasticPacket) -> None:
        """Feed one received packet into the tracker."""
        request_id = packet.request_id
        if not request_id:
            return
        request = self._pending.get(request_id)
        if request is None:
            self._async_remember(request_id, packet)
            return
        self._async_apply(request, packet)

    @callback
    def async_handle_notification(self, notification: MeshtasticNotification) -> None:
        """Feed a firmware client notification into the tracker."""
        reply_id = notification.reply_id
        if not reply_id:
            return
        request = self._pending.get(reply_id)
        if request is None or request.state in _TERMINAL_STATES:
            return
        request.state = RequestState.NACKED
        request.error_reason = NOTIFICATION_REJECTED
        request.notification = notification.message
        self._async_finish(request)

    async def async_wait(
        self, request: PendingRequest, timeout: float
    ) -> RequestResult:
        """Wait for a request to complete, or time out."""
        try:
            if not request.done:
                request.future = asyncio.get_running_loop().create_future()
                try:
                    async with asyncio.timeout(timeout):
                        await request.future
                except TimeoutError:
                    request.state = RequestState.TIMED_OUT
        finally:
            self._pending.pop(request.packet_id, None)
            request.future = None
        return request.result()

    @callback
    def async_cancel(self, packet_id: int) -> None:
        """Forget a request without completing it."""
        self._pending.pop(packet_id, None)

    @callback
    def async_clear(self) -> None:
        """Drop every pending request and orphan; used on disconnect."""
        for request in list(self._pending.values()):
            if request.state not in _TERMINAL_STATES:
                request.state = RequestState.TIMED_OUT
            self._async_finish(request)
        self._pending.clear()
        self._orphans.clear()

    @callback
    def _async_remember(self, request_id: int, packet: MeshtasticPacket) -> None:
        """Buffer an answer that arrived before its request was registered."""
        self._orphans.setdefault(request_id, []).append(packet)
        while len(self._orphans) > _ORPHAN_LIMIT:
            self._orphans.popitem(last=False)

    @callback
    def _async_apply(self, request: PendingRequest, packet: MeshtasticPacket) -> None:
        """Advance a request's state machine with one packet."""
        if request.state in _TERMINAL_STATES:
            return
        if packet.portnum == "ROUTING_APP":
            reason = packet.routing_error or ROUTING_ERROR_NONE
            if reason != ROUTING_ERROR_NONE:
                request.state = RequestState.NACKED
                request.error_reason = reason
            elif request.destination == BROADCAST_NUM:
                # Nobody sends a real ACK for a broadcast; the local node
                # confirming a rebroadcast is as good as it gets.
                request.state = RequestState.ACKED_IMPLICIT
            elif (
                self.my_node_num is not None
                and packet.from_num == self.my_node_num
                and request.destination != self.my_node_num
            ):
                request.state = RequestState.ACKED_IMPLICIT
            else:
                request.state = RequestState.ACKED
        else:
            request.state = RequestState.RESPONDED
            request.response = packet
        if request.state not in _TERMINAL_STATES:
            request.reached = request.state
        self._async_finish(request)

    @callback
    def _async_finish(self, request: PendingRequest) -> None:
        """Wake the waiter when the request reached a final state."""
        if (
            request.done
            and (future := request.future) is not None
            and not future.done()
        ):
            future.set_result(None)


def raise_for_result(result: RequestResult, *, node: str) -> None:
    """Raise a translated error unless the request was delivered."""
    if result.delivered:
        return
    if result.state is RequestState.TIMED_OUT:
        translation_key = TIMEOUT_TRANSLATION_KEYS.get(
            str(result.reached), DEFAULT_ERROR_TRANSLATION_KEY
        )
    else:
        translation_key = ROUTING_ERROR_TRANSLATION_KEYS.get(
            result.error_reason or "", DEFAULT_ERROR_TRANSLATION_KEY
        )
    error: type[HomeAssistantError] = (
        ServiceValidationError
        if result.error_reason in ROUTING_ERROR_VALIDATION
        else MeshtasticRequestError
    )
    raise error(
        translation_domain=DOMAIN,
        translation_key=translation_key,
        translation_placeholders={
            "node": node,
            "reason": result.error_reason or str(result.state),
            "message": result.notification or "",
        },
    )


# ---------------------------------------------------------------------------
# Executor plumbing
# ---------------------------------------------------------------------------


def _guarded[_T](func: Callable[[], _T]) -> _T:
    """Run a library call, converting ``SystemExit`` into an error.

    ``meshtastic.util.our_exit()`` calls ``sys.exit()`` for input validation.
    ``SystemExit`` derives from ``BaseException``, so it would escape an
    ordinary ``except Exception`` and, from an executor job, take the event
    loop down with it.
    """
    try:
        return func()
    except SystemExit as err:
        raise MeshtasticError(
            translation_domain=DOMAIN,
            translation_key="library_aborted",
            translation_placeholders={"error": str(err)},
        ) from err


def _close_interface(interface: TCPInterface) -> None:
    """Close an interface, swallowing anything it throws on the way out."""
    try:
        interface.close()
    except SystemExit as err:
        LOGGER.debug("Library exited while closing the connection: %s", err)
    except OSError as err:
        LOGGER.debug("Error while closing the connection: %s", err)


def _create_interface(host: str, port: int, *, no_nodes: bool) -> TCPInterface:
    """Construct and connect a TCP interface.  Blocking; executor only."""
    return TCPInterface(
        hostname=host,
        portNumber=port,
        noNodes=no_nodes,
        connectNow=True,
        timeout=LIBRARY_TIMEOUT,
    )


@dataclass(slots=True)
class MeshtasticClientCallbacks:
    """Callbacks the client invokes, always on the event loop."""

    connected: Callable[[GatewayInfo], None] = lambda _gateway: None
    disconnected: Callable[[str], None] = lambda _reason: None
    packet: Callable[[MeshtasticPacket], None] = lambda _packet: None
    node_updated: Callable[[MeshtasticNode], None] = lambda _node: None
    notification: Callable[[MeshtasticNotification], None] = lambda _notification: None


class MeshtasticClient:
    """Owns the TCP link to one Meshtastic node."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        *,
        download_node_db: bool = False,
        callbacks: MeshtasticClientCallbacks | None = None,
    ) -> None:
        """Initialise the client.  Does not connect."""
        self.hass = hass
        self.host = host
        self.port = port
        self.download_node_db = download_node_db
        self.callbacks = callbacks or MeshtasticClientCallbacks()
        self.tracker = RequestTracker()

        self._interface: TCPInterface | None = None
        self._gateway: GatewayInfo | None = None
        self._state = ConnectionState.DISCONNECTED
        self._dead_reason: str | None = None
        self._closing = False

        self._send_lock = asyncio.Lock()
        self._port_gate: dict[int, float] = {}

        self._dead = asyncio.Event()
        self._supervisor_task: asyncio.Task[None] | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._subscribed = False

        self._connected_at: float | None = None
        self._last_rx = 0.0
        self._missed_heartbeats = 0
        self._backoff_step = 0
        self._short_connections = 0
        self._reconnect_attempts = 0
        self._breaker_open = False
        self._reboot_grace_until = 0.0

    # -- state ------------------------------------------------------------

    @property
    def connection_state(self) -> ConnectionState:
        """Return the current link state."""
        return self._state

    @property
    def connected(self) -> bool:
        """Return True while the link is up."""
        return self._state is ConnectionState.CONNECTED

    @property
    def available(self) -> bool:
        """Return True while entities should present data.

        A node that was deliberately rebooted comes back within a minute or so;
        flapping every entity to ``unavailable`` in the meantime is noise.
        """
        return self.connected or self.reboot_grace_active

    @property
    def gateway(self) -> GatewayInfo | None:
        """Return the gateway identity, once connected at least once."""
        return self._gateway

    @property
    def reboot_grace_active(self) -> bool:
        """Return True while a reboot we caused is expected to be in progress."""
        return time.monotonic() < self._reboot_grace_until

    @callback
    def async_note_reboot_expected(self) -> None:
        """Open the reboot grace window and probe the link faster."""
        self._reboot_grace_until = time.monotonic() + REBOOT_GRACE

    def stats(self) -> dict[str, Any]:
        """Return link statistics for the diagnostics download."""
        connected_for: float | None = None
        if self._connected_at is not None and self.connected:
            connected_for = round(time.monotonic() - self._connected_at, 1)
        return {
            "state": str(self._state),
            "host": self.host,
            "port": self.port,
            "download_node_db": self.download_node_db,
            "connected_for": connected_for,
            "dead_reason": self._dead_reason,
            "reconnect_attempts": self._reconnect_attempts,
            "short_connections": self._short_connections,
            "circuit_breaker_open": self._breaker_open,
            "missed_heartbeats": self._missed_heartbeats,
            "pending_requests": self.tracker.pending_count,
            "reboot_grace_active": self.reboot_grace_active,
        }

    # -- lifecycle --------------------------------------------------------

    async def async_start(self) -> None:
        """Connect for the first time and start supervising the link."""
        self._closing = False
        self._async_subscribe()
        try:
            await self._async_connect()
        except MeshtasticError:
            self._async_unsubscribe()
            raise
        self._supervisor_task = self.hass.async_create_background_task(
            self._async_supervise(), name=f"{DOMAIN} supervisor {self.host}"
        )
        self._heartbeat_task = self.hass.async_create_background_task(
            self._async_heartbeat_loop(), name=f"{DOMAIN} heartbeat {self.host}"
        )

    async def async_stop(self) -> None:
        """Stop supervising and close the link, promptly and bounded."""
        self._closing = True
        tasks = [
            task
            for task in (self._supervisor_task, self._heartbeat_task)
            if task is not None
        ]
        self._supervisor_task = None
        self._heartbeat_task = None
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._async_unsubscribe()
        self.tracker.async_clear()
        await self._async_teardown()
        self._state = ConnectionState.DISCONNECTED

    async def _async_connect(self) -> None:
        """Create a fresh interface and read the gateway identity."""
        self._state = ConnectionState.CONNECTING
        self._reconnect_attempts += 1
        interface = await self._async_run(
            functools.partial(
                _create_interface,
                self.host,
                self.port,
                no_nodes=not self.download_node_db,
            ),
            timeout=CONNECT_TIMEOUT,
            connect=True,
        )
        # Own the interface from the moment the executor hands it over.  A
        # cancellation between here and the handshake - which is exactly what
        # the config flow's validation timeout does - would otherwise abandon a
        # live socket and its reader thread that async_stop() cannot find.
        self._interface = interface
        try:
            gateway = await self._async_run(
                functools.partial(build_gateway_info, interface),
                timeout=EXECUTOR_JOB_TIMEOUT,
                connect=True,
            )
        except BaseException:
            self._interface = None
            await self.hass.async_add_executor_job(_close_interface, interface)
            raise
        self._gateway = gateway
        self.tracker.my_node_num = gateway.node_num
        self._connected_at = time.monotonic()
        self._last_rx = time.monotonic()
        self._missed_heartbeats = 0
        self._dead_reason = None
        self._port_gate.clear()
        self._dead.clear()
        self._state = ConnectionState.CONNECTED
        self.callbacks.connected(gateway)

    async def _async_teardown(self) -> None:
        """Close the current interface within a bounded time."""
        interface, self._interface = self._interface, None
        if interface is None:
            return
        try:
            async with asyncio.timeout(CLOSE_TIMEOUT):
                await self.hass.async_add_executor_job(_close_interface, interface)
        except TimeoutError:
            LOGGER.warning(
                "Timed out closing the connection to %s; abandoning it", self.host
            )

    @callback
    def _async_mark_dead(self, reason: str) -> None:
        """Declare the link dead and let the supervisor take over."""
        if self._closing or self._state not in (
            ConnectionState.CONNECTED,
            ConnectionState.CONNECTING,
        ):
            return
        self._dead_reason = reason
        self._state = ConnectionState.RECONNECTING
        self.tracker.async_clear()
        self._dead.set()
        self.callbacks.disconnected(reason)

    # -- supervision ------------------------------------------------------

    async def _async_supervise(self) -> None:
        """Reconnect forever, with backoff and a circuit breaker."""
        while True:
            await self._dead.wait()
            self._dead.clear()
            await self._async_teardown()
            self._note_connection_ended()
            while True:
                if self._breaker_open:
                    LOGGER.warning(
                        (
                            "Repeatedly disconnected from %s; another client (the"
                            " phone app or the CLI) may be using the node. Pausing"
                            " reconnection for %s seconds"
                        ),
                        self.host,
                        int(CIRCUIT_BREAKER_COOLDOWN),
                    )
                    self._state = ConnectionState.CIRCUIT_OPEN
                    # Republish the failure now that the breaker is open: the
                    # state the coordinator last heard about was an ordinary
                    # reconnect, and the repair issue keys off this one.
                    self.callbacks.disconnected(
                        f"reconnection paused for {int(CIRCUIT_BREAKER_COOLDOWN)}"
                        " seconds"
                    )
                    await self._async_delay(CIRCUIT_BREAKER_COOLDOWN)
                    self._breaker_open = False
                    self._short_connections = CIRCUIT_BREAKER_TRIPS - 1
                else:
                    await self._async_delay(self._next_backoff())
                try:
                    await self._async_connect()
                except MeshtasticError as err:
                    self._state = ConnectionState.RECONNECTING
                    LOGGER.debug("Reconnect to %s failed: %s", self.host, err)
                    continue
                LOGGER.info(
                    "Reconnected to Meshtastic node %s (attempt %s)",
                    self.host,
                    self._reconnect_attempts,
                )
                break

    def _note_connection_ended(self) -> None:
        """Update backoff and breaker counters after a link died."""
        lifetime = (
            time.monotonic() - self._connected_at
            if self._connected_at is not None
            else 0.0
        )
        self._connected_at = None
        if lifetime >= CONNECTION_STABLE_AFTER:
            self._backoff_step = 0
            self._short_connections = 0
            return
        self._short_connections += 1
        if self._short_connections >= CIRCUIT_BREAKER_TRIPS:
            self._breaker_open = True

    def _next_backoff(self) -> float:
        """Return the next jittered exponential backoff delay."""
        delay = random.uniform(RECONNECT_MIN_DELAY, RECONNECT_MAX_INITIAL_DELAY) * (
            RECONNECT_BACKOFF_FACTOR**self._backoff_step
        )
        self._backoff_step += 1
        return min(delay, RECONNECT_MAX_DELAY)

    async def _async_heartbeat_loop(self) -> None:
        """Keep the firmware's idle timer happy and detect a wedged link."""
        while True:
            await self._async_delay(
                FAST_PROBE_INTERVAL if self.reboot_grace_active else HEARTBEAT_INTERVAL
            )
            interface = self._interface
            if interface is None or not self.connected:
                continue
            marker = getattr(interface, "queueStatus", None)
            try:
                await self._async_run(interface.sendHeartbeat)
            except MeshtasticError as err:
                self._async_mark_dead(f"heartbeat failed: {err}")
                continue
            await self._async_delay(HEARTBEAT_RESPONSE_TIMEOUT)
            if self._interface is not interface or not self.connected:
                continue
            if getattr(interface, "queueStatus", None) is not marker:
                self._last_rx = time.monotonic()
            since_rx = time.monotonic() - self._last_rx
            if since_rx < HEARTBEAT_INTERVAL:
                self._missed_heartbeats = 0
                continue
            self._missed_heartbeats += 1
            if (
                self._missed_heartbeats >= MAX_MISSED_HEARTBEATS
                or since_rx > LIVENESS_TIMEOUT
            ):
                self._async_mark_dead(
                    f"no data from the node for {int(since_rx)} seconds"
                )

    async def _async_delay(self, delay: float) -> None:
        """Sleep using Home Assistant's timer so tests can drive the clock."""
        waiter = self.hass.loop.create_future()

        @callback
        def _resume(_now: datetime) -> None:
            if not waiter.done():
                waiter.set_result(None)

        unsub: CALLBACK_TYPE = async_call_later(self.hass, delay, _resume)
        try:
            await waiter
        finally:
            unsub()

    # -- executor ---------------------------------------------------------

    async def _async_run[_T](
        self,
        func: Callable[[], _T],
        *,
        timeout: float = EXECUTOR_JOB_TIMEOUT,
        connect: bool = False,
    ) -> _T:
        """Run one library call in the executor, bounded and guarded."""
        try:
            async with asyncio.timeout(timeout):
                return await self.hass.async_add_executor_job(
                    functools.partial(_guarded, func)
                )
        except TimeoutError as err:
            raise MeshtasticConnectionError(
                translation_domain=DOMAIN,
                translation_key="timeout",
                translation_placeholders={"host": self.host},
            ) from err
        except (OSError, MeshInterface.MeshInterfaceError) as err:
            raise MeshtasticConnectionError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect" if connect else "connection_lost",
                translation_placeholders={"host": self.host, "error": str(err)},
            ) from err

    def _require_interface(self) -> TCPInterface:
        """Return the live interface, or raise if the link is down."""
        interface = self._interface
        if interface is None or not self.connected:
            raise MeshtasticConnectionError(
                translation_domain=DOMAIN,
                translation_key="not_connected",
                translation_placeholders={"host": self.host},
            )
        return interface

    # -- sending ----------------------------------------------------------

    async def async_send_text(
        self,
        text: str,
        *,
        destination: int | str = BROADCAST_NUM,
        channel_index: int = 0,
        want_ack: bool = True,
        reply_id: int | None = None,
    ) -> RequestResult:
        """Send a text message and wait for the mesh's verdict."""
        node_num = self.resolve_destination(destination)
        payload_length = len(text.encode())
        limit = (
            MAX_TEXT_PAYLOAD_BYTES
            if node_num == BROADCAST_NUM
            else MAX_DIRECT_TEXT_PAYLOAD_BYTES
        )
        if payload_length > limit:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="message_too_long",
                translation_placeholders={
                    "length": str(payload_length),
                    "limit": str(limit),
                },
            )
        kind = (
            RequestKind.TEXT_BROADCAST
            if node_num == BROADCAST_NUM
            else RequestKind.TEXT_DIRECT
        )

        def _send(interface: TCPInterface) -> Any:
            return interface.sendText(
                text,
                destinationId=node_num,
                wantAck=want_ack,
                channelIndex=channel_index,
                replyId=reply_id,
            )

        return await self.async_request(
            kind=kind,
            portnum=PORTNUM_TEXT_MESSAGE_APP,
            destination=node_num,
            send=_send,
            want_ack=want_ack,
        )

    async def async_send_data(
        self,
        payload: bytes,
        *,
        portnum: int,
        destination: int | str = BROADCAST_NUM,
        kind: RequestKind = RequestKind.FIRE_AND_FORGET,
        channel_index: int = 0,
        want_ack: bool = False,
        want_response: bool = False,
        hop_limit: int | None = None,
        pki_encrypted: bool = False,
    ) -> RequestResult:
        """Send a raw payload on a portnum and wait for the mesh's verdict."""
        node_num = self.resolve_destination(destination)

        def _send(interface: TCPInterface) -> Any:
            return interface.sendData(
                payload,
                destinationId=node_num,
                portNum=portnum,
                wantAck=want_ack,
                wantResponse=want_response,
                channelIndex=channel_index,
                hopLimit=hop_limit,
                pkiEncrypted=pki_encrypted,
            )

        return await self.async_request(
            kind=kind,
            portnum=portnum,
            destination=node_num,
            send=_send,
            want_ack=want_ack,
            want_response=want_response,
        )

    async def async_request(
        self,
        *,
        kind: RequestKind,
        portnum: int,
        destination: int,
        send: Callable[[TCPInterface], Any],
        want_ack: bool = True,
        want_response: bool = False,
    ) -> RequestResult:
        """Send something and correlate the answer.

        ``send`` is called in the executor with the live interface and must
        return the ``MeshPacket`` the library produced; its ``id`` is the
        correlation key.
        """
        interface = self._require_interface()
        async with self._send_lock:
            await self._async_wait_for_gate(portnum)
            packet = await self._async_run(functools.partial(send, interface))
            self._port_gate[portnum] = time.monotonic() + SEND_SPACING.get(
                portnum, DEFAULT_SEND_SPACING
            )
        request = PendingRequest(
            packet_id=int(getattr(packet, "id", 0) or 0),
            kind=kind,
            destination=destination,
            want_ack=want_ack,
            want_response=want_response,
        )
        if not request.packet_id:
            # sendTelemetry() and friends return nothing; there is no id to
            # correlate on, so the send is all we can report.
            return request.result()
        self.tracker.async_register(request)
        return await self.tracker.async_wait(
            request, REQUEST_TIMEOUTS.get(kind, DEFAULT_REQUEST_TIMEOUT)
        )

    async def async_refresh_nodes(self) -> None:
        """Ask the node to stream its node database again.

        The firmware accepts a ``want_config_id`` at any time, including on an
        established connection, and the ``SPECIAL_NONCE_ONLY_NODES`` nonce makes
        it send its own ``NodeInfo`` plus every other one it knows and then go
        straight back to forwarding packets.  Nothing goes on the air.

        The library merges the records into its own table and republishes each
        of them on ``meshtastic.node.updated``, which is the path the
        coordinator already listens on, so there is nothing to await here: the
        completion frame carries a nonce the library silently discards.  While
        the stream runs the node's eight-slot to-phone queue can drop received
        packets, which is why this is only ever triggered by an explicit user
        action.
        """
        interface = self._require_interface()

        def _send() -> None:
            request = mesh_pb2.ToRadio()
            request.want_config_id = NODES_ONLY_WANT_CONFIG_ID
            # The library has no public call for this; ``_sendToRadio`` only
            # frames and writes the message.  Do not use ``_startConfig()``,
            # which drops ``myInfo`` and the whole node table first.
            interface._sendToRadio(request)  # noqa: SLF001

        async with self._send_lock:
            await self._async_run(_send)

    async def _async_wait_for_gate(self, portnum: int) -> None:
        """Respect the per-portnum send spacing the firmware enforces."""
        wait = self._port_gate.get(portnum, 0.0) - time.monotonic()
        if wait <= 0:
            return
        if wait > MAX_SEND_GATE_WAIT:
            raise MeshtasticRequestError(
                translation_domain=DOMAIN,
                translation_key="rate_limited",
                translation_placeholders={"seconds": str(int(wait))},
            )
        await self._async_delay(wait)

    def resolve_destination(self, destination: int | str) -> int:
        """Return the node number for a destination.

        Always resolve to a number: handing the library a name would make it
        look the name up in its node table and ``sys.exit()`` on a miss.
        """
        if isinstance(destination, int):
            return destination
        if destination in (BROADCAST_ID, "broadcast", "all"):
            return BROADCAST_NUM
        try:
            return parse_node_id(destination)
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_node",
                translation_placeholders={"node": destination},
            ) from err

    # -- pubsub -----------------------------------------------------------

    @callback
    def _async_subscribe(self) -> None:
        """Subscribe the pubsub listeners.  Bound methods, held by self."""
        if self._subscribed:
            return
        pub.subscribe(self._on_receive, TOPIC_RECEIVE)
        pub.subscribe(self._on_node_updated, TOPIC_NODE_UPDATED)
        pub.subscribe(self._on_connection_established, TOPIC_CONNECTION_ESTABLISHED)
        pub.subscribe(self._on_connection_lost, TOPIC_CONNECTION_LOST)
        pub.subscribe(self._on_client_notification, TOPIC_CLIENT_NOTIFICATION)
        self._subscribed = True

    @callback
    def _async_unsubscribe(self) -> None:
        """Remove the pubsub listeners.

        pypubsub raises if a topic was never created, and its topic tree is
        process-global state we do not own.  Unloading an entry must succeed
        either way, so failures here are logged and swallowed.
        """
        if not self._subscribed:
            return
        self._subscribed = False
        for listener, topic in (
            (self._on_receive, TOPIC_RECEIVE),
            (self._on_node_updated, TOPIC_NODE_UPDATED),
            (self._on_connection_established, TOPIC_CONNECTION_ESTABLISHED),
            (self._on_connection_lost, TOPIC_CONNECTION_LOST),
            (self._on_client_notification, TOPIC_CLIENT_NOTIFICATION),
        ):
            try:
                pub.unsubscribe(listener, topic)
            except Exception:  # noqa: BLE001
                LOGGER.debug("Could not unsubscribe from %s", topic, exc_info=True)

    def _schedule(self, func: Callable[..., Any], *args: Any) -> None:
        """Hop from a library thread onto the event loop.  Never raises."""
        try:
            self.hass.loop.call_soon_threadsafe(func, *args)
        except RuntimeError:  # loop already closed during shutdown
            LOGGER.debug("Dropped a Meshtastic callback; the event loop is gone")

    def _on_receive(self, packet: dict[str, Any], interface: MeshInterface) -> None:
        """Handle any received packet.  Runs on the pubsub thread."""
        if interface is not self._interface:
            return
        self._schedule(self._async_handle_raw_packet, packet)

    def _on_node_updated(self, node: dict[str, Any], interface: MeshInterface) -> None:
        """Handle a node-DB push.  Runs on the pubsub thread."""
        if interface is not self._interface:
            return
        # The library hands out the live dict and keeps mutating it; copy now.
        self._schedule(self._async_handle_raw_node, dict(node))

    def _on_connection_established(self, interface: MeshInterface) -> None:
        """Handle a (re)established handshake.  Runs on the pubsub thread."""
        if interface is not self._interface:
            return
        self._schedule(self._async_touch)

    def _on_connection_lost(self, interface: MeshInterface) -> None:
        """Handle the reader thread going away.  Runs on the pubsub thread."""
        if interface is not self._interface or self._closing:
            return
        self._schedule(self._async_mark_dead, "the node closed the connection")

    def _on_client_notification(
        self, notification: Any, interface: MeshInterface
    ) -> None:
        """Handle a firmware notification.  Runs on the pubsub thread."""
        if interface is not self._interface:
            return
        # Convert the protobuf here so none of it reaches the event loop.
        parsed = MeshtasticNotification(
            message=str(getattr(notification, "message", "")),
            level=_enum_name(notification, "level"),
            reply_id=int(getattr(notification, "reply_id", 0)) or None,
            device_time=int(getattr(notification, "time", 0)) or None,
        )
        self._schedule(self._async_handle_notification, parsed)

    # -- loop side --------------------------------------------------------

    @callback
    def _async_touch(self) -> None:
        """Record that the link produced traffic."""
        self._last_rx = time.monotonic()
        self._missed_heartbeats = 0

    @callback
    def _async_handle_raw_packet(self, raw: dict[str, Any]) -> None:
        """Convert and dispatch a received packet."""
        self._async_touch()
        now = dt_util.utcnow()
        packet = parse_packet(raw, now=now, backlog=self._is_backlog(raw, now))
        if packet is None:
            return
        self.tracker.async_handle_packet(packet)
        self.callbacks.packet(packet)

    @callback
    def _async_handle_raw_node(self, raw: dict[str, Any]) -> None:
        """Convert and dispatch a node-DB record."""
        self._async_touch()
        node = parse_node_info(raw, now=dt_util.utcnow())
        if node is None:
            return
        self.callbacks.node_updated(node)

    @callback
    def _async_handle_notification(self, notification: MeshtasticNotification) -> None:
        """Dispatch a firmware notification."""
        self._async_touch()
        self.tracker.async_handle_notification(notification)
        self.callbacks.notification(notification)

    def _is_backlog(self, raw: dict[str, Any], now: datetime) -> bool:
        """Return True for packets the node queued while we were away."""
        rx_time = _int(raw.get("rxTime"))
        if rx_time:
            return (now.timestamp() - rx_time) > BACKLOG_MAX_AGE
        if self._connected_at is None:
            return False
        return (time.monotonic() - self._connected_at) < BACKLOG_CONNECT_WINDOW


__all__ = [
    "MeshtasticClient",
    "MeshtasticClientCallbacks",
    "MeshtasticConnectionError",
    "MeshtasticError",
    "MeshtasticRequestError",
    "PendingRequest",
    "RequestTracker",
    "build_gateway_info",
    "parse_node_info",
    "parse_packet",
    "parse_position",
    "parse_telemetry",
    "parse_user",
    "raise_for_result",
]
