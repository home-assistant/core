"""Tests for the Meshtastic actions."""

import asyncio
import copy
from datetime import timedelta
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from meshtastic.protobuf import mesh_pb2
import pytest
import voluptuous as vol

from homeassistant.components.meshtastic.const import (
    CONF_DOWNLOAD_NODE_DB,
    CONF_INCLUDE_LOCATION,
    CONFIG_ENTRY_MINOR_VERSION,
    CONFIG_ENTRY_VERSION,
    DEFAULT_PORT,
    DOMAIN,
    NOTIFICATION_REJECTED,
    ROUTING_ERROR_TRANSLATION_KEYS,
    ROUTING_ERROR_VALIDATION,
)
from homeassistant.components.meshtastic.services import (
    ATTR_CONFIRM,
    ATTR_MESSAGE,
    ATTR_NODE,
    ATTR_WANT_ACK,
    REDACTED,
    REFRESH_NODES_SPACING,
    SERVICE_EXPORT_CONFIG,
    SERVICE_REFRESH_NODES,
    SERVICE_REMOVE_NODE,
    SERVICE_REQUEST_TRACEROUTE,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_DEVICE_ID,
    CONF_HOST,
    CONF_PORT,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)
from homeassistant.helpers import device_registry as dr

from . import (
    GATEWAY_ID,
    GATEWAY_NUM,
    REMOTE_ID,
    REMOTE_NUM,
    SENSOR_NODE_NUM,
    FakePubSub,
    inject_connection_lost,
    inject_node_info,
    inject_notification,
    inject_packet,
    setup_integration,
)

from tests.common import MockConfigEntry, async_fire_time_changed

# Just after the newest packet fixture, so none of them counts as backlog.
FROZEN_TIME = "2025-09-08 02:57:10+00:00"

#: What the mocked interface hands back for each kind of send.
TEXT_PACKET_ID = 111222333
DATA_PACKET_ID = 111222334
ADMIN_PACKET_ID = 111222335

pytestmark = pytest.mark.freeze_time(FROZEN_TIME)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entry(
    *, options: dict[str, Any] | None = None, download_node_db: bool = False
) -> MockConfigEntry:
    """Return a config entry with the options a test needs."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="HA Gateway",
        unique_id=GATEWAY_ID,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_PORT: DEFAULT_PORT,
            CONF_DOWNLOAD_NODE_DB: download_node_db,
        },
        options=options or {},
        version=CONFIG_ENTRY_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )


async def _setup(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    pubsub: FakePubSub,
    interface: MagicMock,
    node_fixtures: dict[str, Any],
) -> None:
    """Set up the integration with the gateway and one mesh node known."""
    await setup_integration(hass, entry)
    await inject_node_info(hass, pubsub, interface, node_fixtures[GATEWAY_ID])
    await inject_node_info(hass, pubsub, interface, node_fixtures[REMOTE_ID])
    # The library returns the admin packet from Node._sendAdmin; the fixture's
    # localNode is a stand-in, so give it the method the action reaches for.
    interface.localNode.removeNode = MagicMock(
        return_value=SimpleNamespace(id=ADMIN_PACKET_ID)
    )


async def _start(
    hass: HomeAssistant,
    action: str,
    data: dict[str, Any],
    *,
    return_response: bool = False,
) -> asyncio.Task[Any]:
    """Start an action and let it reach the radio before it is answered."""
    task = hass.async_create_task(
        hass.services.async_call(
            DOMAIN, action, data, blocking=True, return_response=return_response
        )
    )
    # The send runs in the executor; give it a few loop iterations to get out
    # before the answer is injected.
    for _ in range(10):
        await asyncio.sleep(0)
    return task


def _routing(
    request_id: int, error: str = "NONE", *, from_num: int = REMOTE_NUM
) -> dict[str, Any]:
    """Return the routing packet the mesh answers one request with."""
    return {
        "from": from_num,
        "to": GATEWAY_NUM,
        "fromId": f"!{from_num:08x}",
        "toId": GATEWAY_ID,
        "channel": 0,
        "id": 987600000 + (request_id % 1000),
        "rxTime": 1757300500,
        "priority": "ACK",
        "decoded": {
            "portnum": "ROUTING_APP",
            "requestId": request_id,
            "routing": {"errorReason": error},
        },
    }


def _answer(packet: dict[str, Any], request_id: int) -> dict[str, Any]:
    """Return a copy of a fixture packet that answers one request."""
    answer = copy.deepcopy(packet)
    answer["decoded"]["requestId"] = request_id
    answer["to"] = GATEWAY_NUM
    answer["toId"] = GATEWAY_ID
    return answer


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


async def test_only_the_actions_no_entity_can_replace_are_registered(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test the exact set of actions, and that unloading the entry keeps them.

    Anything an entity can express is an entity: the node request buttons, the
    favourite and ignored switches and the gateway's restart button.  What is
    left over either takes a parameter no entity has, answers with a payload or
    is node-database maintenance, so every operation has one implementation and
    therefore one authorisation model.
    """
    actions = {
        SERVICE_EXPORT_CONFIG,
        SERVICE_REFRESH_NODES,
        SERVICE_REMOVE_NODE,
        SERVICE_REQUEST_TRACEROUTE,
        SERVICE_SEND_MESSAGE,
    }
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    assert set(hass.services.async_services_for_domain(DOMAIN)) == actions

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    # Registered in async_setup, so an automation still validates with no entry.
    assert set(hass.services.async_services_for_domain(DOMAIN)) == actions


