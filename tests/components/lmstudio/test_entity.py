"""Test LM Studio entity utility functions."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, Mock

import openai
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
import pytest
import voluptuous as vol

from homeassistant.components.conversation import (
    AssistantContent,
    SystemContent,
    ToolResultContent,
    UserContent,
)
from homeassistant.components.lmstudio.entity import (
    LMStudioBaseLLMEntity,
    _convert_message_to_openai,
    _format_tool,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.helpers.llm import ToolInput


class TestToolWithDescription(llm.Tool):
    """Test tool for testing _format_tool function with description."""

    name = "test_tool"
    description = "Test tool description"
    parameters = vol.Schema({vol.Required("param1"): str})

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> dict[str, Any]:
        """Call the tool."""
        return {"result": "test"}


class TestToolWithoutDescription(llm.Tool):
    """Test tool for testing _format_tool function without description."""

    name = "test_tool"
    description = None
    parameters = vol.Schema({vol.Required("param1"): str})

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> dict[str, Any]:
        """Call the tool."""
        return {"result": "test"}


def test_format_tool_with_description() -> None:
    """Test _format_tool with tool that has description."""
    tool = TestToolWithDescription()

    result = _format_tool(tool, None)

    expected = {
        "type": "function",
        "function": {
            "name": "test_tool",
            "description": "Test tool description",
            "parameters": {
                "type": "object",
                "properties": {"param1": {"type": "string"}},
                "required": ["param1"],
            },
        },
    }
    assert result == expected


def test_format_tool_without_description() -> None:
    """Test _format_tool with tool that has no description."""
    tool = TestToolWithoutDescription()

    result = _format_tool(tool, None)

    expected = {
        "type": "function",
        "function": {
            "name": "test_tool",
            "parameters": {
                "type": "object",
                "properties": {"param1": {"type": "string"}},
                "required": ["param1"],
            },
        },
    }
    assert result == expected


def test_convert_message_system() -> None:
    """Test _convert_message_to_openai for system message."""
    message = SystemContent(content="You are a helpful assistant")

    result = _convert_message_to_openai(message)

    expected = {"role": "system", "content": "You are a helpful assistant"}
    assert result == expected


def test_convert_message_user_string() -> None:
    """Test _convert_message_to_openai for user message with string content."""
    message = UserContent(content="Hello, how are you?")

    result = _convert_message_to_openai(message)

    expected = {"role": "user", "content": "Hello, how are you?"}
    assert result == expected


def test_convert_message_assistant() -> None:
    """Test _convert_message_to_openai for assistant message."""
    tool_call = ToolInput(
        tool_name="test_tool",
        tool_args={"param1": "value1"},
    )
    tool_call.id = "call_123"

    message = AssistantContent(
        agent_id="test_agent",
        content="I'll help you with that",
        tool_calls=[tool_call],
    )

    result = _convert_message_to_openai(message)

    expected = {
        "role": "assistant",
        "content": "I'll help you with that",
        "tool_calls": [
            {
                "id": "call_123",
                "type": "function",
                "function": {
                    "name": "test_tool",
                    "arguments": '{"param1": "value1"}',
                },
            }
        ],
    }
    assert result == expected


def test_convert_message_assistant_no_tool_calls() -> None:
    """Test _convert_message_to_openai for assistant message without tool calls."""
    message = AssistantContent(
        agent_id="test_agent",
        content="Hello there!",
    )

    result = _convert_message_to_openai(message)

    expected = {
        "role": "assistant",
        "content": "Hello there!",
    }
    assert result == expected


def test_convert_message_tool_result() -> None:
    """Test _convert_message_to_openai for tool result message."""
    message = ToolResultContent(
        agent_id="test_agent",
        tool_call_id="call_123",
        tool_name="test_tool",
        tool_result={"status": "success", "data": "test result"},
    )

    result = _convert_message_to_openai(message)

    expected = {
        "role": "tool",
        "tool_call_id": "call_123",
        "content": '{"status": "success", "data": "test result"}',
    }
    assert result == expected


def test_convert_message_unsupported_role() -> None:
    """Test _convert_message_to_openai with unsupported message role."""

    # Create a mock message with unsupported role
    class UnsupportedMessage:
        def __init__(self) -> None:
            self.role = "unknown"

    message = UnsupportedMessage()

    with pytest.raises(ValueError, match="Unsupported message role: unknown"):
        _convert_message_to_openai(message)


async def test_lmstudio_base_llm_entity_properties(
    hass: HomeAssistant, mock_config_entry, mock_openai_client
) -> None:
    """Test LMStudioBaseLLMEntity properties."""

    # Create a simple mock subentry for testing
    class MockSubentry:
        def __init__(self) -> None:
            self.subentry_id = "test_subentry"
            self.title = "Test Model"
            self.data = {"model": "test-model"}

    subentry = MockSubentry()

    mock_config_entry.runtime_data = mock_openai_client
    entity = LMStudioBaseLLMEntity(mock_config_entry, subentry)

    # Test properties
    assert entity.unique_id == f"{mock_config_entry.entry_id}-test_subentry"
    assert entity.name == "Test Model"
    assert entity.available is True

    # Test device info
    device_info = entity.device_info
    assert device_info is not None
    assert device_info["identifiers"] == {("lmstudio", mock_config_entry.entry_id)}
    assert "LM Studio" in device_info["name"]
    assert device_info["manufacturer"] == "LM Studio"
    assert device_info["model"] == "Local LLM Server"


async def test_lmstudio_base_llm_entity_unavailable(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test LMStudioBaseLLMEntity availability when runtime_data is None."""

    # Create a simple mock subentry for testing
    class MockSubentry:
        def __init__(self) -> None:
            self.subentry_id = "test_subentry"
            self.title = "Test Model"
            self.data = {"model": "test-model"}

    subentry = MockSubentry()

    # Set runtime_data to None to simulate unavailable state
    mock_config_entry.runtime_data = None
    entity = LMStudioBaseLLMEntity(mock_config_entry, subentry)

    assert entity.available is False


