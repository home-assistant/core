"""Constants for the Meshtastic integration.

This module never imports the ``meshtastic`` library: the numeric portnums and
routing-error names below are copies of the library's enum values so that every
other module can talk about them without pulling in protobufs.
"""

from collections.abc import Mapping
import logging
from typing import Final

from homeassistant.const import Platform

from .models import RequestKind

DOMAIN: Final = "meshtastic"
LOGGER: Final = logging.getLogger(__package__)
MANUFACTURER: Final = "Meshtastic"

#: Platforms forwarded by ``async_setup_entry``.  A platform work package adds
#: its ``Platform`` member here at the same time as it adds ``<platform>.py``.
PLATFORMS: Final[list[Platform]] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.EVENT,
    Platform.NOTIFY,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TEXT,
]

# ---------------------------------------------------------------------------
# Config entry
# ---------------------------------------------------------------------------

CONFIG_ENTRY_VERSION: Final = 1
#: Bumped to 2 so that an entry the HACS custom integration left behind at
#: version 1.1 still goes through ``async_migrate_entry``: Home Assistant only
#: calls it when the stored version differs from the flow's.
CONFIG_ENTRY_MINOR_VERSION: Final = 2

#: Option: download the full node database at connect time.  Off by default
#: because low-memory nodes (a no-PSRAM T-Beam) crash on a full dump.
CONF_DOWNLOAD_NODE_DB: Final = "download_node_db"
#: Option: publish node positions as device trackers.  A tracker hands a node's
#: coordinates to everything that can read the state machine, and a Meshtastic
#: node is very often a person, so it can be switched off on its own.
CONF_TRACK_POSITION: Final = "track_position"
#: Option: put exact coordinates in the diagnostics download instead of
#: redacting them.  Off by default, because the download ends up in bug reports.
CONF_INCLUDE_LOCATION: Final = "include_location"

DEFAULT_PORT: Final = 4403
DEFAULT_DOWNLOAD_NODE_DB: Final = False
DEFAULT_TRACK_POSITION: Final = True
DEFAULT_INCLUDE_LOCATION: Final = False

#: Keys used by the HACS ``meshtastic`` custom integration, migrated by
#: ``async_migrate_entry``.
LEGACY_CONF_TCP_HOST: Final = "tcp_host"
LEGACY_CONF_TCP_PORT: Final = "tcp_port"

# ---------------------------------------------------------------------------
# Timeouts (seconds)
# ---------------------------------------------------------------------------

#: Upper bound on the blocking ``TCPInterface`` construction in the executor.
CONNECT_TIMEOUT: Final = 45.0
#: Value handed to ``TCPInterface(timeout=...)``; bounds the library's own waits.
LIBRARY_TIMEOUT: Final = 45
#: Upper bound on ``TCPInterface.close()`` in the executor.
CLOSE_TIMEOUT: Final = 5.0
#: Upper bound on any other single library call in the executor.
EXECUTOR_JOB_TIMEOUT: Final = 20.0

#: Heartbeat cadence.  The firmware drops idle TCP clients after 15 minutes.
HEARTBEAT_INTERVAL: Final = 90.0
#: How long to wait for evidence that a heartbeat was processed.
HEARTBEAT_RESPONSE_TIMEOUT: Final = 10.0
#: Consecutive unanswered heartbeats before the link is declared dead.
MAX_MISSED_HEARTBEATS: Final = 2
#: No inbound frame for this long means the link is dead (2 * heartbeat + 15 s).
LIVENESS_TIMEOUT: Final = 195.0

#: After a write that is known to reboot the node, probe fast for this long and
#: keep entities available instead of flapping to ``unavailable``.
REBOOT_GRACE: Final = 90.0
FAST_PROBE_INTERVAL: Final = 5.0

