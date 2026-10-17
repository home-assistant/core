"""Tests for the Meshtastic notify platform."""

import asyncio
from datetime import timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TITLE,
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import (
    REMOTE_ID,
    REMOTE_NUM,
    FakePubSub,
    inject_connection_lost,
    inject_node_info,
    inject_notification,
    inject_packet,
    setup_integration,
)

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

# Just after the newest packet fixture, so none of them counts as backlog.
FROZEN_TIME = "2025-09-08 02:57:10+00:00"

CHANNEL_ENTITY_ID = "notify.ha_gateway_channel_0"
ADMIN_CHANNEL_ENTITY_ID = "notify.ha_gateway_channel_admin"
NODE_ENTITY_ID = "notify.remote_one_direct_message"

SENT_PACKET_ID = 111222333

pytestmark = pytest.mark.freeze_time(FROZEN_TIME)


async def _setup_notify_platform(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    pubsub: FakePubSub,
    interface: MagicMock,
    node_fixtures: dict[str, Any],
) -> None:
    """Set up only the notify platform, with one known mesh node."""
    with patch("homeassistant.components.meshtastic.PLATFORMS", [Platform.NOTIFY]):
        await setup_integration(hass, entry)
    await inject_node_info(hass, pubsub, interface, node_fixtures[REMOTE_ID])


async def _start_send(
    hass: HomeAssistant,
    entity_id: str,
    message: str,
    title: str | None = None,
) -> asyncio.Task[None]:
    """Start a send_message action and let it reach the radio."""
    data: dict[str, Any] = {ATTR_ENTITY_ID: entity_id, ATTR_MESSAGE: message}
    if title is not None:
        data[ATTR_TITLE] = title
    task = hass.async_create_task(
        hass.services.async_call(
            NOTIFY_DOMAIN, SERVICE_SEND_MESSAGE, data, blocking=True
        )
    )
    # The send runs in the executor; give it a few loop iterations to get out
    # before the answer is injected.
    for _ in range(10):
        await asyncio.sleep(0)
    return task


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test one notify entity per enabled channel and per known node."""
    await _setup_notify_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    # The disabled third channel slot of the gateway gets no entity.
    assert hass.states.get("notify.ha_gateway_channel_2") is None

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_broadcast_on_a_channel(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    packet_fixtures: dict[str, dict[str, Any]],
) -> None:
    """Test that a channel entity broadcasts on its own channel index."""
    await _setup_notify_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await _start_send(hass, ADMIN_CHANNEL_ENTITY_ID, "hello everyone")
    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, packet_fixtures["packet_routing_ack"]
    )
    await task

    mock_meshtastic_client.sendText.assert_called_once_with(
        "hello everyone",
        destinationId=0xFFFFFFFF,
        wantAck=True,
        channelIndex=1,
        replyId=None,
    )
    assert (state := hass.states.get(ADMIN_CHANNEL_ENTITY_ID))
    assert state.state == "2025-09-08T02:57:10+00:00"


async def test_direct_message_to_a_node(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    packet_fixtures: dict[str, dict[str, Any]],
) -> None:
    """Test that a node entity sends a direct message to that node."""
    await _setup_notify_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await _start_send(hass, NODE_ENTITY_ID, "are you there")
    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, packet_fixtures["packet_routing_ack"]
    )
    await task

    mock_meshtastic_client.sendText.assert_called_once_with(
        "are you there",
        destinationId=REMOTE_NUM,
        wantAck=True,
        channelIndex=0,
        replyId=None,
    )
    assert (state := hass.states.get(NODE_ENTITY_ID))
    assert state.state == "2025-09-08T02:57:10+00:00"


async def test_title_becomes_a_prefix(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    packet_fixtures: dict[str, dict[str, Any]],
) -> None:
    """Test that a title is prefixed; a Meshtastic packet has no title field."""
    await _setup_notify_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await _start_send(hass, CHANNEL_ENTITY_ID, "the shed is on fire", "Alarm")
    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, packet_fixtures["packet_routing_ack"]
    )
    await task

    assert (
        mock_meshtastic_client.sendText.call_args.args[0]
        == "Alarm: the shed is on fire"
    )


async def test_message_too_long(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that an oversized message is refused before it hits the radio."""
    await _setup_notify_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {ATTR_ENTITY_ID: NODE_ENTITY_ID, ATTR_MESSAGE: "x" * 201},
            blocking=True,
        )

    assert err.value.translation_key == "message_too_long"
    mock_meshtastic_client.sendText.assert_not_called()


