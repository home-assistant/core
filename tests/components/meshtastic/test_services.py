"""Tests for the Meshtastic actions."""

import asyncio
import copy
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
import voluptuous as vol

from homeassistant.components.meshtastic.const import (
    DOMAIN,
    NOTIFICATION_REJECTED,
    ROUTING_ERROR_TRANSLATION_KEYS,
    ROUTING_ERROR_VALIDATION,
)
from homeassistant.components.meshtastic.services import (
    ATTR_CONFIRM,
    ATTR_DELAY,
    ATTR_ENABLED,
    ATTR_MESSAGE,
    ATTR_NODE,
    ATTR_TELEMETRY_TYPE,
    ATTR_WANT_ACK,
    SERVICE_EXPORT_CONFIG,
    SERVICE_REBOOT,
    SERVICE_REFRESH_NODES,
    SERVICE_REMOVE_NODE,
    SERVICE_REQUEST_POSITION,
    SERVICE_REQUEST_TELEMETRY,
    SERVICE_REQUEST_TRACEROUTE,
    SERVICE_SEND_MESSAGE,
    SERVICE_SET_FAVORITE,
    SERVICE_SET_IGNORED,
    TELEMETRY_REQUESTS,
)
from homeassistant.const import ATTR_CONFIG_ENTRY_ID, ATTR_DEVICE_ID
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
    inject_node_info,
    inject_notification,
    inject_packet,
    setup_integration,
)

from tests.common import MockConfigEntry

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
    # localNode is a stand-in, so give it the methods the actions reach for.
    for name in (
        "setFavorite",
        "removeFavorite",
        "setIgnored",
        "removeIgnored",
        "removeNode",
        "reboot",
    ):
        setattr(
            interface.localNode,
            name,
            MagicMock(return_value=SimpleNamespace(id=ADMIN_PACKET_ID)),
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


async def test_actions_are_registered_in_async_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that every action exists and survives unloading the entry."""
    actions = {
        SERVICE_EXPORT_CONFIG,
        SERVICE_REBOOT,
        SERVICE_REFRESH_NODES,
        SERVICE_REMOVE_NODE,
        SERVICE_REQUEST_POSITION,
        SERVICE_REQUEST_TELEMETRY,
        SERVICE_REQUEST_TRACEROUTE,
        SERVICE_SEND_MESSAGE,
        SERVICE_SET_FAVORITE,
        SERVICE_SET_IGNORED,
    }
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    assert actions <= set(hass.services.async_services_for_domain(DOMAIN))

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    # Registered in async_setup, so an automation still validates with no entry.
    assert actions <= set(hass.services.async_services_for_domain(DOMAIN))


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
# request_telemetry
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "family", ["device", "environment", "power", "air_quality", "local_stats"]
)
async def test_request_telemetry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    packet_fixtures: dict[str, dict[str, Any]],
    family: str,
) -> None:
    """Test that every telemetry family can be asked for and comes back."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await _start(
        hass,
        SERVICE_REQUEST_TELEMETRY,
        {ATTR_NODE: REMOTE_ID, ATTR_TELEMETRY_TYPE: family},
        return_response=True,
    )
    await inject_packet(
        hass,
        mock_pubsub,
        mock_meshtastic_client,
        _answer(packet_fixtures["packet_telemetry_device"], DATA_PACKET_ID),
    )
    response = await task

    call = mock_meshtastic_client.sendData.call_args
    assert call.args[0] == TELEMETRY_REQUESTS[family]
    assert call.kwargs["portNum"] == 67
    assert call.kwargs["destinationId"] == REMOTE_NUM
    assert call.kwargs["wantResponse"] is True
    assert response is not None
    assert response["node_id"] == REMOTE_ID
    assert response["node"] == "Remote One"
    assert response["telemetry"]["family"] == "device"
    assert response["telemetry"]["values"]["battery_level"] == 55


async def test_request_telemetry_broadcast_is_refused(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a telemetry request needs a single node."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, SERVICE_REQUEST_TELEMETRY, {ATTR_NODE: "^all"}, blocking=True
        )
    assert err.value.translation_key == "broadcast_not_supported"
    mock_meshtastic_client.sendData.assert_not_called()


async def test_request_telemetry_unknown_family(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a family the firmware never answers is refused."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REQUEST_TELEMETRY,
            {ATTR_NODE: REMOTE_ID, ATTR_TELEMETRY_TYPE: "health"},
            blocking=True,
        )