# ---------------------------------------------------------------------------
# send_message
# ---------------------------------------------------------------------------


async def test_send_message_broadcast(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test broadcasting on a channel and the response it returns."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await _start(
        hass,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_MESSAGE: "hello everyone",
            "channel": 1,
        },
        return_response=True,
    )
    await inject_packet(
        hass,
        mock_pubsub,
        mock_meshtastic_client,
        _routing(TEXT_PACKET_ID, from_num=GATEWAY_NUM),
    )
    response = await task

    mock_meshtastic_client.sendText.assert_called_once_with(
        "hello everyone",
        destinationId=0xFFFFFFFF,
        wantAck=True,
        channelIndex=1,
        replyId=None,
    )
    assert response == {
        "packet_id": TEXT_PACKET_ID,
        "state": "acked_implicit",
        "delivered": True,
        "destination": "^all",
    }


@pytest.mark.parametrize(
    "destination", [REMOTE_ID, REMOTE_NUM, str(REMOTE_NUM), "0xaabbccdd"]
)
async def test_send_message_destination_forms(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    destination: str | int,
) -> None:
    """Test a node id, a node number and a hex id all reach the same node."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await _start(
        hass,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_MESSAGE: "are you there",
            ATTR_NODE: destination,
        },
        return_response=True,
    )
    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, _routing(TEXT_PACKET_ID)
    )
    response = await task

    assert mock_meshtastic_client.sendText.call_args.kwargs["destinationId"] == (
        REMOTE_NUM
    )
    assert response == {
        "packet_id": TEXT_PACKET_ID,
        "state": "acked",
        "delivered": True,
        "destination": REMOTE_ID,
    }


async def test_send_message_by_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a Home Assistant device id resolves the node and the entry."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, f"{GATEWAY_ID}_{REMOTE_ID}")},
    )

    # No config_entry_id: the device says which entry owns it.
    task = await _start(
        hass,
        SERVICE_SEND_MESSAGE,
        {ATTR_MESSAGE: "via the device", ATTR_NODE: device.id},
    )
    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, _routing(TEXT_PACKET_ID)
    )
    await task

    assert mock_meshtastic_client.sendText.call_args.kwargs["destinationId"] == (
        REMOTE_NUM
    )


async def test_send_message_without_acknowledgment(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that an unacknowledged send still reports the packet it made."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await _start(
        hass,
        SERVICE_SEND_MESSAGE,
        {ATTR_MESSAGE: "fire and forget", ATTR_WANT_ACK: False},
        return_response=True,
    )
    await inject_packet(
        hass,
        mock_pubsub,
        mock_meshtastic_client,
        _routing(TEXT_PACKET_ID, from_num=GATEWAY_NUM),
    )
    response = await task

    assert mock_meshtastic_client.sendText.call_args.kwargs["wantAck"] is False
    assert response is not None
    assert response["delivered"] is True


async def test_send_message_unknown_node(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a destination that is not a node id is refused."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            {ATTR_MESSAGE: "hello", ATTR_NODE: "Remote One"},
            blocking=True,
        )
    assert err.value.translation_key == "unknown_node"
    mock_meshtastic_client.sendText.assert_not_called()


async def test_send_message_empty_is_rejected_by_the_schema(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that an empty message never reaches the radio."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, SERVICE_SEND_MESSAGE, {ATTR_MESSAGE: ""}, blocking=True
        )
    mock_meshtastic_client.sendText.assert_not_called()


async def test_send_message_on_a_disabled_channel(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a channel slot the node does not use is refused."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            {ATTR_MESSAGE: "hello", "channel": 2},
            blocking=True,
        )
    assert err.value.translation_key == "invalid_channel"
    mock_meshtastic_client.sendText.assert_not_called()


async def test_send_message_too_long(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that an oversized message is refused before it hits the radio."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            {ATTR_MESSAGE: "x" * 300, ATTR_NODE: REMOTE_ID},
            blocking=True,
        )
    assert err.value.translation_key == "message_too_long"
    mock_meshtastic_client.sendText.assert_not_called()


@pytest.mark.parametrize(
    "error", [name for name in ROUTING_ERROR_TRANSLATION_KEYS if name != "NONE"]
)
async def test_send_message_routing_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    error: str,
) -> None:
    """Test that every Routing.Error becomes its own translated error."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    expected_key = ROUTING_ERROR_TRANSLATION_KEYS[error]

    task = await _start(
        hass, SERVICE_SEND_MESSAGE, {ATTR_MESSAGE: "hello", ATTR_NODE: REMOTE_ID}
    )
    if error == NOTIFICATION_REJECTED:
        # A ClientNotification is how the firmware refuses without routing.
        await inject_notification(
            hass,
            mock_pubsub,
            mock_meshtastic_client,
            SimpleNamespace(
                message="TraceRoute can only be sent once every 30 seconds",
                reply_id=TEXT_PACKET_ID,
                time=0,
            ),
        )
    else:
        await inject_packet(
            hass, mock_pubsub, mock_meshtastic_client, _routing(TEXT_PACKET_ID, error)
        )

    with pytest.raises(HomeAssistantError) as err:
        await task
    assert err.value.translation_key == expected_key
    assert isinstance(err.value, ServiceValidationError) is (
        error in ROUTING_ERROR_VALIDATION
    )


