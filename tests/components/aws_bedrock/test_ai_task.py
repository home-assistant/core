"""Tests for the AWS Bedrock AI Task entity."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components import ai_task, conversation
from homeassistant.components.aws_bedrock.ai_task import (
    AWSBedrockTaskEntity,
    async_setup_entry,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry

DOMAIN = "aws_bedrock"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry with AI task subentry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "access_key_id": "test_key",
            "secret_access_key": "test_secret",
            "region": "us-east-1",
        },
        subentries_data=[
            ConfigSubentryData(
                data={
                    "chat_model": "anthropic.claude-3-sonnet-20240229-v1:0",
                    "max_tokens": 4096,
                    "temperature": 0.7,
                },
                subentry_type="ai_task_data",
                title="Test AI Task",
                unique_id=None,
            ),
        ],
    )


@pytest.fixture
def mock_bedrock_client():
    """Return a mock Bedrock client."""
    client = AsyncMock()
    client.converse = AsyncMock()
    return client


async def test_async_setup_entry_creates_ai_task_entities(
    hass: HomeAssistant,
) -> None:
    """Test that async_setup_entry creates AI task entities."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "access_key_id": "test_key",
            "secret_access_key": "test_secret",
            "region": "us-east-1",
        },
        subentries_data=[
            ConfigSubentryData(
                data={
                    "chat_model": "anthropic.claude-3-sonnet-20240229-v1:0",
                    "max_tokens": 4096,
                    "temperature": 0.7,
                },
                subentry_type="ai_task_data",
                title="Test AI Task",
                unique_id=None,
            ),
        ],
    )
    config_entry.add_to_hass(hass)

    # Mock the entity platform
    entities_added = []

    def mock_add_entities(
        new_entities, update_before_add=False, *, config_subentry_id=None
    ):
        entities_added.extend(new_entities)

    with (
        patch.object(config_entry, "runtime_data", create=True) as mock_runtime_data,
        patch(
            "homeassistant.components.aws_bedrock.ai_task.AWSBedrockTaskEntity.__init__",
            return_value=None,
        ),
    ):
        mock_runtime_data.client = AsyncMock()

        await async_setup_entry(hass, config_entry, mock_add_entities)

    assert len(entities_added) == 1
    assert isinstance(entities_added[0], AWSBedrockTaskEntity)


async def test_async_setup_entry_skips_non_ai_task_subentries(
    hass: HomeAssistant,
) -> None:
    """Test that async_setup_entry skips non-ai_task subentries."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "access_key_id": "test_key",
            "secret_access_key": "test_secret",
            "region": "us-east-1",
        },
        subentries_data=[
            ConfigSubentryData(
                data={},
                subentry_type="conversation",
                title="Test Conversation",
                unique_id=None,
            ),
        ],
    )
    config_entry.add_to_hass(hass)

    entities_added = []

    def mock_add_entities(
        new_entities, update_before_add=False, *, config_subentry_id=None
    ):
        entities_added.extend(new_entities)

    with patch.object(config_entry, "runtime_data", create=True):
        await async_setup_entry(hass, config_entry, mock_add_entities)

    assert len(entities_added) == 0


async def test_async_setup_entry_creates_multiple_ai_task_entities(
    hass: HomeAssistant,
) -> None:
    """Test that async_setup_entry creates multiple AI task entities."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "access_key_id": "test_key",
            "secret_access_key": "test_secret",
            "region": "us-east-1",
        },
        subentries_data=[
            ConfigSubentryData(
                data={
                    "chat_model": "anthropic.claude-3-sonnet-20240229-v1:0",
                    "max_tokens": 4096,
                    "temperature": 0.7,
                },
                subentry_type="ai_task_data",
                title="Test AI Task 1",
                unique_id=None,
            ),
            ConfigSubentryData(
                data={
                    "chat_model": "meta.llama3-2-90b-instruct-v1:0",
                    "max_tokens": 2048,
                    "temperature": 0.5,
                },
                subentry_type="ai_task_data",
                title="Test AI Task 2",
                unique_id=None,
            ),
        ],
    )
    config_entry.add_to_hass(hass)

    # Mock the entity platform
    entities_added = []

    def mock_add_entities(
        new_entities, update_before_add=False, *, config_subentry_id=None
    ):
        entities_added.extend(new_entities)

    with (
        patch.object(config_entry, "runtime_data", create=True) as mock_runtime_data,
        patch(
            "homeassistant.components.aws_bedrock.ai_task.AWSBedrockTaskEntity.__init__",
            return_value=None,
        ),
    ):
        mock_runtime_data.client = AsyncMock()

        await async_setup_entry(hass, config_entry, mock_add_entities)

    assert len(entities_added) == 2


