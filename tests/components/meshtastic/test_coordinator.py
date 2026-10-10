"""Tests for the Meshtastic coordinator and its node registry.

The coordinator is push driven: the client feeds it and it republishes an
immutable snapshot.  What is exercised here is the part that has no entities in
front of it - the merge rules that decide whether a snapshot is worth
publishing at all, the LRU bound on the node table, and the store migration
that reads a persisted table back.
"""

from datetime import timedelta
from typing import Any

import pytest

from homeassistant.components.meshtastic.const import (
    MAX_STORED_NODES,
    STORAGE_KEY_FORMAT,
    STORAGE_VERSION,
    format_node_id,
)
from homeassistant.components.meshtastic.coordinator import (
    MeshtasticCoordinator,
    MeshtasticNodeRegistry,
    MeshtasticNodeStore,
)
from homeassistant.components.meshtastic.models import (
    GatewayInfo,
    MeshtasticNode,
    MeshtasticNotification,
    MeshtasticPacket,
    Position,
    PositionSource,
    TelemetryFamily,
    TelemetrySample,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import GATEWAY_ID, GATEWAY_NUM, REMOTE_ID, REMOTE_NUM

from tests.common import MockConfigEntry


@pytest.fixture
def coordinator(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MeshtasticCoordinator:
    """Return a coordinator that has already heard from its gateway."""
    mock_config_entry.add_to_hass(hass)
    client = _FakeClient()
    coordinator = MeshtasticCoordinator(hass, mock_config_entry, client)  # type: ignore[arg-type]
    coordinator.async_handle_connected(
        GatewayInfo(node_num=GATEWAY_NUM, node_id=GATEWAY_ID, long_name="HA Gateway")
    )
    return coordinator


class _FakeClient:
    """The little of the client the coordinator touches."""

    host = "192.0.2.10"
    connected = True
    callbacks: Any = None


def _packet(**changes: Any) -> MeshtasticPacket:
    """Return a received packet with the given overrides."""
    base: dict[str, Any] = {
        "packet_id": 1,
        "from_num": REMOTE_NUM,
        "from_id": REMOTE_ID,
        "to_num": 0xFFFFFFFF,
        "portnum": "TEXT_MESSAGE_APP",
        "received_at": dt_util.utcnow(),
    }
    return MeshtasticPacket(**{**base, **changes})


async def test_gateway_is_unavailable_before_the_first_connect(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that asking for the gateway before it is known fails loudly."""
    mock_config_entry.add_to_hass(hass)
    coordinator = MeshtasticCoordinator(hass, mock_config_entry, _FakeClient())  # type: ignore[arg-type]

    assert coordinator.gateway_or_none is None
    with pytest.raises(RuntimeError):
        _ = coordinator.gateway

    # Nothing is published while there is no gateway to publish it with.
    coordinator.async_handle_packet(_packet())
    assert coordinator.data is None

    await coordinator.async_shutdown()


async def test_the_gateway_becomes_a_node(coordinator: MeshtasticCoordinator) -> None:
    """Test that the gateway is in its own node table, never presumptive."""
    node = coordinator.get_node(GATEWAY_ID)

    assert node is not None
    assert node.presumptive is False
    assert node.hops_away == 0
    assert node.long_name == "HA Gateway"
    assert coordinator.get_node("!00000000") is None

    await coordinator.async_shutdown()


async def test_an_unchanged_packet_publishes_nothing(
    coordinator: MeshtasticCoordinator,
) -> None:
    """Test that a repeat of what we already know is not a new snapshot.

    Every publish walks every entity, so this is the only dampening a push
    coordinator has: the merge decides, because it is the only place that
    knows whether anything changed.
    """
    packet = _packet(rx_time=1757300000, rx_snr=5.5, rx_rssi=-90)
    coordinator.async_handle_packet(packet)
    first = coordinator.data

    coordinator.async_handle_packet(packet)

    assert coordinator.data is first
    await coordinator.async_shutdown()


async def test_publishing_always_notifies_every_listener(
    coordinator: MeshtasticCoordinator,
) -> None:
    """Test that a snapshot equal to the last one still reaches the listeners.

    ``always_update`` is read in exactly one place in Home Assistant, inside
    ``DataUpdateCoordinator._async_refresh``, which a coordinator with no
    ``update_interval`` and no ``_async_update_data`` never runs.  Passing it
    here would document a dampening that ``async_set_updated_data`` does not
    do, so it is left at its default.
    """
    calls: list[None] = []
    remove = coordinator.async_add_listener(lambda: calls.append(None))

    coordinator.async_handle_packet(_packet(rx_time=1757300000))
    coordinator.async_set_updated_data(coordinator.data)
    remove()
    coordinator.async_set_updated_data(coordinator.data)

    assert len(calls) == 2
    assert coordinator.always_update is True
    await coordinator.async_shutdown()


async def test_a_packet_listener_sees_every_packet(
    coordinator: MeshtasticCoordinator,
) -> None:
    """Test that traffic listeners are fed even by packets that change nothing."""
    seen: list[MeshtasticPacket] = []
    remove = coordinator.async_add_packet_listener(seen.append)

    packet = _packet(rx_time=1757300000)
    coordinator.async_handle_packet(packet)
    coordinator.async_handle_packet(packet)
    remove()
    coordinator.async_handle_packet(packet)

    assert len(seen) == 2
    await coordinator.async_shutdown()


async def test_a_node_record_only_upgrades_what_it_knows(
    coordinator: MeshtasticCoordinator,
) -> None:
    """Test that a presumptive record does not erase a node's identity."""
    now = dt_util.utcnow()
    coordinator.async_handle_node_updated(
        MeshtasticNode(
            num=REMOTE_NUM,
            node_id=REMOTE_ID,
            long_name="Remote One",
            short_name="R1",
            last_heard=now,
            presumptive=False,
        )
    )
    coordinator.async_handle_node_updated(
        MeshtasticNode(
            num=REMOTE_NUM, node_id=REMOTE_ID, is_favorite=True, presumptive=True
        )
    )

    node = coordinator.get_node(REMOTE_ID)
    assert node is not None
    assert node.long_name == "Remote One"
    assert node.presumptive is False
    assert node.is_favorite is True

    await coordinator.async_shutdown()


async def test_older_position_and_telemetry_are_not_applied(
    coordinator: MeshtasticCoordinator,
) -> None:
    """Test that a stale record does not overwrite a newer one.

    A node-DB dump replays whatever the gateway holds, which can be older than
    what we already heard on the air.
    """
    now = dt_util.utcnow()
    coordinator.async_handle_node_updated(
        MeshtasticNode(
            num=REMOTE_NUM,
            node_id=REMOTE_ID,
            presumptive=False,
            last_heard=now,
            position=Position(latitude=52.0, longitude=13.0, device_time=200),
            telemetry={
                str(TelemetryFamily.DEVICE): TelemetrySample(
                    family=TelemetryFamily.DEVICE,
                    values={"battery_level": 90},
                    device_time=200,
                )
            },
        )
    )
    coordinator.async_handle_node_updated(
        MeshtasticNode(
            num=REMOTE_NUM,
            node_id=REMOTE_ID,
            presumptive=False,
            last_heard=now - timedelta(hours=1),
            position=Position(latitude=1.0, longitude=1.0, device_time=100),
            telemetry={
                str(TelemetryFamily.DEVICE): TelemetrySample(
                    family=TelemetryFamily.DEVICE,
                    values={"battery_level": 10},
                    device_time=100,
                )
            },
        )
    )

    node = coordinator.get_node(REMOTE_ID)
    assert node is not None
    assert node.position is not None
    assert node.position.latitude == 52.0
    assert node.last_heard == now
    sample = node.sample(TelemetryFamily.DEVICE)
    assert sample is not None
    assert sample.value("battery_level") == 90

    await coordinator.async_shutdown()


async def test_a_node_record_does_not_blur_a_position_from_a_packet(
    coordinator: MeshtasticCoordinator,
) -> None:
    """Test that a node-DB push of the same fix keeps the packet's precision.

    The firmware's ``ConvertToNodeInfo`` copies only the coordinates, the
    altitude, the location source and the time into the ``NodeInfoLite`` it
    keeps, so the record the gateway pushes for a node it just heard carries
    the same ``device_time`` and none of ``precision_bits``, ``sats_in_view``
    or the ground speed.  Letting it replace the position the packet carried
    would render a deliberately blurred fix as a full precision one, and flip
    it back on the node's next broadcast.
    """
    heard = Position(
        latitude=52.1111111,
        longitude=13.1111111,
        altitude=42,
        precision_bits=16,
        sats_in_view=9,
        ground_speed=1,
        location_source="LOC_EXTERNAL",
        device_time=1757300299,
        source=PositionSource.PACKET,
    )
    coordinator.async_handle_packet(
        _packet(portnum="POSITION_APP", rx_time=1757300300, position=heard)
    )

    coordinator.async_handle_node_updated(
        MeshtasticNode(
            num=REMOTE_NUM,
            node_id=REMOTE_ID,
            presumptive=False,
            position=Position(
                latitude=52.1111111,
                longitude=13.1111111,
                altitude=42,
                location_source="LOC_EXTERNAL",
                device_time=1757300299,
                source=PositionSource.NODE_INFO,
            ),
        )
    )

    node = coordinator.get_node(REMOTE_ID)
    assert node is not None
    assert node.position == heard
    assert node.position.location_accuracy == 364

    await coordinator.async_shutdown()


async def test_a_node_record_with_a_newer_fix_still_wins(
    coordinator: MeshtasticCoordinator,
) -> None:
    """Test that a genuinely newer node-DB position replaces the stored one.

    The precision is only kept for the record that describes the same fix; a
    later one is the node's own newer report, whatever it left out.
    """
    coordinator.async_handle_packet(
        _packet(
            portnum="POSITION_APP",
            rx_time=1757300300,
            position=Position(
                latitude=52.1111111,
                longitude=13.1111111,
                precision_bits=16,
                device_time=1757300299,
                source=PositionSource.PACKET,
            ),
        )
    )

    coordinator.async_handle_node_updated(
        MeshtasticNode(
            num=REMOTE_NUM,
            node_id=REMOTE_ID,
            presumptive=False,
            position=Position(
                latitude=53.0,
                longitude=14.0,
                device_time=1757300999,
                source=PositionSource.NODE_INFO,
            ),
        )
    )

    node = coordinator.get_node(REMOTE_ID)
    assert node is not None
    assert node.position is not None
    assert node.position.latitude == 53.0
    assert node.position.precision_bits is None

    await coordinator.async_shutdown()


async def test_a_node_that_introduces_itself_is_rekeyed(
    coordinator: MeshtasticCoordinator,
) -> None:
    """Test that a node first heard by number is not duplicated by id.

    Relayed traffic is keyed on the formatted node number until the node sends
    its user record, which is where the canonical id comes from.
    """
    coordinator.async_handle_packet(_packet(from_id=None, rx_time=1757300000))
    assert set(coordinator.nodes) == {GATEWAY_ID, REMOTE_ID}
    assert coordinator.nodes[REMOTE_ID].presumptive is True

    await coordinator.async_shutdown()


async def test_the_node_table_is_bounded(coordinator: MeshtasticCoordinator) -> None:
    """Test that the table evicts the least recently heard nodes.

    The gateway, favourites and ignored nodes are kept whatever happens: they
    are the ones the user cares about, and the gateway is the entry itself.
    """
    now = dt_util.utcnow()
    favourite_num = 0x11111111
    ignored_num = 0x22222222
    coordinator.async_handle_node_updated(
        MeshtasticNode(
            num=favourite_num,
            node_id=format_node_id(favourite_num),
            presumptive=False,
            is_favorite=True,
            last_heard=now - timedelta(days=30),
        )
    )
    coordinator.async_handle_node_updated(
        MeshtasticNode(
            num=ignored_num,
            node_id=format_node_id(ignored_num),
            presumptive=False,
            is_ignored=True,
            last_heard=now - timedelta(days=30),
        )
    )
    for index in range(MAX_STORED_NODES + 10):
        num = 0x30000000 + index
        coordinator.async_handle_node_updated(
            MeshtasticNode(
                num=num,
                node_id=format_node_id(num),
                presumptive=False,
                last_heard=now - timedelta(seconds=MAX_STORED_NODES - index),
            )
        )

    nodes = coordinator.nodes
    assert len(nodes) == MAX_STORED_NODES
    assert GATEWAY_ID in nodes
    assert format_node_id(favourite_num) in nodes
    assert format_node_id(ignored_num) in nodes
    # The oldest ordinary nodes went first.
    assert format_node_id(0x30000000) not in nodes
    assert format_node_id(0x30000000 + MAX_STORED_NODES + 9) in nodes

    await coordinator.async_shutdown()


async def test_a_notification_is_only_logged(
    coordinator: MeshtasticCoordinator,
) -> None:
    """Test that a firmware notification does not republish the table."""
    coordinator.async_handle_packet(_packet(rx_time=1757300000))
    before = coordinator.data

    coordinator.async_handle_notification(MeshtasticNotification(message="hello"))

    assert coordinator.data is before
    await coordinator.async_shutdown()


# ---------------------------------------------------------------------------
# Node registry
# ---------------------------------------------------------------------------


async def test_registry_reads_a_damaged_store(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test that an unreadable stored table loads as an empty one."""
    key = STORAGE_KEY_FORMAT.format(entry_id="entry")
    registry = MeshtasticNodeRegistry(hass, "entry")

    hass_storage[key] = {"version": 1, "minor_version": 1, "data": {}}
    assert await registry.async_load() == {}

    hass_storage[key] = {"version": 1, "minor_version": 1, "data": {"nodes": "gone"}}
    assert await registry.async_load() == {}

    hass_storage[key] = {
        "version": 1,
        "minor_version": 1,
        "data": {"nodes": {REMOTE_ID: "not a node", "!00000000": {"num": 1}}},
    }
    assert await registry.async_load() == {}

    await registry.async_shutdown()


async def test_registry_flush_without_anything_to_write(hass: HomeAssistant) -> None:
    """Test that flushing before anything was scheduled writes nothing."""
    registry = MeshtasticNodeRegistry(hass, "entry")

    await registry.async_flush()
    await registry.async_shutdown()
    await registry.async_remove()


async def test_registry_ignores_a_save_after_it_closed(hass: HomeAssistant) -> None:
    """Test that a packet arriving during unload leaves no timer behind.

    ``async_call_later`` schedules a real event-loop timer, and one nobody
    cancels keeps Home Assistant from shutting down cleanly.
    """
    registry = MeshtasticNodeRegistry(hass, "entry")
    await registry.async_shutdown()

    registry.async_schedule_save(dict)

    assert registry._unsub_timer is None


async def test_store_migration_rewrites_every_record(hass: HomeAssistant) -> None:
    """Test that a stored table is re-parsed on the way in.

    Re-parsing drops keys this version no longer knows and defaults ones that
    were added; an unreadable record is dropped rather than failing the load.
    """
    store = MeshtasticNodeStore(hass, STORAGE_VERSION, "test", minor_version=1)

    migrated = await store._async_migrate_func(
        1,
        1,
        {
            "nodes": {
                REMOTE_ID: {
                    "num": REMOTE_NUM,
                    "node_id": REMOTE_ID,
                    "long_name": "Remote One",
                    "gone_in_this_version": True,
                },
                "!00000000": {"node_id": "!00000000"},
                "!11111111": "not a record",
            }
        },
    )

    assert set(migrated["nodes"]) == {REMOTE_ID}
    assert "gone_in_this_version" not in migrated["nodes"][REMOTE_ID]
    assert migrated["nodes"][REMOTE_ID]["long_name"] == "Remote One"


async def test_store_migration_of_an_empty_table(hass: HomeAssistant) -> None:
    """Test that a store without a node table migrates to an empty one."""
    store = MeshtasticNodeStore(hass, STORAGE_VERSION, "test", minor_version=1)

    assert await store._async_migrate_func(1, 1, {}) == {"nodes": {}}


async def test_store_migration_refuses_a_future_version(hass: HomeAssistant) -> None:
    """Test that a table written by a newer version fails rather than truncates."""
    store = MeshtasticNodeStore(hass, STORAGE_VERSION, "test", minor_version=1)

    with pytest.raises(NotImplementedError):
        await store._async_migrate_func(STORAGE_VERSION + 1, 1, {})
