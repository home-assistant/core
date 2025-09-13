"""Test initialization of the AI Task component."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

from freezegun import freeze_time
from freezegun.api import FrozenDateTimeFactory
import pytest
import voluptuous as vol

from homeassistant.components import media_source
from homeassistant.components.ai_task import AITaskPreferences
from homeassistant.components.ai_task.const import DATA_MEDIA_SOURCE, DATA_PREFERENCES
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from .conftest import TEST_ENTITY_ID, MockAITaskEntity

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
            {"gen_data_entity_id": TEST_ENTITY_ID},
            {},
        ),
        (
            {},
            {
                "entity_id": TEST_ENTITY_ID,
                "attachments": [
                    {
                        "media_content_id": "media-source://mock/blah_blah_blah.mp4",
                        "media_content_type": "video/mp4",
                    }
                ],
            },
        ),
    ],
)
async def test_generate_data_service(
    hass: HomeAssistant,
    init_components: None,
    freezer: FrozenDateTimeFactory,
    set_preferences: dict[str, str | None],
    msg_extra: dict[str, str],
    mock_ai_task_entity: MockAITaskEntity,
) -> None:
    """Test the generate data service."""
    preferences = hass.data[DATA_PREFERENCES]
    preferences.async_set_preferences(**set_preferences)

    with patch(
        "homeassistant.components.media_source.async_resolve_media",
        return_value=media_source.PlayMedia(
            url="http://example.com/media.mp4",
            mime_type="video/mp4",
            path=Path("media.mp4"),
        ),
    ):
        result = await hass.services.async_call(
            "ai_task",
            "generate_data",
            {
                "task_name": "Test Name",
                "instructions": "Test prompt",
            }
            | msg_extra,
            blocking=True,
            return_response=True,
        )

    assert result["data"] == "Mock result"

    assert len(mock_ai_task_entity.mock_generate_data_tasks) == 1
    task = mock_ai_task_entity.mock_generate_data_tasks[0]

    assert len(task.attachments or []) == len(
        msg_attachments := msg_extra.get("attachments", [])
    )

    for msg_attachment, attachment in zip(
        msg_attachments, task.attachments or [], strict=False
    ):
        assert attachment.mime_type == "video/mp4"
        assert attachment.media_content_id == msg_attachment["media_content_id"]
        assert attachment.path == Path("media.mp4")


async def test_generate_data_service_structure_fields(
    hass: HomeAssistant,
    init_components: None,
    mock_ai_task_entity: MockAITaskEntity,
) -> None:
    """Test the entity can generate structured data with a top level object schema."""
    result = await hass.services.async_call(
        "ai_task",
        "generate_data",
        {
            "task_name": "Profile Generation",
            "instructions": "Please generate a profile for a new user",
            "entity_id": TEST_ENTITY_ID,
            "structure": {
                "name": {
                    "description": "First and last name of the user such as Alice Smith",
                    "required": True,
                    "selector": {"text": {}},
                },
                "age": {
                    "description": "Age of the user",
                    "selector": {
                        "number": {
                            "min": 0,
                            "max": 120,
                        }
                    },
                },
            },
        },
        blocking=True,
        return_response=True,
    )
    # Arbitrary data returned by the mock entity (not determined by above schema in test)
    assert result["data"] == {
        "name": "Tracy Chen",
        "age": 30,
    }

    assert mock_ai_task_entity.mock_generate_data_tasks
    task = mock_ai_task_entity.mock_generate_data_tasks[0]
    assert task.instructions == "Please generate a profile for a new user"
    assert task.structure
    assert isinstance(task.structure, vol.Schema)
    schema = list(task.structure.schema.items())
    assert len(schema) == 2

    name_key, name_value = schema[0]
    assert name_key == "name"
    assert isinstance(name_key, vol.Required)
    assert name_key.description == "First and last name of the user such as Alice Smith"
    assert isinstance(name_value, selector.TextSelector)

    age_key, age_value = schema[1]
    assert age_key == "age"
    assert isinstance(age_key, vol.Optional)
    assert age_key.description == "Age of the user"
    assert isinstance(age_value, selector.NumberSelector)
    assert age_value.config["min"] == 0
    assert age_value.config["max"] == 120


@pytest.mark.parametrize(
    ("structure", "expected_exception", "expected_error"),
    [
        (
            {
                "name": {
                    "description": "First and last name of the user such as Alice Smith",
                    "selector": {"invalid-selector": {}},
                },
            },
            vol.Invalid,
            r"Unknown selector type invalid-selector.*",
        ),
        (
            {
                "name": {
                    "description": "First and last name of the user such as Alice Smith",
                    "selector": {
                        "text": {
                            "extra-config": False,
                        }
                    },
                },
            },
            vol.Invalid,
            r"extra keys not allowed.*",
        ),
        (
            {
                "name": {
                    "description": "First and last name of the user such as Alice Smith",
                },
            },
            vol.Invalid,
            r"required key not provided.*selector.*",
        ),
        (12345, vol.Invalid, r"xpected a dictionary.*"),
        ("name", vol.Invalid, r"xpected a dictionary.*"),
        (["name"], vol.Invalid, r"xpected a dictionary.*"),
        (
            {
                "name": {
                    "description": "First and last name of the user such as Alice Smith",
                    "selector": {"text": {}},
                    "extra-fields": "Some extra fields",
                },
            },
            vol.Invalid,
            r"extra keys not allowed .*",
        ),
        (
            {
                "name": {
                    "description": "First and last name of the user such as Alice Smith",
                    "selector": "invalid-schema",
                },
            },
            vol.Invalid,
            r"xpected a dictionary for dictionary.",
        ),
    ],
    ids=(
        "invalid-selector",
        "invalid-selector-config",
        "missing-selector",
        "structure-is-int-not-object",
        "structure-is-str-not-object",
        "structure-is-list-not-object",
        "extra-fields",
        "invalid-selector-schema",
    ),
)
async def test_generate_data_service_invalid_structure(
    hass: HomeAssistant,
    init_components: None,
    structure: Any,
    expected_exception: Exception,
    expected_error: str,
) -> None:
    """Test the entity can generate structured data."""
    with pytest.raises(expected_exception, match=expected_error):
        await hass.services.async_call(
            "ai_task",
            "generate_data",
            {
                "task_name": "Profile Generation",
                "instructions": "Please generate a profile for a new user",
                "entity_id": TEST_ENTITY_ID,
                "structure": structure,
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize(
    ("set_preferences", "msg_extra"),
    [
        ({}, {"entity_id": TEST_ENTITY_ID}),
        ({"gen_image_entity_id": TEST_ENTITY_ID}, {}),
        (
            {"gen_image_entity_id": "ai_task.other_entity"},
            {"entity_id": TEST_ENTITY_ID},
        ),
    ],
)
@freeze_time("2025-06-14 22:59:00")
async def test_generate_image_service(
    hass: HomeAssistant,
    init_components: None,
    set_preferences: dict[str, str | None],
    msg_extra: dict[str, str],
    mock_ai_task_entity: MockAITaskEntity,
) -> None:
    """Test the generate image service."""
    preferences = hass.data[DATA_PREFERENCES]
    preferences.async_set_preferences(**set_preferences)

    with patch.object(
        hass.data[DATA_MEDIA_SOURCE],
        "async_upload_media",
        return_value="media-source://ai_task/image/2025-06-14_225900_test_task.png",
    ) as mock_upload_media:
        result = await hass.services.async_call(
            "ai_task",
            "generate_image",
            {
                "task_name": "Test Image",
                "instructions": "Generate a test image",
            }
            | msg_extra,
            blocking=True,
            return_response=True,
        )

    mock_upload_media.assert_called_once()
    assert "image_data" not in result
    assert (
        result["media_source_id"]
        == "media-source://ai_task/image/2025-06-14_225900_test_task.png"
    )
    assert result["url"].startswith(
        "http://10.10.10.10:8123/ai_task/image/2025-06-14_225900_test_task.png?authSig="
    )
    assert result["mime_type"] == "image/png"
    assert result["model"] == "mock_model"
    assert result["revised_prompt"] == "mock_revised_prompt"

    assert len(mock_ai_task_entity.mock_generate_image_tasks) == 1
    task = mock_ai_task_entity.mock_generate_image_tasks[0]
    assert task.instructions == "Generate a test image"


async def test_generate_image_service_no_entity(
    hass: HomeAssistant,
    init_components: None,
) -> None:
    """Test the generate image service with no entity specified."""
    with pytest.raises(
        HomeAssistantError,
        match="No entity_id provided and no preferred entity set",
    ):
        await hass.services.async_call(
            "ai_task",
            "generate_image",
            {
                "task_name": "Test Image",
                "instructions": "Generate a test image",
            },
            blocking=True,
            return_response=True,
        )
