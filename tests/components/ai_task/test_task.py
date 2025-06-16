"""Test tasks for the AI Task integration."""

from freezegun import freeze_time
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ai_task import (
    DATA_PREFERENCES,
    GenTextTaskType,
    async_generate_text,
)
from homeassistant.components.conversation import async_get_chat_log
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import chat_session

from .conftest import TEST_ENTITY_ID


@pytest.mark.parametrize(
    "task_type", [GenTextTaskType.SUMMARY, GenTextTaskType.GENERATE]
)
async def test_run_task_preferred_entity(
    hass: HomeAssistant,
    init_components: None,
    task_type: GenTextTaskType,
) -> None:
    """Test running a task with an unknown entity."""
    preferences = hass.data[DATA_PREFERENCES]
    preferences_key = f"gen_text_{task_type.value}_entity_id"

    with pytest.raises(
        ValueError,
        match="No entity_id provided and no preferred entity set for this task type",
    ):
        await async_generate_text(
            hass,
            task_name="Test Task",
            task_type=task_type,
            instructions="Test prompt",
        )

    preferences.async_set_preferences(**{preferences_key: "ai_task.unknown"})

    with pytest.raises(ValueError, match="AI Task entity ai_task.unknown not found"):
        await async_generate_text(
            hass,
            task_name="Test Task",
            task_type=task_type,
            instructions="Test prompt",
        )

    preferences.async_set_preferences(**{preferences_key: TEST_ENTITY_ID})
    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    result = await async_generate_text(
        hass,
        task_name="Test Task",
        task_type=task_type,
        instructions="Test prompt",
    )
    assert result.result == "Mock result"
    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNKNOWN


async def test_run_task_unknown_entity(
    hass: HomeAssistant,
    init_components: None,
) -> None:
    """Test running a task with an unknown entity."""

    with pytest.raises(
        ValueError, match="AI Task entity ai_task.unknown_entity not found"
    ):
        await async_generate_text(
            hass,
            task_name="Test Task",
            entity_id="ai_task.unknown_entity",
            task_type="summary",
            instructions="Test prompt",
        )


@freeze_time("2025-06-14 22:59:00")
async def test_run_task_updates_chat_log(
    hass: HomeAssistant,
    init_components: None,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that running a task updates the chat log."""
    result = await async_generate_text(
        hass,
        task_name="Test Task",
        entity_id=TEST_ENTITY_ID,
        task_type=GenTextTaskType.SUMMARY,
        instructions="Test prompt",
    )
    assert result.result == "Mock result"

    with (
        chat_session.async_get_chat_session(hass, result.conversation_id) as session,
        async_get_chat_log(hass, session) as chat_log,
    ):
        assert chat_log.content == snapshot