async def test_send_message_while_disconnected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that an action on an entry whose entry is gone is refused."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                ATTR_MESSAGE: "hello",
            },
            blocking=True,
        )
    assert err.value.translation_key == "service_config_entry_not_loaded"


async def test_send_message_unknown_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that an unknown config entry id is refused."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            {ATTR_CONFIG_ENTRY_ID: "does-not-exist", ATTR_MESSAGE: "hello"},
            blocking=True,
        )
    assert err.value.translation_key == "service_config_entry_not_found"


async def test_action_on_a_foreign_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a device belonging to another integration is refused."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    other = MockConfigEntry(domain="other")
    other.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=other.entry_id, identifiers={("other", "thing")}
    )

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            {ATTR_MESSAGE: "hello", ATTR_NODE: device.id},
            blocking=True,
        )
    assert err.value.translation_key == "service_device_wrong_domain"


# ---------------------------------------------------------------------------
# request_traceroute
# ---------------------------------------------------------------------------


async def test_request_traceroute(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    packet_fixtures: dict[str, dict[str, Any]],
) -> None:
    """Test that a traceroute returns both legs of the route with their SNR."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    answer = _answer(packet_fixtures["packet_traceroute"], DATA_PACKET_ID)
    # An unmeasured hop, as the firmware reports it.
    answer["decoded"]["traceroute"]["snrBack"] = [16, -128]

    task = await _start(
        hass, SERVICE_REQUEST_TRACEROUTE, {ATTR_NODE: REMOTE_ID}, return_response=True
    )
    # The answer is an ordinary packet quoting the request id, correlated from
    # pubsub like every other response.
    await inject_packet(hass, mock_pubsub, mock_meshtastic_client, answer)
    response = await task

    call = mock_meshtastic_client.sendData.call_args
    assert call.args[0] == b""
    assert call.kwargs["portNum"] == 70
    assert call.kwargs["destinationId"] == REMOTE_NUM
    assert call.kwargs["wantAck"] is True
    # No one-shot handler is filed, so none can be left behind.
    assert "onResponse" not in call.kwargs
    assert response == {
        "node_id": REMOTE_ID,
        "node": "Remote One",
        "route_towards": [GATEWAY_ID, "!deadbeef", REMOTE_ID],
        "snr_towards": [5.0, 3.0],
        "route_back": [REMOTE_ID, "!deadbeef", GATEWAY_ID],
        "snr_back": [4.0, None],
    }


async def test_request_traceroute_without_a_route(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    packet_fixtures: dict[str, dict[str, Any]],
) -> None:
    """Test an answer on the traceroute port that carries no route."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    answer = _answer(packet_fixtures["packet_traceroute"], DATA_PACKET_ID)
    del answer["decoded"]["traceroute"]

    task = await _start(hass, SERVICE_REQUEST_TRACEROUTE, {ATTR_NODE: REMOTE_ID})
    await inject_packet(hass, mock_pubsub, mock_meshtastic_client, answer)

    with pytest.raises(HomeAssistantError) as err:
        await task
    assert err.value.translation_key == "no_response"


