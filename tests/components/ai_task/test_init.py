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
) -> None:
    """Test that AITaskPreferences are stored and loaded correctly."""
    preferences = AITaskPreferences(hass)
    await preferences.async_load()

    # Initial state should be None for entity IDs
    for key in AITaskPreferences.KEYS:
        assert getattr(preferences, key) is None, f"Initial {key} should be None"

    new_values = {key: f"ai_task.test_{key}" for key in AITaskPreferences.KEYS}

    preferences.async_set_preferences(**new_values)

    # Verify that current preferences object is updated
    for key, value in new_values.items():
        assert getattr(preferences, key) == value, (
            f"Current {key} should match set value"
        )

    await flush_store(preferences._store)

    # Create a new preferences instance to test loading from store
    new_preferences_instance = AITaskPreferences(hass)
    await new_preferences_instance.async_load()

    for key in AITaskPreferences.KEYS:
        assert getattr(preferences, key) == getattr(new_preferences_instance, key), (
            f"Loaded {key} should match saved value"
        )


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

    assert result["text"] == "Mock result"
