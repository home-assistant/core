"""Test sandbox websocket entity registration and service forwarding."""

from unittest.mock import patch

import pytest

from homeassistant.components.sandbox.const import DATA_SANDBOX
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


@pytest.fixture
async def sandbox_ws(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> tuple:
    """Set up sandbox with a websocket client authenticated as the sandbox token."""
    assert await async_setup_component(hass, "sandbox", {})

    sandbox_id = "test_sandbox_ws"
    entry = MockConfigEntry(
        domain="sandbox",
        entry_id=sandbox_id,
        data={
            "entries": [
                {
                    "entry_id": "hue_entry_ws",
                    "domain": "hue",
                    "title": "Hue Bridge",
                    "data": {"host": "192.168.1.100"},
                }
            ]
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.sandbox._spawn_sandbox",
        return_value=None,
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    sandbox_data = hass.data[DATA_SANDBOX]
    instance = sandbox_data.sandboxes[sandbox_id]

    client = await hass_ws_client(hass, access_token=instance.access_token)
    return hass, client, sandbox_id


async def test_register_entity_via_ws(sandbox_ws: tuple) -> None:
    """Test registering an entity via websocket creates a proxy light."""
    hass, client, sandbox_id = sandbox_ws

    # Subscribe to entity commands first
    await client.send_json({"id": 1, "type": "sandbox/subscribe_entity_commands"})
    resp = await client.receive_json()
    assert resp["success"]

    # Register a light entity
    await client.send_json(
        {
            "id": 2,
            "type": "sandbox/register_entity",
            "sandbox_entry_id": "hue_entry_ws",
            "domain": "light",
            "platform": "hue",
            "unique_id": "hue_light_1",
            "original_name": "Living Room Light",
            "supported_features": 0,
            "capabilities": {"supported_color_modes": ["brightness"]},
            "suggested_object_id": "living_room_light",
        }
    )
    resp = await client.receive_json()
    assert resp["success"]
    entity_id = resp["result"]["entity_id"]
    assert entity_id.startswith("light.")

    # Push state update
    await client.send_json(
        {
            "id": 3,
            "type": "sandbox/update_state",
            "entity_id": entity_id,
            "state": "on",
            "attributes": {"brightness": 255, "color_mode": "brightness"},
        }
    )
    resp = await client.receive_json()
    assert resp["success"]

    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"
    assert state.attributes.get("brightness") == 255


async def test_entity_command_forwarding_via_ws(sandbox_ws: tuple) -> None:
    """Test that service calls on proxy entities forward to sandbox via ws."""
    hass, client, sandbox_id = sandbox_ws

    # Subscribe to entity commands
    await client.send_json({"id": 1, "type": "sandbox/subscribe_entity_commands"})
    resp = await client.receive_json()
    assert resp["success"]

    # Register a light entity
    await client.send_json(
        {
            "id": 2,
            "type": "sandbox/register_entity",
            "sandbox_entry_id": "hue_entry_ws",
            "domain": "light",
            "platform": "hue",
            "unique_id": "hue_light_cmd",
            "original_name": "Command Light",
            "supported_features": 0,
            "capabilities": {"supported_color_modes": ["brightness"]},
            "suggested_object_id": "command_light",
        }
    )
    resp = await client.receive_json()
    assert resp["success"]
    entity_id = resp["result"]["entity_id"]

    # Push initial state so entity is "on"
    await client.send_json(
        {
            "id": 3,
            "type": "sandbox/update_state",
            "entity_id": entity_id,
            "state": "on",
            "attributes": {"brightness": 128, "color_mode": "brightness"},
        }
    )
    resp = await client.receive_json()
    assert resp["success"]
    await hass.async_block_till_done()

    # Call turn_off on the entity via HA services
    import asyncio

    async def call_service():
        await hass.services.async_call(
            "light", "turn_off", {"entity_id": entity_id}, blocking=True
        )

    # Start the service call in the background (it will block waiting for response)
    task = asyncio.create_task(call_service())

    # Receive the command forwarded to sandbox
    cmd_msg = await client.receive_json()
    assert cmd_msg["type"] == "event"
    event = cmd_msg["event"]
    assert event["type"] == "call_method"
    assert event["entity_id"] == entity_id
    assert event["method"] == "async_turn_off"

    # Send result back
    call_id = event["call_id"]
    await client.send_json(
        {
            "id": 4,
            "type": "sandbox/entity_command_result",
            "call_id": call_id,
            "success": True,
        }
    )
    resp = await client.receive_json()
    assert resp["success"]

    # Service call should complete
    await task