async def test_a_traceroute_answer_without_snr_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    packet_fixtures: dict[str, dict[str, Any]],
) -> None:
    """Test an answer that carries the route but no SNR measurements."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    answer = _answer(packet_fixtures["packet_traceroute"], DATA_PACKET_ID)
    del answer["decoded"]["traceroute"]["snrTowards"]
    del answer["decoded"]["traceroute"]["snrBack"]

    task = await _start(
        hass, SERVICE_REQUEST_TRACEROUTE, {ATTR_NODE: REMOTE_ID}, return_response=True
    )
    await inject_packet(hass, mock_pubsub, mock_meshtastic_client, answer)
    response = await task

    assert response is not None
    assert response["route_towards"] == [GATEWAY_ID, "!deadbeef", REMOTE_ID]
    assert response["snr_towards"] == []
    assert response["snr_back"] == []


async def test_a_traceroute_that_loses_the_link_still_reports_the_link(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a link lost mid-traceroute reports the traceroute's verdict.

    The request is already in flight when the interface goes away; what the
    caller has to see is why the traceroute failed, not an error from anything
    the action does afterwards.
    """
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await _start(hass, SERVICE_REQUEST_TRACEROUTE, {ATTR_NODE: REMOTE_ID})
    await inject_connection_lost(hass, mock_pubsub, mock_meshtastic_client)

    with pytest.raises(HomeAssistantError) as err:
        await task
    # The traceroute's own verdict, not "not connected" from somewhere else.
    assert err.value.translation_key == "timeout_no_ack"


