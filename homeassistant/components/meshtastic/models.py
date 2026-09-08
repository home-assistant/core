"""Immutable data models for the Meshtastic integration.

Everything in this module is a plain, frozen, JSON-safe dataclass or enum.  No
protobuf objects and no ``bytes`` ever reach these types: the client converts
the library's dictionaries into them before anything else in the integration
sees them.

The dataclasses use the default (field based) ``__eq__`` so that the
coordinator can run with ``always_update=False`` and only notify listeners when
something actually changed.  Timestamps are timezone-aware ``datetime`` objects
for entity use; :meth:`as_dict` renders them as ISO-8601 strings for the node
store and for diagnostics.
"""

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from typing import Any, Self

# --------------------------------------------------------------------------
# Enumerations
# --------------------------------------------------------------------------


class ConnectionState(StrEnum):
    """State of the TCP link to the gateway node."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    CIRCUIT_OPEN = "circuit_open"


class RequestState(StrEnum):
    """State of a packet we sent and are correlating answers for."""

    SENT = "sent"
    ACKED_IMPLICIT = "acked_implicit"
    ACKED = "acked"
    RESPONDED = "responded"
    NACKED = "nacked"
    TIMED_OUT = "timed_out"


class RequestKind(StrEnum):
    """Kind of request, which decides completion rules and the timeout."""

    TEXT_BROADCAST = "text_broadcast"
    TEXT_DIRECT = "text_direct"
    FIRE_AND_FORGET = "fire_and_forget"
    DIRECT_REQUEST = "direct_request"
    TRACEROUTE = "traceroute"
    ADMIN_LOCAL_GET = "admin_local_get"
    ADMIN_LOCAL_SET = "admin_local_set"
    ADMIN_REMOTE_GET = "admin_remote_get"
    ADMIN_REMOTE_SET = "admin_remote_set"


class TelemetryFamily(StrEnum):
    """Telemetry oneof member names, normalised to snake case."""

    DEVICE = "device"
    ENVIRONMENT = "environment"
    AIR_QUALITY = "air_quality"
    POWER = "power"
    LOCAL_STATS = "local_stats"
    HEALTH = "health"
    HOST = "host"


class PositionSource(StrEnum):
    """Where a stored position came from."""

    PACKET = "packet"
    NODE_INFO = "node_info"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _iso(value: datetime | None) -> str | None:
    """Render a datetime as an ISO-8601 string."""
    return None if value is None else value.isoformat()


def _parse_dt(value: Any) -> datetime | None:
    """Parse an ISO-8601 string back into a datetime."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _int_or_none(value: Any) -> int | None:
    """Coerce to int, or None when the value is missing or unusable."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except TypeError, ValueError:
        return None


def _float_or_none(value: Any) -> float | None:
    """Coerce to float, or None when the value is missing or unusable."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except TypeError, ValueError:
        return None


