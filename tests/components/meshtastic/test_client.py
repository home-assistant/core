"""Tests for the Meshtastic client's pure helpers and request tracker.

The conversion helpers turn the library's loosely typed dicts into the frozen
models the rest of the integration uses, and the tracker is what makes a send
answerable at all.  Both are exercised here without a radio: the packet dicts
are the real shapes the library produces, and the tracker runs entirely on the
event loop, which is where the pubsub listeners hand everything over.
"""

import asyncio
from datetime import timedelta
import threading
import time
from typing import Any
from unittest.mock import MagicMock, patch

from meshtastic.mesh_interface import MeshInterface
from meshtastic.protobuf import mesh_pb2
import pytest

from homeassistant.components.meshtastic.client import (
    NODES_ONLY_WANT_CONFIG_ID,
    MeshtasticClient,
    MeshtasticClientCallbacks,
    MeshtasticConnectionError,
    MeshtasticError,
    MeshtasticInterface,
    MeshtasticRequestError,
    PendingRequest,
    RequestTracker,
    _close_interface,
    _guarded,
    build_gateway_info,
    parse_node_info,
    parse_packet,
    parse_position,
    parse_telemetry,
    parse_user,
    raise_for_result,
)
from homeassistant.components.meshtastic.const import (
    BROADCAST_NUM,
    CLOSE_TIMEOUT,
    CONNECT_TIMEOUT,
    HEARTBEAT_INTERVAL,
    HEARTBEAT_RESPONSE_TIMEOUT,
    LIVENESS_TIMEOUT,
    MAX_MISSED_HEARTBEATS,
    MAX_SEND_GATE_WAIT,
    MAX_TEXT_PAYLOAD_BYTES,
    PORTNUM_TEXT_MESSAGE_APP,
    PORTNUM_TRACEROUTE_APP,
    QUEUE_REFUSED_TX_DISABLED,
    REBOOT_GRACE,
    RECONNECT_MAX_DELAY,
    REQUEST_TIMEOUTS,
    SEND_SPACING,
    SOCKET_CONNECT_TIMEOUT,
    TX_QUEUE_TIMEOUT,
)
from homeassistant.components.meshtastic.models import (
    ConnectionState,
    MeshtasticNotification,
    MeshtasticPacket,
    PositionSource,
    RequestKind,
    RequestResult,
    RequestState,
    TelemetryFamily,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util

from . import (
    GATEWAY_ID,
    GATEWAY_NUM,
    REMOTE_ID,
    REMOTE_NUM,
    TOPIC_CLIENT_NOTIFICATION,
    TOPIC_CONNECTION_ESTABLISHED,
    TOPIC_CONNECTION_LOST,
    TOPIC_NODE_UPDATED,
    TOPIC_RECEIVE,
    FakePubSub,
)

from tests.common import async_fire_time_changed

# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------


def test_parse_user_needs_an_id() -> None:
    """Test that a user record without a node id is unusable."""
    assert parse_user({}) is None
    assert parse_user({"id": 12345}) is None

    user = parse_user(
        {
            "id": REMOTE_ID,
            "longName": "Remote One",
            "shortName": "R1",
            "hwModel": "HELTEC_V3",
            "role": "CLIENT",
            "isLicensed": True,
            "publicKey": "AAAA",
        }
    )
    assert user is not None
    assert user.has_public_key is True
    assert user.is_licensed is True
    assert user.hardware_model == "HELTEC_V3"


def test_parse_user_ignores_non_string_enums() -> None:
    """Test that a numeric hardware model or role is dropped, not rendered."""
    user = parse_user({"id": REMOTE_ID, "hwModel": 4, "role": 1, "longName": ""})

    assert user is not None
    assert user.hardware_model is None
    assert user.role is None
    assert user.long_name is None
    assert user.has_public_key is False


def test_parse_position_from_scaled_integers() -> None:
    """Test that a position given only as 1e-7 integers is converted."""
    now = dt_util.utcnow()
    position = parse_position(
        {"latitudeI": 521234567, "longitudeI": 131234567, "precisionBits": 16},
        now=now,
        source=PositionSource.NODE_INFO,
    )

    assert position is not None
    assert position.latitude == pytest.approx(52.1234567)
    assert position.longitude == pytest.approx(13.1234567)
    assert position.source is PositionSource.NODE_INFO


def test_parse_position_needs_both_coordinates() -> None:
    """Test that a half position is no position."""
    now = dt_util.utcnow()

    assert parse_position({}, now=now) is None
    assert parse_position({"latitude": 52.1}, now=now) is None
    assert parse_position({"latitude": "north", "longitude": 13.1}, now=now) is None


def test_parse_telemetry_families_and_scalars() -> None:
    """Test that a telemetry dict becomes a snake-cased sample."""
    now = dt_util.utcnow()
    sample = parse_telemetry(
        {
            "time": 1757300000,
            "environmentMetrics": {
                "temperature": 21.5,
                "relativeHumidity": 44,
                "raw": object(),
                "unwanted": object(),
            },
        },
        now=now,
    )

    assert sample is not None
    assert sample.family is TelemetryFamily.ENVIRONMENT
    assert sample.device_time == 1757300000
    assert sample.values == {"temperature": 21.5, "relative_humidity": 44}


def test_parse_telemetry_without_a_known_family() -> None:
    """Test that a telemetry message this version cannot read is skipped."""
    assert parse_telemetry({"time": 1}, now=dt_util.utcnow()) is None


def test_parse_packet_needs_a_sender(packet_fixtures: dict[str, Any]) -> None:
    """Test that a packet dict with no sender is dropped."""
    now = dt_util.utcnow()

    assert parse_packet({}, now=now) is None
    assert parse_packet({"from": None}, now=now) is None


def test_parse_packet_of_an_encrypted_frame(
    packet_fixtures: dict[str, Any],
) -> None:
    """Test that an undecryptable packet still counts as the node being heard."""
    packet = parse_packet(packet_fixtures["packet_encrypted"], now=dt_util.utcnow())

    assert packet is not None
    assert packet.portnum == "UNKNOWN_APP"
    assert packet.text is None
    assert packet.user is None
    assert packet.position is None
    assert packet.telemetry is None


def test_parse_packet_marks_backlog(packet_fixtures: dict[str, Any]) -> None:
    """Test that the backlog flag is carried through."""
    packet = parse_packet(
        packet_fixtures["packet_text"], now=dt_util.utcnow(), backlog=True
    )

    assert packet is not None
    assert packet.backlog is True


def test_parse_packet_of_a_routing_answer(packet_fixtures: dict[str, Any]) -> None:
    """Test that an acknowledgement reports no error reason."""
    ack = parse_packet(packet_fixtures["packet_routing_ack"], now=dt_util.utcnow())
    nak = parse_packet(packet_fixtures["packet_routing_nak"], now=dt_util.utcnow())

    assert ack is not None
    assert ack.routing_error == "NONE"
    assert nak is not None
    assert nak.routing_error not in (None, "NONE")


def test_parse_node_info_needs_a_number(node_fixtures: dict[str, Any]) -> None:
    """Test that a node-DB record without a node number is unusable."""
    assert parse_node_info({}, now=dt_util.utcnow()) is None


def test_parse_node_info_without_a_user_is_presumptive() -> None:
    """Test that a node that never introduced itself stays presumptive."""
    node = parse_node_info(
        {"num": REMOTE_NUM, "snr": 5.25, "hopsAway": 2}, now=dt_util.utcnow()
    )

    assert node is not None
    assert node.presumptive is True
    assert node.node_id == REMOTE_ID
    assert node.snr == 5.25
    assert node.last_heard is None


def test_parse_node_info_reads_telemetry(node_fixtures: dict[str, Any]) -> None:
    """Test that the metrics on a node-DB record become telemetry samples."""
    node = parse_node_info(node_fixtures[REMOTE_ID], now=dt_util.utcnow())

    assert node is not None
    assert node.presumptive is False
    assert node.sample(TelemetryFamily.DEVICE) is not None


def test_build_gateway_info_without_my_info() -> None:
    """Test that a handshake that never reported an identity is an error."""
    interface = MagicMock()
    interface.myInfo = None

    with pytest.raises(MeshtasticConnectionError):
        build_gateway_info(interface)


# ---------------------------------------------------------------------------
# Executor plumbing
# ---------------------------------------------------------------------------


def test_guarded_converts_a_library_exit() -> None:
    """Test that the library's ``sys.exit()`` becomes a translated error.

    ``SystemExit`` derives from ``BaseException``; unguarded it would escape
    the executor job and take the event loop with it.
    """

    def _exits() -> None:
        raise SystemExit("bad input")

    with pytest.raises(MeshtasticError) as err:
        _guarded(_exits)

    assert err.value.translation_key == "library_aborted"
    assert _guarded(lambda: 42) == 42


def test_close_interface_swallows_everything() -> None:
    """Test that closing a wedged interface never raises.

    Unloading the config entry has to succeed even when the library throws on
    the way out.
    """
    exiting = MagicMock()
    exiting.close.side_effect = SystemExit("nope")
    failing = MagicMock()
    failing.close.side_effect = OSError("broken pipe")

    _close_interface(exiting)
    _close_interface(failing)


# ---------------------------------------------------------------------------
# raise_for_result
# ---------------------------------------------------------------------------


def _result(**changes: Any) -> RequestResult:
    """Return a request result with the given overrides."""
    base: dict[str, Any] = {
        "packet_id": 1,
        "kind": RequestKind.TEXT_DIRECT,
        "state": RequestState.NACKED,
        "destination": REMOTE_NUM,
    }
    return RequestResult(**{**base, **changes})


def test_raise_for_result_is_silent_when_delivered() -> None:
    """Test that a delivered request raises nothing."""
    raise_for_result(_result(state=RequestState.ACKED), node="Remote One")


@pytest.mark.parametrize(
    ("reason", "translation_key", "validation"),
    [
        ("NO_ROUTE", "delivery_failed", False),
        ("MAX_RETRANSMIT", "not_acknowledged", False),
        ("NO_CHANNEL", "invalid_channel", True),
        ("TOO_LARGE", "packet_too_large", True),
        ("RATE_LIMIT_EXCEEDED", "sending_too_fast", False),
        ("BAD_REQUEST", "rejected_bad_request", True),
        ("CLIENT_NOTIFICATION", "client_rejected", True),
        ("SOMETHING_NEW", "delivery_failed", False),
    ],
)
def test_raise_for_result_maps_every_routing_error(
    reason: str, translation_key: str, validation: bool
) -> None:
    """Test that each refusal becomes its own translated error.

    ``raise_for_result`` only ever supplies ``node``, ``reason`` and
    ``message``, so every key it can pick must be satisfied by those three.
    """
    with pytest.raises(HomeAssistantError) as err:
        raise_for_result(_result(error_reason=reason), node="Remote One")

    assert err.value.translation_key == translation_key
    assert isinstance(err.value, ServiceValidationError) is validation
    assert set(err.value.translation_placeholders or {}) == {
        "node",
        "reason",
        "message",
    }


@pytest.mark.parametrize(
    ("reached", "translation_key"),
    [
        (RequestState.SENT, "timeout_no_ack"),
        (RequestState.ACKED_IMPLICIT, "timeout_not_acknowledged"),
        (RequestState.ACKED, "timeout_no_response"),
        (RequestState.RESPONDED, "delivery_failed"),
    ],
)
def test_raise_for_result_explains_a_timeout(
    reached: RequestState, translation_key: str
) -> None:
    """Test that a timeout is explained by how far the request got."""
    with pytest.raises(MeshtasticRequestError) as err:
        raise_for_result(
            _result(state=RequestState.TIMED_OUT, reached=reached), node="Remote One"
        )

    assert err.value.translation_key == translation_key


# ---------------------------------------------------------------------------
# RequestTracker
# ---------------------------------------------------------------------------


def _routing(
    request_id: int, *, from_num: int, error: str = "NONE"
) -> MeshtasticPacket:
    """Return a routing packet answering one request."""
    return MeshtasticPacket(
        packet_id=request_id + 1,
        from_num=from_num,
        to_num=GATEWAY_NUM,
        portnum="ROUTING_APP",
        request_id=request_id,
        routing_error=error,
    )


def _tracker() -> RequestTracker:
    """Return a tracker that knows which node is ours."""
    tracker = RequestTracker()
    tracker.my_node_num = GATEWAY_NUM
    return tracker


async def test_tracker_direct_ack() -> None:
    """Test that a real acknowledgement from the destination completes."""
    tracker = _tracker()
    request = PendingRequest(
        packet_id=10, kind=RequestKind.TEXT_DIRECT, destination=REMOTE_NUM
    )
    tracker.async_register(request)

    task = asyncio.create_task(tracker.async_wait(request, 5))
    await asyncio.sleep(0)
    tracker.async_handle_packet(_routing(10, from_num=REMOTE_NUM))

    result = await task
    assert result.state is RequestState.ACKED
    assert result.delivered is True
    assert tracker.pending_count == 0


async def test_tracker_implicit_ack_only_completes_a_broadcast() -> None:
    """Test that our own node relaying a direct message is not an answer.

    The local node confirms it put the packet on the air, which is all there
    is for a broadcast, but a direct message still owes us a real ACK.
    """
    tracker = _tracker()
    broadcast = PendingRequest(
        packet_id=11, kind=RequestKind.TEXT_BROADCAST, destination=BROADCAST_NUM
    )
    tracker.async_register(broadcast)
    tracker.async_handle_packet(_routing(11, from_num=GATEWAY_NUM))
    assert broadcast.done is True
    assert broadcast.state is RequestState.ACKED_IMPLICIT

    direct = PendingRequest(
        packet_id=12, kind=RequestKind.TEXT_DIRECT, destination=REMOTE_NUM
    )
    tracker.async_register(direct)
    tracker.async_handle_packet(_routing(12, from_num=GATEWAY_NUM))
    assert direct.state is RequestState.ACKED_IMPLICIT
    assert direct.done is False
    assert direct.reached is RequestState.ACKED_IMPLICIT


async def test_tracker_local_request_is_acked_by_the_gateway() -> None:
    """Test that a request to our own node treats its routing reply as an ACK."""
    tracker = _tracker()
    request = PendingRequest(
        packet_id=13, kind=RequestKind.ADMIN_LOCAL_SET, destination=GATEWAY_NUM
    )
    tracker.async_register(request)
    tracker.async_handle_packet(_routing(13, from_num=GATEWAY_NUM))

    assert request.state is RequestState.ACKED
    assert request.done is True


async def test_tracker_response_completes_a_want_response_request() -> None:
    """Test that only the data packet completes a request that wants one."""
    tracker = _tracker()
    request = PendingRequest(
        packet_id=14,
        kind=RequestKind.DIRECT_REQUEST,
        destination=REMOTE_NUM,
        want_response=True,
    )
    tracker.async_register(request)

    tracker.async_handle_packet(_routing(14, from_num=REMOTE_NUM))
    assert request.done is False
    assert request.reached is RequestState.ACKED

    answer = MeshtasticPacket(
        packet_id=99,
        from_num=REMOTE_NUM,
        to_num=GATEWAY_NUM,
        portnum="POSITION_APP",
        request_id=14,
    )
    tracker.async_handle_packet(answer)
    assert request.state is RequestState.RESPONDED
    assert request.response is answer


async def test_tracker_a_late_implicit_ack_never_unsays_a_real_one() -> None:
    """Test that a second, weaker acknowledgement cannot move a request back.

    Our own node emits an implicit acknowledgement for every rebroadcast of our
    packet that it overhears, with no ordering against the destination's real
    one.  If the later one won, a request that was acknowledged and then went
    unanswered would be explained as never having been acknowledged, which is
    the opposite of what happened and the wrong advice for the user.
    """
    tracker = _tracker()
    request = PendingRequest(
        packet_id=20,
        kind=RequestKind.DIRECT_REQUEST,
        destination=REMOTE_NUM,
        want_response=True,
    )
    tracker.async_register(request)

    tracker.async_handle_packet(_routing(20, from_num=REMOTE_NUM))
    assert request.state is RequestState.ACKED
    # A relay rebroadcasts the request; our node confirms it overheard it.
    tracker.async_handle_packet(_routing(20, from_num=GATEWAY_NUM))

    assert request.state is RequestState.ACKED
    assert request.reached is RequestState.ACKED

    # The destination throttles the answer, so the request runs out of time.
    result = await tracker.async_wait(request, 0)

    with pytest.raises(MeshtasticRequestError) as err:
        raise_for_result(result, node=REMOTE_ID)
    assert err.value.translation_key == "timeout_no_response"


async def test_tracker_nak_is_terminal() -> None:
    """Test that a refusal ends the request and later packets are ignored."""
    tracker = _tracker()
    request = PendingRequest(
        packet_id=15, kind=RequestKind.TEXT_DIRECT, destination=REMOTE_NUM
    )
    tracker.async_register(request)

    tracker.async_handle_packet(_routing(15, from_num=REMOTE_NUM, error="NO_ROUTE"))
    tracker.async_handle_packet(_routing(15, from_num=REMOTE_NUM))

    assert request.state is RequestState.NACKED
    assert request.error_reason == "NO_ROUTE"


async def test_tracker_replays_an_answer_that_arrived_first() -> None:
    """Test the race where the mesh answers before the send call returned.

    The reader thread can decode the acknowledgement while the executor job
    that sent the packet has not handed the packet id back yet.
    """
    tracker = _tracker()
    tracker.async_handle_packet(_routing(16, from_num=REMOTE_NUM))

    request = PendingRequest(
        packet_id=16, kind=RequestKind.TEXT_DIRECT, destination=REMOTE_NUM
    )
    tracker.async_register(request)

    assert request.state is RequestState.ACKED


async def test_tracker_bounds_the_orphan_buffer() -> None:
    """Test that unclaimed answers cannot grow without bound."""
    tracker = _tracker()
    for request_id in range(1, 200):
        tracker.async_handle_packet(_routing(request_id, from_num=REMOTE_NUM))

    # The oldest are evicted, the newest are still replayable.
    request = PendingRequest(
        packet_id=199, kind=RequestKind.TEXT_DIRECT, destination=REMOTE_NUM
    )
    tracker.async_register(request)
    assert request.state is RequestState.ACKED

    stale = PendingRequest(
        packet_id=1, kind=RequestKind.TEXT_DIRECT, destination=REMOTE_NUM
    )
    tracker.async_register(stale)
    assert stale.state is RequestState.SENT

    tracker.async_cancel(stale.packet_id)
    tracker.async_cancel(request.packet_id)
    assert tracker.pending_count == 0


async def test_tracker_ignores_packets_without_a_request_id() -> None:
    """Test that ordinary mesh traffic does not disturb the tracker."""
    tracker = _tracker()
    tracker.async_handle_packet(
        MeshtasticPacket(
            packet_id=1, from_num=REMOTE_NUM, to_num=0, portnum="TEXT_MESSAGE_APP"
        )
    )

    assert tracker.pending_count == 0


async def test_tracker_notification_refuses_a_request() -> None:
    """Test that a firmware notification refuses the request it replies to."""
    tracker = _tracker()
    request = PendingRequest(
        packet_id=17, kind=RequestKind.TRACEROUTE, destination=REMOTE_NUM
    )
    tracker.async_register(request)

    # A notification for something else, and one for nothing at all.
    tracker.async_handle_notification(MeshtasticNotification(message="hi"))
    tracker.async_handle_notification(
        MeshtasticNotification(message="hi", reply_id=999)
    )
    assert request.state is RequestState.SENT

    tracker.async_handle_notification(
        MeshtasticNotification(message="Traceroute rate limit", reply_id=17)
    )
    assert request.state is RequestState.NACKED
    assert request.error_reason == "CLIENT_NOTIFICATION"
    assert request.notification == "Traceroute rate limit"


async def test_tracker_times_out() -> None:
    """Test that a request nobody answers ends as a timeout."""
    tracker = _tracker()
    request = PendingRequest(
        packet_id=18, kind=RequestKind.TEXT_DIRECT, destination=REMOTE_NUM
    )
    tracker.async_register(request)

    result = await tracker.async_wait(request, 0)

    assert result.state is RequestState.TIMED_OUT
    assert result.reached is RequestState.SENT
    assert tracker.pending_count == 0


async def test_tracker_clear_wakes_every_waiter() -> None:
    """Test that losing the link times out everything in flight."""
    tracker = _tracker()
    request = PendingRequest(
        packet_id=19, kind=RequestKind.TEXT_DIRECT, destination=REMOTE_NUM
    )
    tracker.async_register(request)
    task = asyncio.create_task(tracker.async_wait(request, 30))
    await asyncio.sleep(0)

    tracker.async_clear()
    result = await task

    assert result.state is RequestState.TIMED_OUT
    assert tracker.pending_count == 0


# ---------------------------------------------------------------------------
# Client behaviour that needs no radio
# ---------------------------------------------------------------------------


@pytest.fixture
def client(hass: HomeAssistant) -> MeshtasticClient:
    """Return a client that has never connected."""
    return MeshtasticClient(hass, "192.0.2.10", 4403)


def test_resolve_destination(client: MeshtasticClient) -> None:
    """Test every destination spelling the client accepts."""
    assert client.resolve_destination(REMOTE_NUM) == REMOTE_NUM
    assert client.resolve_destination(REMOTE_ID) == REMOTE_NUM
    assert client.resolve_destination("0xaabbccdd") == REMOTE_NUM
    assert client.resolve_destination("aabbccdd") == REMOTE_NUM
    assert client.resolve_destination("^all") == BROADCAST_NUM
    assert client.resolve_destination("broadcast") == BROADCAST_NUM
    assert client.resolve_destination("all") == BROADCAST_NUM


def test_resolve_destination_refuses_a_name(client: MeshtasticClient) -> None:
    """Test that a node name is refused rather than handed to the library.

    The library looks names up in its own table and calls ``sys.exit()`` on a
    miss, so a name must never get that far.
    """
    with pytest.raises(ServiceValidationError) as err:
        client.resolve_destination("Remote One")

    assert err.value.translation_key == "unknown_node"


@pytest.mark.parametrize(
    "destination", ["!-1234567", "!+1234567", "!12_34567", "! 1234567", "0x-1234567"]
)
def test_resolve_destination_refuses_a_signed_node_id(
    client: MeshtasticClient, destination: str
) -> None:
    """Test that a node id has to be eight hexadecimal digits and nothing else.

    ``int(candidate, 16)`` also accepts a sign, whitespace and underscore
    separators, so an id like ``!-1234567`` used to resolve to a negative node
    number that no later check rejects.  It is assigned straight to ``uint32``
    protobuf fields, which raises a bare ``ValueError`` out of an executor job
    instead of the translated message every other malformed id produces.
    """
    with pytest.raises(ServiceValidationError) as err:
        client.resolve_destination(destination)

    assert err.value.translation_key == "unknown_node"


async def test_sending_without_a_link_is_an_error(client: MeshtasticClient) -> None:
    """Test that every send refuses while the link is down."""
    with pytest.raises(MeshtasticConnectionError) as err:
        await client.async_send_text("hi")
    assert err.value.translation_key == "not_connected"

    with pytest.raises(MeshtasticConnectionError):
        await client.async_send_data(b"", portnum=PORTNUM_TEXT_MESSAGE_APP)

    with pytest.raises(MeshtasticConnectionError):
        await client.async_refresh_nodes()


async def test_text_longer_than_a_packet_is_refused(client: MeshtasticClient) -> None:
    """Test that an oversized message is rejected before anything is sent."""
    with pytest.raises(ServiceValidationError) as err:
        await client.async_send_text("x" * (MAX_TEXT_PAYLOAD_BYTES + 1))

    assert err.value.translation_key == "message_too_long"
    assert err.value.translation_placeholders == {
        "length": str(MAX_TEXT_PAYLOAD_BYTES + 1),
        "limit": str(MAX_TEXT_PAYLOAD_BYTES),
    }


async def test_send_gate_refuses_an_impossible_wait(client: MeshtasticClient) -> None:
    """Test that a pacing gate longer than the cap fails fast.

    Waiting a minute inside an action would look like a hang; the caller is
    told to try again instead.
    """
    client._port_gate[PORTNUM_TEXT_MESSAGE_APP] = (
        asyncio.get_running_loop().time() + MAX_SEND_GATE_WAIT + 300
    )

    with pytest.raises(MeshtasticRequestError) as err:
        await client._async_wait_for_gate(PORTNUM_TEXT_MESSAGE_APP)

    assert err.value.translation_key == "rate_limited"


async def test_stats_before_the_first_connect(client: MeshtasticClient) -> None:
    """Test the diagnostics payload of a client that never connected."""
    stats = client.stats()

    assert stats["state"] == "disconnected"
    assert stats["connected_for"] is None
    assert stats["pending_requests"] == 0
    assert client.connected is False
    assert client.available is False
    assert client.gateway is None


async def test_reboot_grace_keeps_the_client_available(
    client: MeshtasticClient,
) -> None:
    """Test that a reboot we asked for does not make everything unavailable."""
    assert client.reboot_grace_active is False

    client.async_note_reboot_expected()

    assert client.reboot_grace_active is True
    assert client.available is True
    assert client.stats()["reboot_grace_active"] is True


async def test_the_reboot_grace_covers_the_delay_the_node_was_given(
    client: MeshtasticClient,
) -> None:
    """Test that a reboot scheduled for later keeps its grace window open.

    The ``reboot`` action passes a delay of up to five minutes to the node,
    which then carries on as normal until it expires.  A window measured only
    from now closes while the node is still running, so every entity flaps to
    unavailable at exactly the moment the window exists to cover, and the
    duplicate-reboot guard reopens while the first reboot is still pending.
    """
    with patch("homeassistant.components.meshtastic.client.time.monotonic") as clock:
        clock.return_value = 0.0
        client.async_note_reboot_expected(delay=120.0)

        clock.return_value = REBOOT_GRACE + 1.0
        assert client.reboot_grace_active is True
        assert client.available is True

        clock.return_value = 120.0 + REBOOT_GRACE + 1.0
        assert client.reboot_grace_active is False


async def test_pubsub_listeners_ignore_a_foreign_interface(
    hass: HomeAssistant,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    packet_fixtures: dict[str, Any],
) -> None:
    """Test that traffic from a previous connection is dropped.

    A reconnect builds a new interface; the old one's reader thread can still
    publish for a moment.  pypubsub delivers to every subscriber of a topic,
    so the only thing that keeps a stale reader out is the identity check on
    the interface each listener starts with.  The client has to be connected
    for that check to mean anything, and every callback has to be watched:
    a packet from a dead link would be merged into the node table, and a
    ``connection.lost`` from it would tear the live link down.
    """
    seen: dict[str, list[Any]] = {
        "packet": [],
        "node": [],
        "notification": [],
        "disconnected": [],
    }
    client = MeshtasticClient(
        hass,
        "192.0.2.10",
        4403,
        callbacks=MeshtasticClientCallbacks(
            packet=seen["packet"].append,
            node_updated=seen["node"].append,
            notification=seen["notification"].append,
            disconnected=seen["disconnected"].append,
        ),
    )
    await client.async_start()
    # The handshake seeds the node table, so only what arrives after this
    # point can have come from the stale interface.
    seen["node"].clear()
    stale = MagicMock(spec=MeshInterface)

    mock_pubsub.sendMessage(
        TOPIC_RECEIVE, packet=packet_fixtures["packet_text"], interface=stale
    )
    mock_pubsub.sendMessage(
        TOPIC_NODE_UPDATED, node={"num": REMOTE_NUM}, interface=stale
    )
    mock_pubsub.sendMessage(
        TOPIC_CLIENT_NOTIFICATION,
        notification=mesh_pb2.ClientNotification(),
        interface=stale,
    )
    mock_pubsub.sendMessage(TOPIC_CONNECTION_LOST, interface=stale)
    mock_pubsub.sendMessage(TOPIC_CONNECTION_ESTABLISHED, interface=stale)
    await hass.async_block_till_done()

    assert seen == {
        "packet": [],
        "node": [],
        "notification": [],
        "disconnected": [],
    }
    assert client.connection_state is ConnectionState.CONNECTED

    # The live interface is still heard, so the filter is not simply off.
    client._last_rx = time.monotonic() - HEARTBEAT_INTERVAL
    mock_pubsub.sendMessage(
        TOPIC_RECEIVE,
        packet=packet_fixtures["packet_text"],
        interface=mock_meshtastic_client,
    )
    mock_pubsub.sendMessage(
        TOPIC_CONNECTION_ESTABLISHED, interface=mock_meshtastic_client
    )
    await hass.async_block_till_done()

    assert len(seen["packet"]) == 1
    # Both handlers count as the link having produced traffic.
    assert time.monotonic() - client._last_rx < HEARTBEAT_INTERVAL

    await client.async_stop()


async def test_refresh_nodes_uses_the_nodes_only_nonce(
    hass: HomeAssistant, mock_meshtastic_client: MagicMock
) -> None:
    """Test that refreshing the node table asks for the node database only.

    The full-handshake nonce would make the library drop ``myInfo`` and the
    whole node table first.
    """
    client = MeshtasticClient(hass, "192.0.2.10", 4403)
    await client.async_start()
    try:
        await client.async_refresh_nodes()
    finally:
        await client.async_stop()

    sent = mock_meshtastic_client._sendToRadio.call_args[0][0]
    assert sent.want_config_id == NODES_ONLY_WANT_CONFIG_ID


async def test_start_reports_a_node_that_never_identified_itself(
    hass: HomeAssistant, mock_meshtastic_client: MagicMock
) -> None:
    """Test that a handshake without an identity is a connection error.

    The interface is closed again rather than left behind with its reader
    thread running.
    """
    mock_meshtastic_client.myInfo = None
    client = MeshtasticClient(hass, "192.0.2.10", 4403)

    with pytest.raises(MeshtasticConnectionError) as err:
        await client.async_start()

    assert err.value.translation_key == "no_node_info"
    assert mock_meshtastic_client.close.called
    # Nothing is left subscribed or running to clean up.
    await client.async_stop()


async def test_stop_is_idempotent(
    hass: HomeAssistant, mock_meshtastic_client: MagicMock
) -> None:
    """Test that stopping twice is harmless."""
    client = MeshtasticClient(hass, "192.0.2.10", 4403)
    await client.async_start()

    await client.async_stop()
    await client.async_stop()

    assert client.connected is False
    assert mock_meshtastic_client.close.call_count == 1


async def test_gateway_identity_is_read_from_the_node(
    hass: HomeAssistant, mock_meshtastic_client: MagicMock
) -> None:
    """Test the identity the client publishes after a handshake.

    Disabled channel slots are left out and no pre-shared key is carried.
    """
    client = MeshtasticClient(hass, "192.0.2.10", 4403)
    await client.async_start()
    gateway = client.gateway
    await client.async_stop()

    assert gateway is not None
    assert gateway.node_id == GATEWAY_ID
    assert gateway.node_num == GATEWAY_NUM
    assert gateway.hardware_model == "TBEAM"
    assert gateway.firmware_version == "2.7.26.54e0d8d"
    assert gateway.region == "EU_868"
    assert gateway.modem_preset == "LONG_FAST"
    assert [channel.index for channel in gateway.channels] == [0, 1]
    assert all("psk" not in channel.as_dict() for channel in gateway.channels)


# ---------------------------------------------------------------------------
# Heartbeat and liveness
# ---------------------------------------------------------------------------


async def _settle(hass: HomeAssistant) -> None:
    """Let the client's background tasks run.

    The heartbeat and the reconnect supervisor are background tasks, which
    ``async_block_till_done`` deliberately does not wait for.
    """
    for _ in range(5):
        await asyncio.sleep(0)
    await hass.async_block_till_done()


async def _advance(hass: HomeAssistant, seconds: float) -> None:
    """Fire every timer due within ``seconds`` and let it play out."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await _settle(hass)


async def _heartbeat_cycle(hass: HomeAssistant) -> None:
    """Drive one whole heartbeat: the probe and the wait for an answer.

    The loop arms the second timer only once the first has fired, so each of
    the two waits needs its own turn of the clock.
    """
    await _advance(hass, HEARTBEAT_INTERVAL + 1)
    await _advance(hass, HEARTBEAT_RESPONSE_TIMEOUT + 1)


async def test_a_heartbeat_the_node_refuses_kills_the_link(
    hass: HomeAssistant, mock_meshtastic_client: MagicMock
) -> None:
    """Test that a heartbeat the socket refuses is reported as a dead link."""
    reasons: list[str] = []
    client = MeshtasticClient(
        hass,
        "192.0.2.10",
        4403,
        callbacks=MeshtasticClientCallbacks(disconnected=reasons.append),
    )
    await client.async_start()
    mock_meshtastic_client.sendHeartbeat.side_effect = OSError("broken pipe")

    await _advance(hass, HEARTBEAT_INTERVAL + 1)
    assert mock_meshtastic_client.sendHeartbeat.called

    assert client.connection_state is ConnectionState.RECONNECTING
    assert reasons and reasons[0].startswith("heartbeat failed")
    assert client.stats()["dead_reason"].startswith("heartbeat failed")

    await client.async_stop()


async def test_a_silent_node_is_declared_dead(
    hass: HomeAssistant, mock_meshtastic_client: MagicMock
) -> None:
    """Test that heartbeats nobody answers eventually end the link.

    The firmware bumps its queue status on every heartbeat it processes, so a
    status that never changes is the only evidence that the link is wedged
    while the socket is still open.  How long ago the last frame arrived is
    measured on the monotonic clock, which ``async_fire_time_changed`` does not
    move, so the arrival time is put in the past instead.
    """
    reasons: list[str] = []
    client = MeshtasticClient(
        hass,
        "192.0.2.10",
        4403,
        callbacks=MeshtasticClientCallbacks(disconnected=reasons.append),
    )
    await client.async_start()

    for _ in range(MAX_MISSED_HEARTBEATS):
        client._last_rx = time.monotonic() - HEARTBEAT_INTERVAL - 5
        await _heartbeat_cycle(hass)

    assert client.stats()["missed_heartbeats"] >= MAX_MISSED_HEARTBEATS
    assert client.connection_state is ConnectionState.RECONNECTING
    assert reasons and reasons[0].startswith("no data from the node")

    await client.async_stop()


async def test_a_node_past_the_liveness_timeout_is_declared_dead(
    hass: HomeAssistant, mock_meshtastic_client: MagicMock
) -> None:
    """Test that a long enough silence ends the link on the first probe."""
    client = MeshtasticClient(hass, "192.0.2.10", 4403)
    await client.async_start()

    client._last_rx = time.monotonic() - LIVENESS_TIMEOUT - 5
    await _heartbeat_cycle(hass)

    assert client.connection_state is ConnectionState.RECONNECTING
    assert client.stats()["dead_reason"].startswith("no data from the node")

    await client.async_stop()


async def test_an_answered_heartbeat_resets_the_counter(
    hass: HomeAssistant, mock_meshtastic_client: MagicMock
) -> None:
    """Test that a node whose queue status moves is treated as alive.

    The firmware answers every heartbeat with a ``FromRadio.queueStatus``
    frame, and the library replaces ``interface.queueStatus`` with the new
    message.  On a quiet mesh nothing else arrives, so that replacement is the
    only evidence that the link still works - which is why the answer has to
    land *between* the probe and the check, exactly as the node produces it.

    The link must survive more than ``MAX_MISSED_HEARTBEATS`` such rounds
    without being declared dead: a reconnect would also leave the client
    connected with the counter back at zero, so the number of connection
    attempts is what tells the two apart.
    """
    client = MeshtasticClient(hass, "192.0.2.10", 4403)
    await client.async_start()
    free = 16

    def _answer_with_a_queue_status() -> None:
        """Reply to the heartbeat the way the node does."""
        nonlocal free
        free -= 1
        mock_meshtastic_client.queueStatus = mesh_pb2.QueueStatus(free=free, maxlen=16)

    mock_meshtastic_client.sendHeartbeat.side_effect = _answer_with_a_queue_status
    rounds = MAX_MISSED_HEARTBEATS + 2

    for _ in range(rounds):
        # Nothing else is received, so the last frame keeps receding.
        client._last_rx = time.monotonic() - HEARTBEAT_INTERVAL - 5
        await _heartbeat_cycle(hass)

    assert client.connected is True
    assert client.stats()["missed_heartbeats"] == 0
    assert mock_meshtastic_client.sendHeartbeat.call_count == rounds
    # Still the very first connection: the link was never dropped and rebuilt.
    assert client.stats()["reconnect_attempts"] == 1

    await client.async_stop()


async def test_a_close_that_hangs_cannot_hold_up_the_stop(
    hass: HomeAssistant,
    mock_meshtastic_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a wedged ``close()`` does not block unloading the entry.

    ``TCPInterface.close()`` joins the library's reader thread with no
    timeout, so a reader stuck inside a subscriber never comes back.  The
    close therefore runs in the executor under ``CLOSE_TIMEOUT``; past that
    the interface is abandoned and the stop completes anyway.
    """
    client = MeshtasticClient(hass, "192.0.2.10", 4403)
    await client.async_start()

    release = threading.Event()
    mock_meshtastic_client.close.side_effect = lambda: release.wait(10)

    try:
        stopping = hass.async_create_task(client.async_stop())
        for _ in range(20):
            await asyncio.sleep(0)
            if stopping.done():
                break
            async_fire_time_changed(
                hass, dt_util.utcnow() + timedelta(seconds=CLOSE_TIMEOUT + 1)
            )
        await stopping
    finally:
        release.set()

    assert mock_meshtastic_client.close.call_count == 1
    assert client.connection_state is ConnectionState.DISCONNECTED
    assert "Timed out closing the connection" in caplog.text


async def test_a_failed_reconnect_is_retried(
    hass: HomeAssistant, mock_meshtastic_client: MagicMock
) -> None:
    """Test that the supervisor keeps trying after a reconnect is refused."""
    client = MeshtasticClient(hass, "192.0.2.10", 4403)
    await client.async_start()
    interface_class = mock_meshtastic_client.interface_class
    interface_class.side_effect = OSError("connection refused")

    client._async_mark_dead("test")
    await _settle(hass)
    await _advance(hass, RECONNECT_MAX_DELAY + 1)
    assert client.connection_state is ConnectionState.RECONNECTING

    interface_class.side_effect = None
    await _advance(hass, RECONNECT_MAX_DELAY + 1)

    assert client.connected is True
    assert client.stats()["reconnect_attempts"] >= 3

    await client.async_stop()


# ---------------------------------------------------------------------------
# The interface subclass, driven for real
#
# These tests deliberately build a real ``MeshtasticInterface``.  Everything
# else in this package mocks the library at the class boundary, which is
# exactly why the library's own unbounded waits and in-place reconnect went
# unnoticed: no mock can reproduce them.  ``connectNow=False`` opens no socket
# and starts no thread, so nothing here touches the network.
# ---------------------------------------------------------------------------


def _offline_interface() -> MeshtasticInterface:
    """Return an interface that has never been connected."""
    return MeshtasticInterface("192.0.2.10", connectNow=False)


def test_every_library_hook_the_interface_overrides_still_exists() -> None:
    """Test that the pinned library still has the private methods we replace.

    ``MeshtasticInterface`` exists because three of the library's blocking or
    self-healing behaviours have no public switch, and ``async_refresh_nodes``
    frames its own ``ToRadio`` for ``_sendToRadio``.  A rename in a library
    update would leave every override in place, overriding nothing, and the
    failure would surface as an untranslated ``AttributeError`` from inside an
    executor job.  Fail the version bump here instead.
    """
    bases = MeshtasticInterface.__mro__[1:]

    for name in (
        "myConnect",
        "close",
        "_reconnect",
        "_socket_shutdown",
        "_sendToRadio",
        "_queueHasFreeSpace",
    ):
        assert any(name in base.__dict__ for base in bases), (
            f"meshtastic no longer defines {name}"
        )


def test_the_connect_is_bounded_and_reads_stay_blocking() -> None:
    """Test that the socket connect cannot outlive the client's own timeout.

    ``TCPInterface.myConnect`` hands no timeout to ``socket.create_connection``,
    so an unreachable node holds an executor thread for the operating system's
    SYN timeout - minutes - while the supervisor is already opening the next
    connection.
    """
    interface = _offline_interface()
    with patch(
        "homeassistant.components.meshtastic.client.socket.create_connection"
    ) as create_connection:
        interface.myConnect()

    assert create_connection.call_args.args[0] == ("192.0.2.10", 4403)
    assert create_connection.call_args.kwargs["timeout"] == SOCKET_CONNECT_TIMEOUT
    # A connect timeout must not become a read timeout: the reader thread
    # blocks on a quiet but healthy link, and would tear it down otherwise.
    create_connection.return_value.settimeout.assert_called_once_with(None)
    assert interface.socket is create_connection.return_value


def test_a_dropped_socket_ends_the_interface_instead_of_reconnecting() -> None:
    """Test that the library never re-handshakes behind the client's back.

    ``TCPInterface._readBytes`` calls ``_reconnect()`` on end-of-stream, which
    sleeps a second and opens a new socket on the reader thread without
    publishing ``meshtastic.connection.lost``.  The client's supervisor,
    backoff and circuit breaker would never see the drop.
    """
    interface = _offline_interface()
    interface.socket = MagicMock()
    interface.socket.recv.return_value = b""

    assert interface._readBytes(1) == b""

    # _wantExit is what makes the reader fall out of its loop, and its
    # ``finally`` is what publishes meshtastic.connection.lost.
    assert interface._wantExit is True
    interface.socket.shutdown.assert_called_once()


def test_the_transmit_queue_wait_reports_what_the_radio_said() -> None:
    """Test the three answers the bounded transmit-queue wait can give."""
    interface = _offline_interface()

    # Nothing reported yet: the library sends and finds out.
    assert interface._queueHasFreeSpace() is True

    interface.queueStatus = mesh_pb2.QueueStatus(free=0, maxlen=16)
    interface._tx_deadline = time.monotonic() + TX_QUEUE_TIMEOUT
    # Full, but still within the deadline: wait, exactly as the library does.
    assert interface._queueHasFreeSpace() is False

    # Closing: never wait.  Nothing written now can reach the node anyway.
    interface._closing_down = True
    assert interface._queueHasFreeSpace() is True


def test_a_full_transmit_queue_cannot_wedge_the_close() -> None:
    """Test that closing a node with a full transmit queue always returns.

    ``MeshInterface.close()`` sends a disconnect frame, and ``_sendToRadio``
    waits for transmit-queue space in an unbounded ``time.sleep(0.5)`` loop.
    ``TCPInterface.close()`` has already dropped the socket and joined the
    reader by then, so ``queueStatus.free`` can never be refreshed and the
    executor thread is lost for the life of the process.
    """
    interface = _offline_interface()
    # The firmware answers every packet with a QueueStatus, and the library
    # leaves a ``False`` marker behind for each one it did not expect.
    interface.queue[0x1234] = False
    interface.queueStatus = mesh_pb2.QueueStatus(free=0, maxlen=16)

    # Daemon, so that a regression fails the test instead of hanging pytest.
    closing = threading.Thread(
        target=interface.close, name="close under test", daemon=True
    )
    closing.start()
    closing.join(timeout=10)

    assert not closing.is_alive()
    assert interface.queue == {}


def test_a_full_transmit_queue_fails_the_send_instead_of_waiting() -> None:
    """Test that a congested radio fails a send rather than parking a thread."""
    interface = _offline_interface()
    interface.queue[0x1234] = mesh_pb2.ToRadio()
    interface.queueStatus = mesh_pb2.QueueStatus(free=0, maxlen=16)

    with (
        patch("homeassistant.components.meshtastic.client.TX_QUEUE_TIMEOUT", 0.0),
        pytest.raises(MeshInterface.MeshInterfaceError),
    ):
        interface.sendHeartbeat()

    assert interface.queue == {}


def test_the_interface_records_the_packet_id_it_framed() -> None:
    """Test the id a library helper that returns nothing leaves behind.

    ``Node.writeConfig()`` sends its ``AdminMessage`` and returns ``None``, and
    the library offers only ``currentPacketId`` - a counter
    ``_generatePacketId()`` advances for every caller on every thread.  Every
    mesh packet passes through ``_sendToRadio``, so the id of the one that was
    really framed is recorded there instead.
    """
    interface = _offline_interface()
    # No socket: _writeBytes returns without writing, so nothing leaves here.
    assert interface.socket is None
    assert interface.last_packet_id == 0

    interface._sendToRadio(mesh_pb2.ToRadio(packet=mesh_pb2.MeshPacket(id=0xABCDEF01)))
    assert interface.last_packet_id == 0xABCDEF01

    # A frame with no packet carries no id: the heartbeat the library's own
    # timer thread sends must not erase the last one.
    interface.sendHeartbeat()
    assert interface.last_packet_id == 0xABCDEF01


# ---------------------------------------------------------------------------
# Connect
# ---------------------------------------------------------------------------


def _stream_the_node_db(interface_class: MagicMock, pubsub: FakePubSub) -> None:
    """Publish every node record from inside the constructor, as the node does.

    The whole database arrives while ``StreamInterface.__init__`` is still
    blocked in ``waitForConfig()``, which is the reason none of it can be
    picked up from the pubsub topic.
    """
    build = interface_class.side_effect

    def _construct(*args: Any, **kwargs: Any) -> MagicMock:
        interface = build(*args, **kwargs)
        for node in list(interface.nodesByNum.values()):
            pubsub.sendMessage(TOPIC_NODE_UPDATED, node=node, interface=interface)
        return interface

    interface_class.side_effect = _construct


async def test_the_node_database_the_handshake_streamed_is_kept(
    hass: HomeAssistant,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that turning the node database on actually produces nodes.

    Every ``meshtastic.node.updated`` the handshake publishes arrives before
    the client owns the interface, so the identity check in the listener drops
    all of them; nothing else read the library's table.  The option shipped as
    a complete no-op.
    """
    seen: list[Any] = []
    _stream_the_node_db(mock_meshtastic_client.interface_class, mock_pubsub)
    client = MeshtasticClient(
        hass,
        "192.0.2.10",
        4403,
        download_node_db=True,
        callbacks=MeshtasticClientCallbacks(node_updated=seen.append),
    )

    await client.async_start()

    assert {node.node_id for node in seen} == set(node_fixtures)
    assert mock_meshtastic_client.interface_class.call_args.kwargs["noNodes"] is False

    await client.async_stop()


async def test_the_gateway_node_info_survives_a_nodeless_connect(
    hass: HomeAssistant,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
) -> None:
    """Test that the node's own record is kept even without the database.

    The nodeless nonce still streams the gateway's own ``NodeInfo`` - its
    position, its device metrics and its favourite/ignored flags - and it was
    being discarded on every single connect.
    """
    seen: list[Any] = []
    _stream_the_node_db(mock_meshtastic_client.interface_class, mock_pubsub)
    client = MeshtasticClient(
        hass,
        "192.0.2.10",
        4403,
        callbacks=MeshtasticClientCallbacks(node_updated=seen.append),
    )

    await client.async_start()

    assert [node.node_id for node in seen] == [GATEWAY_ID]
    assert mock_meshtastic_client.interface_class.call_args.kwargs["noNodes"] is True

    await client.async_stop()


async def test_a_connection_that_arrives_too_late_is_closed(
    hass: HomeAssistant, mock_meshtastic_client: MagicMock
) -> None:
    """Test that a handshake finishing after the timeout is not abandoned.

    An executor job cannot be cancelled.  When the connect overruns
    ``CONNECT_TIMEOUT`` - a node mid-reboot, or a large node database over a
    congested link - the interface the worker eventually returns owns a live
    socket, a reader thread and the library's own heartbeat timer, and nothing
    would ever close it.
    """
    release = threading.Event()
    build = mock_meshtastic_client.interface_class.side_effect

    def _slow_handshake(*args: Any, **kwargs: Any) -> MagicMock:
        release.wait(10)
        return build(*args, **kwargs)

    mock_meshtastic_client.interface_class.side_effect = _slow_handshake
    client = MeshtasticClient(hass, "192.0.2.10", 4403)

    try:
        starting = hass.async_create_task(client.async_start())
        for _ in range(20):
            await asyncio.sleep(0)
            if starting.done():
                break
            await _advance(hass, CONNECT_TIMEOUT + 1)
        with pytest.raises(MeshtasticConnectionError) as err:
            await starting
    finally:
        release.set()
    await _settle(hass)

    assert err.value.translation_key == "timeout"
    assert mock_meshtastic_client.close.call_count == 1


async def test_a_connect_cancelled_mid_handshake_is_closed_when_it_lands(
    hass: HomeAssistant, mock_meshtastic_client: MagicMock
) -> None:
    """Test that a cancelled connect does not abandon a live interface either.

    Nothing cancels an executor thread, and the config flow's own validation
    timeout and an entry being unloaded both cancel the awaiting task rather
    than letting the connect time out.  The handshake finishes anyway, and the
    firmware serves one API client at a time: an abandoned session goes on
    kicking every later attempt until Home Assistant is restarted.
    """
    release = threading.Event()
    build = mock_meshtastic_client.interface_class.side_effect

    def _slow_handshake(*args: Any, **kwargs: Any) -> MagicMock:
        release.wait(10)
        return build(*args, **kwargs)

    mock_meshtastic_client.interface_class.side_effect = _slow_handshake
    client = MeshtasticClient(hass, "192.0.2.10", 4403)

    try:
        starting = hass.async_create_task(client.async_start())
        for _ in range(10):
            await asyncio.sleep(0)
        assert not starting.done()

        starting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await starting
        # Everything the client knows about is closed, and it knows about
        # nothing: the interface has not been handed over yet.
        await client.async_stop()
        assert client._interface is None
    finally:
        release.set()
    await _settle(hass)

    assert mock_meshtastic_client.close.call_count == 1


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------


async def test_a_send_that_waited_out_the_gate_rechecks_the_link(
    hass: HomeAssistant, mock_meshtastic_client: MagicMock, mock_pubsub: FakePubSub
) -> None:
    """Test that a queued send never runs against a closed interface.

    ``async_request`` waits for the send lock and then for the per-portnum
    pacing gate, together up to about a minute for a traceroute.  A drop in
    that window replaces the interface, but a send on the old one writes into
    a closed socket, which the library reports as a success: the request then
    waits out its whole deadline and reports that nothing acknowledged it.
    """
    client = MeshtasticClient(hass, "192.0.2.10", 4403)
    await client.async_start()
    # A packet id of zero is the library's "nothing to correlate on", so each
    # send reports as soon as it is out and only the gate is under test here.
    mock_meshtastic_client.sendData.side_effect = lambda *args, **kwargs: (
        mesh_pb2.MeshPacket(id=0)
    )
    await client.async_send_data(
        b"first", portnum=PORTNUM_TRACEROUTE_APP, destination=REMOTE_NUM
    )

    queued = hass.async_create_task(
        client.async_send_data(
            b"second", portnum=PORTNUM_TRACEROUTE_APP, destination=REMOTE_NUM
        )
    )
    for _ in range(10):
        await asyncio.sleep(0)
    assert not queued.done()

    # The node goes away while the second send is still waiting on the gate,
    # and stays away, so nothing can put an interface back.
    mock_meshtastic_client.interface_class.side_effect = OSError("unreachable")
    mock_pubsub.sendMessage(TOPIC_CONNECTION_LOST, interface=mock_meshtastic_client)
    for _ in range(10):
        await asyncio.sleep(0)
    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=SEND_SPACING[PORTNUM_TRACEROUTE_APP] + 1),
    )

    with pytest.raises(MeshtasticConnectionError) as err:
        await queued
    assert err.value.translation_key == "not_connected"
    assert mock_meshtastic_client.sendData.call_count == 1

    await client.async_stop()


async def test_a_message_sent_without_acknowledgment_reports_success(
    hass: HomeAssistant, mock_meshtastic_client: MagicMock
) -> None:
    """Test that turning acknowledgement off does not fail every send.

    Nothing on the mesh answers a packet the firmware was not asked to track:
    it writes no retransmission record for one, so neither a real nor an
    implicit acknowledgement can arrive.  Waiting the acknowledgement deadline
    out would block the action for half a minute and then report that nobody
    relayed the message - unconditionally, for everyone who turns the option
    off, which is the default for a broadcast.
    """
    client = MeshtasticClient(hass, "192.0.2.10", 4403)
    await client.async_start()

    sending = hass.async_create_task(
        client.async_send_text("fire and forget", want_ack=False)
    )
    # Nothing is injected: this is what the mesh really sends back, which is
    # nothing at all.  The short grace for a refusal generated before the
    # packet went out is the whole wait.
    await _advance(hass, REQUEST_TIMEOUTS[RequestKind.FIRE_AND_FORGET] + 1)
    assert sending.done()
    result = await sending

    assert mock_meshtastic_client.sendText.call_args.kwargs["wantAck"] is False
    assert result.kind is RequestKind.FIRE_AND_FORGET
    assert result.state is RequestState.SENT
    # The action reports success rather than blaming the mesh.
    raise_for_result(result, node="^all")

    await client.async_stop()


async def test_a_message_the_radio_refused_still_fails_without_an_ack(
    hass: HomeAssistant, mock_meshtastic_client: MagicMock
) -> None:
    """Test that the grace is what a send without acknowledgement is for.

    A node whose transmitter is off answers with a ``QueueStatus`` and no
    routing packet at all.  Reporting every unacknowledged send as a success
    without looking would hide the one failure that is still knowable.
    """
    client = MeshtasticClient(hass, "192.0.2.10", 4403)
    await client.async_start()
    mock_meshtastic_client.queueStatus = mesh_pb2.QueueStatus(
        res=34, free=16, maxlen=16, mesh_packet_id=111222333
    )

    sending = hass.async_create_task(
        client.async_send_text("fire and forget", want_ack=False)
    )
    await _advance(hass, REQUEST_TIMEOUTS[RequestKind.FIRE_AND_FORGET] + 1)
    assert sending.done()
    result = await sending

    assert result.state is RequestState.NACKED
    assert result.error_reason == QUEUE_REFUSED_TX_DISABLED
    with pytest.raises(MeshtasticRequestError) as err:
        raise_for_result(result, node="^all")
    assert err.value.translation_key == "tx_disabled"

    await client.async_stop()


async def test_one_portnums_spacing_does_not_stall_the_others(
    hass: HomeAssistant, mock_meshtastic_client: MagicMock
) -> None:
    """Test that the pacing gate is not waited out under the global send lock.

    The gate belongs to one portnum, the lock to the whole link.  Holding the
    lock across the wait makes a traceroute's 31 seconds of spacing stall every
    unrelated send behind it, and each request only ever measures the wait that
    is left once the one in front has finished, so a queue can grow past the
    cap that is supposed to bound it without anybody being told.
    """
    client = MeshtasticClient(hass, "192.0.2.10", 4403)
    await client.async_start()
    # A packet id of zero is the library's "nothing to correlate on", so each
    # send reports as soon as it is out and only the pacing is under test.
    mock_meshtastic_client.sendData.side_effect = lambda *args, **kwargs: (
        mesh_pb2.MeshPacket(id=0)
    )
    mock_meshtastic_client.sendText.side_effect = lambda *args, **kwargs: (
        mesh_pb2.MeshPacket(id=0)
    )
    await client.async_send_data(
        b"first", portnum=PORTNUM_TRACEROUTE_APP, destination=REMOTE_NUM
    )

    queued = hass.async_create_task(
        client.async_send_data(
            b"second", portnum=PORTNUM_TRACEROUTE_APP, destination=REMOTE_NUM
        )
    )
    for _ in range(10):
        await asyncio.sleep(0)
    assert not queued.done()

    # A text message is paced on its own clock and has to go out straight away.
    texting = hass.async_create_task(
        client.async_send_text("hello", destination=REMOTE_NUM)
    )
    for _ in range(10):
        await asyncio.sleep(0)
    assert texting.done()
    await texting
    assert mock_meshtastic_client.sendText.call_count == 1

    # A third traceroute would have to sit through both of the waits ahead of
    # it, which is longer than the cap: it is told so now, not in a minute.
    with pytest.raises(MeshtasticRequestError) as err:
        await client.async_send_data(
            b"third", portnum=PORTNUM_TRACEROUTE_APP, destination=REMOTE_NUM
        )
    assert err.value.translation_key == "rate_limited"

    await _advance(hass, SEND_SPACING[PORTNUM_TRACEROUTE_APP] + 1)
    await queued
    assert mock_meshtastic_client.sendData.call_count == 2

    await client.async_stop()


async def test_a_node_refresh_that_waited_for_the_lock_rechecks_the_link(
    hass: HomeAssistant, mock_meshtastic_client: MagicMock, mock_pubsub: FakePubSub
) -> None:
    """Test that a queued node refresh never runs against a closed interface.

    ``async_refresh_nodes`` queues behind every other send, and the library
    writes into a closed socket without complaining, so a refresh that lost the
    link while it waited would look like it had worked.
    """
    client = MeshtasticClient(hass, "192.0.2.10", 4403)
    await client.async_start()
    mock_meshtastic_client._sendToRadio.reset_mock()

    # Stand in for a long send already in flight.
    await client._send_lock.acquire()
    refreshing = hass.async_create_task(client.async_refresh_nodes())
    for _ in range(10):
        await asyncio.sleep(0)
    assert not refreshing.done()

    # The node goes away while the refresh waits, and stays away, so nothing
    # can put an interface back.
    mock_meshtastic_client.interface_class.side_effect = OSError("unreachable")
    mock_pubsub.sendMessage(TOPIC_CONNECTION_LOST, interface=mock_meshtastic_client)
    for _ in range(10):
        await asyncio.sleep(0)
    client._send_lock.release()

    with pytest.raises(MeshtasticConnectionError) as err:
        await refreshing
    assert err.value.translation_key == "not_connected"
    mock_meshtastic_client._sendToRadio.assert_not_called()

    await client.async_stop()


async def test_a_packet_the_radio_refused_names_the_reason(
    hass: HomeAssistant, mock_meshtastic_client: MagicMock
) -> None:
    """Test that a silent firmware drop is reported as what it is.

    A node whose LoRa region is unset, or whose transmitter is off, answers
    with ``QueueStatus.res = 34`` and no routing packet at all.  Without
    reading it every send waits out its full deadline and then blames the
    mesh for not relaying the message, forever, with nothing pointing at the
    setting that is actually wrong.
    """
    client = MeshtasticClient(hass, "192.0.2.10", 4403)
    await client.async_start()
    mock_meshtastic_client.queueStatus = mesh_pb2.QueueStatus(
        res=34, free=16, maxlen=16, mesh_packet_id=111222333
    )

    sending = hass.async_create_task(
        client.async_send_text("hello", destination=REMOTE_NUM)
    )
    await _advance(hass, REQUEST_TIMEOUTS[RequestKind.TEXT_DIRECT] + 1)
    result = await sending

    assert result.state is RequestState.NACKED
    assert result.error_reason == QUEUE_REFUSED_TX_DISABLED
    with pytest.raises(MeshtasticRequestError) as err:
        raise_for_result(result, node=REMOTE_ID)
    assert err.value.translation_key == "tx_disabled"

    await client.async_stop()


async def test_a_queue_status_for_another_packet_is_ignored(
    hass: HomeAssistant, mock_meshtastic_client: MagicMock
) -> None:
    """Test that only the answer to our own packet can explain its timeout."""
    client = MeshtasticClient(hass, "192.0.2.10", 4403)
    await client.async_start()
    mock_meshtastic_client.queueStatus = mesh_pb2.QueueStatus(
        res=34, free=16, maxlen=16, mesh_packet_id=999
    )

    sending = hass.async_create_task(
        client.async_send_text("hello", destination=REMOTE_NUM)
    )
    await _advance(hass, REQUEST_TIMEOUTS[RequestKind.TEXT_DIRECT] + 1)
    result = await sending

    assert result.state is RequestState.TIMED_OUT
    assert result.error_reason is None

    await client.async_stop()


async def test_the_node_table_is_only_delivered_for_the_live_link(
    hass: HomeAssistant,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a node table read for a link that has since died is dropped."""
    seen: list[Any] = []
    client = MeshtasticClient(
        hass,
        "192.0.2.10",
        4403,
        callbacks=MeshtasticClientCallbacks(node_updated=seen.append),
    )
    await client.async_start()
    seen.clear()
    live = client._interface
    assert live is not None

    with patch(
        "homeassistant.components.meshtastic.client._snapshot_nodes",
        return_value=[dict(node_fixtures[REMOTE_ID])],
    ):
        await client._async_seed_nodes(MagicMock(spec=MeshInterface))
    assert seen == []

    # A table that cannot be read at all is not worth failing the connect for.
    with patch(
        "homeassistant.components.meshtastic.client._snapshot_nodes",
        side_effect=OSError("the node went away"),
    ):
        await client._async_seed_nodes(live)
    assert seen == []
    assert client.connected is True

    await client.async_stop()
