"""Tests for the Infrared integration websocket API."""

from infrared_protocols.commands.nec import NECCommand
import pytest

from homeassistant.components.infrared import InfraredReceivedSignal
from homeassistant.components.infrared.code import code_to_frame, frames_match
from homeassistant.core import HomeAssistant

from .common import MockInfraredReceiverEntity

from tests.typing import WebSocketGenerator

RECEIVER_ENTITY_ID = "infrared.test_ir_receiver"

TEST_COMMAND = NECCommand(address=0x04FB, command=0xF7)


async def test_subscribe_receiver(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test received signals are forwarded as codes until unsubscribed."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "infrared/receiver/subscribe", "entity_id": RECEIVER_ENTITY_ID}
    )
    subscription = await client.receive_json()
    assert subscription["success"]

    signal = InfraredReceivedSignal(
        timings=TEST_COMMAND.get_raw_timings(), modulation=TEST_COMMAND.modulation
    )
    mock_infrared_receiver_entity._handle_received_signal(signal)

    event = await client.receive_json()
    assert event["event"]["code"]
    # The captured code must match the signal it was captured from.
    assert frames_match(signal.timings, code_to_frame(event["event"]["code"]))

    await client.send_json_auto_id(
        {"type": "unsubscribe_events", "subscription": subscription["id"]}
    )
    assert (await client.receive_json())["success"]

    mock_infrared_receiver_entity._handle_received_signal(signal)
    await client.send_json_auto_id({"type": "ping"})
    assert (await client.receive_json())["type"] == "pong"


@pytest.mark.usefixtures("mock_infrared_receiver_entity")
async def test_subscribe_receiver_discards_unusable_signal(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test a signal that cannot be encoded is not forwarded."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "infrared/receiver/subscribe", "entity_id": RECEIVER_ENTITY_ID}
    )
    assert (await client.receive_json())["success"]

    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=[])
    )
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=TEST_COMMAND.get_raw_timings(), modulation=TEST_COMMAND.modulation
        )
    )

    event = await client.receive_json()
    assert event["event"]["code"]


@pytest.mark.usefixtures("init_infrared")
async def test_subscribe_unknown_receiver(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test subscribing to an entity that is not an infrared receiver."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "infrared/receiver/subscribe", "entity_id": "infrared.does_not_exist"}
    )

    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "not_found"


@pytest.mark.usefixtures("mock_infrared_receiver_entity")
async def test_subscribe_receiver_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    """Test capturing codes requires admin access."""
    client = await hass_ws_client(hass, hass_read_only_access_token)
    await client.send_json_auto_id(
        {"type": "infrared/receiver/subscribe", "entity_id": RECEIVER_ENTITY_ID}
    )

    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "unauthorized"
