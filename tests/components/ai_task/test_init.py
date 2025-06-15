"""Test initialization of the AI Task component."""

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.ai_task import AITaskPreferences
from homeassistant.components.ai_task.const import DATA_PREFERENCES
from homeassistant.core import HomeAssistant

from .conftest import TEST_ENTITY_ID

from tests.common import flush_store


async def test_preferences_storage_load(
    hass: HomeAssistant,
    init_components: None,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that AITaskPreferences are stored and loaded correctly."""
    preferences = hass.data[DATA_PREFERENCES]

    # Initial state should be None for entity IDs
    assert preferences.gen_text_entity_id is None

    gen_text_id_1 = "sensor.summary_one"

    preferences.async_set_preferences(
        gen_text_entity_id=gen_text_id_1,
    )

    # Verify that current preferences object is updated
    assert preferences.gen_text_entity_id == gen_text_id_1

    await flush_store(preferences._store)

    # Create a new preferences instance to test loading from store
    new_preferences_instance = AITaskPreferences(hass)
    await new_preferences_instance.async_load()

    assert new_preferences_instance.gen_text_entity_id == gen_text_id_1

    # Test updating one preference and setting another to None
    gen_text_id_2 = "sensor.summary_two"
    preferences.async_set_preferences(gen_text_entity_id=gen_text_id_2)

    # Verify that current preferences object is updated
    assert preferences.gen_text_entity_id == gen_text_id_2

    await flush_store(preferences._store)

    # Create another new preferences instance to confirm persistence of the update
    another_new_preferences_instance = AITaskPreferences(hass)
    await another_new_preferences_instance.async_load()

    assert another_new_preferences_instance.gen_text_entity_id == gen_text_id_2


@pytest.mark.parametrize(
    ("set_preferences", "msg_extra"),
    [
        (
            {"gen_text_entity_id": TEST_ENTITY_ID},
            {},
        ),
        (
            {},
            {"entity_id": TEST_ENTITY_ID},
        ),
    ],
)
async def test_generate_text_service(
    hass: HomeAssistant,
    init_components: None,
    freezer: FrozenDateTimeFactory,
    set_preferences: dict[str, str | None],
    msg_extra: dict[str, str],
) -> None:
    """Test the generate text service."""
    preferences = hass.data[DATA_PREFERENCES]
    preferences.async_set_preferences(**set_preferences)

    result = await hass.services.async_call(
        "ai_task",
        "generate_text",
        {
            "task_name": "Test Name",
            "instructions": "Test prompt",
        }
        | msg_extra,
        blocking=True,
        return_response=True,
    )

    assert result["result"] == "Mock result"
