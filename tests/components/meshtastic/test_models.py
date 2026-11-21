"""Tests for the Meshtastic data models.

These are the frozen records every other module passes around, and the
``from_dict`` half of each one is what reads the persisted node table back.  A
stored record written by an older version, or corrupted, must never take the
integration down: it is dropped or defaulted instead.
"""

from typing import Any

from homeassistant.components.meshtastic.models import (
    GatewayInfo,
    MeshtasticChannel,
    MeshtasticData,
    MeshtasticMessage,
    MeshtasticNode,
    MeshtasticPacket,
    Position,
    PositionSource,
    RequestKind,
    RequestResult,
    RequestState,
    TelemetryFamily,
    TelemetrySample,
    TracerouteRoute,
)
from homeassistant.util import dt as dt_util

from . import GATEWAY_ID, GATEWAY_NUM, REMOTE_ID, REMOTE_NUM

BROADCAST_NUM = 0xFFFFFFFF


def _gateway() -> GatewayInfo:
    """Return a minimal gateway identity."""
    return GatewayInfo(
        node_num=GATEWAY_NUM,
        node_id=GATEWAY_ID,
        long_name="HA Gateway",
        channels=(MeshtasticChannel(index=0, name="", role="PRIMARY"),),
    )


def test_position_round_trip() -> None:
    """Test that a position survives a store round trip unchanged."""
    now = dt_util.utcnow()
    position = Position(
        latitude=52.1,
        longitude=13.2,
        altitude=34,
        precision_bits=16,
        location_source="LOC_INTERNAL",
        sats_in_view=9,
        ground_speed=3,
        ground_track=180.5,
        device_time=1757300000,
        reported_at=now,
        source=PositionSource.NODE_INFO,
    )

    assert Position.from_dict(position.as_dict()) == position


def test_position_from_dict_defaults_an_unknown_source() -> None:
    """Test that a source this version does not know falls back to the packet."""
    position = Position.from_dict({"latitude": 1.0, "longitude": 2.0, "source": "moon"})

    assert position.source is PositionSource.PACKET
    assert position.valid is True


def test_position_from_dict_survives_unusable_values() -> None:
    """Test that unreadable numbers and timestamps become None."""
    position = Position.from_dict(
        {
            "latitude": "not a number",
            "longitude": None,
            "altitude": [1],
            "precision_bits": True,
            "ground_track": {},
            "reported_at": "yesterday",
        }
    )

    assert position.latitude is None
    assert position.longitude is None
    assert position.altitude is None
    assert position.precision_bits is None
    assert position.ground_track is None
    assert position.reported_at is None
    assert position.valid is False
    assert position.location_accuracy == 0


def test_position_accuracy_from_precision_bits() -> None:
    """Test the metre radius a blurred position stands for."""
    assert (
        Position(latitude=1.0, longitude=2.0, precision_bits=16).location_accuracy
        == 364
    )
    assert (
        Position(latitude=1.0, longitude=2.0, precision_bits=32).location_accuracy == 0
    )


def test_telemetry_sample_round_trip() -> None:
    """Test that a telemetry sample survives a store round trip."""
    sample = TelemetrySample(
        family=TelemetryFamily.DEVICE,
        values={"battery_level": 87, "voltage": 4.01},
        device_time=1757300000,
        reported_at=dt_util.utcnow(),
    )

    assert TelemetrySample.from_dict(sample.as_dict()) == sample


def test_telemetry_sample_from_dict_rejects_unusable_records() -> None:
    """Test that a sample without a readable family is dropped."""
    assert TelemetrySample.from_dict({}) is None
    assert TelemetrySample.from_dict({"family": "unknown_family"}) is None
    assert (
        TelemetrySample.from_dict({"family": "device", "values": "nope"}).values == {}
    )


def test_node_round_trip_and_helpers() -> None:
    """Test the node record's round trip, name fallback and sample lookup."""
    now = dt_util.utcnow()
    sample = TelemetrySample(family=TelemetryFamily.DEVICE, values={"battery_level": 5})
    node = MeshtasticNode(
        num=REMOTE_NUM,
        node_id=REMOTE_ID,
        long_name="Remote One",
        short_name="R1",
        first_seen=now,
        last_heard=now,
        position=Position(latitude=1.0, longitude=2.0),
        telemetry={str(TelemetryFamily.DEVICE): sample},
        presumptive=False,
    )

    assert MeshtasticNode.from_dict(node.as_dict()) == node
    assert node.name == "Remote One"
    assert node.sample(TelemetryFamily.DEVICE) is sample
    assert node.sample(TelemetryFamily.POWER) is None
    assert node.with_updates(long_name=None).name == "R1"
    assert node.with_updates(long_name=None, short_name=None).name == REMOTE_ID


def test_node_from_dict_rejects_unusable_records() -> None:
    """Test that a record without a usable identity is dropped."""
    assert MeshtasticNode.from_dict({}) is None
    assert MeshtasticNode.from_dict({"num": REMOTE_NUM}) is None
    assert MeshtasticNode.from_dict({"node_id": REMOTE_ID}) is None
    assert MeshtasticNode.from_dict({"num": "x", "node_id": REMOTE_ID}) is None