async def test_request_telemetry_answered_without_a_payload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    packet_fixtures: dict[str, dict[str, Any]],
) -> None:
    """Test the node answering on the right port but with nothing in it."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    empty = _answer(packet_fixtures["packet_telemetry_device"], DATA_PACKET_ID)
    del empty["decoded"]["telemetry"]

    task = await _start(
        hass, SERVICE_REQUEST_TELEMETRY, {ATTR_NODE: REMOTE_ID}, return_response=True
    )
    await inject_packet(hass, mock_pubsub, mock_meshtastic_client, empty)

    with pytest.raises(HomeAssistantError) as err:
        await task
    assert err.value.translation_key == "no_response"


async def test_request_telemetry_nak(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a refused telemetry request raises a translated error."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await _start(hass, SERVICE_REQUEST_TELEMETRY, {ATTR_NODE: REMOTE_ID})
    await inject_packet(
        hass,
        mock_pubsub,
        mock_meshtastic_client,
        _routing(DATA_PACKET_ID, "NO_RESPONSE"),
    )

    with pytest.raises(HomeAssistantError) as err:
        await task
    assert err.value.translation_key == "no_response"


# ---------------------------------------------------------------------------
# request_position
# ---------------------------------------------------------------------------


async def test_request_position(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    packet_fixtures: dict[str, dict[str, Any]],
) -> None:
    """Test that a position request returns the position the node answers."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await _start(
        hass, SERVICE_REQUEST_POSITION, {ATTR_NODE: REMOTE_ID}, return_response=True
    )
    await inject_packet(
        hass,
        mock_pubsub,
        mock_meshtastic_client,
        _answer(packet_fixtures["packet_position"], DATA_PACKET_ID),
    )
    response = await task

    call = mock_meshtastic_client.sendData.call_args
    assert call.args[0] == b""
    assert call.kwargs["portNum"] == 3
    assert call.kwargs["wantResponse"] is True
    assert response is not None
    assert response["node_id"] == REMOTE_ID
    assert response["position"]["latitude"] == pytest.approx(52.1111111)
    assert response["position"]["longitude"] == pytest.approx(13.1111111)
    assert response["position"]["altitude"] == 42


async def test_request_position_answered_without_a_payload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    packet_fixtures: dict[str, dict[str, Any]],
) -> None:
    """Test a position answer that carries no position."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    empty = _answer(packet_fixtures["packet_position"], DATA_PACKET_ID)
    del empty["decoded"]["position"]

    task = await _start(hass, SERVICE_REQUEST_POSITION, {ATTR_NODE: REMOTE_ID})
    await inject_packet(hass, mock_pubsub, mock_meshtastic_client, empty)

    with pytest.raises(HomeAssistantError) as err:
        await task
    assert err.value.translation_key == "no_response"


async def test_request_position_broadcast_is_refused(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a position request needs a single node."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, SERVICE_REQUEST_POSITION, {ATTR_NODE: "broadcast"}, blocking=True
        )
    assert err.value.translation_key == "broadcast_not_supported"


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
    # The library hands the route to the response handler while it decodes the
    # packet, and only then publishes it.
    on_response = mock_meshtastic_client.sendData.call_args.kwargs["onResponse"]
    on_response(answer)
    await inject_packet(hass, mock_pubsub, mock_meshtastic_client, answer)
    response = await task

    call = mock_meshtastic_client.sendData.call_args
    assert call.args[0] == b""
    assert call.kwargs["portNum"] == 70
    assert call.kwargs["destinationId"] == REMOTE_NUM
    assert call.kwargs["wantAck"] is True
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
    mock_meshtastic_client.sendData.call_args.kwargs["onResponse"](answer)
    await inject_packet(hass, mock_pubsub, mock_meshtastic_client, answer)

    with pytest.raises(HomeAssistantError) as err:
        await task
    assert err.value.translation_key == "no_response"


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
    local_node.getURL = MagicMock(return_value="https://meshtastic.org/e/#Ck0SIA")
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
    assert response["channel_url"] == "https://meshtastic.org/e/#Ck0SIA"
    assert response["config"]["lora"]["region"] == "EU_868"
    assert response["config"]["lora"]["hop_limit"] == 3
    assert response["config"]["security"]["private_key"] == "**REDACTED**"
    assert response["config"]["security"]["admin_key"] == "**REDACTED**"
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


async def test_export_config_with_a_fixed_position(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a fixed position is exported the way the CLI exports it."""
    mock_meshtastic_client.localNode.localConfig.position.fixed_position = True
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

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
    # A node that cannot produce a channel URL is still exportable.
    assert response["channel_url"] is None


