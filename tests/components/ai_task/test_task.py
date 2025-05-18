"""Test tasks for the AI Task integration."""

from freezegun import freeze_time
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ai_task import GenTextTaskType, async_generate_text
from homeassistant.components.conversation import async_get_chat_log
from homeassistant.core import HomeAssistant
from homeassistant.helpers import chat_session

from .conftest import TEST_ENTITY_ID


async def test_run_text_task_unknown_entity(
    hass: HomeAssistant,
    init_components: None,
) -> None:
    """Test running a text task with an unknown entity."""

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
async def test_run_text_task_updates_chat_log(
    hass: HomeAssistant,
    init_components: None,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that running a text task updates the chat log."""
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