async def test_request_traceroute_rate_limited(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test the firmware refusing a traceroute with a client notification."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await _start(hass, SERVICE_REQUEST_TRACEROUTE, {ATTR_NODE: REMOTE_ID})
    await inject_notification(
        hass,
        mock_pubsub,
        mock_meshtastic_client,
        SimpleNamespace(
            message="TraceRoute can only be sent once every 30 seconds",
            reply_id=DATA_PACKET_ID,
            time=0,
        ),
    )

    with pytest.raises(ServiceValidationError) as err:
        await task
    assert err.value.translation_key == "client_rejected"


async def test_request_traceroute_broadcast_is_refused(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a multi-hop broadcast traceroute is refused, as it must be."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, SERVICE_REQUEST_TRACEROUTE, {ATTR_NODE: "^all"}, blocking=True
        )
    assert err.value.translation_key == "broadcast_not_supported"


async def test_an_unanswered_traceroute_leaves_no_response_handler(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that the traceroute never files the library's one-shot handler.

    ``MeshInterface._addResponseHandler`` files a callback under the packet id
    and removes it only when it fires; its own ``FIXME`` says nothing ages the
    entries out.  An automation tracing a node that never answers would leave
    one dead handler, and everything its closure holds, behind on every
    attempt.  The route comes back through the tracker instead, so no handler
    is ever registered and there is nothing to leak.
    """
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    handlers: dict[int, Any] = {}
    mock_meshtastic_client.responseHandlers = handlers

    def _send_data(*args: Any, **kwargs: Any) -> mesh_pb2.MeshPacket:
        """File the response handler the way the library would."""
        if (on_response := kwargs.get("onResponse")) is not None:
            handlers[DATA_PACKET_ID] = on_response
        return mesh_pb2.MeshPacket(id=DATA_PACKET_ID)

    mock_meshtastic_client.sendData.side_effect = _send_data

    task = await _start(hass, SERVICE_REQUEST_TRACEROUTE, {ATTR_NODE: REMOTE_ID})
    assert handlers == {}
    freezer.tick(timedelta(seconds=91))
    async_fire_time_changed(hass)

    with pytest.raises(HomeAssistantError):
        await task

    assert handlers == {}


# ---------------------------------------------------------------------------
# refresh_nodes
# ---------------------------------------------------------------------------


async def test_refresh_nodes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that the node-database refresh uses the nodes-only nonce."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_REFRESH_NODES,
        {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id},
        blocking=True,
    )

    mock_meshtastic_client._sendToRadio.assert_called_once()
    sent = mock_meshtastic_client._sendToRadio.call_args.args[0]
    assert sent.want_config_id == 69421
    # A refresh must not restart the handshake or drop the node table.
    mock_meshtastic_client.close.assert_not_called()


async def test_refresh_nodes_merges_the_records_it_streams(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that the nodes the refresh streams land in the coordinator."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    coordinator = mock_config_entry.runtime_data.coordinator
    assert coordinator.get_node("!deadbeef") is None

    await hass.services.async_call(DOMAIN, SERVICE_REFRESH_NODES, {}, blocking=True)
    await inject_node_info(
        hass, mock_pubsub, mock_meshtastic_client, node_fixtures["!deadbeef"]
    )

    assert (node := coordinator.get_node("!deadbeef")) is not None
    assert node.num == SENSOR_NODE_NUM


async def test_refresh_nodes_requires_an_administrator(
    hass: HomeAssistant,
    hass_read_only_user: Any,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a non-administrator cannot restart the node-info stream.

    While the database streams, the node is out of its packet-forwarding state
    and drops what it receives, so this is not something every user may trigger.
    """
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH_NODES,
            {},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )
    mock_meshtastic_client._sendToRadio.assert_not_called()


async def test_refresh_nodes_is_paced(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that refreshes cannot follow each other without a pause.

    Nothing else limits this send, so an automation on a short interval would
    restart the node-info stream over and over and the node would stop serving
    the packets it receives.
    """
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    await hass.services.async_call(DOMAIN, SERVICE_REFRESH_NODES, {}, blocking=True)
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN, SERVICE_REFRESH_NODES, {}, blocking=True)

    assert err.value.translation_key == "refresh_too_soon"
    assert mock_meshtastic_client._sendToRadio.call_count == 1

    freezer.tick(timedelta(seconds=REFRESH_NODES_SPACING + 1))
    await hass.services.async_call(DOMAIN, SERVICE_REFRESH_NODES, {}, blocking=True)

    assert mock_meshtastic_client._sendToRadio.call_count == 2


async def test_a_refresh_that_never_reached_the_node_keeps_no_pause(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a refused refresh does not use up the pause.

    The pause exists to spare the node; a call that never got as far as the
    node has nothing to spare it from, and the user must be able to try again
    as soon as the link is back.
    """
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    await inject_connection_lost(hass, mock_pubsub, mock_meshtastic_client)

    with pytest.raises(HomeAssistantError) as first:
        await hass.services.async_call(DOMAIN, SERVICE_REFRESH_NODES, {}, blocking=True)
    with pytest.raises(HomeAssistantError) as second:
        await hass.services.async_call(DOMAIN, SERVICE_REFRESH_NODES, {}, blocking=True)

    assert first.value.translation_key == "not_connected"
    assert second.value.translation_key == "not_connected"
    mock_meshtastic_client._sendToRadio.assert_not_called()


@pytest.mark.parametrize("download_node_db", [True, False])
async def test_refresh_nodes_notes_the_dump_the_option_avoids(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    download_node_db: bool,
) -> None:
    """Test that a refresh on an entry that avoids the dump says so.

    ``download_node_db`` is off by default because a node without PSRAM can run
    out of memory over a full dump.  The action performs exactly that dump, so
    a node that dies right afterwards can be explained from the log.
    """
    entry = _entry(download_node_db=download_node_db)
    await _setup(hass, entry, mock_pubsub, mock_meshtastic_client, node_fixtures)

    await hass.services.async_call(DOMAIN, SERVICE_REFRESH_NODES, {}, blocking=True)

    mock_meshtastic_client._sendToRadio.assert_called_once()
    assert (
        "node database download switched off" in caplog.text
    ) is not download_node_db


# ---------------------------------------------------------------------------
# export_config
# ---------------------------------------------------------------------------


async def test_export_config(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test the exported structure, including the redacted key material."""
    local_node = mock_meshtastic_client.localNode
    local_node.localConfig.security.private_key = b"\x01" * 32
    local_node.localConfig.security.public_key = b"\x02" * 32
    local_node.localConfig.security.admin_key.append(b"\x03" * 32)
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_EXPORT_CONFIG,
        {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert response["owner"] == "HA Gateway"
    assert response["owner_short"] == "HAGW"
    assert response["config"]["lora"]["region"] == "EU_868"
    assert response["config"]["lora"]["hop_limit"] == 3
    assert response["config"]["security"]["private_key"] == REDACTED
    assert response["config"]["security"]["admin_key"] == REDACTED
    # The public key is not a secret and is what identifies the node.
    assert (
        response["config"]["security"]["public_key"]
        == "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgI="
    )
    assert response["module_config"] == {}
    assert "location" not in response
    # Nothing goes on the air for an export.
    mock_meshtastic_client.sendData.assert_not_called()
    mock_meshtastic_client.sendText.assert_not_called()


async def test_export_config_redacts_every_credential(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that no password, key or PIN the node holds reaches the response.

    Whoever may run the action sees the whole response, and it is stored in the
    trace of the automation that asked for it, so it must not carry anything
    that lets a reader onto the node's Wi-Fi, its MQTT broker or the node.
    """
    config = mock_meshtastic_client.localNode.localConfig
    config.network.wifi_enabled = True
    config.network.wifi_ssid = "HomeWiFi"
    config.network.wifi_psk = "correct-horse-battery-staple"
    config.bluetooth.enabled = True
    config.bluetooth.fixed_pin = 123456
    config.security.private_key = b"\x01" * 32
    config.security.admin_key.append(b"\x03" * 32)
    module_config = mock_meshtastic_client.localNode.moduleConfig
    module_config.mqtt.enabled = True
    module_config.mqtt.address = "mqtt.example.invalid"
    module_config.mqtt.username = "meshdev"
    module_config.mqtt.password = "S3cret!"
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    response = await hass.services.async_call(
        DOMAIN, SERVICE_EXPORT_CONFIG, {}, blocking=True, return_response=True
    )

    assert response is not None
    network = response["config"]["network"]
    mqtt = response["module_config"]["mqtt"]
    assert network["wifi_psk"] == REDACTED
    assert mqtt["username"] == REDACTED
    assert mqtt["password"] == REDACTED
    assert response["config"]["bluetooth"]["fixed_pin"] == REDACTED
    assert response["config"]["security"]["private_key"] == REDACTED
    assert response["config"]["security"]["admin_key"] == REDACTED
    # Everything that is not a credential is still exported.
    assert network["wifi_ssid"] == "HomeWiFi"
    assert mqtt["address"] == "mqtt.example.invalid"
    rendered = json.dumps(response)
    assert "correct-horse-battery-staple" not in rendered
    assert "S3cret!" not in rendered
    assert "meshdev" not in rendered


async def test_export_config_never_returns_the_channel_url(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that the mesh's channel keys are not part of the response.

    ``Node.getURL()`` serialises the ``ChannelSettings`` of every channel, and
    the pre-shared key is part of that: whoever holds the URL can decrypt the
    mesh and transmit on it.  The key is the payload of that URL, so there is
    no partial redaction to do -- it is not read at all.
    """
    local_node = mock_meshtastic_client.localNode
    local_node.getURL = MagicMock(return_value="https://meshtastic.org/e/#Ck0SIA")
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    response = await hass.services.async_call(
        DOMAIN, SERVICE_EXPORT_CONFIG, {}, blocking=True, return_response=True
    )

    assert response is not None
    assert "channel_url" not in response
    assert "meshtastic.org/e/" not in json.dumps(response)
    local_node.getURL.assert_not_called()


async def test_export_config_requires_an_administrator(
    hass: HomeAssistant,
    hass_read_only_user: Any,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a non-administrator cannot read the node's configuration."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_EXPORT_CONFIG,
            {},
            blocking=True,
            return_response=True,
            context=Context(user_id=hass_read_only_user.id),
        )


async def test_export_config_omits_the_gateway_location_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that the coordinates need the same opt-in as the diagnostics.

    A response outlives the call in an automation trace, and the position of a
    fixed node is the position of somebody's home.
    """
    mock_meshtastic_client.localNode.localConfig.position.fixed_position = True
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    response = await hass.services.async_call(
        DOMAIN, SERVICE_EXPORT_CONFIG, {}, blocking=True, return_response=True
    )

    assert response is not None
    # That the node has a fixed position is not the same as where it is.
    assert response["config"]["position"]["fixed_position"] is True
    assert "location" not in response


async def test_export_config_with_a_fixed_position(
    hass: HomeAssistant,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that an opted-in fixed position is exported as the CLI does it."""
    mock_meshtastic_client.localNode.localConfig.position.fixed_position = True
    entry = _entry(options={CONF_INCLUDE_LOCATION: True})
    await _setup(hass, entry, mock_pubsub, mock_meshtastic_client, node_fixtures)

    response = await hass.services.async_call(
        DOMAIN, SERVICE_EXPORT_CONFIG, {}, blocking=True, return_response=True
    )

    assert response is not None
    assert response["location"] == {
        "latitude": pytest.approx(52.1234567),
        "longitude": pytest.approx(13.1234567),
        "altitude": 38,
    }


async def test_export_config_without_a_configuration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test a node that never sent its configuration."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    mock_meshtastic_client.localNode = SimpleNamespace(localConfig=None)

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN, SERVICE_EXPORT_CONFIG, {}, blocking=True, return_response=True
        )
    assert err.value.translation_key == "no_config"


async def test_export_config_of_a_node_with_module_configuration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that nested messages, repeated fields and enums are all rendered."""
    local_node = mock_meshtastic_client.localNode
    local_node.moduleConfig.mqtt.enabled = True
    local_node.moduleConfig.mqtt.address = "mqtt.example.invalid"
    local_node.moduleConfig.mqtt.map_reporting_enabled = True
    local_node.moduleConfig.mqtt.map_report_settings.publish_interval_secs = 3600
    local_node.moduleConfig.telemetry.device_update_interval = 900
    local_node.localConfig.lora.ignore_incoming.extend([REMOTE_NUM, SENSOR_NODE_NUM])
    local_node.localConfig.device.role = 2
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    response = await hass.services.async_call(
        DOMAIN, SERVICE_EXPORT_CONFIG, {}, blocking=True, return_response=True
    )

    assert response is not None
    assert response["module_config"]["mqtt"]["address"] == "mqtt.example.invalid"
    assert response["module_config"]["telemetry"]["device_update_interval"] == 900
    # A repeated scalar field keeps its members, and an enum reads as its name.
    assert response["config"]["lora"]["ignore_incoming"] == [
        REMOTE_NUM,
        SENSOR_NODE_NUM,
    ]
    # A nested message becomes a nested dict, and an enum reads as its name.
    assert response["module_config"]["mqtt"]["map_report_settings"] == {
        "publish_interval_secs": 3600
    }
    assert response["config"]["device"]["role"] == "ROUTER"


async def test_export_config_without_a_module_configuration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test a node whose module configuration was never downloaded."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    mock_meshtastic_client.localNode = SimpleNamespace(
        localConfig=mock_meshtastic_client.localNode.localConfig, moduleConfig=None
    )

    response = await hass.services.async_call(
        DOMAIN, SERVICE_EXPORT_CONFIG, {}, blocking=True, return_response=True
    )

    assert response is not None
    assert response["module_config"] == {}


# ---------------------------------------------------------------------------
# remove_node
# ---------------------------------------------------------------------------


async def test_remove_node(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a confirmed removal reaches the node database."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await _start(
        hass, SERVICE_REMOVE_NODE, {ATTR_NODE: REMOTE_ID, ATTR_CONFIRM: True}
    )
    await inject_packet(
        hass,
        mock_pubsub,
        mock_meshtastic_client,
        _routing(ADMIN_PACKET_ID, from_num=GATEWAY_NUM),
    )
    await task

    mock_meshtastic_client.localNode.removeNode.assert_called_once_with(REMOTE_NUM)


async def test_remove_node_without_confirmation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that an unconfirmed removal changes nothing."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REMOVE_NODE,
            {ATTR_NODE: REMOTE_ID, ATTR_CONFIRM: False},
            blocking=True,
        )
    assert err.value.translation_key == "confirmation_required"
    mock_meshtastic_client.localNode.removeNode.assert_not_called()


async def test_remove_node_refuses_the_gateway(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that the node Home Assistant is talking to cannot remove itself."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REMOVE_NODE,
            {ATTR_NODE: GATEWAY_ID, ATTR_CONFIRM: True},
            blocking=True,
        )
    assert err.value.translation_key == "cannot_remove_gateway"
    mock_meshtastic_client.localNode.removeNode.assert_not_called()


async def test_remove_node_requires_an_administrator(
    hass: HomeAssistant,
    hass_read_only_user: Any,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a non-administrator cannot remove a node."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REMOVE_NODE,
            {ATTR_NODE: REMOTE_ID, ATTR_CONFIRM: True},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )
    mock_meshtastic_client.localNode.removeNode.assert_not_called()


# ---------------------------------------------------------------------------
# Scope resolution
# ---------------------------------------------------------------------------


async def test_gateway_device_resolves_the_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that the gateway device can be used as a destination too."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, GATEWAY_ID), mock_config_entry.entry_id
    )
    assert device is not None

    task = await _start(
        hass, SERVICE_SEND_MESSAGE, {ATTR_MESSAGE: "note to self", ATTR_NODE: device.id}
    )
    await inject_packet(
        hass,
        mock_pubsub,
        mock_meshtastic_client,
        _routing(TEXT_PACKET_ID, from_num=GATEWAY_NUM),
    )
    await task

    assert mock_meshtastic_client.sendText.call_args.kwargs["destinationId"] == (
        GATEWAY_NUM
    )


async def test_config_entry_id_wins_over_the_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that an explicit entry is used even when a device is given."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, f"{GATEWAY_ID}_{REMOTE_ID}")},
    )

    task = await _start(
        hass,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_MESSAGE: "both given",
            ATTR_NODE: device.id,
        },
    )
    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, _routing(TEXT_PACKET_ID)
    )
    await task

    assert mock_meshtastic_client.sendText.call_args.kwargs["destinationId"] == (
        REMOTE_NUM
    )


