"""Test the HTTP API for AI Task integration."""

from homeassistant.core import HomeAssistant

from tests.typing import WebSocketGenerator


async def test_ws_preferences(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_components: None,
) -> None:
    """Test preferences via the WebSocket API."""
    client = await hass_ws_client(hass)

    # Get initial preferences
    await client.send_json_auto_id({"type": "ai_task/preferences/get"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "gen_text_entity_id": None,
    }

    # Set preferences
    await client.send_json_auto_id(
        {
            "type": "ai_task/preferences/set",
            "gen_text_entity_id": "ai_task.summary_1",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "gen_text_entity_id": "ai_task.summary_1",
    }

    # Get updated preferences
    await client.send_json_auto_id({"type": "ai_task/preferences/get"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "gen_text_entity_id": "ai_task.summary_1",
    }

    # Update an existing preference
    await client.send_json_auto_id(
        {
            "type": "ai_task/preferences/set",
            "gen_text_entity_id": "ai_task.summary_2",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "gen_text_entity_id": "ai_task.summary_2",
    }

    # Get updated preferences
    await client.send_json_auto_id({"type": "ai_task/preferences/get"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "gen_text_entity_id": "ai_task.summary_2",
    }

    # No preferences set will preserve existing preferences
    await client.send_json_auto_id(
        {
            "type": "ai_task/preferences/set",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "gen_text_entity_id": "ai_task.summary_2",
    }

    # Get updated preferences
    await client.send_json_auto_id({"type": "ai_task/preferences/get"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "gen_text_entity_id": "ai_task.summary_2",
    }
