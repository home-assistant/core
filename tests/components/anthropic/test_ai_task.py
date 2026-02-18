"""Tests for the Anthropic integration."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

from freezegun import freeze_time
import pytest
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol

from homeassistant.components import ai_task, media_source
from homeassistant.components.anthropic.const import CONF_CHAT_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, selector

from . import create_content_block, create_tool_use_block

from tests.common import MockConfigEntry


async def test_generate_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test AI Task data generation."""
    entity_id = "ai_task.claude_ai_task"

    # Ensure entity is linked to the subentry
    entity_entry = entity_registry.async_get(entity_id)
    ai_task_entry = next(
        iter(
            entry
            for entry in mock_config_entry.subentries.values()
            if entry.subentry_type == "ai_task_data"
        )
    )
    assert entity_entry is not None
    assert entity_entry.config_entry_id == mock_config_entry.entry_id
    assert entity_entry.config_subentry_id == ai_task_entry.subentry_id

    mock_create_stream.return_value = [create_content_block(0, ["The test data"])]

    result = await ai_task.async_generate_data(
        hass,
        task_name="Test Task",
        entity_id=entity_id,
        instructions="Generate test data",
    )

    assert result.data == "The test data"


async def test_empty_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test AI Task data generation but the data returned is empty."""
    mock_create_stream.return_value = [create_content_block(0, [""])]

    with pytest.raises(
        HomeAssistantError, match="Last content in chat log is not an AssistantContent"
    ):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id="ai_task.claude_ai_task",
            instructions="Generate test data",
        )


@freeze_time("2026-01-01 12:00:00")
async def test_generate_structured_data_legacy(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test AI Task structured data generation with legacy method."""
    for subentry in mock_config_entry.subentries.values():
        hass.config_entries.async_update_subentry(
            mock_config_entry,
            subentry,
            data={
                CONF_CHAT_MODEL: "claude-sonnet-4-0",
            },
        )

    mock_create_stream.return_value = [
        create_tool_use_block(
            1,
            "toolu_0123456789AbCdEfGhIjKlM",
            "test_task",
            ['{"charac', 'ters": ["Mario', '", "Luigi"]}'],
        ),
    ]

    result = await ai_task.async_generate_data(
        hass,
        task_name="Test Task",
        entity_id="ai_task.claude_ai_task",
        instructions="Generate test data",
        structure=vol.Schema(
            {
                vol.Required("characters"): selector.selector(
                    {
                        "text": {
                            "multiple": True,
                        }
                    }
                )
            },
        ),
    )

    assert result.data == {"characters": ["Mario", "Luigi"]}
    assert mock_create_stream.call_args.kwargs.copy() == snapshot


@freeze_time("2026-01-01 12:00:00")
async def test_generate_structured_data_legacy_tools(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test AI Task structured data generation with legacy method and tools enabled."""
    mock_create_stream.return_value = [
        create_tool_use_block(
            1,
            "toolu_0123456789AbCdEfGhIjKlM",
            "test_task",
            ['{"charac', 'ters": ["Mario', '", "Luigi"]}'],
        ),
    ]

    for subentry in mock_config_entry.subentries.values():
        hass.config_entries.async_update_subentry(
            mock_config_entry,
            subentry,
            data={"chat_model": "claude-sonnet-4-0", "web_search": True},
        )

    result = await ai_task.async_generate_data(
        hass,
        task_name="Test Task",
        entity_id="ai_task.claude_ai_task",
        instructions="Generate test data",
        structure=vol.Schema(
            {
                vol.Required("characters"): selector.selector(
                    {
                        "text": {
                            "multiple": True,
                        }
                    }
                )
            },
        ),
    )

    assert result.data == {"characters": ["Mario", "Luigi"]}
    assert mock_create_stream.call_args.kwargs.copy() == snapshot


@freeze_time("2026-01-01 12:00:00")
async def test_generate_structured_data_legacy_extended_thinking(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test AI Task structured data generation with legacy method and extended_thinking."""
    mock_create_stream.return_value = [
        create_tool_use_block(
            1,
            "toolu_0123456789AbCdEfGhIjKlM",
            "test_task",
            ['{"charac', 'ters": ["Mario', '", "Luigi"]}'],
        ),
    ]

    for subentry in mock_config_entry.subentries.values():
        hass.config_entries.async_update_subentry(
            mock_config_entry,
            subentry,
            data={
                "chat_model": "claude-sonnet-4-0",
                "thinking_budget": 1500,
            },
        )

    result = await ai_task.async_generate_data(
        hass,
        task_name="Test Task",
        entity_id="ai_task.claude_ai_task",
        instructions="Generate test data",
        structure=vol.Schema(
            {
                vol.Required("characters"): selector.selector(
                    {
                        "text": {
                            "multiple": True,
                        }
                    }
                )
            },
        ),
    )

    assert result.data == {"characters": ["Mario", "Luigi"]}
    assert mock_create_stream.call_args.kwargs.copy() == snapshot


async def test_generate_invalid_structured_data_legacy(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
) -> None:
    """Test AI Task with invalid JSON response with legacy method."""
    for subentry in mock_config_entry.subentries.values():
        hass.config_entries.async_update_subentry(
            mock_config_entry,
            subentry,
            data={
                CONF_CHAT_MODEL: "claude-sonnet-4-0",
            },
        )

    mock_create_stream.return_value = [
        create_tool_use_block(
            1,
            "toolu_0123456789AbCdEfGhIjKlM",
            "test_task",
            "INVALID JSON RESPONSE",
        )
    ]

    with pytest.raises(
        HomeAssistantError, match="Error with Claude structured response"
    ):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id="ai_task.claude_ai_task",
            instructions="Generate test data",
            structure=vol.Schema(
                {
                    vol.Required("characters"): selector.selector(
                        {
                            "text": {
                                "multiple": True,
                            }
                        }
                    )
                },
            ),
        )