async def test_device_id_is_not_a_field(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that unknown fields are refused rather than silently ignored."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            {ATTR_MESSAGE: "hello", ATTR_DEVICE_ID: "whatever"},
            blocking=True,
        )


# ---------------------------------------------------------------------------
# Calling without asking for a response
# ---------------------------------------------------------------------------


async def test_traceroute_without_a_response(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    packet_fixtures: dict[str, dict[str, Any]],
) -> None:
    """Test that a traceroute called without a response still runs."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await _start(hass, SERVICE_REQUEST_TRACEROUTE, {ATTR_NODE: REMOTE_ID})
    await inject_packet(
        hass,
        mock_pubsub,
        mock_meshtastic_client,
        _answer(packet_fixtures["packet_traceroute"], DATA_PACKET_ID),
    )

    assert await task is None


async def test_send_message_without_a_response(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that sending a message without asking for a response returns None."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await _start(hass, SERVICE_SEND_MESSAGE, {ATTR_MESSAGE: "hello"})
    await inject_packet(
        hass,
        mock_pubsub,
        mock_meshtastic_client,
        _routing(TEXT_PACKET_ID, from_num=GATEWAY_NUM),
    )

    assert await task is None


@pytest.mark.parametrize(
    "node",
    [
        pytest.param(True, id="a_boolean"),
        pytest.param("   ", id="whitespace"),
        pytest.param(-1, id="a_negative_number"),
        pytest.param("99999999999", id="a_number_beyond_the_broadcast_address"),
    ],
)
async def test_destination_is_validated_by_the_schema(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    node: Any,
) -> None:
    """Test that a destination that cannot be a node is refused up front.

    A node name would make the library look it up in its own table and call
    ``sys.exit()`` on a miss, so nothing but an identifier gets through.
    """
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, SERVICE_REQUEST_TRACEROUTE, {ATTR_NODE: node}, blocking=True
        )

    mock_meshtastic_client.sendData.assert_not_called()


async def test_a_node_the_mesh_has_not_named_is_labelled_by_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that an error about an unknown node still names it usefully."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await _start(hass, SERVICE_REQUEST_TRACEROUTE, {ATTR_NODE: "!00c0ffee"})
    await inject_packet(
        hass,
        mock_pubsub,
        mock_meshtastic_client,
        _routing(DATA_PACKET_ID, "NO_ROUTE", from_num=GATEWAY_NUM),
    )

    with pytest.raises(HomeAssistantError) as err:
        await task

    assert (err.value.translation_placeholders or {})["node"] == "!00c0ffee"