#: A packet whose ``rxTime`` is older than this is treated as connect backlog.
BACKLOG_MAX_AGE: Final = 60.0
#: Packets arriving within this window after a connect can also be backlog.
BACKLOG_CONNECT_WINDOW: Final = 2.0

#: A node not heard from for this long is considered offline (firmware default).
NODE_ONLINE_SECONDS: Final = 7200

# ---------------------------------------------------------------------------
# Reconnect backoff and circuit breaker
# ---------------------------------------------------------------------------

RECONNECT_MIN_DELAY: Final = 2.0
RECONNECT_MAX_INITIAL_DELAY: Final = 4.0
RECONNECT_BACKOFF_FACTOR: Final = 2.0
RECONNECT_MAX_DELAY: Final = 120.0
#: A connection that survives this long resets the backoff.
CONNECTION_STABLE_AFTER: Final = 60.0
#: Consecutive short-lived connections before the breaker opens.  The firmware
#: accepts one API client at a time, so a phone app or the CLI fighting us
#: produces exactly this pattern.
CIRCUIT_BREAKER_TRIPS: Final = 5
CIRCUIT_BREAKER_COOLDOWN: Final = 300.0

# ---------------------------------------------------------------------------
# Port numbers (``meshtastic.protobuf.portnums_pb2.PortNum``)
# ---------------------------------------------------------------------------

PORTNUM_UNKNOWN_APP: Final = 0
PORTNUM_TEXT_MESSAGE_APP: Final = 1
PORTNUM_REMOTE_HARDWARE_APP: Final = 2
PORTNUM_POSITION_APP: Final = 3
PORTNUM_NODEINFO_APP: Final = 4
PORTNUM_ROUTING_APP: Final = 5
PORTNUM_ADMIN_APP: Final = 6
PORTNUM_WAYPOINT_APP: Final = 8
PORTNUM_DETECTION_SENSOR_APP: Final = 10
PORTNUM_ALERT_APP: Final = 11
PORTNUM_PAXCOUNTER_APP: Final = 34
PORTNUM_STORE_FORWARD_APP: Final = 65
PORTNUM_RANGE_TEST_APP: Final = 66
PORTNUM_TELEMETRY_APP: Final = 67
PORTNUM_TRACEROUTE_APP: Final = 70
PORTNUM_NEIGHBORINFO_APP: Final = 71
PORTNUM_MAP_REPORT_APP: Final = 73
PORTNUM_PRIVATE_APP: Final = 256

#: Portnum number to the library's enum name, as it appears in packet dicts.
PORTNUM_NAMES: Final[Mapping[int, str]] = {
    PORTNUM_UNKNOWN_APP: "UNKNOWN_APP",
    PORTNUM_TEXT_MESSAGE_APP: "TEXT_MESSAGE_APP",
    PORTNUM_REMOTE_HARDWARE_APP: "REMOTE_HARDWARE_APP",
    PORTNUM_POSITION_APP: "POSITION_APP",
    PORTNUM_NODEINFO_APP: "NODEINFO_APP",
    PORTNUM_ROUTING_APP: "ROUTING_APP",
    PORTNUM_ADMIN_APP: "ADMIN_APP",
    PORTNUM_WAYPOINT_APP: "WAYPOINT_APP",
    PORTNUM_DETECTION_SENSOR_APP: "DETECTION_SENSOR_APP",
    PORTNUM_ALERT_APP: "ALERT_APP",
    PORTNUM_PAXCOUNTER_APP: "PAXCOUNTER_APP",
    PORTNUM_STORE_FORWARD_APP: "STORE_FORWARD_APP",
    PORTNUM_RANGE_TEST_APP: "RANGE_TEST_APP",
    PORTNUM_TELEMETRY_APP: "TELEMETRY_APP",
    PORTNUM_TRACEROUTE_APP: "TRACEROUTE_APP",
    PORTNUM_NEIGHBORINFO_APP: "NEIGHBORINFO_APP",
    PORTNUM_MAP_REPORT_APP: "MAP_REPORT_APP",
    PORTNUM_PRIVATE_APP: "PRIVATE_APP",
}

