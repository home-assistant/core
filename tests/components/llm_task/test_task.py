"""Test tasks for the LLM Task integration."""

import pytest

from homeassistant.components.conversation import async_get_chat_log
from homeassistant.components.llm_task import LLMTaskType, async_run_task
from homeassistant.core import HomeAssistant
from homeassistant.helpers import chat_session

from .conftest import TEST_ENTITY_ID


async def test_run_task_unknown_entity(
    hass: HomeAssistant,
    init_components: None,
) -> None:
    """Test running a task with an unknown entity."""

    with pytest.raises(
        ValueError, match="LLM Task entity llm_task.unknown_entity not found"
    ):
        await async_run_task(
            hass, "Test Task", "llm_task.unknown_entity", "summary", "Test prompt"
        )


async def test_run_task_updates_chat_log(
    hass: HomeAssistant,
    init_components: None,
) -> None:
    """Test that running a task updates the chat log."""
    result = await async_run_task(
        hass, "Test Task", TEST_ENTITY_ID, LLMTaskType.SUMMARY, "Test prompt"
    )
    assert result.result == "Mock result"

    with (
        chat_session.async_get_chat_session(hass, result.conversation_id) as session,
        async_get_chat_log(hass, session) as chat_log,
    ):
        assert chat_log.content[0].role == "system"
        assert chat_log.content[1].role == "user"
        assert chat_log.content[1].content == "Test prompt"
        assert chat_log.content[2].role == "assistant"
        assert chat_log.content[2].content == "Mock result"
