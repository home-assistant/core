"""Tests for the OpenAI integration."""

from collections.abc import Generator
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, patch

from freezegun import freeze_time
from httpx import Response
from openai import RateLimitError
from openai.types.chat.chat_completion_chunk import (
    ChatCompletionChunk,
    Choice,
    ChoiceDelta,
    ChoiceDeltaToolCall,
    ChoiceDeltaToolCallFunction,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import conversation
from homeassistant.components.conversation import chat_log
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import chat_session, intent
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

ASSIST_RESPONSE_FINISH = (
    # Assistant message
    ChatCompletionChunk(
        id="chatcmpl-B",
        created=1700000000,
        model="gpt-4-1106-preview",
        object="chat.completion.chunk",
        choices=[Choice(index=0, delta=ChoiceDelta(content="Cool"))],
    ),
    # Finish stream
    ChatCompletionChunk(
        id="chatcmpl-B",
        created=1700000000,
        model="gpt-4-1106-preview",
        object="chat.completion.chunk",
        choices=[Choice(index=0, finish_reason="stop", delta=ChoiceDelta())],
    ),
)


@pytest.fixture
def mock_create_stream() -> Generator[AsyncMock]:
    """Mock stream response."""

    async def mock_generator(stream):
        for value in stream:
            yield value

    with patch(
        "openai.resources.chat.completions.AsyncCompletions.create",
        AsyncMock(),
    ) as mock_create:
        mock_create.side_effect = lambda **kwargs: mock_generator(
            mock_create.return_value.pop(0)
        )

        yield mock_create


@dataclass
class MockChatLog(chat_log.ChatLog):
    """Mock chat log."""

    _mock_tool_results: dict = field(default_factory=dict)

    def mock_tool_results(self, results: dict) -> None:
        """Set tool results."""
        self._mock_tool_results = results

    @property
    def llm_api(self):
        """Return LLM API."""
        return self._llm_api

    @llm_api.setter
    def llm_api(self, value):
        """Set LLM API."""
        self._llm_api = value

        if not value:
            return

        async def async_call_tool(tool_input):
            """Call tool."""
            if tool_input.id not in self._mock_tool_results:
                raise ValueError(f"Tool {tool_input.id} not found")
            return self._mock_tool_results[tool_input.id]

        self._llm_api.async_call_tool = async_call_tool

    def latest_content(self) -> list[conversation.Content]:
        """Return content from latest version chat log.

        The chat log makes copies until it's committed. Helper to get latest content.
        """
        with (
            chat_session.async_get_chat_session(
                self.hass, self.conversation_id
            ) as session,
            conversation.async_get_chat_log(self.hass, session) as chat_log,
        ):
            return chat_log.content


@pytest.fixture
async def mock_chat_log(hass: HomeAssistant) -> MockChatLog:
    """Return mock chat logs."""
    with (
        patch(
            "homeassistant.components.conversation.chat_log.ChatLog",
            MockChatLog,
        ),
        chat_session.async_get_chat_session(hass, "mock-conversation-id") as session,
        conversation.async_get_chat_log(hass, session) as chat_log,
    ):
        chat_log.async_add_user_content(conversation.UserContent("hello"))
        return chat_log


async def test_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test entity properties."""
    state = hass.states.get("conversation.openai")
    assert state
    assert state.attributes["supported_features"] == 0

    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            **mock_config_entry.options,
            CONF_LLM_HASS_API: "assist",
        },
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)

    state = hass.states.get("conversation.openai")
    assert state
    assert (
        state.attributes["supported_features"]
        == conversation.ConversationEntityFeature.CONTROL
    )


async def test_error_handling(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_init_component
) -> None:
    """Test that we handle errors when calling completion API."""
    with patch(
        "openai.resources.chat.completions.AsyncCompletions.create",
        new_callable=AsyncMock,
        side_effect=RateLimitError(
            response=Response(status_code=None, request=""), body=None, message=None
        ),
    ):
        result = await conversation.async_converse(
            hass, "hello", None, Context(), agent_id=mock_config_entry.entry_id
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
    assert result.response.error_code == "unknown", result


async def test_conversation_agent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test OpenAIAgent."""
    agent = conversation.get_agent_manager(hass).async_get_agent(
        mock_config_entry.entry_id
    )
    assert agent.supported_languages == "*"


async def test_function_call(
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
    mock_chat_log: MockChatLog,
    snapshot: SnapshotAssertion,
) -> None:
    """Test function call from the assistant."""
    mock_create_stream.return_value = [
        # Initial conversation
        (
            # First tool call
            ChatCompletionChunk(
                id="chatcmpl-A",
                created=1700000000,
                model="gpt-4-1106-preview",
                object="chat.completion.chunk",
                choices=[
                    Choice(
                        index=0,
                        delta=ChoiceDelta(
                            tool_calls=[
                                ChoiceDeltaToolCall(
                                    id="call_call_1",
                                    index=0,
                                    function=ChoiceDeltaToolCallFunction(
                                        name="test_tool",
                                        arguments=None,
                                    ),
                                )
                            ]
                        ),
                    )
                ],
            ),
            ChatCompletionChunk(
                id="chatcmpl-A",
                created=1700000000,
                model="gpt-4-1106-preview",
                object="chat.completion.chunk",
                choices=[
                    Choice(
                        index=0,
                        delta=ChoiceDelta(
                            tool_calls=[
                                ChoiceDeltaToolCall(
                                    index=0,
                                    function=ChoiceDeltaToolCallFunction(
                                        name=None,
                                        arguments='{"para',
                                    ),
                                )
                            ]
                        ),
                    )
                ],
            ),
            ChatCompletionChunk(
                id="chatcmpl-A",
                created=1700000000,
                model="gpt-4-1106-preview",
                object="chat.completion.chunk",
                choices=[
                    Choice(
                        index=0,
                        delta=ChoiceDelta(
                            tool_calls=[
                                ChoiceDeltaToolCall(
                                    index=0,
                                    function=ChoiceDeltaToolCallFunction(
                                        name=None,
                                        arguments='m1":"call1"}',
                                    ),
                                )
                            ]
                        ),
                    )
                ],
            ),
            # Second tool call
            ChatCompletionChunk(
                id="chatcmpl-A",
                created=1700000000,
                model="gpt-4-1106-preview",
                object="chat.completion.chunk",
                choices=[
                    Choice(
                        index=0,
                        delta=ChoiceDelta(
                            tool_calls=[
                                ChoiceDeltaToolCall(
                                    id="call_call_2",
                                    index=1,
                                    function=ChoiceDeltaToolCallFunction(
                                        name="test_tool",
                                        arguments='{"param1":"call2"}',
                                    ),
                                )
                            ]
                        ),
                    )
                ],
            ),
            # Finish stream
            ChatCompletionChunk(
                id="chatcmpl-A",
                created=1700000000,
                model="gpt-4-1106-preview",
                object="chat.completion.chunk",
                choices=[
                    Choice(index=0, finish_reason="tool_calls", delta=ChoiceDelta())
                ],
            ),
        ),
        # Response after tool responses
        ASSIST_RESPONSE_FINISH,
    ]
    mock_chat_log.mock_tool_results(
        {
            "call_call_1": "value1",
            "call_call_2": "value2",
        }
    )

    with freeze_time("2024-06-03 23:00:00"):
        result = await conversation.async_converse(
            hass,
            "Please call the test function",
            "mock-conversation-id",
            Context(),
            agent_id="conversation.openai",
        )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert mock_chat_log.latest_content() == snapshot


@pytest.mark.parametrize(
    ("description", "messages"),
    [
        (
            "Test function call started with missing arguments",
            (
                ChatCompletionChunk(
                    id="chatcmpl-A",
                    created=1700000000,
                    model="gpt-4-1106-preview",
                    object="chat.completion.chunk",
                    choices=[
                        Choice(
                            index=0,
                            delta=ChoiceDelta(
                                tool_calls=[
                                    ChoiceDeltaToolCall(
                                        id="call_call_1",
                                        index=0,
                                        function=ChoiceDeltaToolCallFunction(
                                            name="test_tool",
                                            arguments=None,
                                        ),
                                    )
                                ]
                            ),
                        )
                    ],
                ),
                ChatCompletionChunk(
                    id="chatcmpl-B",
                    created=1700000000,
                    model="gpt-4-1106-preview",
                    object="chat.completion.chunk",
                    choices=[Choice(index=0, delta=ChoiceDelta(content="Cool"))],
                ),
            ),
        ),
        (
            "Test invalid JSON",
            (
                ChatCompletionChunk(
                    id="chatcmpl-A",
                    created=1700000000,
                    model="gpt-4-1106-preview",
                    object="chat.completion.chunk",
                    choices=[
                        Choice(
                            index=0,
                            delta=ChoiceDelta(
                                tool_calls=[
                                    ChoiceDeltaToolCall(
                                        id="call_call_1",
                                        index=0,
                                        function=ChoiceDeltaToolCallFunction(
                                            name="test_tool",
                                            arguments=None,
                                        ),
                                    )
                                ]
                            ),
                        )
                    ],
                ),
                ChatCompletionChunk(
                    id="chatcmpl-A",
                    created=1700000000,
                    model="gpt-4-1106-preview",
                    object="chat.completion.chunk",
                    choices=[
                        Choice(
                            index=0,
                            delta=ChoiceDelta(
                                tool_calls=[
                                    ChoiceDeltaToolCall(
                                        index=0,
                                        function=ChoiceDeltaToolCallFunction(
                                            name=None,
                                            arguments='{"para',
                                        ),
                                    )
                                ]
                            ),
                        )
                    ],
                ),
                ChatCompletionChunk(
                    id="chatcmpl-B",
                    created=1700000000,
                    model="gpt-4-1106-preview",
                    object="chat.completion.chunk",
                    choices=[
                        Choice(
                            index=0,
                            delta=ChoiceDelta(content="Cool"),
                            finish_reason="tool_calls",
                        )
                    ],
                ),
            ),
        ),
    ],
)
async def test_function_call_invalid(
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
    mock_chat_log: MockChatLog,
    description: str,
    messages: tuple[ChatCompletionChunk],
) -> None:
    """Test function call containing invalid data."""
    mock_create_stream.return_value = [messages]

    with pytest.raises(ValueError):
        await conversation.async_converse(
            hass,
            "Please call the test function",
            "mock-conversation-id",
            Context(),
            agent_id="conversation.openai",
        )


async def test_assist_api_tools_conversion(
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
    mock_create_stream,
) -> None:
    """Test that we are able to convert actual tools from Assist API."""
    for component in (
        "calendar",
        "climate",
        "cover",
        "humidifier",
        "intent",
        "light",
        "media_player",
        "script",
        "shopping_list",
        "todo",
        "vacuum",
        "weather",
    ):
        assert await async_setup_component(hass, component, {})
        hass.states.async_set(f"{component}.test", "on")
        async_expose_entity(hass, "conversation", f"{component}.test", True)

    mock_create_stream.return_value = [ASSIST_RESPONSE_FINISH]

    await conversation.async_converse(
        hass, "hello", None, Context(), agent_id="conversation.openai"
    )

    tools = mock_create_stream.mock_calls[0][2]["tools"]
    assert tools