# --------------------------------------------------------------------------
# Gateway
# --------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True, slots=True)
class MeshtasticChannel:
    """One channel slot of the gateway node.  Never carries the PSK."""

    index: int
    name: str
    role: str
    encrypted: bool = False
    uplink_enabled: bool = False
    downlink_enabled: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""
        return {
            "index": self.index,
            "name": self.name,
            "role": self.role,
            "encrypted": self.encrypted,
            "uplink_enabled": self.uplink_enabled,
            "downlink_enabled": self.downlink_enabled,
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class GatewayInfo:
    """Identity and capabilities of the node Home Assistant is connected to."""

    node_num: int
    node_id: str
    long_name: str | None = None
    short_name: str | None = None
    hardware_model: str | None = None
    firmware_version: str | None = None
    role: str | None = None
    region: str | None = None
    modem_preset: str | None = None
    has_bluetooth: bool = False
    has_wifi: bool = False
    reboot_count: int | None = None
    nodedb_count: int | None = None
    channels: tuple[MeshtasticChannel, ...] = ()

    @property
    def name(self) -> str:
        """Return the best human readable name for the gateway."""
        return self.long_name or self.short_name or self.node_id

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""
        return {
            "node_num": self.node_num,
            "node_id": self.node_id,
            "long_name": self.long_name,
            "short_name": self.short_name,
            "hardware_model": self.hardware_model,
            "firmware_version": self.firmware_version,
            "role": self.role,
            "region": self.region,
            "modem_preset": self.modem_preset,
            "has_bluetooth": self.has_bluetooth,
            "has_wifi": self.has_wifi,
            "reboot_count": self.reboot_count,
            "nodedb_count": self.nodedb_count,
            "channels": [channel.as_dict() for channel in self.channels],
        }


# --------------------------------------------------------------------------
# Node payloads
# --------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True, slots=True)
class NodeUser:
    """The ``user`` sub-message of a node info record."""

    node_id: str
    long_name: str | None = None
    short_name: str | None = None
    hardware_model: str | None = None
    role: str | None = None
    is_licensed: bool = False
    is_unmessagable: bool | None = None
    has_public_key: bool = False


@dataclass(frozen=True, kw_only=True, slots=True)
class Position:
    """A position report.  Latitude/longitude are decimal degrees."""

    latitude: float | None = None
    longitude: float | None = None
    altitude: int | None = None
    precision_bits: int | None = None
    location_source: str | None = None
    sats_in_view: int | None = None
    ground_speed: int | None = None
    ground_track: float | None = None
    device_time: int | None = None
    reported_at: datetime | None = None
    source: PositionSource = PositionSource.PACKET

    @property
    def valid(self) -> bool:
        """Return True when the position carries usable coordinates."""
        return self.latitude is not None and self.longitude is not None

    @property
    def location_accuracy(self) -> int:
        """Return the radius in metres implied by ``precision_bits``.

        Meshtastic truncates the 1e-7 degree integers to ``precision_bits``
        significant bits, so the cell edge is ``2 ** (32 - bits) * 1e-7``
        degrees.  ``0`` means "unknown / full precision".
        """
        bits = self.precision_bits
        if bits is None or bits <= 0 or bits >= 32:
            return 0
        return int(2 ** (32 - bits) * 1e-7 * 111320 / 2)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude": self.altitude,
            "precision_bits": self.precision_bits,
            "location_source": self.location_source,
            "sats_in_view": self.sats_in_view,
            "ground_speed": self.ground_speed,
            "ground_track": self.ground_track,
            "device_time": self.device_time,
            "reported_at": _iso(self.reported_at),
            "source": str(self.source),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Rebuild a position from its stored representation."""
        try:
            source = PositionSource(data.get("source", PositionSource.PACKET))
        except ValueError:
            source = PositionSource.PACKET
        return cls(
            latitude=_float_or_none(data.get("latitude")),
            longitude=_float_or_none(data.get("longitude")),
            altitude=_int_or_none(data.get("altitude")),
            precision_bits=_int_or_none(data.get("precision_bits")),
            location_source=data.get("location_source"),
            sats_in_view=_int_or_none(data.get("sats_in_view")),
            ground_speed=_int_or_none(data.get("ground_speed")),
            ground_track=_float_or_none(data.get("ground_track")),
            device_time=_int_or_none(data.get("device_time")),
            reported_at=_parse_dt(data.get("reported_at")),
            source=source,
        )


type TelemetryValue = float | int | bool | str


@dataclass(frozen=True, kw_only=True, slots=True)
class TelemetrySample:
    """One telemetry family sample, with the time it was reported."""

    family: TelemetryFamily
    values: dict[str, TelemetryValue] = field(default_factory=dict)
    device_time: int | None = None
    reported_at: datetime | None = None

    def value(self, key: str) -> TelemetryValue | None:
        """Return one metric of this sample."""
        return self.values.get(key)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""
        return {
            "family": str(self.family),
            "values": dict(self.values),
            "device_time": self.device_time,
            "reported_at": _iso(self.reported_at),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self | None:
        """Rebuild a sample from its stored representation."""
        try:
            family = TelemetryFamily(data["family"])
        except KeyError, ValueError:
            return None
        values = data.get("values")
        return cls(
            family=family,
            values=dict(values) if isinstance(values, dict) else {},
            device_time=_int_or_none(data.get("device_time")),
            reported_at=_parse_dt(data.get("reported_at")),
        )


@dataclass(frozen=True, kw_only=True, slots=True)
class MeshtasticNode:
    """A node the gateway knows about, as published by the coordinator."""

    num: int
    node_id: str
    long_name: str | None = None
    short_name: str | None = None
    hardware_model: str | None = None
    role: str | None = None
    hops_away: int | None = None
    snr: float | None = None
    rssi: int | None = None
    channel: int = 0
    via_mqtt: bool = False
    first_seen: datetime | None = None
    last_heard: datetime | None = None
    last_heard_device: int | None = None
    position: Position | None = None
    telemetry: dict[str, TelemetrySample] = field(default_factory=dict)
    is_favorite: bool = False
    is_ignored: bool = False
    is_muted: bool = False
    is_key_manually_verified: bool = False
    is_licensed: bool = False
    is_unmessagable: bool | None = None
    has_public_key: bool = False
    presumptive: bool = True

    @property
    def name(self) -> str:
        """Return the best human readable name for the node."""
        return self.long_name or self.short_name or self.node_id

    def sample(self, family: TelemetryFamily) -> TelemetrySample | None:
        """Return the newest sample of a telemetry family, if any."""
        return self.telemetry.get(str(family))

    def with_updates(self, **changes: Any) -> MeshtasticNode:
        """Return a copy of this node with the given fields replaced."""
        return replace(self, **changes)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""
        return {
            "num": self.num,
            "node_id": self.node_id,
            "long_name": self.long_name,
            "short_name": self.short_name,
            "hardware_model": self.hardware_model,
            "role": self.role,
            "hops_away": self.hops_away,
            "snr": self.snr,
            "rssi": self.rssi,
            "channel": self.channel,
            "via_mqtt": self.via_mqtt,
            "first_seen": _iso(self.first_seen),
            "last_heard": _iso(self.last_heard),
            "last_heard_device": self.last_heard_device,
            "position": None if self.position is None else self.position.as_dict(),
            "telemetry": {
                family: sample.as_dict() for family, sample in self.telemetry.items()
            },
            "is_favorite": self.is_favorite,
            "is_ignored": self.is_ignored,
            "is_muted": self.is_muted,
            "is_key_manually_verified": self.is_key_manually_verified,
            "is_licensed": self.is_licensed,
            "is_unmessagable": self.is_unmessagable,
            "has_public_key": self.has_public_key,
            "presumptive": self.presumptive,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self | None:
        """Rebuild a node from its stored representation.

        Returns ``None`` for records that cannot be trusted (no node number),
        so a corrupt entry is skipped instead of poisoning the whole store.
        """
        num = _int_or_none(data.get("num"))
        node_id = data.get("node_id")
        if num is None or not isinstance(node_id, str):
            return None
        position_data = data.get("position")
        telemetry: dict[str, TelemetrySample] = {}
        raw_telemetry = data.get("telemetry")
        if isinstance(raw_telemetry, dict):
            for key, value in raw_telemetry.items():
                if isinstance(value, dict) and (
                    sample := TelemetrySample.from_dict(value)
                ):
                    telemetry[key] = sample
        return cls(
            num=num,
            node_id=node_id,
            long_name=data.get("long_name"),
            short_name=data.get("short_name"),
            hardware_model=data.get("hardware_model"),
            role=data.get("role"),
            hops_away=_int_or_none(data.get("hops_away")),
            snr=_float_or_none(data.get("snr")),
            rssi=_int_or_none(data.get("rssi")),
            channel=_int_or_none(data.get("channel")) or 0,
            via_mqtt=bool(data.get("via_mqtt", False)),
            first_seen=_parse_dt(data.get("first_seen")),
            last_heard=_parse_dt(data.get("last_heard")),
            last_heard_device=_int_or_none(data.get("last_heard_device")),
            position=(
                Position.from_dict(position_data)
                if isinstance(position_data, dict)
                else None
            ),
            telemetry=telemetry,
            is_favorite=bool(data.get("is_favorite", False)),
            is_ignored=bool(data.get("is_ignored", False)),
            is_muted=bool(data.get("is_muted", False)),
            is_key_manually_verified=bool(data.get("is_key_manually_verified", False)),
            is_licensed=bool(data.get("is_licensed", False)),
            is_unmessagable=data.get("is_unmessagable"),
            has_public_key=bool(data.get("has_public_key", False)),
            presumptive=bool(data.get("presumptive", True)),
        )


# --------------------------------------------------------------------------
# Received traffic
# --------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True, slots=True)
class MeshtasticPacket:
    """A decoded packet, sanitised of protobufs and raw payload bytes."""

    packet_id: int
    from_num: int
    from_id: str | None = None
    to_num: int = 0
    to_id: str | None = None
    portnum: str = "UNKNOWN_APP"
    channel: int = 0
    want_ack: bool = False
    via_mqtt: bool = False
    priority: str | None = None
    hop_limit: int | None = None
    hop_start: int | None = None
    rx_time: int | None = None
    rx_snr: float | None = None
    rx_rssi: int | None = None
    request_id: int | None = None
    reply_id: int | None = None
    routing_error: str | None = None
    text: str | None = None
    user: NodeUser | None = None
    position: Position | None = None
    telemetry: TelemetrySample | None = None
    received_at: datetime | None = None
    backlog: bool = False

    @property
    def is_broadcast(self) -> bool:
        """Return True when the packet was addressed to everybody."""
        return self.to_num == 0xFFFFFFFF

    @property
    def hops_away(self) -> int | None:
        """Return the hop count derived from hop_start and hop_limit."""
        if self.hop_start is None or self.hop_limit is None:
            return None
        hops = self.hop_start - self.hop_limit
        return hops if hops >= 0 else None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""
        return {
            "packet_id": self.packet_id,
            "from_num": self.from_num,
            "from_id": self.from_id,
            "to_num": self.to_num,
            "to_id": self.to_id,
            "portnum": self.portnum,
            "channel": self.channel,
            "want_ack": self.want_ack,
            "via_mqtt": self.via_mqtt,
            "priority": self.priority,
            "hop_limit": self.hop_limit,
            "hop_start": self.hop_start,
            "rx_time": self.rx_time,
            "rx_snr": self.rx_snr,
            "rx_rssi": self.rx_rssi,
            "request_id": self.request_id,
            "reply_id": self.reply_id,
            "routing_error": self.routing_error,
            "text": self.text,
            "position": None if self.position is None else self.position.as_dict(),
            "telemetry": None if self.telemetry is None else self.telemetry.as_dict(),
            "received_at": _iso(self.received_at),
            "backlog": self.backlog,
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class MeshtasticMessage:
    """A text message payload, ready for an event entity or a bus event."""

    packet_id: int
    from_num: int
    from_id: str | None
    from_name: str | None
    to_num: int
    to_id: str | None
    channel: int
    text: str
    portnum: str
    reply_id: int | None = None
    rx_time: int | None = None
    rx_snr: float | None = None
    rx_rssi: int | None = None
    hops_away: int | None = None
    via_mqtt: bool = False
    received_at: datetime | None = None
    backlog: bool = False

    @property
    def is_broadcast(self) -> bool:
        """Return True when the message was addressed to everybody."""
        return self.to_num == 0xFFFFFFFF

    @classmethod
    def from_packet(
        cls, packet: MeshtasticPacket, *, from_name: str | None = None
    ) -> Self | None:
        """Build a message from a packet, or None when it carries no text."""
        if packet.text is None:
            return None
        return cls(
            packet_id=packet.packet_id,
            from_num=packet.from_num,
            from_id=packet.from_id,
            from_name=from_name,
            to_num=packet.to_num,
            to_id=packet.to_id,
            channel=packet.channel,
            text=packet.text,
            portnum=packet.portnum,
            reply_id=packet.reply_id,
            rx_time=packet.rx_time,
            rx_snr=packet.rx_snr,
            rx_rssi=packet.rx_rssi,
            hops_away=packet.hops_away,
            via_mqtt=packet.via_mqtt,
            received_at=packet.received_at,
            backlog=packet.backlog,
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""
        return {
            "packet_id": self.packet_id,
            "from_num": self.from_num,
            "from_id": self.from_id,
            "from_name": self.from_name,
            "to_num": self.to_num,
            "to_id": self.to_id,
            "channel": self.channel,
            "text": self.text,
            "portnum": self.portnum,
            "reply_id": self.reply_id,
            "rx_time": self.rx_time,
            "rx_snr": self.rx_snr,
            "rx_rssi": self.rx_rssi,
            "hops_away": self.hops_away,
            "via_mqtt": self.via_mqtt,
            "received_at": _iso(self.received_at),
            "backlog": self.backlog,
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class MeshtasticNotification:
    """A ``ClientNotification`` pushed by the firmware."""

    message: str
    level: str | None = None
    reply_id: int | None = None
    device_time: int | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class RequestResult:
    """Outcome of one correlated request."""

    packet_id: int
    kind: RequestKind
    state: RequestState
    destination: int
    #: Furthest non-terminal state reached; explains a timeout.
    reached: RequestState = RequestState.SENT
    error_reason: str | None = None
    notification: str | None = None
    response: MeshtasticPacket | None = None

    @property
    def delivered(self) -> bool:
        """Return True when the mesh confirmed delivery in some form."""
        return self.state in (
            RequestState.ACKED,
            RequestState.ACKED_IMPLICIT,
            RequestState.RESPONDED,
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""
        return {
            "packet_id": self.packet_id,
            "kind": str(self.kind),
            "state": str(self.state),
            "reached": str(self.reached),
            "destination": self.destination,
            "delivered": self.delivered,
            "error_reason": self.error_reason,
            "notification": self.notification,
            "response": None if self.response is None else self.response.as_dict(),
        }


# --------------------------------------------------------------------------
# Coordinator payload
# --------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True, slots=True)
class MeshtasticData:
    """Everything the coordinator publishes to entities."""

    gateway: GatewayInfo
    nodes: dict[str, MeshtasticNode] = field(default_factory=dict)

    def node(self, node_id: str) -> MeshtasticNode | None:
        """Return one node by its ``!xxxxxxxx`` id."""
        return self.nodes.get(node_id)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""
        return {
            "gateway": self.gateway.as_dict(),
            "nodes": {node_id: node.as_dict() for node_id, node in self.nodes.items()},
        }
