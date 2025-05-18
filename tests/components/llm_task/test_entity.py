"""Tests for the LLM Task entity model."""

from freezegun import freeze_time

from homeassistant.components.llm_task import LLMTaskType, async_run_task
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .conftest import TEST_ENTITY_ID, MockLLMTaskEntity

from tests.common import MockConfigEntry


@freeze_time("2025-06-08 16:28:13")
async def test_state(
    hass: HomeAssistant,
    init_components: None,
    mock_config_entry: MockConfigEntry,
    mock_llm_task_entity: MockLLMTaskEntity,
) -> None:
    """Test the state of the LLM Task entity."""
    entity = hass.states.get(TEST_ENTITY_ID)
    assert entity is not None
    assert entity.state == STATE_UNKNOWN

    result = await async_run_task(
        hass,
        task_name="Test task",
        entity_id=TEST_ENTITY_ID,
        task_type=LLMTaskType.SUMMARY,
        prompt="Test prompt",
    )
    assert result.result == "Mock result"

    entity = hass.states.get(TEST_ENTITY_ID)
    assert entity.state == "2025-06-08T16:28:13+00:00"

    assert mock_llm_task_entity.mock_tasks_handled
    task = mock_llm_task_entity.mock_tasks_handled[0]
    assert task.type == LLMTaskType.SUMMARY
    assert task.prompt == "Test prompt"