#: Library enum name back to the portnum number.
PORTNUM_VALUES: Final[Mapping[str, int]] = {
    name: value for value, name in PORTNUM_NAMES.items()
}

#: Portnums whose packets carry a text payload.
TEXT_PORTNUMS: Final[frozenset[int]] = frozenset(
    {
        PORTNUM_TEXT_MESSAGE_APP,
        PORTNUM_RANGE_TEST_APP,
        PORTNUM_DETECTION_SENSOR_APP,
    }
)

# ---------------------------------------------------------------------------
# Send pacing
# ---------------------------------------------------------------------------

#: Minimum seconds between two sends on the same portnum.  The firmware silently
#: drops packets that violate its own client rate limits (2 s for text, 10 s for
#: position/telemetry/waypoint/alert, 30 s for traceroute), so we stay just
#: outside them.
SEND_SPACING: Final[Mapping[int, float]] = {
    PORTNUM_TEXT_MESSAGE_APP: 2.5,
    PORTNUM_POSITION_APP: 10.5,
    PORTNUM_TELEMETRY_APP: 10.5,
    PORTNUM_WAYPOINT_APP: 10.5,
    PORTNUM_ALERT_APP: 10.5,
    PORTNUM_TRACEROUTE_APP: 31.0,
    PORTNUM_ADMIN_APP: 1.0,
}
DEFAULT_SEND_SPACING: Final = 0.0
#: Never wait longer than this for a pacing gate before giving up.
MAX_SEND_GATE_WAIT: Final = 35.0

#: Largest text payload the library accepts.
MAX_TEXT_PAYLOAD_BYTES: Final = 233
#: Safe limit for a PKI-encrypted direct message (12 bytes of PKI overhead).
MAX_DIRECT_TEXT_PAYLOAD_BYTES: Final = 200

# ---------------------------------------------------------------------------
# Request correlation
# ---------------------------------------------------------------------------

BROADCAST_NUM: Final = 0xFFFFFFFF
BROADCAST_ID: Final = "^all"
LOCAL_ID: Final = "^local"

#: Per-kind deadline, from the moment the packet left the executor.
REQUEST_TIMEOUTS: Final[Mapping[RequestKind, float]] = {
    RequestKind.TEXT_BROADCAST: 30.0,
    RequestKind.TEXT_DIRECT: 60.0,
    RequestKind.FIRE_AND_FORGET: 3.0,
    RequestKind.DIRECT_REQUEST: 60.0,
    RequestKind.TRACEROUTE: 90.0,
    RequestKind.ADMIN_LOCAL_GET: 10.0,
    RequestKind.ADMIN_LOCAL_SET: 10.0,
    RequestKind.ADMIN_REMOTE_GET: 60.0,
    RequestKind.ADMIN_REMOTE_SET: 60.0,
}
DEFAULT_REQUEST_TIMEOUT: Final = 60.0

