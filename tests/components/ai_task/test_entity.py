"""Tests for the AI Task entity model."""

from freezegun import freeze_time

from homeassistant.components.ai_task import async_generate_data
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .conftest import TEST_ENTITY_ID, MockAITaskEntity

from tests.common import MockConfigEntry


@freeze_time("2025-06-08 16:28:13")
async def test_state_generate_data(
    hass: HomeAssistant,
    init_components: None,
    mock_config_entry: MockConfigEntry,
    mock_ai_task_entity: MockAITaskEntity,
) -> None:
    """Test the state of the AI Task entity is updated when generating data."""
    entity = hass.states.get(TEST_ENTITY_ID)
    assert entity is not None
    assert entity.state == STATE_UNKNOWN

    result = await async_generate_data(
        hass,
        task_name="Test task",
        entity_id=TEST_ENTITY_ID,
        instructions="Test prompt",
    )
    assert result.data == "Mock result"

    entity = hass.states.get(TEST_ENTITY_ID)
    assert entity.state == "2025-06-08T16:28:13+00:00"

    assert mock_ai_task_entity.mock_generate_data_tasks
    task = mock_ai_task_entity.mock_generate_data_tasks[0]
    assert task.instructions == "Test prompt"
