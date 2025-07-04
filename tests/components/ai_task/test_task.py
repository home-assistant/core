"""Test tasks for the AI Task integration."""

from freezegun import freeze_time
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ai_task import AITaskEntityFeature, async_generate_data
from homeassistant.components.conversation import async_get_chat_log
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import chat_session

from .conftest import TEST_ENTITY_ID, MockAITaskEntity

from tests.typing import WebSocketGenerator


async def test_run_task_preferred_entity(
    hass: HomeAssistant,
    init_components: None,
    mock_ai_task_entity: MockAITaskEntity,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test running a task with an unknown entity."""
    client = await hass_ws_client(hass)

    with pytest.raises(
        HomeAssistantError, match="No entity_id provided and no preferred entity set"
    ):
        await async_generate_data(
            hass,
            task_name="Test Task",
            instructions="Test prompt",
        )

    await client.send_json_auto_id(
        {
            "type": "ai_task/preferences/set",
            "gen_data_entity_id": "ai_task.unknown",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]

    with pytest.raises(
        HomeAssistantError, match="AI Task entity ai_task.unknown not found"
    ):
        await async_generate_data(
            hass,
            task_name="Test Task",
            instructions="Test prompt",
        )

    await client.send_json_auto_id(
        {
            "type": "ai_task/preferences/set",
            "gen_data_entity_id": TEST_ENTITY_ID,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    result = await async_generate_data(
        hass,
        task_name="Test Task",
        instructions="Test prompt",
    )
    assert result.data == "Mock result"
    as_dict = result.as_dict()
    assert as_dict["conversation_id"] == result.conversation_id
    assert as_dict["data"] == "Mock result"
    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNKNOWN

    mock_ai_task_entity.supported_features = AITaskEntityFeature(0)
    with pytest.raises(
        HomeAssistantError,
        match="AI Task entity ai_task.test_task_entity does not support generating data",
    ):
        await async_generate_data(
            hass,
            task_name="Test Task",
            instructions="Test prompt",
        )


async def test_run_data_task_unknown_entity(
    hass: HomeAssistant,
    init_components: None,
) -> None:
    """Test running a data task with an unknown entity."""

    with pytest.raises(
        HomeAssistantError, match="AI Task entity ai_task.unknown_entity not found"
    ):
        await async_generate_data(
            hass,
            task_name="Test Task",
            entity_id="ai_task.unknown_entity",
            instructions="Test prompt",
        )


@freeze_time("2025-06-14 22:59:00")
async def test_run_data_task_updates_chat_log(
    hass: HomeAssistant,
    init_components: None,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that running a data task updates the chat log."""
    result = await async_generate_data(
        hass,
        task_name="Test Task",
        entity_id=TEST_ENTITY_ID,
        instructions="Test prompt",
    )
    assert result.data == "Mock result"

    with (
        chat_session.async_get_chat_session(hass, result.conversation_id) as session,
        async_get_chat_log(hass, session) as chat_log,
    ):
        assert chat_log.content == snapshot