# ``mesh_pb2.Routing.Error`` names, as they appear in packet dicts.
ROUTING_ERROR_NONE: Final = "NONE"
ROUTING_ERROR_NO_ROUTE: Final = "NO_ROUTE"
ROUTING_ERROR_GOT_NAK: Final = "GOT_NAK"
ROUTING_ERROR_TIMEOUT: Final = "TIMEOUT"
ROUTING_ERROR_NO_INTERFACE: Final = "NO_INTERFACE"
ROUTING_ERROR_MAX_RETRANSMIT: Final = "MAX_RETRANSMIT"
ROUTING_ERROR_NO_CHANNEL: Final = "NO_CHANNEL"
ROUTING_ERROR_TOO_LARGE: Final = "TOO_LARGE"
ROUTING_ERROR_NO_RESPONSE: Final = "NO_RESPONSE"
ROUTING_ERROR_DUTY_CYCLE_LIMIT: Final = "DUTY_CYCLE_LIMIT"
ROUTING_ERROR_BAD_REQUEST: Final = "BAD_REQUEST"
ROUTING_ERROR_NOT_AUTHORIZED: Final = "NOT_AUTHORIZED"
ROUTING_ERROR_PKI_FAILED: Final = "PKI_FAILED"
ROUTING_ERROR_PKI_UNKNOWN_PUBKEY: Final = "PKI_UNKNOWN_PUBKEY"
ROUTING_ERROR_ADMIN_BAD_SESSION_KEY: Final = "ADMIN_BAD_SESSION_KEY"
ROUTING_ERROR_ADMIN_PUBLIC_KEY_UNAUTHORIZED: Final = "ADMIN_PUBLIC_KEY_UNAUTHORIZED"
ROUTING_ERROR_RATE_LIMIT_EXCEEDED: Final = "RATE_LIMIT_EXCEEDED"
ROUTING_ERROR_PKI_SEND_FAIL_PUBLIC_KEY: Final = "PKI_SEND_FAIL_PUBLIC_KEY"

#: Pseudo reason used when the firmware answered with a ``ClientNotification``
#: instead of a routing packet (traceroute rate limit, duty cycle).
NOTIFICATION_REJECTED: Final = "CLIENT_NOTIFICATION"

#: ``Routing.Error`` name to the ``exceptions`` translation key in strings.json.
ROUTING_ERROR_TRANSLATION_KEYS: Final[Mapping[str, str]] = {
    ROUTING_ERROR_NO_ROUTE: "delivery_failed",
    ROUTING_ERROR_GOT_NAK: "delivery_failed",
    ROUTING_ERROR_TIMEOUT: "delivery_failed",
    ROUTING_ERROR_NO_INTERFACE: "no_radio",
    ROUTING_ERROR_MAX_RETRANSMIT: "not_acknowledged",
    ROUTING_ERROR_NO_CHANNEL: "invalid_channel",
    ROUTING_ERROR_TOO_LARGE: "packet_too_large",
    ROUTING_ERROR_NO_RESPONSE: "no_response",
    ROUTING_ERROR_DUTY_CYCLE_LIMIT: "duty_cycle_limit",
    ROUTING_ERROR_BAD_REQUEST: "rejected_bad_request",
    ROUTING_ERROR_NOT_AUTHORIZED: "admin_not_authorized",
    ROUTING_ERROR_PKI_FAILED: "pki_failed",
    ROUTING_ERROR_PKI_UNKNOWN_PUBKEY: "peer_missing_our_key",
    ROUTING_ERROR_ADMIN_BAD_SESSION_KEY: "admin_session_expired",
    ROUTING_ERROR_ADMIN_PUBLIC_KEY_UNAUTHORIZED: "admin_key_not_authorized",
    ROUTING_ERROR_RATE_LIMIT_EXCEEDED: "sending_too_fast",
    ROUTING_ERROR_PKI_SEND_FAIL_PUBLIC_KEY: "peer_key_unknown",
    NOTIFICATION_REJECTED: "client_rejected",
}

#: Routing errors that are the user's fault and must raise
#: ``ServiceValidationError`` rather than ``HomeAssistantError``.
ROUTING_ERROR_VALIDATION: Final[frozenset[str]] = frozenset(
    {
        ROUTING_ERROR_NO_CHANNEL,
        ROUTING_ERROR_TOO_LARGE,
        ROUTING_ERROR_BAD_REQUEST,
        NOTIFICATION_REJECTED,
    }
)

#: Translation key used when a request simply ran out of time, keyed by the
#: furthest state it reached.
TIMEOUT_TRANSLATION_KEYS: Final[Mapping[str, str]] = {
    "sent": "timeout_no_ack",
    "acked_implicit": "timeout_not_acknowledged",
    "acked": "timeout_no_response",
}
DEFAULT_ERROR_TRANSLATION_KEY: Final = "delivery_failed"