@freeze_time("2026-01-01 12:00:00")
async def test_generate_structured_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test AI Task structured data generation."""
    mock_create_stream.return_value = [
        create_content_block(0, ['{"charac', 'ters": ["Mario', '", "Luigi"]}'])
    ]

    result = await ai_task.async_generate_data(
        hass,
        task_name="Test Task",
        entity_id="ai_task.claude_ai_task",
        instructions="Generate test data",
        structure=vol.Schema(
            {
                vol.Required("characters"): selector.selector(
                    {
                        "text": {
                            "multiple": True,
                        }
                    }
                )
            },
        ),
    )

    assert result.data == {"characters": ["Mario", "Luigi"]}
    assert mock_create_stream.call_args.kwargs.copy() == snapshot


async def test_generate_data_with_attachments(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test AI Task data generation with attachments."""
    entity_id = "ai_task.claude_ai_task"

    mock_create_stream.return_value = [create_content_block(0, ["Hi there!"])]

    # Test with attachments
    with (
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            side_effect=[
                media_source.PlayMedia(
                    url="http://example.com/doorbell_snapshot.jpg",
                    mime_type="image/jpg",
                    path=Path("doorbell_snapshot.jpg"),
                ),
                media_source.PlayMedia(
                    url="http://example.com/context.pdf",
                    mime_type="application/pdf",
                    path=Path("context.pdf"),
                ),
            ],
        ),
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=b"fake_image_data"),
    ):
        result = await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=entity_id,
            instructions="Test prompt",
            attachments=[
                {"media_content_id": "media-source://media/doorbell_snapshot.jpg"},
                {"media_content_id": "media-source://media/context.pdf"},
            ],
        )

    assert result.data == "Hi there!"

    # Verify that the create stream was called with the correct parameters
    # The last call should have the user message with attachments
    call_args = mock_create_stream.call_args
    assert call_args is not None

    # Check that the input includes the attachments
    input_messages = call_args[1]["messages"]
    assert len(input_messages) > 0

    # Find the user message with attachments
    user_message_with_attachments = input_messages[-2]

    assert user_message_with_attachments is not None
    assert isinstance(user_message_with_attachments["content"], list)
    assert len(user_message_with_attachments["content"]) == 3  # Text + attachments

    text_block, image_block, document_block = user_message_with_attachments["content"]

    # Text block
    assert text_block["type"] == "text"
    assert text_block["text"] == "Test prompt"

    # Image attachment
    assert image_block["type"] == "image"
    assert image_block["source"] == {
        "data": "ZmFrZV9pbWFnZV9kYXRh",
        "media_type": "image/jpeg",
        "type": "base64",
    }

    # Document attachment (ignore extra metadata like cache_control)
    assert document_block["type"] == "document"
    assert document_block["source"]["data"] == "ZmFrZV9pbWFnZV9kYXRh"
    assert document_block["source"]["media_type"] == "application/pdf"
    assert document_block["source"]["type"] == "base64"


async def test_generate_data_invalid_attachments(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test AI Task data generation with attachments of unsupported type."""
    entity_id = "ai_task.claude_ai_task"

    mock_create_stream.return_value = [create_content_block(0, ["Hi there!"])]

    # Test path that doesn't exist
    with (
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            side_effect=[
                media_source.PlayMedia(
                    url="http://example.com/doorbell_snapshot.jpg",
                    mime_type="image/jpeg",
                    path=Path("doorbell_snapshot.jpg"),
                )
            ],
        ),
        patch("pathlib.Path.exists", return_value=False),
        pytest.raises(
            HomeAssistantError, match="`doorbell_snapshot.jpg` does not exist"
        ),
    ):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=entity_id,
            instructions="Test prompt",
            attachments=[
                {"media_content_id": "media-source://media/doorbell_snapshot.jpg"},
            ],
        )

    # Test unsupported file type
    with (
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            side_effect=[
                media_source.PlayMedia(
                    url="http://example.com/doorbell_snapshot.txt",
                    mime_type=None,
                    path=Path("doorbell_snapshot.txt"),
                )
            ],
        ),
        patch("pathlib.Path.exists", return_value=True),
        patch(
            "homeassistant.components.anthropic.entity.guess_file_type",
            return_value=("text/plain", None),
        ),
        pytest.raises(
            HomeAssistantError,
            match="Only images and PDF are supported by the Anthropic API",
        ),
    ):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=entity_id,
            instructions="Test prompt",
            attachments=[
                {"media_content_id": "media-source://media/doorbell_snapshot.txt"},
            ],
        )
