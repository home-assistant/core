"""Test initialization of the LLM Task component."""

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.llm_task import LLMTaskPreferences
from homeassistant.components.llm_task.const import DATA_PREFERENCES
from homeassistant.core import HomeAssistant

from tests.common import flush_store


async def test_preferences_storage_load(
    hass: HomeAssistant,
    init_components: None,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that LLMTaskPreferences are stored and loaded correctly."""
    preferences = hass.data[DATA_PREFERENCES]

    # Initial state should be None for entity IDs
    assert preferences.summary_entity_id is None
    assert preferences.generate_entity_id is None

    summary_id_1 = "sensor.summary_one"
    generate_id_1 = "sensor.generate_one"

    preferences.async_set_preferences(
        summary_entity_id=summary_id_1,
        generate_entity_id=generate_id_1,
    )

    # Verify that current preferences object is updated
    assert preferences.summary_entity_id == summary_id_1
    assert preferences.generate_entity_id == generate_id_1

    await flush_store(preferences._store)

    # Create a new preferences instance to test loading from store
    new_preferences_instance = LLMTaskPreferences(hass)
    await new_preferences_instance.async_load()

    assert new_preferences_instance.summary_entity_id == summary_id_1
    assert new_preferences_instance.generate_entity_id == generate_id_1

    # Test updating one preference and setting another to None
    summary_id_2 = "sensor.summary_two"
    preferences.async_set_preferences(
        summary_entity_id=summary_id_2, generate_entity_id=None
    )

    # Verify that current preferences object is updated
    assert preferences.summary_entity_id == summary_id_2
    assert preferences.generate_entity_id is None

    await flush_store(preferences._store)

    # Create another new preferences instance to confirm persistence of the update
    another_new_preferences_instance = LLMTaskPreferences(hass)
    await another_new_preferences_instance.async_load()

    assert another_new_preferences_instance.summary_entity_id == summary_id_2
    assert another_new_preferences_instance.generate_entity_id is None