# ---------------------------------------------------------------------------
# Node registry storage
# ---------------------------------------------------------------------------

STORAGE_KEY_FORMAT: Final = f"{DOMAIN}.nodes.{{entry_id}}"
STORAGE_VERSION: Final = 1
STORAGE_MINOR_VERSION: Final = 1
#: Debounced save: one write at most every this many seconds, never starved.
STORAGE_SAVE_DELAY: Final = 45.0
#: LRU bound on the persisted node table.
MAX_STORED_NODES: Final = 500

# ---------------------------------------------------------------------------
# Bus event and attribute names
# ---------------------------------------------------------------------------

EVENT_MESHTASTIC: Final = "meshtastic_event"

ATTR_BACKLOG: Final = "backlog"
ATTR_CHANNEL: Final = "channel"
ATTR_ENTRY_ID: Final = "entry_id"
ATTR_EVENT_TYPE: Final = "event_type"
ATTR_FROM_ID: Final = "from_id"
ATTR_FROM_NUM: Final = "from_num"
ATTR_GATEWAY_ID: Final = "gateway_id"
ATTR_HOPS_AWAY: Final = "hops_away"
ATTR_HOP_LIMIT: Final = "hop_limit"
ATTR_HOP_START: Final = "hop_start"
ATTR_LOCATION_SOURCE: Final = "location_source"
ATTR_NODE_ID: Final = "node_id"
ATTR_NODE_NUM: Final = "node_num"
ATTR_PACKET_ID: Final = "packet_id"
ATTR_PORTNUM: Final = "portnum"
ATTR_PRECISION_BITS: Final = "precision_bits"
ATTR_PRIORITY: Final = "priority"
ATTR_REQUEST_ID: Final = "request_id"
ATTR_RSSI: Final = "rssi"
ATTR_SNR: Final = "snr"
ATTR_TEXT: Final = "text"
ATTR_TO_ID: Final = "to_id"
ATTR_TO_NUM: Final = "to_num"
ATTR_VIA_MQTT: Final = "via_mqtt"

# ---------------------------------------------------------------------------
# Identifier helpers
#
# Unique ids and device identifiers are built only from immutable numbers.  A
# node's names change all the time and must never appear in one of these.
# ---------------------------------------------------------------------------


def format_node_id(node_num: int) -> str:
    """Return the canonical ``!xxxxxxxx`` id of a node number."""
    return f"!{node_num & 0xFFFFFFFF:08x}"


def parse_node_id(node_id: str) -> int:
    """Return the node number of a ``!xxxxxxxx``/``0x``/hex node id.

    Raises ``ValueError`` when the id is not parseable.
    """
    candidate = node_id.strip()
    if candidate.startswith("!"):
        candidate = candidate[1:]
    elif candidate.lower().startswith("0x"):
        candidate = candidate[2:]
    if len(candidate) != 8:
        raise ValueError(f"Not a Meshtastic node id: {node_id}")
    return int(candidate, 16)


def gateway_device_id(gateway_num: int) -> str:
    """Return the device-registry identifier of the gateway node."""
    return format_node_id(gateway_num)


def node_device_id(gateway_num: int, node_num: int) -> str:
    """Return the device-registry identifier of a mesh node.

    Node devices are scoped to their gateway so that two config entries that
    both hear the same node do not fight over one device entry.
    """
    return f"{format_node_id(gateway_num)}_{format_node_id(node_num)}"


def gateway_unique_id(gateway_num: int, key: str) -> str:
    """Return the unique id of a gateway-scoped entity."""
    return f"{format_node_id(gateway_num)}_{key}"


def node_unique_id(gateway_num: int, node_num: int, key: str) -> str:
    """Return the unique id of a node-scoped entity."""
    return f"{node_device_id(gateway_num, node_num)}_{key}"
