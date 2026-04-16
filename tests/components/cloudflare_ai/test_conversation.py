"""Tests for the Cloudflare Workers AI conversation entity."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import voluptuous as vol

from homeassistant.components import conversation as conv
from homeassistant.components.cloudflare_ai.client import CloudflareAIAuthError
from homeassistant.components.cloudflare_ai.conversation import (
    CloudflareConversationEntity,
    _format_tool,
)
from homeassistant.components.conversation import ToolResultContent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import (
    SAMPLE_CHAT_RESPONSE,
    SAMPLE_TOOL_CALL_RESPONSE,
    SAMPLE_TOOL_RESULT_RESPONSE,
)

from tests.common import MockConfigEntry


async def test_conversation_entity_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_validate_credentials: AsyncMock,
    mock_run_model: AsyncMock,
    setup_ha_components: None,
) -> None:
    """Test that the conversation entity is created on setup."""
    mock_run_model.return_value = SAMPLE_CHAT_RESPONSE

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("conversation.cloudflare_ai_conversation")
    assert state is not None


async def test_simple_chat_response(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_validate_credentials: AsyncMock,
    mock_run_model: AsyncMock,
    setup_ha_components: None,
) -> None:
    """Test a simple chat without tool calls."""
    mock_run_model.return_value = SAMPLE_CHAT_RESPONSE

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.services.async_call(
        "conversation",
        "process",
        {
            "text": "Hello!",
            "agent_id": "conversation.cloudflare_ai_conversation",
        },
        blocking=True,
        return_response=True,
    )
    assert result is not None
    speech = result["response"]["speech"]["plain"]["speech"]
    assert "Hello" in speech


async def test_chat_with_tool_call(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_validate_credentials: AsyncMock,
    mock_run_model: AsyncMock,
    setup_ha_components: None,
) -> None:
    """Test conversation with a tool call and follow-up response."""
    mock_run_model.side_effect = [
        SAMPLE_TOOL_CALL_RESPONSE,
        SAMPLE_TOOL_RESULT_RESPONSE,
    ]

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.helpers.llm.APIInstance.async_call_tool",
        new_callable=AsyncMock,
        return_value={"date": "2026-03-18", "time": "20:00:00"},
    ):
        result = await hass.services.async_call(
            "conversation",
            "process",
            {
                "text": "What time is it?",
                "agent_id": "conversation.cloudflare_ai_conversation",
            },
            blocking=True,
            return_response=True,
        )

    assert result is not None
    speech = result["response"]["speech"]["plain"]["speech"]
    assert "March 18" in speech or "2026" in speech


async def test_chat_auth_error_triggers_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_validate_credentials: AsyncMock,
    mock_run_model: AsyncMock,
    setup_ha_components: None,
) -> None:
    """Test that auth errors trigger reauth."""
    mock_run_model.side_effect = CloudflareAIAuthError("Invalid token")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.services.async_call(
        "conversation",
        "process",
        {
            "text": "Hello",
            "agent_id": "conversation.cloudflare_ai_conversation",
        },
        blocking=True,
        return_response=True,
    )
    assert result is not None
    assert result["response"]["response_type"] == "error"


class TestResponseParsing:
    """Test conversation response parsing."""

    def test_parse_workers_ai_native(self) -> None:
        """Test parsing Workers AI native format."""
        entity = object.__new__(CloudflareConversationEntity)
        result = entity._parse_response(
            {
                "response": "Hello!",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }
        )
        assert result["content"] == "Hello!"
        assert result["role"] == "assistant"

    def test_parse_with_tool_calls(self) -> None:
        """Test parsing response with tool calls."""
        entity = object.__new__(CloudflareConversationEntity)
        result = entity._parse_response(
            {
                "response": None,
                "tool_calls": [{"name": "GetDateTime", "arguments": {}}],
            }
        )
        assert result["content"] == ""
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["name"] == "GetDateTime"

    def test_parse_openai_format(self) -> None:
        """Test parsing OpenAI-compatible format."""
        entity = object.__new__(CloudflareConversationEntity)
        result = entity._parse_response(
            {"choices": [{"message": {"role": "assistant", "content": "Hi there!"}}]}
        )
        assert result["content"] == "Hi there!"

    def test_parse_fallback(self) -> None:
        """Test fallback for unknown format."""
        entity = object.__new__(CloudflareConversationEntity)
        result = entity._parse_response("raw string response")
        assert result["content"] == "raw string response"
        assert result["role"] == "assistant"


class TestToolCallParsing:
    """Test tool call format handling."""

    def test_cf_native_tool_format(self) -> None:
        """Test CF native tool call format: {name, arguments}."""
        entity = object.__new__(CloudflareConversationEntity)
        messages: list[dict] = []
        entity._append_tool_call_messages(
            messages,
            {
                "content": "",
                "tool_calls": [
                    {"name": "GetDateTime", "arguments": {}},
                ],
            },
        )
        assert len(messages) == 1
        tc = messages[0]["tool_calls"][0]
        assert tc["function"]["name"] == "GetDateTime"
        assert tc["type"] == "function"
        # Without an explicit ID, a unique fallback ID is generated.
        assert tc["id"].startswith("call_")

    def test_cf_native_tool_format_with_id(self) -> None:
        """Test CF native tool call format keeps explicit ID when provided."""
        entity = object.__new__(CloudflareConversationEntity)
        messages: list[dict] = []
        entity._append_tool_call_messages(
            messages,
            {
                "content": "",
                "tool_calls": [
                    {"id": "explicit_id", "name": "GetDateTime", "arguments": {}},
                ],
            },
        )
        tc = messages[0]["tool_calls"][0]
        assert tc["id"] == "explicit_id"

    def test_unique_ids_for_multiple_calls(self) -> None:
        """Test unique IDs are generated for multiple tool calls."""
        entity = object.__new__(CloudflareConversationEntity)
        messages: list[dict] = []
        entity._append_tool_call_messages(
            messages,
            {
                "content": "",
                "tool_calls": [
                    {"name": "GetTime", "arguments": {}},
                    {"name": "GetTime", "arguments": {}},
                ],
            },
        )
        tc_list = messages[0]["tool_calls"]
        # Both should have unique IDs even when calling the same tool twice
        assert tc_list[0]["id"] != tc_list[1]["id"]

    def test_openai_tool_format(self) -> None:
        """Test OpenAI tool call format: {function: {name, arguments}}."""
        entity = object.__new__(CloudflareConversationEntity)
        messages: list[dict] = []
        entity._append_tool_call_messages(
            messages,
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_123",
                        "type": "function",
                        "function": {
                            "name": "GetDateTime",
                            "arguments": "{}",
                        },
                    },
                ],
            },
        )
        assert len(messages) == 1
        tc = messages[0]["tool_calls"][0]
        assert tc["function"]["name"] == "GetDateTime"
        assert tc["id"] == "call_123"


class TestTokenUsageTracking:
    """Test token usage tracking."""

    def test_trace_usage_with_stats(self) -> None:
        """Test that usage data is traced."""
        chat_log = MagicMock()
        CloudflareConversationEntity._trace_usage(
            chat_log,
            {
                "response": "hello",
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 20,
                    "total_tokens": 120,
                },
            },
        )
        chat_log.async_trace.assert_called_once_with(
            {
                "stats": {
                    "input_tokens": 100,
                    "output_tokens": 20,
                }
            }
        )

    def test_trace_usage_no_usage(self) -> None:
        """Test that missing usage is handled gracefully."""
        chat_log = MagicMock()
        CloudflareConversationEntity._trace_usage(chat_log, {"response": "hello"})
        chat_log.async_trace.assert_not_called()

    def test_trace_usage_not_dict(self) -> None:
        """Test that non-dict responses are handled."""
        chat_log = MagicMock()
        CloudflareConversationEntity._trace_usage(chat_log, "not a dict")
        chat_log.async_trace.assert_not_called()


class TestFormatTool:
    """Test tool formatting for the API."""

    def test_format_tool_basic(self) -> None:
        """Test formatting a basic HA LLM tool."""
        tool = MagicMock()
        tool.name = "HassTurnOn"
        tool.description = "Turn on a device"
        tool.parameters = vol.Schema({vol.Required("entity_id"): str})
        result = _format_tool(tool, custom_serializer=None)
        assert result["type"] == "function"
        assert result["function"]["name"] == "HassTurnOn"
        assert result["function"]["description"] == "Turn on a device"

    def test_format_tool_no_parameters(self) -> None:
        """Test formatting a tool with no parameters."""
        tool = MagicMock()
        tool.name = "GetDateTime"
        tool.description = "Get the current date and time"
        tool.parameters = vol.Schema({})
        result = _format_tool(tool, custom_serializer=None)
        assert result["function"]["parameters"]["type"] == "object"
        assert result["type"] == "function"
        assert result["function"]["name"] == "GetDateTime"


class TestBuildMessages:
    """Test conversation chat log to messages conversion."""

    def test_system_content(self) -> None:
        """Test SystemContent is converted to system role."""
        entity = object.__new__(CloudflareConversationEntity)
        chat_log = MagicMock()
        sys_content = MagicMock(spec=conv.SystemContent)
        sys_content.content = "You are a helper"
        chat_log.content = [sys_content]
        result = entity._build_messages(chat_log)
        assert result == [{"role": "system", "content": "You are a helper"}]

    def test_user_content(self) -> None:
        """Test UserContent is converted to user role."""
        entity = object.__new__(CloudflareConversationEntity)
        chat_log = MagicMock()
        user_content = MagicMock(spec=conv.UserContent)
        user_content.content = "Hello"
        chat_log.content = [user_content]
        result = entity._build_messages(chat_log)
        assert result == [{"role": "user", "content": "Hello"}]

    def test_assistant_content_no_tools(self) -> None:
        """Test AssistantContent without tool calls."""
        entity = object.__new__(CloudflareConversationEntity)
        chat_log = MagicMock()
        ast_content = MagicMock(spec=conv.AssistantContent)
        ast_content.content = "Hi!"
        ast_content.tool_calls = None
        chat_log.content = [ast_content]
        result = entity._build_messages(chat_log)
        assert result == [{"role": "assistant", "content": "Hi!"}]

    def test_assistant_content_with_tool_calls(self) -> None:
        """Test AssistantContent with tool calls."""
        entity = object.__new__(CloudflareConversationEntity)
        chat_log = MagicMock()
        ast_content = MagicMock(spec=conv.AssistantContent)
        ast_content.content = ""
        tc = MagicMock()
        tc.id = "call_1"
        tc.tool_name = "GetTime"
        tc.tool_args = {}
        ast_content.tool_calls = [tc]
        chat_log.content = [ast_content]
        result = entity._build_messages(chat_log)
        assert result[0]["role"] == "assistant"
        assert result[0]["tool_calls"][0]["id"] == "call_1"
        assert result[0]["tool_calls"][0]["function"]["name"] == "GetTime"

    def test_tool_result_content(self) -> None:
        """Test ToolResultContent is converted to tool role."""
        entity = object.__new__(CloudflareConversationEntity)
        chat_log = MagicMock()
        tool_result = MagicMock(spec=ToolResultContent)
        tool_result.tool_call_id = "call_1"
        tool_result.tool_result = {"result": "ok"}
        chat_log.content = [tool_result]
        result = entity._build_messages(chat_log)
        assert result[0]["role"] == "tool"
        assert result[0]["tool_call_id"] == "call_1"


class TestExecuteToolCalls:
    """Test tool call execution."""

    async def test_execute_openai_format_tool(self) -> None:
        """Test executing an OpenAI-format tool call."""
        entity = object.__new__(CloudflareConversationEntity)
        chat_log = MagicMock()
        chat_log.llm_api = MagicMock()
        chat_log.llm_api.async_call_tool = AsyncMock(return_value={"result": "ok"})
        user_input = MagicMock()

        tool_calls = [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "GetTime",
                    "arguments": '{"timezone": "UTC"}',
                },
            }
        ]
        results = await entity._execute_tool_calls(tool_calls, chat_log, user_input)
        assert len(results) == 1
        assert results[0]["role"] == "tool"
        assert results[0]["tool_call_id"] == "call_1"

    async def test_execute_cf_native_format_tool(self) -> None:
        """Test executing a CF native format tool call."""
        entity = object.__new__(CloudflareConversationEntity)
        chat_log = MagicMock()
        chat_log.llm_api = MagicMock()
        chat_log.llm_api.async_call_tool = AsyncMock(return_value={"r": 1})
        user_input = MagicMock()

        tool_calls = [{"name": "GetDateTime", "arguments": {}}]
        results = await entity._execute_tool_calls(tool_calls, chat_log, user_input)
        assert len(results) == 1
        # Without an explicit ID, a unique fallback ID is generated.
        assert results[0]["tool_call_id"].startswith("call_")

    async def test_execute_no_llm_api(self) -> None:
        """Test executing tool calls when no LLM API is configured."""
        entity = object.__new__(CloudflareConversationEntity)
        chat_log = MagicMock()
        chat_log.llm_api = None
        user_input = MagicMock()

        tool_calls = [{"name": "GetTime", "arguments": {}}]
        results = await entity._execute_tool_calls(tool_calls, chat_log, user_input)
        assert "No LLM API configured" in results[0]["content"]

    async def test_execute_invalid_json_args(self) -> None:
        """Test executing tool calls with invalid JSON args."""
        entity = object.__new__(CloudflareConversationEntity)
        chat_log = MagicMock()
        chat_log.llm_api = MagicMock()
        chat_log.llm_api.async_call_tool = AsyncMock(return_value={"r": 1})
        user_input = MagicMock()

        tool_calls = [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "GetTime", "arguments": "not-json"},
            }
        ]
        results = await entity._execute_tool_calls(tool_calls, chat_log, user_input)
        assert len(results) == 1
        # Tool was still called with empty args after JSON decode failure
        chat_log.llm_api.async_call_tool.assert_called_once()

    async def test_execute_tool_failure(self) -> None:
        """Test tool execution failure is captured."""
        entity = object.__new__(CloudflareConversationEntity)
        chat_log = MagicMock()
        chat_log.llm_api = MagicMock()
        chat_log.llm_api.async_call_tool = AsyncMock(
            side_effect=HomeAssistantError("tool failed")
        )
        user_input = MagicMock()

        tool_calls = [{"name": "BadTool", "arguments": {}}]
        results = await entity._execute_tool_calls(tool_calls, chat_log, user_input)
        assert "tool failed" in results[0]["content"]


class TestParseResponseEdgeCases:
    """Additional edge cases for response parsing."""

    def test_parse_tool_calls_only(self) -> None:
        """Test parsing dict with tool_calls but no response or choices."""
        entity = object.__new__(CloudflareConversationEntity)
        result = entity._parse_response(
            {
                "tool_calls": [{"name": "GetTime", "arguments": {}}],
                "content": "thinking...",
            }
        )
        assert result["tool_calls"] == [{"name": "GetTime", "arguments": {}}]
        assert result["content"] == "thinking..."

    def test_parse_empty_dict(self) -> None:
        """Test parsing empty dict falls through."""
        entity = object.__new__(CloudflareConversationEntity)
        result = entity._parse_response({})
        assert result["role"] == "assistant"
        assert result["content"] == ""

    def test_parse_none(self) -> None:
        """Test parsing None."""
        entity = object.__new__(CloudflareConversationEntity)
        result = entity._parse_response(None)
        assert result["content"] == ""