async def test_async_handle_chat_log_with_model(
    hass: HomeAssistant, mock_config_entry, mock_openai_client
) -> None:
    """Test _async_handle_chat_log with model specified."""

    # Create a simple mock subentry for testing
    class MockSubentry:
        def __init__(self) -> None:
            self.subentry_id = "test_subentry"
            self.title = "Test Model"
            self.data = {"model": "test-model", "max_tokens": 100, "temperature": 0.7}

    subentry = MockSubentry()

    # Mock the chat completion response
    mock_choice = Choice(
        index=0,
        message=ChatCompletionMessage(
            role="assistant",
            content="Hello! How can I help you today?",
        ),
        finish_reason="stop",
    )
    mock_response = ChatCompletion(
        id="test-completion",
        choices=[mock_choice],
        created=1234567890,
        model="test-model",
        object="chat.completion",
    )

    mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)
    mock_config_entry.runtime_data = mock_openai_client
    # Use the existing data from the mock config entry

    entity = LMStudioBaseLLMEntity(mock_config_entry, subentry)

    # Create a mock chat log
    chat_log = Mock()
    chat_log.content = [
        UserContent(content="Hello, how are you?"),
    ]
    chat_log.llm_api = None
    chat_log.async_add_assistant_content_without_tools = Mock()

    # Test the method
    await entity._async_handle_chat_log(chat_log)

    # Verify the OpenAI client was called correctly
    mock_openai_client.chat.completions.create.assert_called_once()
    call_args = mock_openai_client.chat.completions.create.call_args[1]
    assert call_args["model"] == "test-model"
    assert call_args["max_tokens"] == 100
    assert call_args["temperature"] == 0.7
    assert len(call_args["messages"]) == 1
    assert call_args["messages"][0]["role"] == "user"
    assert call_args["messages"][0]["content"] == "Hello, how are you?"

    # Verify response was added to chat log
    chat_log.async_add_assistant_content_without_tools.assert_called_once()


async def test_async_handle_chat_log_no_model_auto_fetch(
    hass: HomeAssistant, mock_config_entry, mock_openai_client
) -> None:
    """Test _async_handle_chat_log auto-fetching model when none specified."""

    # Create a simple mock subentry without model
    class MockSubentry:
        def __init__(self) -> None:
            self.subentry_id = "test_subentry"
            self.title = "Test Model"
            self.data = {}  # No model specified

    subentry = MockSubentry()

    # Mock the models list response
    mock_models = Mock()
    mock_models.data = [Mock(id="auto-model-1"), Mock(id="auto-model-2")]
    mock_openai_client.with_options.return_value.models.list = AsyncMock(
        return_value=mock_models
    )

    # Mock the chat completion response
    mock_choice = Choice(
        index=0,
        message=ChatCompletionMessage(
            role="assistant",
            content="Auto-fetched model response",
        ),
        finish_reason="stop",
    )
    mock_response = ChatCompletion(
        id="test-completion",
        choices=[mock_choice],
        created=1234567890,
        model="auto-model-1",
        object="chat.completion",
    )

    mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)
    mock_config_entry.runtime_data = mock_openai_client
    # Use the existing data from the mock config entry

    entity = LMStudioBaseLLMEntity(mock_config_entry, subentry)

    # Create a mock chat log
    chat_log = Mock()
    chat_log.content = [UserContent(content="Test message")]
    chat_log.llm_api = None
    chat_log.async_add_assistant_content_without_tools = Mock()

    # Test the method
    await entity._async_handle_chat_log(chat_log)

    # Verify models list was called to auto-fetch
    mock_openai_client.with_options.assert_called_once_with(timeout=10.0)
    mock_openai_client.with_options.return_value.models.list.assert_called_once()

    # Verify the chat completion used the auto-fetched model
    call_args = mock_openai_client.chat.completions.create.call_args[1]
    assert call_args["model"] == "auto-model-1"