async def test_not_acknowledged(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    packet_fixtures: dict[str, dict[str, Any]],
) -> None:
    """Test that a NAK from the mesh becomes a translated error."""
    await _setup_notify_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await _start_send(hass, NODE_ENTITY_ID, "are you there")
    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, packet_fixtures["packet_routing_nak"]
    )

    with pytest.raises(HomeAssistantError) as err:
        await task

    assert err.value.translation_key == "not_acknowledged"
    assert err.value.translation_placeholders == {
        "node": "Remote One",
        "reason": "MAX_RETRANSMIT",
        "message": "",
    }


async def test_rejected_by_the_node(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a firmware refusal becomes a translated validation error."""
    await _setup_notify_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await _start_send(hass, CHANNEL_ENTITY_ID, "hello everyone")
    await inject_notification(
        hass,
        mock_pubsub,
        mock_meshtastic_client,
        SimpleNamespace(
            message="Duty cycle limit exceeded",
            reply_id=SENT_PACKET_ID,
            time=0,
        ),
    )

    with pytest.raises(ServiceValidationError) as err:
        await task

    assert err.value.translation_key == "client_rejected"
    assert err.value.translation_placeholders == {
        "node": "channel 0",
        "reason": "CLIENT_NOTIFICATION",
        "message": "Duty cycle limit exceeded",
    }


async def test_nobody_relayed_the_message(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a request nothing ever answers becomes a translated error."""
    await _setup_notify_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await _start_send(hass, NODE_ENTITY_ID, "are you there")
    freezer.tick(timedelta(seconds=90))
    async_fire_time_changed(hass)

    with pytest.raises(HomeAssistantError) as err:
        await task

    assert err.value.translation_key == "timeout_no_ack"


async def test_unavailable_while_the_link_is_down(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that nothing can be sent while the node is unreachable."""
    await _setup_notify_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    assert (state := hass.states.get(CHANNEL_ENTITY_ID))
    assert state.state != STATE_UNAVAILABLE

    await inject_connection_lost(hass, mock_pubsub, mock_meshtastic_client)

    assert (state := hass.states.get(CHANNEL_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE
    assert (state := hass.states.get(NODE_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE


async def test_sending_while_the_node_reboots(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test the error when the link is down but the entity is still offered.

    Entities stay available across a reboot Home Assistant asked for, so a
    send can still be attempted while there is no link to send it on.
    """
    await _setup_notify_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    mock_config_entry.runtime_data.client.async_note_reboot_expected()
    await inject_connection_lost(hass, mock_pubsub, mock_meshtastic_client)

    assert (state := hass.states.get(CHANNEL_ENTITY_ID))
    assert state.state != STATE_UNAVAILABLE

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {ATTR_ENTITY_ID: CHANNEL_ENTITY_ID, ATTR_MESSAGE: "anyone there"},
            blocking=True,
        )

    assert err.value.translation_key == "not_connected"


async def test_unmessagable_node_is_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a node which cannot receive text is not offered as a target."""
    node = node_fixtures[REMOTE_ID]
    node["user"] = node["user"] | {"isUnmessagable": True}

    await _setup_notify_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    assert (state := hass.states.get(NODE_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE


async def test_node_entities_are_added_dynamically(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    packet_fixtures: dict[str, dict[str, Any]],
) -> None:
    """Test that a node gets a notify entity once it introduces itself."""
    with patch("homeassistant.components.meshtastic.PLATFORMS", [Platform.NOTIFY]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(CHANNEL_ENTITY_ID)
    assert hass.states.get(NODE_ENTITY_ID) is None

    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, packet_fixtures["packet_nodeinfo"]
    )

    # Two channels plus the node that just introduced itself.  The gateway
    # node is served by its channel entities and never gets a second,
    # direct-message device of its own.
    assert len(hass.states.async_entity_ids(NOTIFY_DOMAIN)) == 3
    assert hass.states.get(NODE_ENTITY_ID)
