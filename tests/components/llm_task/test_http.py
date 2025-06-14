"""Test the HTTP API for LLM Task integration."""

from homeassistant.components.llm_task import LLMTaskType
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .conftest import TEST_ENTITY_ID

from tests.typing import WebSocketGenerator


async def test_ws_run_task(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_components: None,
) -> None:
    """Test running a task via the WebSocket API."""
    entity = hass.states.get(TEST_ENTITY_ID)
    assert entity is not None
    assert entity.state == STATE_UNKNOWN

    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "llm_task/run_task",
            "task_name": "Test Task",
            "entity_id": TEST_ENTITY_ID,
            "task_type": LLMTaskType.SUMMARY.value,
            "prompt": "Test prompt",
        }
    )

    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"]["result"] == "Mock result"

    entity = hass.states.get(TEST_ENTITY_ID)
    assert entity.state != STATE_UNKNOWN
