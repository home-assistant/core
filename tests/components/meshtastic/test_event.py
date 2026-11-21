"""Tests for the Meshtastic event platform."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    REMOTE_ID,
    REMOTE_NUM,
    SENSOR_NODE_ID,
    FakePubSub,
    inject_node_info,
    inject_packet,
    setup_integration,
)

from tests.common import MockConfigEntry, snapshot_platform

# Just after the newest packet fixture, so none of them counts as backlog.
FROZEN_TIME = "2025-09-08 02:57:10+00:00"

GATEWAY_ENTITY_ID = "event.ha_gateway_message"
REMOTE_ENTITY_ID = "event.remote_one_message"
SENSOR_ENTITY_ID = "event.weather_shed_message"

pytestmark = pytest.mark.freeze_time(FROZEN_TIME)


async def _setup_event_platform(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    pubsub: FakePubSub,
    interface: MagicMock,
    node_fixtures: dict[str, Any],
) -> None:
    """Set up only the event platform, with two known mesh nodes."""
    with patch("homeassistant.components.meshtastic.PLATFORMS", [Platform.EVENT]):
        await setup_integration(hass, entry)
    for node_id in (REMOTE_ID, SENSOR_NODE_ID):
        await inject_node_info(hass, pubsub, interface, node_fixtures[node_id])


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test the event entities of the gateway and of every known node."""
    await _setup_event_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_broadcast_message_fires_event(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    packet_fixtures: dict[str, dict[str, Any]],
) -> None:
    """Test that a broadcast text message fires a ``message`` event."""
    await _setup_event_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    assert (state := hass.states.get(GATEWAY_ENTITY_ID))
    assert state.state == STATE_UNKNOWN

    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, packet_fixtures["packet_text"]
    )

    assert (state := hass.states.get(GATEWAY_ENTITY_ID))
    assert state.state != STATE_UNKNOWN
    assert state.attributes == snapshot


async def test_direct_message_fires_direct_message_event(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    packet_fixtures: dict[str, dict[str, Any]],
) -> None:
    """Test that a message addressed to the gateway is a direct message."""
    await _setup_event_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, packet_fixtures["packet_text_direct"]
    )

    assert (state := hass.states.get(GATEWAY_ENTITY_ID))
    assert state.attributes["event_type"] == "direct_message"
    assert state.attributes == snapshot


async def test_node_event_reports_only_its_own_node(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    packet_fixtures: dict[str, dict[str, Any]],
) -> None:
    """Test that a node event entity ignores the traffic of other nodes."""
    await _setup_event_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, packet_fixtures["packet_text"]
    )

    assert (state := hass.states.get(REMOTE_ENTITY_ID))
    assert state.attributes["from_num"] == REMOTE_NUM
    assert state.attributes["text"] == "hallo mesh"
    # The same packet reached the gateway entity, but not the other node.
    assert (other := hass.states.get(SENSOR_ENTITY_ID))
    assert other.state == STATE_UNKNOWN


async def test_message_carries_the_sender_name(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    packet_fixtures: dict[str, dict[str, Any]],
) -> None:
    """Test that the sender is named when the mesh has introduced it."""
    with patch("homeassistant.components.meshtastic.PLATFORMS", [Platform.EVENT]):
        await setup_integration(hass, mock_config_entry)

    # A node that has only ever been heard is named by its id.
    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, packet_fixtures["packet_text"]
    )
    assert (state := hass.states.get(GATEWAY_ENTITY_ID))
    assert state.attributes["from_name"] == REMOTE_ID

    await inject_node_info(
        hass, mock_pubsub, mock_meshtastic_client, node_fixtures[REMOTE_ID]
    )
    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, packet_fixtures["packet_text"]
    )

    assert (state := hass.states.get(GATEWAY_ENTITY_ID))
    assert state.attributes["from_name"] == "Remote One"


async def test_backlog_is_suppressed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    packet_fixtures: dict[str, dict[str, Any]],
) -> None:
    """Test that the messages a node replays after a connect fire nothing.

    A Meshtastic node hands a freshly connected client everything it queued
    while nobody was listening.  Those are old messages and must not re-run
    automations.
    """
    await _setup_event_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    stale = packet_fixtures["packet_text"] | {"rxTime": 1757300200 - 3600}
    await inject_packet(hass, mock_pubsub, mock_meshtastic_client, stale)

    assert (state := hass.states.get(GATEWAY_ENTITY_ID))
    assert state.state == STATE_UNKNOWN
    assert (state := hass.states.get(REMOTE_ENTITY_ID))
    assert state.state == STATE_UNKNOWN


async def test_undated_packet_right_after_connect_is_backlog(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    packet_fixtures: dict[str, dict[str, Any]],
) -> None:
    """Test that an undated packet arriving right after a connect is backlog."""
    await _setup_event_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    undated = {
        key: value
        for key, value in packet_fixtures["packet_text"].items()
        if key != "rxTime"
    }
    await inject_packet(hass, mock_pubsub, mock_meshtastic_client, undated)

    assert (state := hass.states.get(GATEWAY_ENTITY_ID))
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "packet_name", ["packet_position", "packet_telemetry_device", "packet_encrypted"]
)
async def test_packets_without_text_fire_nothing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    packet_fixtures: dict[str, dict[str, Any]],
    packet_name: str,
) -> None:
    """Test that only text messages fire an event."""
    await _setup_event_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, packet_fixtures[packet_name]
    )

    assert (state := hass.states.get(GATEWAY_ENTITY_ID))
    assert state.state == STATE_UNKNOWN


async def test_node_event_entities_are_added_dynamically(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    packet_fixtures: dict[str, dict[str, Any]],
) -> None:
    """Test that a node gets an event entity once it introduces itself."""
    with patch("homeassistant.components.meshtastic.PLATFORMS", [Platform.EVENT]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(GATEWAY_ENTITY_ID)
    assert hass.states.get(REMOTE_ENTITY_ID) is None

    # A node that is only heard, never introduced, gets no entity.
    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, packet_fixtures["packet_text"]
    )
    assert hass.states.get(REMOTE_ENTITY_ID) is None

    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, packet_fixtures["packet_nodeinfo"]
    )
    assert hass.states.get(REMOTE_ENTITY_ID)
