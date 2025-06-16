"""Test the HTTP API for AI Task integration."""

import pytest

from homeassistant.components.ai_task import DATA_PREFERENCES, GenTextTaskType
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .conftest import TEST_ENTITY_ID

from tests.typing import WebSocketGenerator


@pytest.mark.parametrize(
    "task_type", [GenTextTaskType.SUMMARY, GenTextTaskType.GENERATE]
)
async def test_ws_generate_text(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_components: None,
    task_type: GenTextTaskType,
) -> None:
    """Test running a task via the WebSocket API."""
    entity = hass.states.get(TEST_ENTITY_ID)
    assert entity is not None
    assert entity.state == STATE_UNKNOWN

    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "ai_task/generate_text",
            "task_name": "Test Task",
            "entity_id": TEST_ENTITY_ID,
            "task_type": task_type.value,
            "instructions": "Test prompt",
        }
    )

    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"]["result"] == "Mock result"

    entity = hass.states.get(TEST_ENTITY_ID)
    assert entity.state != STATE_UNKNOWN


@pytest.mark.parametrize(
    "task_type", [GenTextTaskType.SUMMARY, GenTextTaskType.GENERATE]
)
async def test_ws_run_task_preferred_entity(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_components: None,
    task_type: GenTextTaskType,
) -> None:
    """Test running a task via the WebSocket API."""
    preferences = hass.data[DATA_PREFERENCES]
    preferences_key = f"gen_text_{task_type.value}_entity_id"
    preferences.async_set_preferences(**{preferences_key: TEST_ENTITY_ID})

    entity = hass.states.get(TEST_ENTITY_ID)
    assert entity is not None
    assert entity.state == STATE_UNKNOWN

    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "ai_task/generate_text",
            "task_name": "Test Task",
            "task_type": task_type.value,
            "instructions": "Test prompt",
        }
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
        "gen_text_summary_entity_id": None,
        "gen_text_generate_entity_id": None,
    }

    # Set preferences
    await client.send_json_auto_id(
        {
            "type": "ai_task/preferences/set",
            "gen_text_summary_entity_id": "ai_task.summary_1",
            "gen_text_generate_entity_id": "ai_task.generate_1",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "gen_text_summary_entity_id": "ai_task.summary_1",
        "gen_text_generate_entity_id": "ai_task.generate_1",
    }

    # Get updated preferences
    await client.send_json_auto_id({"type": "ai_task/preferences/get"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "gen_text_summary_entity_id": "ai_task.summary_1",
        "gen_text_generate_entity_id": "ai_task.generate_1",
    }

    # Set only one preference
    await client.send_json_auto_id(
        {
            "type": "ai_task/preferences/set",
            "gen_text_summary_entity_id": "ai_task.summary_2",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "gen_text_summary_entity_id": "ai_task.summary_2",
        "gen_text_generate_entity_id": "ai_task.generate_1",
    }

    # Get updated preferences
    await client.send_json_auto_id({"type": "ai_task/preferences/get"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "gen_text_summary_entity_id": "ai_task.summary_2",
        "gen_text_generate_entity_id": "ai_task.generate_1",
    }

    # Clear a preference
    await client.send_json_auto_id(
        {
            "type": "ai_task/preferences/set",
            "gen_text_generate_entity_id": None,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "gen_text_summary_entity_id": "ai_task.summary_2",
        "gen_text_generate_entity_id": None,
    }

    # Get updated preferences
    await client.send_json_auto_id({"type": "ai_task/preferences/get"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "gen_text_summary_entity_id": "ai_task.summary_2",
        "gen_text_generate_entity_id": None,
    }
