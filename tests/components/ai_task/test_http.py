"""Test the HTTP API for AI Task integration."""

import pytest

from homeassistant.components.ai_task import DATA_PREFERENCES
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .conftest import TEST_ENTITY_ID

from tests.typing import WebSocketGenerator


@pytest.mark.parametrize(
    "msg_extra",
    [
        {},
        {"entity_id": TEST_ENTITY_ID},
    ],
)
async def test_ws_generate_text(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_components: None,
    msg_extra: dict,
) -> None:
    """Test running a generate text task via the WebSocket API."""
    hass.data[DATA_PREFERENCES].async_set_preferences(gen_text_entity_id=TEST_ENTITY_ID)
    entity = hass.states.get(TEST_ENTITY_ID)
    assert entity is not None
    assert entity.state == STATE_UNKNOWN

    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "ai_task/generate_text",
            "task_name": "Test Task",
            "instructions": "Test prompt",
        }
        | msg_extra
    )

    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"]["result"] == "Mock result"

    entity = hass.states.get(TEST_ENTITY_ID)
    assert entity.state != STATE_UNKNOWN


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

    # Set only one preference
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

    # Clear a preference
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
