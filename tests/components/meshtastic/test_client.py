"""Tests for the Meshtastic client's pure helpers and request tracker.

The conversion helpers turn the library's loosely typed dicts into the frozen
models the rest of the integration uses, and the tracker is what makes a send
answerable at all.  Both are exercised here without a radio: the packet dicts
are the real shapes the library produces, and the tracker runs entirely on the
event loop, which is where the pubsub listeners hand everything over.
"""

import asyncio
from datetime import timedelta
import time
from typing import Any
from unittest.mock import MagicMock

from meshtastic.mesh_interface import MeshInterface
from meshtastic.protobuf import mesh_pb2
import pytest

from homeassistant.components.meshtastic.client import (
    NODES_ONLY_WANT_CONFIG_ID,
    MeshtasticClient,
    MeshtasticClientCallbacks,
    MeshtasticConnectionError,
    MeshtasticError,
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
    HEARTBEAT_INTERVAL,
    HEARTBEAT_RESPONSE_TIMEOUT,
    LIVENESS_TIMEOUT,
    MAX_MISSED_HEARTBEATS,
    MAX_SEND_GATE_WAIT,
    MAX_TEXT_PAYLOAD_BYTES,
    PORTNUM_TEXT_MESSAGE_APP,
    RECONNECT_MAX_DELAY,
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

from . import GATEWAY_ID, GATEWAY_NUM, REMOTE_ID, REMOTE_NUM

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


async def test_pubsub_listeners_ignore_a_foreign_interface(
    client: MeshtasticClient, packet_fixtures: dict[str, Any]
) -> None:
    """Test that traffic from a previous connection is dropped.

    A reconnect builds a new interface; the old one's reader thread can still
    publish for a moment and must not be mistaken for the live link.
    """
    other = MagicMock(spec=MeshInterface)

    client._on_receive(packet_fixtures["packet_text"], other)
    client._on_node_updated({"num": REMOTE_NUM}, other)
    client._on_connection_established(other)
    client._on_connection_lost(other)
    client._on_client_notification(mesh_pb2.ClientNotification(), other)
    await asyncio.sleep(0)

    assert client.connection_state.value == "disconnected"


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
    """Test that a node whose queue status moves is treated as alive."""
    client = MeshtasticClient(hass, "192.0.2.10", 4403)
    await client.async_start()

    for index in range(3):
        client._last_rx = time.monotonic() - HEARTBEAT_INTERVAL - 5
        # The firmware bumps its queue status for every heartbeat it handles.
        mock_meshtastic_client.queueStatus = mesh_pb2.QueueStatus(
            free=16 - index, maxlen=16
        )
        await _heartbeat_cycle(hass)

    assert client.connected is True
    assert client.stats()["missed_heartbeats"] == 0
    assert mock_meshtastic_client.sendHeartbeat.call_count == 3

    await client.async_stop()


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