def test_node_from_dict_drops_unreadable_members() -> None:
    """Test that a corrupt position or telemetry entry is skipped, not fatal."""
    node = MeshtasticNode.from_dict(
        {
            "num": REMOTE_NUM,
            "node_id": REMOTE_ID,
            "position": "not a position",
            "telemetry": {"device": "not a sample", "power": {"family": "power"}},
        }
    )

    assert node is not None
    assert node.position is None
    assert set(node.telemetry) == {"power"}


def test_packet_broadcast_and_hops() -> None:
    """Test the derived properties of a received packet."""
    packet = MeshtasticPacket(
        packet_id=1,
        from_num=REMOTE_NUM,
        to_num=BROADCAST_NUM,
        portnum="TEXT_MESSAGE_APP",
        hop_start=3,
        hop_limit=1,
    )

    assert packet.is_broadcast is True
    assert packet.hops_away == 2
    assert packet.as_dict()["portnum"] == "TEXT_MESSAGE_APP"


def test_packet_hops_ignores_a_negative_count() -> None:
    """Test that a hop limit above the start reports nothing.

    A relay that raised the limit is nonsense, and a negative hop count would
    be rendered as a sensor state.
    """
    packet = MeshtasticPacket(
        packet_id=1,
        from_num=REMOTE_NUM,
        to_num=BROADCAST_NUM,
        portnum="TEXT_MESSAGE_APP",
        hop_start=1,
        hop_limit=3,
    )

    assert packet.hops_away is None


def test_packet_hops_needs_both_ends() -> None:
    """Test that a packet without both hop fields reports no hop count."""
    packet = MeshtasticPacket(
        packet_id=1, from_num=REMOTE_NUM, to_num=0, portnum="POSITION_APP", hop_start=3
    )

    assert packet.hops_away is None
    assert packet.is_broadcast is False


def test_message_from_packet_needs_text() -> None:
    """Test that only a packet carrying text becomes a message."""
    packet = MeshtasticPacket(
        packet_id=7,
        from_num=REMOTE_NUM,
        from_id=REMOTE_ID,
        to_num=BROADCAST_NUM,
        portnum="TEXT_MESSAGE_APP",
    )

    assert MeshtasticMessage.from_packet(packet) is None

    message = MeshtasticMessage.from_packet(
        MeshtasticPacket(
            packet_id=7,
            from_num=REMOTE_NUM,
            from_id=REMOTE_ID,
            to_num=BROADCAST_NUM,
            portnum="TEXT_MESSAGE_APP",
            text="hello",
        ),
        from_name="Remote One",
    )
    assert message is not None
    assert message.is_broadcast is True
    assert message.as_dict()["from_name"] == "Remote One"


def test_request_result_delivery_and_dict() -> None:
    """Test the delivery verdict and the JSON shape of a request result."""
    response = MeshtasticPacket(
        packet_id=2,
        from_num=REMOTE_NUM,
        to_num=GATEWAY_NUM,
        portnum="TRACEROUTE_APP",
        traceroute=TracerouteRoute(
            route=(REMOTE_NUM,), snr_towards=(20, -128), route_back=(), snr_back=(12,)
        ),
    )
    result = RequestResult(
        packet_id=1,
        kind=RequestKind.DIRECT_REQUEST,
        state=RequestState.RESPONDED,
        destination=REMOTE_NUM,
        response=response,
    )

    as_dict: dict[str, Any] = result.as_dict()
    assert result.delivered is True
    assert as_dict["delivered"] is True
    assert as_dict["kind"] == "direct_request"
    assert as_dict["response"]["packet_id"] == 2
    # Tuples, so the model stays hashable and immutable; lists once rendered.
    assert as_dict["response"]["traceroute"] == {
        "route": [REMOTE_NUM],
        "snr_towards": [20, -128],
        "route_back": [],
        "snr_back": [12],
    }

    nacked = RequestResult(
        packet_id=1,
        kind=RequestKind.TEXT_DIRECT,
        state=RequestState.NACKED,
        destination=REMOTE_NUM,
        error_reason="NO_ROUTE",
    )
    assert nacked.delivered is False
    assert nacked.as_dict()["response"] is None


def test_data_lookup_and_dict() -> None:
    """Test the coordinator payload's node lookup and JSON shape."""
    node = MeshtasticNode(num=REMOTE_NUM, node_id=REMOTE_ID, presumptive=False)
    data = MeshtasticData(gateway=_gateway(), nodes={REMOTE_ID: node})

    assert data.node(REMOTE_ID) is node
    assert data.node("!00000000") is None
    assert data.as_dict()["gateway"]["node_id"] == GATEWAY_ID
    assert set(data.as_dict()["nodes"]) == {REMOTE_ID}


def test_gateway_name_falls_back() -> None:
    """Test that a gateway with no names is still identifiable."""
    assert _gateway().name == "HA Gateway"
    assert GatewayInfo(node_num=GATEWAY_NUM, node_id=GATEWAY_ID).name == GATEWAY_ID
    assert (
        GatewayInfo(node_num=GATEWAY_NUM, node_id=GATEWAY_ID, short_name="HA").name
        == "HA"
    )


def test_channel_never_carries_a_key() -> None:
    """Test that a channel only reports whether it is encrypted."""
    channel = MeshtasticChannel(index=1, name="admin", role="SECONDARY", encrypted=True)

    assert channel.as_dict() == {
        "index": 1,
        "name": "admin",
        "role": "SECONDARY",
        "encrypted": True,
        "uplink_enabled": False,
        "downlink_enabled": False,
    }
