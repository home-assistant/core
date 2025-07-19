"""Test AI Task platform of Ollama integration."""

from pathlib import Path
from unittest.mock import patch

import ollama
import pytest
import voluptuous as vol

from homeassistant.components import ai_task, media_source
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, selector

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test AI Task data generation."""
    entity_id = "ai_task.ollama_ai_task"

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

    # Mock the Ollama chat response as an async iterator
    async def mock_chat_response():
        """Mock streaming response."""
        yield {
            "message": {"role": "assistant", "content": "Generated test data"},
            "done": True,
            "done_reason": "stop",
        }

    with patch(
        "ollama.AsyncClient.chat",
        return_value=mock_chat_response(),
    ):
        result = await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=entity_id,
            instructions="Generate test data",
        )

    assert result.data == "Generated test data"


@pytest.mark.usefixtures("mock_init_component")
async def test_run_task_with_streaming(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test AI Task data generation with streaming response."""
    entity_id = "ai_task.ollama_ai_task"

    async def mock_stream():
        """Mock streaming response."""
        yield {"message": {"role": "assistant", "content": "Stream "}}
        yield {
            "message": {"role": "assistant", "content": "response"},
            "done": True,
            "done_reason": "stop",
        }

    with patch(
        "ollama.AsyncClient.chat",
        return_value=mock_stream(),
    ):
        result = await ai_task.async_generate_data(
            hass,
            task_name="Test Streaming Task",
            entity_id=entity_id,
            instructions="Generate streaming data",
        )

    assert result.data == "Stream response"


@pytest.mark.usefixtures("mock_init_component")
async def test_run_task_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test AI Task with connection error."""
    entity_id = "ai_task.ollama_ai_task"

    with (
        patch(
            "ollama.AsyncClient.chat",
            side_effect=Exception("Connection failed"),
        ),
        pytest.raises(Exception, match="Connection failed"),
    ):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Error Task",
            entity_id=entity_id,
            instructions="Generate data that will fail",
        )


@pytest.mark.usefixtures("mock_init_component")
async def test_run_task_empty_response(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test AI Task with empty response."""
    entity_id = "ai_task.ollama_ai_task"

    # Mock response with space (minimally non-empty)
    async def mock_minimal_response():
        """Mock minimal streaming response."""
        yield {
            "message": {"role": "assistant", "content": " "},
            "done": True,
            "done_reason": "stop",
        }

    with patch(
        "ollama.AsyncClient.chat",
        return_value=mock_minimal_response(),
    ):
        result = await ai_task.async_generate_data(
            hass,
            task_name="Test Minimal Task",
            entity_id=entity_id,
            instructions="Generate minimal data",
        )

    assert result.data == " "


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_structured_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test AI Task data generation."""
    entity_id = "ai_task.ollama_ai_task"

    # Mock the Ollama chat response as an async iterator
    async def mock_chat_response():
        """Mock streaming response."""
        yield {
            "message": {
                "role": "assistant",
                "content": '{"characters": ["Mario", "Luigi"]}',
            },
            "done": True,
            "done_reason": "stop",
        }

    with patch(
        "ollama.AsyncClient.chat",
        return_value=mock_chat_response(),
    ) as mock_chat:
        result = await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=entity_id,
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

    assert mock_chat.call_count == 1
    assert mock_chat.call_args[1]["format"] == {
        "type": "object",
        "properties": {"characters": {"items": {"type": "string"}, "type": "array"}},
        "required": ["characters"],
    }


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_invalid_structured_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test AI Task data generation."""
    entity_id = "ai_task.ollama_ai_task"

    # Mock the Ollama chat response as an async iterator
    async def mock_chat_response():
        """Mock streaming response."""
        yield {
            "message": {
                "role": "assistant",
                "content": "INVALID JSON RESPONSE",
            },
            "done": True,
            "done_reason": "stop",
        }

    with (
        patch(
            "ollama.AsyncClient.chat",
            return_value=mock_chat_response(),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=entity_id,
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


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_data_with_attachment(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test AI Task data generation with image attachments."""
    entity_id = "ai_task.ollama_ai_task"

    # Mock the Ollama chat response as an async iterator
    async def mock_chat_response():
        """Mock streaming response."""
        yield {
            "message": {"role": "assistant", "content": "Generated test data"},
            "done": True,
            "done_reason": "stop",
        }

    with (
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            side_effect=[
                media_source.PlayMedia(
                    url="http://example.com/doorbell_snapshot.jpg",
                    mime_type="image/jpeg",
                    path=Path("doorbell_snapshot.jpg"),
                ),
            ],
        ),
        patch(
            "ollama.AsyncClient.chat",
            return_value=mock_chat_response(),
        ) as mock_chat,
    ):
        result = await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=entity_id,
            instructions="Generate test data",
            attachments=[
                {"media_content_id": "media-source://media/doorbell_snapshot.jpg"},
            ],
        )

    assert result.data == "Generated test data"

    assert mock_chat.call_count == 1
    messages = mock_chat.call_args[1]["messages"]
    assert len(messages) == 2
    chat_message = messages[1]
    assert chat_message.role == "user"
    assert chat_message.content == "Generate test data"
    assert chat_message.images == [
        ollama.Image(value=Path("doorbell_snapshot.jpg")),
    ]


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_data_with_unsupported_file_format(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test AI Task data generation with image attachments."""
    entity_id = "ai_task.ollama_ai_task"

    # Mock the Ollama chat response as an async iterator
    async def mock_chat_response():
        """Mock streaming response."""
        yield {
            "message": {"role": "assistant", "content": "Generated test data"},
            "done": True,
            "done_reason": "stop",
        }

    with (
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            side_effect=[
                media_source.PlayMedia(
                    url="http://example.com/doorbell_snapshot.jpg",
                    mime_type="image/jpeg",
                    path=Path("doorbell_snapshot.jpg"),
                ),
                media_source.PlayMedia(
                    url="http://example.com/context.txt",
                    mime_type="text/plain",
                    path=Path("context.txt"),
                ),
            ],
        ),
        patch(
            "ollama.AsyncClient.chat",
            return_value=mock_chat_response(),
        ),
        pytest.raises(
            HomeAssistantError,
            match="Ollama only supports image attachments in user content",
        ),
    ):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=entity_id,
            instructions="Generate test data",
            attachments=[
                {"media_content_id": "media-source://media/doorbell_snapshot.jpg"},
                {"media_content_id": "media-source://media/context.txt"},
            ],
        )
