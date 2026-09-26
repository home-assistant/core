"""Live integration tests for Google Gemini Interactions API."""

from collections.abc import Generator
import os
import socket

from google import genai
import probatio
import pytest
import pytest_socket

from homeassistant.components import conversation
from homeassistant.components.google_generative_ai_conversation.interactions import (
    build_interaction_request,
    format_tools_for_interactions,
    transform_interactions_stream,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from tests.conftest import HASocketBlockedError, _real_getaddrinfo

pytestmark = pytest.mark.skipif(
    "GEMINI_API_KEY" not in os.environ,
    reason="GEMINI_API_KEY environment variable not set",
)


@pytest.fixture(autouse=True)
def allow_live_network(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    """Allow network connections for live integration testing."""
    monkeypatch.setattr(socket, "getaddrinfo", _real_getaddrinfo)
    pytest_socket.enable_socket()
    pytest_socket.socket_allow_hosts(["0.0.0.0/0", "::/0"])
    yield
    pytest_socket.disable_socket(allow_unix_socket=True)
    pytest_socket.socket_allow_hosts(["127.0.0.1"])
    HASocketBlockedError.instances.clear()


async def test_live_chat_log_streaming(hass: HomeAssistant) -> None:
    """Test live Interactions API streaming using ChatLog and utility functions."""
    api_key = os.environ["GEMINI_API_KEY"]
    client = genai.Client(api_key=api_key)

    chat_log = conversation.ChatLog(hass, "test_live_conversation")
    user_prompt = "Say hello and reply with exactly: Hello world!"
    chat_log.async_add_user_content(conversation.UserContent(content=user_prompt))

    request = build_interaction_request(
        model="gemini-2.5-flash",
        input_content=user_prompt,
        stream=True,
        store=False,
    )

    stream = await client.aio.interactions.create(**request)
    async for _ in chat_log.async_add_delta_content_stream(
        "conversation.google_ai_conversation",
        transform_interactions_stream(chat_log, stream),
    ):
        pass

    assert len(chat_log.content) == 3
    assert isinstance(chat_log.content[-1], conversation.AssistantContent)
    assistant_content = chat_log.content[-1]
    assert assistant_content.role == "assistant"
    assert assistant_content.content
    assert len(assistant_content.content.strip()) > 0


async def test_live_chat_log_tool_calling(hass: HomeAssistant) -> None:
    """Test live Interactions API tool calling using ChatLog and utility functions."""
    api_key = os.environ["GEMINI_API_KEY"]
    client = genai.Client(api_key=api_key)

    chat_log = conversation.ChatLog(hass, "test_live_conversation_tools")
    user_prompt = (
        "What is the weather in Tokyo right now? You must call the get_weather tool."
    )
    chat_log.async_add_user_content(conversation.UserContent(content=user_prompt))

    class WeatherTool(llm.Tool):
        name = "get_weather"
        description = "Get current weather for a city"
        parameters = probatio.Schema({probatio.Required("city"): str})

        async def async_call(
            self,
            hass: HomeAssistant,
            tool_input: llm.ToolInput,
            llm_context: llm.LLMContext,
        ) -> llm.ToolResult:
            return llm.ToolResult(data={"weather": "Sunny, 22C"})

    tool = WeatherTool()
    formatted_tools = format_tools_for_interactions([tool])

    request = build_interaction_request(
        model="gemini-2.5-flash",
        input_content=user_prompt,
        stream=True,
        store=False,
        tools=formatted_tools,
    )

    stream = await client.aio.interactions.create(**request)
    deltas = [delta async for delta in transform_interactions_stream(chat_log, stream)]

    assert deltas[0] == {"role": "assistant"}
    tool_call_deltas = [d for d in deltas if "tool_calls" in d]
    assert len(tool_call_deltas) > 0
    tool_calls = tool_call_deltas[0]["tool_calls"]
    assert len(tool_calls) > 0
    assert tool_calls[0].tool_name == "get_weather"
    assert "city" in tool_calls[0].tool_args
