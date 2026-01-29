"""Tests for AWS Bedrock entity helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock, patch

from botocore.exceptions import ClientError
import pytest
import voluptuous as vol

from homeassistant.components import conversation
from homeassistant.components.aws_bedrock.const import DOMAIN
from homeassistant.components.aws_bedrock.entity import (
    AWSBedrockBaseLLMEntity,
    _build_tool_name_maps,
    _clean_schema,
    _convert_messages,
    _sanitize_bedrock_tool_name,
)
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.util.json import JsonObjectType

from .bedrock_response_fixtures import (
    create_final_response_after_tool_results,
    create_nova_model_response,
    create_response_with_malformed_tool_use,
    create_response_with_only_thinking,
    create_response_with_structured_output,
    create_response_with_thinking,
    create_response_with_tool_use,
    create_simple_text_response,
)
from .chat_log_fixtures import (
    create_conversation_history,
    create_message_with_attachments,
    create_message_with_system_prompt,
    create_simple_user_message,
)

from tests.common import MockConfigEntry


def test_convert_messages_skips_ui_only_assistant_between_tool_use_and_result() -> None:
    """Test that UI-only assistant messages are not sent to Bedrock."""
    chat_content: list[conversation.Content] = [
        conversation.UserContent("Turn on the living room lights"),
        conversation.AssistantContent(
            agent_id="test",
            content="I'll help you turn on the lights in the living room.",
            tool_calls=[
                llm.ToolInput(
                    id="tool_1",
                    tool_name="HassTurnOn",
                    tool_args={"area": "living room", "domain": ["light"]},
                )
            ],
        ),
        # This can be injected by HA while the tool runs; it must be skipped.
        conversation.AssistantContent(
            agent_id="test",
            content="Calling HassTurnOn…",
            tool_calls=None,
        ),
        conversation.ToolResultContent(
            agent_id="test",
            tool_call_id="tool_1",
            tool_name="HassTurnOn",
            tool_result={"success": True},
        ),
        conversation.AssistantContent(agent_id="test", content="Done", tool_calls=None),
    ]

    messages = _convert_messages(chat_content)

    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]

    assistant_with_tool = messages[1]
    assert any("toolUse" in part for part in assistant_with_tool["content"])

    # Ensure the UI-only assistant message did not get included.
    assert all(
        part.get("text") != "Calling HassTurnOn…"
        for msg in messages
        for part in msg.get("content", [])
        if isinstance(part, dict)
    )

    # Ensure toolResult follows immediately after toolUse
    tool_result_msg = messages[2]
    assert tool_result_msg["role"] == "user"
    assert any("toolResult" in part for part in tool_result_msg["content"])


def test_clean_schema_keeps_only_supported_fields() -> None:
    """Test schema cleaning for Nova tool requirements."""
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "My Schema",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "area": {
                "type": "string",
                "description": "Area name",
                "title": "Area",
            },
            "device": {
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Name"}},
                "required": ["name"],
                "additionalProperties": False,
            },
        },
        "required": ["area"],
    }

    cleaned = _clean_schema(schema)

    assert set(cleaned) <= {"type", "properties", "required"}
    assert cleaned["type"] == "object"
    assert "properties" in cleaned
    assert "required" in cleaned
    assert isinstance(cleaned["required"], list)

    area = cleaned["properties"]["area"]
    assert set(area) <= {
        "type",
        "enum",
        "description",
        "properties",
        "required",
        "items",
    }
    assert area["type"] == "string"


def test_clean_schema_adds_required_when_missing() -> None:
    """Test required is added for object schemas when missing."""
    cleaned = _clean_schema({"type": "object", "properties": {"x": {"type": "string"}}})

    assert cleaned["type"] == "object"
    assert "required" in cleaned
    assert cleaned["required"] == []


def test_sanitize_bedrock_tool_name() -> None:
    """Test Nova-safe tool name sanitization."""
    assert _sanitize_bedrock_tool_name("aws-bedrock-web-search__web_search") == (
        "aws_bedrock_web_search__web_search"
    )
    assert _sanitize_bedrock_tool_name("123bad") == "t_123bad"


def test_convert_messages_maps_tool_names() -> None:
    """Test that toolUse names are mapped to Bedrock-safe names."""

    class _TestTool(llm.Tool):
        name = "aws-bedrock-web-search__web_search"
        description = "Web search"
        parameters = vol.Schema({"q": str})

        async def async_call(
            self,
            hass: HomeAssistant,
            tool_input: llm.ToolInput,
            llm_context: llm.LLMContext,
        ) -> JsonObjectType:
            raise NotImplementedError

    tool = _TestTool()
    ha_to_bedrock, _ = _build_tool_name_maps([tool])

    chat_content: list[conversation.Content] = [
        conversation.AssistantContent(
            agent_id="test",
            content=None,
            tool_calls=[
                llm.ToolInput(
                    id="tool_1",
                    tool_name=tool.name,
                    tool_args={"q": "hi"},
                )
            ],
        )
    ]

    messages = _convert_messages(chat_content, ha_to_bedrock_tool_name=ha_to_bedrock)
    tool_use = next(
        part["toolUse"] for part in messages[0]["content"] if "toolUse" in part
    )
    assert tool_use["name"] == "aws_bedrock_web_search__web_search"


def create_mock_subentry(
    model="anthropic.claude-3-5-sonnet-20240620-v1:0", temperature=1.0, max_tokens=4096
):
    """Create a mock ConfigSubEntry for testing."""
    subentry = Mock(spec=ConfigSubentry)
    subentry.subentry_id = "test_subentry_id"
    subentry.data = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    subentry.title = "Test Subentry"
    return subentry


def create_mock_chat_log(content, llm_api=None):
    """Create a mock ChatLog for testing."""
    chat_log = Mock()
    chat_log.content = content
    chat_log.llm_api = llm_api
    chat_log._added_content = []
    chat_log._tool_results = []
    # Track how many tool call iterations - used to know when to stop
    chat_log._tool_iteration = 0

    # Make unresponded_tool_results a property
    type(chat_log).unresponded_tool_results = property(
        lambda self: self._tool_results if self._tool_results else None
    )

    async def async_add_assistant_content(new_content):
        """Mock async generator for adding assistant content."""
        chat_log._added_content.append(new_content)

        # If there are tool calls, simulate executing them
        if new_content.tool_calls and llm_api:
            chat_log._tool_iteration += 1
            chat_log._tool_results = []
            for tool_call in new_content.tool_calls:
                # Call the tool
                result = await llm_api.async_call_tool(tool_call)
                chat_log._tool_results.append(
                    {
                        "toolUseId": tool_call.id,
                        "content": [{"json": result}],
                    }
                )
                # Yield the tool result
                yield result
            # After first tool iteration, clear results to stop loop on next check
            # This simulates the real behavior where tool results are consumed
        else:
            # Clear tool results since we're done
            chat_log._tool_results = []
            return
            yield  # Makes this an async generator

    chat_log.async_add_assistant_content = async_add_assistant_content
    return chat_log


def create_mock_llm_api(tools=None, custom_serializer=None):
    """Create a mock LLM API for testing."""
    mock_llm_api = Mock()
    mock_llm_api.tools = tools or []
    mock_llm_api.custom_serializer = (
        custom_serializer  # Must be None for proper schema conversion
    )
    return mock_llm_api


def create_mock_tool(name, description="Test tool", parameters=None):
    """Create a mock LLM tool for testing."""
    mock_tool = Mock(spec=["name", "description", "parameters"])
    mock_tool.name = name
    mock_tool.description = description
    mock_tool.parameters = parameters if parameters is not None else vol.Schema({})
    return mock_tool


def setup_entity_with_hass(
    hass: HomeAssistant, entry: ConfigEntry, subentry: ConfigSubentry
) -> AWSBedrockBaseLLMEntity:
    """Set up entity with hass attribute for testing."""
    entity = AWSBedrockBaseLLMEntity(entry, subentry)
    entity.hass = hass
    entity.entity_id = "conversation.test"
    return entity


@pytest.mark.asyncio
async def test_handle_chat_log_simple_message(hass: HomeAssistant) -> None:
    """Test handling simple text message."""
    # Setup
    mock_entry = MockConfigEntry(domain=DOMAIN, data={})
    mock_entry.add_to_hass(hass)

    # Mock Bedrock client
    mock_client = MagicMock()
    mock_entry.runtime_data = mock_client

    # Configure response
    mock_client.converse.return_value = create_simple_text_response(
        "The weather today is sunny with a high of 75°F."
    )

    subentry = create_mock_subentry()
    entity = setup_entity_with_hass(hass, mock_entry, subentry)

    # Create chat log
    content = create_simple_user_message("What's the weather like today?")
    chat_log = create_mock_chat_log(content)

    # Mock async_add_executor_job to execute synchronously
    async def mock_executor_job(func):
        return func()

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor_job):
        # Execute
        await entity._async_handle_chat_log(
            chat_log, structure=None, structure_name=None
        )

    # Verify
    assert len(chat_log._added_content) == 1
    assert (
        chat_log._added_content[0].content
        == "The weather today is sunny with a high of 75°F."
    )
    mock_client.converse.assert_called_once()


@pytest.mark.asyncio
async def test_handle_chat_log_with_system_prompt(hass: HomeAssistant) -> None:
    """Test message with system prompt."""
    mock_entry = MockConfigEntry(domain=DOMAIN, data={})
    mock_entry.add_to_hass(hass)

    mock_client = MagicMock()
    mock_entry.runtime_data = mock_client
    mock_client.converse.return_value = create_simple_text_response(
        "I'm a helpful assistant."
    )

    subentry = create_mock_subentry()
    entity = setup_entity_with_hass(hass, mock_entry, subentry)

    content = create_message_with_system_prompt(
        "You are a helpful assistant", "Hello, who are you?"
    )
    chat_log = create_mock_chat_log(content)

    async def mock_executor_job(func):
        return func()

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor_job):
        await entity._async_handle_chat_log(
            chat_log, structure=None, structure_name=None
        )

    # Verify system prompt was included in API call
    call_kwargs = mock_client.converse.call_args[1]
    assert "system" in call_kwargs
    assert len(call_kwargs["system"]) == 1
    assert call_kwargs["system"][0]["text"] == "You are a helpful assistant"


@pytest.mark.asyncio
async def test_handle_chat_log_with_tool_use(hass: HomeAssistant) -> None:
    """Test tool use with multiple iterations."""
    mock_entry = MockConfigEntry(domain=DOMAIN, data={})
    mock_entry.add_to_hass(hass)

    mock_client = MagicMock()
    mock_entry.runtime_data = mock_client

    # First call returns tool use
    # Second call returns final answer
    mock_client.converse.side_effect = [
        create_response_with_tool_use("weather_get", {"location": "San Francisco"}),
        create_final_response_after_tool_results("The temperature is 72°F."),
    ]

    # Mock LLM API with tool
    mock_tool = create_mock_tool("weather_get", "Get weather")
    mock_llm_api = create_mock_llm_api(tools=[mock_tool])

    # Mock tool execution
    async def mock_call_tool(tool_input):
        return {"temperature": "72°F"}

    mock_llm_api.async_call_tool = AsyncMock(side_effect=mock_call_tool)

    subentry = create_mock_subentry()
    entity = setup_entity_with_hass(hass, mock_entry, subentry)

    content = create_simple_user_message("What's the weather in San Francisco?")
    chat_log = create_mock_chat_log(content, llm_api=mock_llm_api)

    async def mock_executor_job(func):
        return func()

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor_job):
        await entity._async_handle_chat_log(
            chat_log, structure=None, structure_name=None
        )

    # Verify two iterations occurred (first with tool call, second with final response)
    assert mock_client.converse.call_count == 2
    assert len(chat_log._added_content) == 2
    # First content has tool calls
    assert chat_log._added_content[0].tool_calls is not None
    # Second content has final text response
    assert chat_log._added_content[1].content == "The temperature is 72°F."


@pytest.mark.asyncio
async def test_handle_chat_log_thinking_content_removal(hass: HomeAssistant) -> None:
    """Test that thinking content is removed from response."""
    mock_entry = MockConfigEntry(domain=DOMAIN, data={})
    mock_entry.add_to_hass(hass)

    mock_client = MagicMock()
    mock_entry.runtime_data = mock_client
    mock_client.converse.return_value = create_response_with_thinking(
        "This is my thinking process", "This is the actual answer"
    )

    subentry = create_mock_subentry()
    entity = setup_entity_with_hass(hass, mock_entry, subentry)

    content = create_simple_user_message("Solve this problem")
    chat_log = create_mock_chat_log(content)

    async def mock_executor_job(func):
        return func()

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor_job):
        await entity._async_handle_chat_log(
            chat_log, structure=None, structure_name=None
        )

    # Verify thinking content was removed
    assert len(chat_log._added_content) == 1
    assert "thinking" not in chat_log._added_content[0].content.lower()
    assert chat_log._added_content[0].content == "This is the actual answer"


@pytest.mark.asyncio
async def test_handle_chat_log_only_thinking_triggers_recall(
    hass: HomeAssistant,
) -> None:
    """Test that response with only thinking triggers re-call."""
    mock_entry = MockConfigEntry(domain=DOMAIN, data={})
    mock_entry.add_to_hass(hass)

    mock_client = MagicMock()
    mock_entry.runtime_data = mock_client

    # First call returns only thinking
    # Second call returns actual response
    mock_client.converse.side_effect = [
        create_response_with_only_thinking("Let me think about this"),
        create_simple_text_response("Here's the answer"),
    ]

    subentry = create_mock_subentry()
    entity = setup_entity_with_hass(hass, mock_entry, subentry)

    content = create_simple_user_message("Complex question")
    chat_log = create_mock_chat_log(content)

    async def mock_executor_job(func):
        return func()

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor_job):
        await entity._async_handle_chat_log(
            chat_log, structure=None, structure_name=None
        )

    # Verify two calls were made
    assert mock_client.converse.call_count == 2
    assert chat_log._added_content[0].content == "Here's the answer"


@pytest.mark.asyncio
async def test_handle_chat_log_nova_model_with_tools(hass: HomeAssistant) -> None:
    """Test Nova model gets temperature=0 and topK=1 when tools present."""
    mock_entry = MockConfigEntry(domain=DOMAIN, data={})
    mock_entry.add_to_hass(hass)

    mock_client = MagicMock()
    mock_entry.runtime_data = mock_client
    # Use side_effect to return different responses for each call
    mock_client.converse.side_effect = [
        create_nova_model_response("Result"),
        create_simple_text_response("Done"),  # Response after tool execution
    ]

    # Mock LLM API with tool
    mock_tool = create_mock_tool("test_tool", "Test")
    mock_llm_api = create_mock_llm_api(tools=[mock_tool])

    # Add async_call_tool to handle the tool use in the response
    mock_llm_api.async_call_tool = AsyncMock(return_value={"result": "success"})

    subentry = create_mock_subentry(model="us.amazon.nova-pro-v1:0", temperature=1.0)
    entity = setup_entity_with_hass(hass, mock_entry, subentry)

    content = create_simple_user_message("Test with tools")
    chat_log = create_mock_chat_log(content, llm_api=mock_llm_api)

    async def mock_executor_job(func):
        return func()

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor_job):
        await entity._async_handle_chat_log(
            chat_log, structure=None, structure_name=None
        )

    # Verify temperature=0 was set and topK=1 is in additionalModelRequestFields
    call_kwargs = mock_client.converse.call_args[1]
    assert call_kwargs["inferenceConfig"]["temperature"] == 0
    assert call_kwargs["additionalModelRequestFields"]["inferenceConfig"]["topK"] == 1


@pytest.mark.asyncio
async def test_handle_chat_log_max_tokens_increased_for_tools(
    hass: HomeAssistant,
) -> None:
    """Test max_tokens increased to minimum 3000 when tools present."""
    mock_entry = MockConfigEntry(domain=DOMAIN, data={})
    mock_entry.add_to_hass(hass)

    mock_client = MagicMock()
    mock_entry.runtime_data = mock_client
    mock_client.converse.return_value = create_simple_text_response("Result")

    # Mock LLM API with tool
    mock_tool = create_mock_tool("test_tool", "Test")
    mock_llm_api = create_mock_llm_api(tools=[mock_tool])

    subentry = create_mock_subentry(max_tokens=1000)  # Low value
    entity = setup_entity_with_hass(hass, mock_entry, subentry)

    content = create_simple_user_message("Test with tools")
    chat_log = create_mock_chat_log(content, llm_api=mock_llm_api)

    async def mock_executor_job(func):
        return func()

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor_job):
        await entity._async_handle_chat_log(
            chat_log, structure=None, structure_name=None
        )

    # Verify max_tokens was increased to 3000
    call_kwargs = mock_client.converse.call_args[1]
    assert call_kwargs["inferenceConfig"]["maxTokens"] >= 3000


@pytest.mark.asyncio
async def test_handle_chat_log_with_attachments(hass: HomeAssistant) -> None:
    """Test handling message with image attachments."""
    mock_entry = MockConfigEntry(domain=DOMAIN, data={})
    mock_entry.add_to_hass(hass)

    mock_client = MagicMock()
    mock_entry.runtime_data = mock_client
    mock_client.converse.return_value = create_simple_text_response(
        "I see a cat in the image"
    )

    subentry = create_mock_subentry()
    entity = setup_entity_with_hass(hass, mock_entry, subentry)

    content = create_message_with_attachments(
        [{"url": "/media/local/image.jpg", "mime_type": "image/jpeg"}]
    )
    chat_log = create_mock_chat_log(content)

    async def mock_executor_job(func):
        return func()

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor_job):
        await entity._async_handle_chat_log(
            chat_log, structure=None, structure_name=None
        )

    # Verify image was included in API call
    call_kwargs = mock_client.converse.call_args[1]
    messages = call_kwargs["messages"]
    # Should have image content in the message
    assert any(
        "image" in str(part) for msg in messages for part in msg.get("content", [])
    )


@pytest.mark.asyncio
async def test_handle_chat_log_api_error(hass: HomeAssistant) -> None:
    """Test handling of API errors."""
    mock_entry = MockConfigEntry(domain=DOMAIN, data={})
    mock_entry.add_to_hass(hass)

    mock_client = MagicMock()
    mock_entry.runtime_data = mock_client

    # Simulate API error
    mock_client.converse.side_effect = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
        "converse",
    )

    subentry = create_mock_subentry()
    entity = setup_entity_with_hass(hass, mock_entry, subentry)

    content = create_simple_user_message("Test message")
    chat_log = create_mock_chat_log(content)

    async def mock_executor_job(func):
        return func()

    with (
        patch.object(hass, "async_add_executor_job", side_effect=mock_executor_job),
        pytest.raises(HomeAssistantError),
    ):
        await entity._async_handle_chat_log(
            chat_log, structure=None, structure_name=None
        )


@pytest.mark.asyncio
async def test_handle_chat_log_malformed_tool_response(hass: HomeAssistant) -> None:
    """Test handling malformed tool response from API."""
    mock_entry = MockConfigEntry(domain=DOMAIN, data={})
    mock_entry.add_to_hass(hass)

    mock_client = MagicMock()
    mock_entry.runtime_data = mock_client
    mock_client.converse.return_value = create_response_with_malformed_tool_use()

    # Mock LLM API with tool
    mock_tool = create_mock_tool("test_tool", "Test")
    mock_llm_api = create_mock_llm_api(tools=[mock_tool])

    subentry = create_mock_subentry()
    entity = setup_entity_with_hass(hass, mock_entry, subentry)

    content = create_simple_user_message("Test")
    chat_log = create_mock_chat_log(content, llm_api=mock_llm_api)

    async def mock_executor_job(func):
        return func()

    with (
        patch.object(hass, "async_add_executor_job", side_effect=mock_executor_job),
        pytest.raises(HomeAssistantError),
    ):
        await entity._async_handle_chat_log(
            chat_log, structure=None, structure_name=None
        )


@pytest.mark.asyncio
async def test_handle_chat_log_with_structured_output(hass: HomeAssistant) -> None:
    """Test structured output as a tool."""
    mock_entry = MockConfigEntry(domain=DOMAIN, data={})
    mock_entry.add_to_hass(hass)

    mock_client = MagicMock()
    mock_entry.runtime_data = mock_client
    mock_client.converse.return_value = create_response_with_structured_output(
        {"name": "John", "age": 30}
    )

    subentry = create_mock_subentry()
    entity = setup_entity_with_hass(hass, mock_entry, subentry)

    # Define structure schema as JSON schema dict
    structure = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
        },
        "required": ["name", "age"],
    }

    content = create_simple_user_message("Extract person info")
    chat_log = create_mock_chat_log(content)

    async def mock_executor_job(func):
        return func()

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor_job):
        await entity._async_handle_chat_log(
            chat_log, structure=structure, structure_name="PersonInfo"
        )

    # Verify structure was added as tool in API call
    # Note: structure_name gets slugified to "personinfo"
    call_kwargs = mock_client.converse.call_args[1]
    assert "toolConfig" in call_kwargs
    tools = call_kwargs["toolConfig"]["tools"]
    assert any(tool["toolSpec"]["name"] == "personinfo" for tool in tools)


@pytest.mark.asyncio
async def test_handle_chat_log_conversation_history(hass: HomeAssistant) -> None:
    """Test multi-turn conversation history."""
    mock_entry = MockConfigEntry(domain=DOMAIN, data={})
    mock_entry.add_to_hass(hass)

    mock_client = MagicMock()
    mock_entry.runtime_data = mock_client
    mock_client.converse.return_value = create_simple_text_response(
        "Based on our previous discussion..."
    )

    subentry = create_mock_subentry()
    entity = setup_entity_with_hass(hass, mock_entry, subentry)

    content = create_conversation_history(
        [
            ("user", "What's 2+2?"),
            ("assistant", "2+2 equals 4"),
            ("user", "What about 3+3?"),
        ]
    )
    chat_log = create_mock_chat_log(content)

    async def mock_executor_job(func):
        return func()

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor_job):
        await entity._async_handle_chat_log(
            chat_log, structure=None, structure_name=None
        )

    # Verify all messages were included in API call
    call_kwargs = mock_client.converse.call_args[1]
    messages = call_kwargs["messages"]
    # Should have 3 messages: user, assistant, user
    assert len(messages) == 3
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[2]["role"] == "user"


@pytest.mark.asyncio
async def test_handle_chat_log_tool_name_mapping(hass: HomeAssistant) -> None:
    """Test tool name sanitization and reverse mapping."""
    mock_entry = MockConfigEntry(domain=DOMAIN, data={})
    mock_entry.add_to_hass(hass)

    mock_client = MagicMock()
    mock_entry.runtime_data = mock_client

    # Response uses sanitized name
    mock_client.converse.return_value = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "toolUse": {
                            "toolUseId": "tool_1",
                            "name": "my_domain_my_tool",  # Sanitized
                            "input": {"param": "value"},
                        }
                    }
                ],
            }
        },
        "stopReason": "tool_use",
        "usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15},
    }

    # Mock LLM API with tool that has special chars
    mock_tool = create_mock_tool(
        "my.domain.my-tool",  # Original name with dots and dashes
        "Test tool",
        vol.Schema({vol.Required("param"): str}),
    )
    mock_llm_api = create_mock_llm_api(tools=[mock_tool])

    # Mock tool execution
    async def mock_call_tool(tool_input):
        assert tool_input.tool_name == "my.domain.my-tool"  # Should use original name
        return {"result": "success"}

    mock_llm_api.async_call_tool = AsyncMock(side_effect=mock_call_tool)

    # Second call after tool execution
    mock_client.converse.side_effect = [
        mock_client.converse.return_value,
        create_simple_text_response("Tool executed successfully"),
    ]

    subentry = create_mock_subentry()
    entity = setup_entity_with_hass(hass, mock_entry, subentry)

    content = create_simple_user_message("Use the tool")
    chat_log = create_mock_chat_log(content, llm_api=mock_llm_api)

    async def mock_executor_job(func):
        return func()

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor_job):
        await entity._async_handle_chat_log(
            chat_log, structure=None, structure_name=None
        )

    # Verify tool was called with correct original name
    mock_llm_api.async_call_tool.assert_called_once()


@pytest.mark.asyncio
async def test_handle_chat_log_empty_response(hass: HomeAssistant) -> None:
    """Test handling of empty response content."""
    mock_entry = MockConfigEntry(domain=DOMAIN, data={})
    mock_entry.add_to_hass(hass)

    mock_client = MagicMock()
    mock_entry.runtime_data = mock_client

    # Empty content response
    mock_client.converse.return_value = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [],  # Empty content array
            }
        },
        "stopReason": "end_turn",
        "usage": {"inputTokens": 10, "outputTokens": 0, "totalTokens": 10},
    }

    subentry = create_mock_subentry()
    entity = setup_entity_with_hass(hass, mock_entry, subentry)

    content = create_simple_user_message("Test")
    chat_log = create_mock_chat_log(content)

    async def mock_executor_job(func):
        return func()

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor_job):
        await entity._async_handle_chat_log(
            chat_log, structure=None, structure_name=None
        )

    # Verify empty response was handled gracefully
    # Should not crash, may add empty content or skip
    assert True  # If we reach here, no exception was raised


def test_clean_schema_non_dict_returns_as_is() -> None:
    """Test _clean_schema returns non-dict values as-is."""
    # Non-dict input should be returned unchanged
    assert _clean_schema("string value") == "string value"  # type: ignore[arg-type]
    assert _clean_schema(123) == 123  # type: ignore[arg-type]
    assert _clean_schema(None) is None  # type: ignore[arg-type]
    assert _clean_schema([1, 2, 3]) == [1, 2, 3]  # type: ignore[arg-type]


def test_clean_schema_with_empty_items() -> None:
    """Test _clean_schema handles array items that become empty after cleaning."""
    schema = {
        "type": "array",
        "items": {
            "$schema": "unsupported",  # Will be removed
            "title": "unsupported",  # Will be removed
        },
    }
    cleaned = _clean_schema(schema)

    # items should be empty or not included since all fields were unsupported
    assert "items" not in cleaned or cleaned.get("items") == {}


def test_clean_schema_filters_required_to_existing_properties() -> None:
    """Test that required array only contains properties that exist."""
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
        },
        "required": ["name", "nonexistent_field"],  # nonexistent should be removed
    }
    cleaned = _clean_schema(schema)

    assert "required" in cleaned
    assert "name" in cleaned["required"]
    assert "nonexistent_field" not in cleaned["required"]


def test_clean_schema_with_nested_object_properties() -> None:
    """Test _clean_schema handles deeply nested object properties."""
    schema = {
        "type": "object",
        "properties": {
            "outer": {
                "type": "object",
                "properties": {
                    "inner": {
                        "type": "string",
                        "description": "An inner property",
                        "title": "Should be removed",
                    }
                },
                "required": ["inner"],
            }
        },
        "required": ["outer"],
    }
    cleaned = _clean_schema(schema)

    # Verify nested structure is preserved
    assert "outer" in cleaned["properties"]
    outer = cleaned["properties"]["outer"]
    assert "inner" in outer["properties"]
    inner = outer["properties"]["inner"]

    # Inner property should have allowed fields
    assert inner["type"] == "string"
    assert inner.get("description") == "An inner property"
    # Title should be removed
    assert "title" not in inner


def test_build_tool_name_maps_handles_collision() -> None:
    """Test _build_tool_name_maps adds suffix for collisions."""

    class _Tool1(llm.Tool):
        name = "test.tool"
        description = "Tool 1"
        parameters = vol.Schema({})

        async def async_call(
            self,
            hass: HomeAssistant,
            tool_input: llm.ToolInput,
            llm_context: llm.LLMContext,
        ) -> JsonObjectType:
            raise NotImplementedError

    class _Tool2(llm.Tool):
        name = "test_tool"  # Would sanitize to same as above
        description = "Tool 2"
        parameters = vol.Schema({})

        async def async_call(
            self,
            hass: HomeAssistant,
            tool_input: llm.ToolInput,
            llm_context: llm.LLMContext,
        ) -> JsonObjectType:
            raise NotImplementedError

    tools = [_Tool1(), _Tool2()]
    ha_to_bedrock, _bedrock_to_ha = _build_tool_name_maps(tools)

    # Both tools should have unique Bedrock names
    bedrock_names = list(ha_to_bedrock.values())
    assert len(set(bedrock_names)) == 2  # All unique

    # One should have a suffix
    assert "test_tool" in bedrock_names
    assert "test_tool_2" in bedrock_names


@pytest.mark.asyncio
async def test_handle_chat_log_with_structured_output_nova_model(
    hass: HomeAssistant,
) -> None:
    """Test structured output with Nova model applies schema cleaning."""
    mock_entry = MockConfigEntry(domain=DOMAIN, data={})
    mock_entry.add_to_hass(hass)

    mock_client = MagicMock()
    mock_entry.runtime_data = mock_client
    mock_client.converse.return_value = create_response_with_structured_output(
        {"name": "test", "value": 42}
    )

    subentry = create_mock_subentry(model="amazon.nova-pro-v1:0")
    entity = setup_entity_with_hass(hass, mock_entry, subentry)

    content = create_simple_user_message("Generate data")
    chat_log = create_mock_chat_log(content)

    structure = {
        "$schema": "http://json-schema.org/draft-07/schema#",  # Should be removed
        "title": "TestStructure",  # Should be removed
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "value": {"type": "integer"},
        },
    }

    async def mock_executor_job(func):
        return func()

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor_job):
        await entity._async_handle_chat_log(
            chat_log, structure_name="test_structure", structure=structure
        )

    # Verify the API was called with tools containing cleaned schema
    call_kwargs = mock_client.converse.call_args[1]
    assert "toolConfig" in call_kwargs
    tools = call_kwargs["toolConfig"]["tools"]

    # Find the structure tool
    structure_tool = next(t for t in tools if t["toolSpec"]["name"] == "test_structure")
    schema = structure_tool["toolSpec"]["inputSchema"]["json"]

    # Verify unsupported fields were removed
    assert "$schema" not in schema
    assert "title" not in schema
    assert "type" in schema
    assert "properties" in schema