def test_entity_supported_features(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entity has correct supported features."""
    mock_config_entry.add_to_hass(hass)
    subentry = next(iter(mock_config_entry.subentries.values()))

    with patch.object(
        mock_config_entry, "runtime_data", create=True
    ) as mock_runtime_data:
        mock_runtime_data.client = AsyncMock()
        entity = AWSBedrockTaskEntity(mock_config_entry, subentry)

    assert entity._attr_supported_features == ai_task.AITaskEntityFeature.GENERATE_DATA


async def test_generate_data_with_unstructured_response(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bedrock_client: AsyncMock,
) -> None:
    """Test generate data task with unstructured response."""
    mock_config_entry.add_to_hass(hass)
    subentry = next(iter(mock_config_entry.subentries.values()))

    with patch.object(
        mock_config_entry, "runtime_data", create=True
    ) as mock_runtime_data:
        mock_runtime_data.client = mock_bedrock_client
        entity = AWSBedrockTaskEntity(mock_config_entry, subentry)

        # Create a mock task without structure
        task = ai_task.GenDataTask(
            name="Test Task",
            instructions="Generate a simple response",
            structure=None,
        )

        # Create a mock chat log with assistant response
        chat_log = conversation.ChatLog(hass, conversation_id="test-conv-123")
        chat_log.content.append(
            conversation.AssistantContent(
                agent_id="test",
                content="This is a simple text response.",
                tool_calls=None,
            )
        )

        # Mock _async_handle_chat_log to do nothing
        with patch.object(entity, "_async_handle_chat_log", return_value=None):
            result = await entity._async_generate_data(task, chat_log)

        assert result.conversation_id == "test-conv-123"
        assert result.data == "This is a simple text response."


async def test_generate_data_with_structured_response(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bedrock_client: AsyncMock,
) -> None:
    """Test generate data task with structured JSON response."""
    mock_config_entry.add_to_hass(hass)
    subentry = next(iter(mock_config_entry.subentries.values()))

    with patch.object(
        mock_config_entry, "runtime_data", create=True
    ) as mock_runtime_data:
        mock_runtime_data.client = mock_bedrock_client
        entity = AWSBedrockTaskEntity(mock_config_entry, subentry)

        # Create a mock task with structure
        task = ai_task.GenDataTask(
            name="Test Task",
            instructions="Generate structured data",
            structure={  # type: ignore[arg-type]
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "number"},
                },
            },
        )

        # Create a mock chat log with JSON response
        chat_log = conversation.ChatLog(hass, conversation_id="test-conv-456")
        chat_log.content.append(
            conversation.AssistantContent(
                agent_id="test",
                content='{"name": "John Doe", "age": 30}',
                tool_calls=None,
            )
        )

        # Mock _async_handle_chat_log to do nothing
        with patch.object(entity, "_async_handle_chat_log", return_value=None):
            result = await entity._async_generate_data(task, chat_log)

        assert result.conversation_id == "test-conv-456"
        assert result.data == {"name": "John Doe", "age": 30}


async def test_generate_data_with_invalid_json_raises_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bedrock_client: AsyncMock,
) -> None:
    """Test generate data task with invalid JSON raises error."""
    mock_config_entry.add_to_hass(hass)
    subentry = next(iter(mock_config_entry.subentries.values()))

    with patch.object(
        mock_config_entry, "runtime_data", create=True
    ) as mock_runtime_data:
        mock_runtime_data.client = mock_bedrock_client
        entity = AWSBedrockTaskEntity(mock_config_entry, subentry)

        # Create a mock task with structure
        task = ai_task.GenDataTask(
            name="Test Task",
            instructions="Generate structured data",
            structure={"type": "object"},  # type: ignore[arg-type]
        )

        # Create a mock chat log with invalid JSON response
        chat_log = conversation.ChatLog(hass, conversation_id="test-conv-789")
        chat_log.content.append(
            conversation.AssistantContent(
                agent_id="test",
                content="{invalid json syntax}",
                tool_calls=None,
            )
        )

        # Mock _async_handle_chat_log to do nothing
        with (
            patch.object(entity, "_async_handle_chat_log", return_value=None),
            pytest.raises(
                HomeAssistantError,
                match="Error with AWS Bedrock structured response",
            ),
        ):
            await entity._async_generate_data(task, chat_log)


async def test_generate_data_with_non_assistant_content_raises_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bedrock_client: AsyncMock,
) -> None:
    """Test generate data task with non-AssistantContent raises error."""
    mock_config_entry.add_to_hass(hass)
    subentry = next(iter(mock_config_entry.subentries.values()))

    with patch.object(
        mock_config_entry, "runtime_data", create=True
    ) as mock_runtime_data:
        mock_runtime_data.client = mock_bedrock_client
        entity = AWSBedrockTaskEntity(mock_config_entry, subentry)

        # Create a mock task
        task = ai_task.GenDataTask(
            name="Test Task",
            instructions="Generate response",
            structure=None,
        )

        # Create a mock chat log with non-AssistantContent as last item
        chat_log = conversation.ChatLog(hass, conversation_id="test-conv-error")
        chat_log.content.append(
            conversation.UserContent(content="This is user content")
        )

        # Mock _async_handle_chat_log to do nothing
        with (
            patch.object(entity, "_async_handle_chat_log", return_value=None),
            pytest.raises(
                HomeAssistantError,
                match="Last content in chat log is not an AssistantContent",
            ),
        ):
            await entity._async_generate_data(task, chat_log)


async def test_generate_data_with_empty_assistant_content(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bedrock_client: AsyncMock,
) -> None:
    """Test generate data task with empty assistant content."""
    mock_config_entry.add_to_hass(hass)
    subentry = next(iter(mock_config_entry.subentries.values()))

    with patch.object(
        mock_config_entry, "runtime_data", create=True
    ) as mock_runtime_data:
        mock_runtime_data.client = mock_bedrock_client
        entity = AWSBedrockTaskEntity(mock_config_entry, subentry)

        # Create a mock task without structure
        task = ai_task.GenDataTask(
            name="Test Task",
            instructions="Generate response",
            structure=None,
        )

        # Create a mock chat log with empty assistant content
        chat_log = conversation.ChatLog(hass, conversation_id="test-conv-empty")
        chat_log.content.append(
            conversation.AssistantContent(
                agent_id="test",
                content=None,  # Empty content
                tool_calls=None,
            )
        )

        # Mock _async_handle_chat_log to do nothing
        with patch.object(entity, "_async_handle_chat_log", return_value=None):
            result = await entity._async_generate_data(task, chat_log)

        assert result.conversation_id == "test-conv-empty"
        assert result.data == ""


async def test_generate_data_with_dict_structure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bedrock_client: AsyncMock,
) -> None:
    """Test generate data task with dict structure passed to handler."""
    mock_config_entry.add_to_hass(hass)
    subentry = next(iter(mock_config_entry.subentries.values()))

    with patch.object(
        mock_config_entry, "runtime_data", create=True
    ) as mock_runtime_data:
        mock_runtime_data.client = mock_bedrock_client
        entity = AWSBedrockTaskEntity(mock_config_entry, subentry)

        # Create a mock task with dict structure
        structure = {
            "type": "object",
            "properties": {"status": {"type": "string"}},
        }
        task = ai_task.GenDataTask(
            name="Test Task",
            instructions="Generate status",
            structure=structure,  # type: ignore[arg-type]
        )

        # Create a mock chat log with JSON response
        chat_log = conversation.ChatLog(hass, conversation_id="test-conv-dict")
        chat_log.content.append(
            conversation.AssistantContent(
                agent_id="test",
                content='{"status": "complete"}',
                tool_calls=None,
            )
        )

        # Mock _async_handle_chat_log and verify it's called with structure
        with patch.object(
            entity, "_async_handle_chat_log", return_value=None
        ) as mock_handler:
            result = await entity._async_generate_data(task, chat_log)

            # Verify handler was called with correct parameters
            mock_handler.assert_called_once_with(chat_log, "Test Task", structure)

        assert result.conversation_id == "test-conv-dict"
        assert result.data == {"status": "complete"}


async def test_generate_data_with_non_dict_structure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bedrock_client: AsyncMock,
) -> None:
    """Test generate data task with non-dict structure passed as None to handler."""
    mock_config_entry.add_to_hass(hass)
    subentry = next(iter(mock_config_entry.subentries.values()))

    with patch.object(
        mock_config_entry, "runtime_data", create=True
    ) as mock_runtime_data:
        mock_runtime_data.client = mock_bedrock_client
        entity = AWSBedrockTaskEntity(mock_config_entry, subentry)

        # Create a mock task with non-dict structure (e.g., string)
        # When structure is not a dict but not None/False, it still attempts JSON parsing
        task = ai_task.GenDataTask(
            name="Test Task",
            instructions="Generate data",
            structure="string",  # type: ignore[arg-type]  # Non-dict structure for testing
        )

        # Create a mock chat log with valid JSON response for string structure
        chat_log = conversation.ChatLog(hass, conversation_id="test-conv-string")
        chat_log.content.append(
            conversation.AssistantContent(
                agent_id="test",
                content='"Simple text"',  # Valid JSON string
                tool_calls=None,
            )
        )

        # Mock _async_handle_chat_log and verify it's called with None structure
        with patch.object(
            entity, "_async_handle_chat_log", return_value=None
        ) as mock_handler:
            result = await entity._async_generate_data(task, chat_log)

            # Verify handler was called with None instead of the string structure
            mock_handler.assert_called_once_with(chat_log, "Test Task", None)

        assert result.conversation_id == "test-conv-string"
        assert result.data == "Simple text"