async def test_async_handle_chat_log_openai_error(
    hass: HomeAssistant, mock_config_entry, mock_openai_client
) -> None:
    """Test _async_handle_chat_log with OpenAI error."""

    # Create a simple mock subentry
    class MockSubentry:
        def __init__(self) -> None:
            self.subentry_id = "test_subentry"
            self.title = "Test Model"
            self.data = {"model": "test-model"}

    subentry = MockSubentry()

    # Mock OpenAI error
    mock_openai_client.chat.completions.create = AsyncMock(
        side_effect=openai.OpenAIError("API Error")
    )
    mock_config_entry.runtime_data = mock_openai_client
    # Use the existing data from the mock config entry

    entity = LMStudioBaseLLMEntity(mock_config_entry, subentry)

    # Create a mock chat log
    chat_log = Mock()
    chat_log.content = [UserContent(content="Test message")]
    chat_log.llm_api = None

    # Test the method should raise HomeAssistantError
    with pytest.raises(HomeAssistantError, match="LM Studio API error"):
        await entity._async_handle_chat_log(chat_log)


async def test_async_handle_chat_log_no_models_available(
    hass: HomeAssistant, mock_config_entry, mock_openai_client
) -> None:
    """Test _async_handle_chat_log when no models are available."""

    # Create a simple mock subentry without model
    class MockSubentry:
        def __init__(self) -> None:
            self.subentry_id = "test_subentry"
            self.title = "Test Model"
            self.data = {}  # No model specified

    subentry = MockSubentry()

    # Mock empty models list response
    mock_models = Mock()
    mock_models.data = []  # No models available
    mock_openai_client.with_options.return_value.models.list = AsyncMock(
        return_value=mock_models
    )

    mock_config_entry.runtime_data = mock_openai_client

    entity = LMStudioBaseLLMEntity(mock_config_entry, subentry)

    # Create a mock chat log
    chat_log = Mock()
    chat_log.content = [UserContent(content="Test message")]
    chat_log.llm_api = None

    # Test the method should raise HomeAssistantError
    with pytest.raises(
        HomeAssistantError, match="No models available on LM Studio server"
    ):
        await entity._async_handle_chat_log(chat_log)


async def test_async_handle_chat_log_models_fetch_error(
    hass: HomeAssistant, mock_config_entry, mock_openai_client
) -> None:
    """Test _async_handle_chat_log when model fetching fails."""

    # Create a simple mock subentry without model
    class MockSubentry:
        def __init__(self) -> None:
            self.subentry_id = "test_subentry"
            self.title = "Test Model"
            self.data = {}  # No model specified

    subentry = MockSubentry()

    # Mock models list error
    mock_openai_client.with_options.return_value.models.list = AsyncMock(
        side_effect=openai.OpenAIError("Failed to fetch models")
    )

    mock_config_entry.runtime_data = mock_openai_client

    entity = LMStudioBaseLLMEntity(mock_config_entry, subentry)

    # Create a mock chat log
    chat_log = Mock()
    chat_log.content = [UserContent(content="Test message")]
    chat_log.llm_api = None

    # Test the method should raise HomeAssistantError
    with pytest.raises(HomeAssistantError, match="Failed to get models"):
        await entity._async_handle_chat_log(chat_log)


async def test_async_handle_chat_log_general_exception(
    hass: HomeAssistant, mock_config_entry, mock_openai_client
) -> None:
    """Test _async_handle_chat_log with general exception."""

    # Create a simple mock subentry
    class MockSubentry:
        def __init__(self) -> None:
            self.subentry_id = "test_subentry"
            self.title = "Test Model"
            self.data = {"model": "test-model"}

    subentry = MockSubentry()

    # Mock general exception
    mock_openai_client.chat.completions.create = AsyncMock(
        side_effect=Exception("Unexpected error")
    )
    mock_config_entry.runtime_data = mock_openai_client

    entity = LMStudioBaseLLMEntity(mock_config_entry, subentry)

    # Create a mock chat log
    chat_log = Mock()
    chat_log.content = [UserContent(content="Test message")]
    chat_log.llm_api = None

    # Test the method should raise HomeAssistantError
    with pytest.raises(HomeAssistantError, match="Unexpected error"):
        await entity._async_handle_chat_log(chat_log)