# ---------------------------------------------------------------------------
# set_favorite / set_ignored
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("action", "enabled", "method"),
    [
        (SERVICE_SET_FAVORITE, True, "setFavorite"),
        (SERVICE_SET_FAVORITE, False, "removeFavorite"),
        (SERVICE_SET_IGNORED, True, "setIgnored"),
        (SERVICE_SET_IGNORED, False, "removeIgnored"),
    ],
)
async def test_node_flags(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    action: str,
    enabled: bool,
    method: str,
) -> None:
    """Test that each node flag is written with the right admin call."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await _start(hass, action, {ATTR_NODE: REMOTE_ID, ATTR_ENABLED: enabled})
    await inject_packet(
        hass,
        mock_pubsub,
        mock_meshtastic_client,
        _routing(ADMIN_PACKET_ID, from_num=GATEWAY_NUM),
    )
    await task

    getattr(mock_meshtastic_client.localNode, method).assert_called_once_with(
        REMOTE_NUM
    )


async def test_set_favorite_not_acknowledged(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a refused node-database write raises a translated error."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await _start(hass, SERVICE_SET_FAVORITE, {ATTR_NODE: REMOTE_ID})
    await inject_packet(
        hass,
        mock_pubsub,
        mock_meshtastic_client,
        _routing(ADMIN_PACKET_ID, "NOT_AUTHORIZED", from_num=GATEWAY_NUM),
    )

    with pytest.raises(HomeAssistantError) as err:
        await task
    assert err.value.translation_key == "admin_not_authorized"


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
# reboot
# ---------------------------------------------------------------------------


async def test_reboot(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a confirmed reboot opens the grace window."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    client = mock_config_entry.runtime_data.client
    assert client.reboot_grace_active is False

    task = await _start(hass, SERVICE_REBOOT, {ATTR_CONFIRM: True, ATTR_DELAY: 5})
    await inject_packet(
        hass,
        mock_pubsub,
        mock_meshtastic_client,
        _routing(ADMIN_PACKET_ID, from_num=GATEWAY_NUM),
    )
    await task

    mock_meshtastic_client.localNode.reboot.assert_called_once_with(5)
    # The node keeps answering for a few seconds and then drops off; entities
    # must not flap to unavailable in the meantime.
    assert client.reboot_grace_active is True


async def test_reboot_while_already_rebooting(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a second reboot while the node is on its way down is refused."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    mock_config_entry.runtime_data.client.async_note_reboot_expected()

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, SERVICE_REBOOT, {ATTR_CONFIRM: True}, blocking=True
        )
    assert err.value.translation_key == "reboot_in_progress"
    mock_meshtastic_client.localNode.reboot.assert_not_called()


async def test_reboot_without_confirmation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that an unconfirmed reboot changes nothing."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, SERVICE_REBOOT, {ATTR_CONFIRM: False}, blocking=True
        )
    assert err.value.translation_key == "confirmation_required"
    mock_meshtastic_client.localNode.reboot.assert_not_called()


async def test_reboot_requires_an_administrator(
    hass: HomeAssistant,
    hass_read_only_user: Any,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a non-administrator cannot reboot the node."""
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REBOOT,
            {ATTR_CONFIRM: True},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )
    mock_meshtastic_client.localNode.reboot.assert_not_called()


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


@pytest.mark.parametrize(
    ("action", "answer"),
    [
        (SERVICE_REQUEST_TELEMETRY, "packet_telemetry_device"),
        (SERVICE_REQUEST_POSITION, "packet_position"),
    ],
)
async def test_requests_without_a_response(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    packet_fixtures: dict[str, dict[str, Any]],
    action: str,
    answer: str,
) -> None:
    """Test that an action called for its side effect returns nothing.

    Every request action supports a response but does not require one, so an
    automation can simply ask a node to report and let the entities update.
    """
    await _setup(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await _start(hass, action, {ATTR_NODE: REMOTE_ID})
    await inject_packet(
        hass,
        mock_pubsub,
        mock_meshtastic_client,
        _answer(packet_fixtures[answer], DATA_PACKET_ID),
    )

    assert await task is None


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
    on_response = mock_meshtastic_client.sendData.call_args.kwargs["onResponse"]
    on_response(packet_fixtures["packet_traceroute"])
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
            DOMAIN, SERVICE_REQUEST_POSITION, {ATTR_NODE: node}, blocking=True
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

    task = await _start(hass, SERVICE_REQUEST_POSITION, {ATTR_NODE: "!00c0ffee"})
    await inject_packet(
        hass,
        mock_pubsub,
        mock_meshtastic_client,
        _routing(DATA_PACKET_ID, "NO_ROUTE", from_num=GATEWAY_NUM),
    )

    with pytest.raises(HomeAssistantError) as err:
        await task

    assert (err.value.translation_placeholders or {})["node"] == "!00c0ffee"
