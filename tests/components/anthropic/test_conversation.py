"""Tests for the Anthropic integration."""

import datetime
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from anthropic import RateLimitError
from anthropic.types import (
    CitationsWebSearchResultLocation,
    CitationWebSearchResultLocationParam,
    ThinkingBlock,
    WebSearchResultBlock,
)
from freezegun import freeze_time
from httpx import URL, Request, Response
import pytest
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol

from homeassistant.components import conversation
from homeassistant.components.anthropic.const import (
    CONF_CHAT_MODEL,
    CONF_THINKING_BUDGET,
    CONF_THINKING_EFFORT,
    CONF_WEB_SEARCH,
    CONF_WEB_SEARCH_CITY,
    CONF_WEB_SEARCH_COUNTRY,
    CONF_WEB_SEARCH_MAX_USES,
    CONF_WEB_SEARCH_REGION,
    CONF_WEB_SEARCH_TIMEZONE,
    CONF_WEB_SEARCH_USER_LOCATION,
)
from homeassistant.components.anthropic.entity import CitationDetails, ContentDetails
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import chat_session, intent, llm
from homeassistant.setup import async_setup_component
from homeassistant.util import ulid as ulid_util

from . import (
    create_content_block,
    create_redacted_thinking_block,
    create_thinking_block,
    create_tool_use_block,
    create_web_search_block,
    create_web_search_result_block,
)

from tests.common import MockConfigEntry


async def test_entity(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_init_component
) -> None:
    """Test entity properties."""
    state = hass.states.get("conversation.claude_conversation")
    assert state
    assert state.attributes["supported_features"] == 0

    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={
            **subentry.data,
            CONF_LLM_HASS_API: "assist",
        },
    )
    with patch("anthropic.resources.models.AsyncModels.retrieve"):
        await hass.config_entries.async_reload(mock_config_entry.entry_id)

    state = hass.states.get("conversation.claude_conversation")
    assert state
    assert (
        state.attributes["supported_features"]
        == conversation.ConversationEntityFeature.CONTROL
    )


async def test_error_handling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
) -> None:
    """Test that the default prompt works."""
    mock_create_stream.side_effect = RateLimitError(
        message=None,
        response=Response(status_code=429, request=Request(method="POST", url=URL())),
        body=None,
    )

    result = await conversation.async_converse(
        hass, "hello", None, Context(), agent_id="conversation.claude_conversation"
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == "unknown", result


async def test_template_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that template error handling works."""
    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={
            "prompt": "talk like a {% if True %}smarthome{% else %}pirate please.",
        },
    )
    with patch("anthropic.resources.models.AsyncModels.list", new_callable=AsyncMock):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    result = await conversation.async_converse(
        hass, "hello", None, Context(), agent_id="conversation.claude_conversation"
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == "unknown", result


async def test_template_variables(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_stream: AsyncMock,
) -> None:
    """Test that template variables work."""
    context = Context(user_id="12345")
    mock_user = Mock()
    mock_user.id = "12345"
    mock_user.name = "Test User"

    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={
            "prompt": (
                "The user name is {{ user_name }}. "
                "The user id is {{ llm_context.context.user_id }}."
            ),
        },
    )

    mock_create_stream.return_value = [
        create_content_block(0, ["Okay, let", " me take care of that for you", "."])
    ]
    with (
        patch("anthropic.resources.models.AsyncModels.list", new_callable=AsyncMock),
        patch("homeassistant.auth.AuthManager.async_get_user", return_value=mock_user),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        result = await conversation.async_converse(
            hass, "hello", None, context, agent_id="conversation.claude_conversation"
        )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert (
        result.response.speech["plain"]["speech"]
        == "Okay, let me take care of that for you."
    )

    system = mock_create_stream.call_args.kwargs["system"]
    assert isinstance(system, list)
    system_text = " ".join(block["text"] for block in system if "text" in block)

    assert "The user name is Test User." in system_text
    assert "The user id is 12345." in system_text


async def test_conversation_agent(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_init_component
) -> None:
    """Test Anthropic Agent."""
    agent = conversation.agent_manager.async_get_agent(
        hass, "conversation.claude_conversation"
    )
    assert agent.supported_languages == "*"


async def test_system_prompt_uses_text_block_with_cache_control(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_stream: AsyncMock,
) -> None:
    """Ensure system prompt is sent as TextBlockParam with cache_control."""
    context = Context()

    mock_create_stream.return_value = [
        create_content_block(0, ["ok"]),
    ]

    with patch("anthropic.resources.models.AsyncModels.list", new_callable=AsyncMock):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        await conversation.async_converse(
            hass,
            "hello",
            None,
            context,
            agent_id="conversation.claude_conversation",
        )

    system = mock_create_stream.call_args.kwargs["system"]
    assert isinstance(system, list)
    assert len(system) == 1
    block = system[0]
    assert block["type"] == "text"
    assert "Home Assistant" in block["text"]
    assert block["cache_control"] == {"type": "ephemeral"}


@patch("homeassistant.components.anthropic.entity.llm.AssistAPI._async_get_tools")
@pytest.mark.parametrize(
    ("tool_call_json_parts", "expected_call_tool_args"),
    [
        (
            ['{"param1": "test_value"}'],
            {"param1": "test_value"},
        ),
        (
            ['{"para', 'm1": "test_valu', 'e"}'],
            {"param1": "test_value"},
        ),
        ([""], {}),
    ],
)
async def test_function_call(
    mock_get_tools,
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
    tool_call_json_parts: list[str],
    expected_call_tool_args: dict[str, Any],
) -> None:
    """Test function call from the assistant."""
    agent_id = "conversation.claude_conversation"
    context = Context()

    mock_tool = AsyncMock()
    mock_tool.name = "test_tool"
    mock_tool.description = "Test function"
    mock_tool.parameters = vol.Schema(
        {vol.Optional("param1", description="Test parameters"): str}
    )
    mock_tool.async_call.return_value = "Test response"

    mock_get_tools.return_value = [mock_tool]

    mock_create_stream.return_value = [
        (
            *create_content_block(0, ["Certainly, calling it now!"]),
            *create_tool_use_block(
                1,
                "toolu_0123456789AbCdEfGhIjKlM",
                "test_tool",
                tool_call_json_parts,
            ),
        ),
        create_content_block(0, ["I have ", "successfully called ", "the function"]),
    ]

    with freeze_time("2024-06-03 23:00:00"):
        result = await conversation.async_converse(
            hass,
            "Please call the test function",
            None,
            context,
            agent_id=agent_id,
        )

    system = mock_create_stream.mock_calls[1][2]["system"]
    assert isinstance(system, list)
    system_text = " ".join(block["text"] for block in system if "text" in block)
    assert "You are a voice assistant for Home Assistant." in system_text

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert (
        result.response.speech["plain"]["speech"]
        == "I have successfully called the function"
    )
    assert mock_create_stream.mock_calls[1][2]["messages"][2] == {
        "role": "user",
        "content": [
            {
                "content": '"Test response"',
                "tool_use_id": "toolu_0123456789AbCdEfGhIjKlM",
                "type": "tool_result",
            }
        ],
    }
    mock_tool.async_call.assert_awaited_once_with(
        hass,
        llm.ToolInput(
            id="toolu_0123456789AbCdEfGhIjKlM",
            tool_name="test_tool",
            tool_args=expected_call_tool_args,
        ),
        llm.LLMContext(
            platform="anthropic",
            context=context,
            language="en",
            assistant="conversation",
            device_id=None,
        ),
    )


@patch("homeassistant.components.anthropic.entity.llm.AssistAPI._async_get_tools")
async def test_function_exception(
    mock_get_tools,
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
) -> None:
    """Test function call with exception."""
    agent_id = "conversation.claude_conversation"
    context = Context()

    mock_tool = AsyncMock()
    mock_tool.name = "test_tool"
    mock_tool.description = "Test function"
    mock_tool.parameters = vol.Schema(
        {vol.Optional("param1", description="Test parameters"): str}
    )
    mock_tool.async_call.side_effect = HomeAssistantError("Test tool exception")

    mock_get_tools.return_value = [mock_tool]

    mock_create_stream.return_value = [
        (
            *create_content_block(0, ["Certainly, calling it now!"]),
            *create_tool_use_block(
                1,
                "toolu_0123456789AbCdEfGhIjKlM",
                "test_tool",
                ['{"param1": "test_value"}'],
            ),
        ),
        create_content_block(0, ["There was an error calling the function"]),
    ]

    result = await conversation.async_converse(
        hass,
        "Please call the test function",
        None,
        context,
        agent_id=agent_id,
    )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert (
        result.response.speech["plain"]["speech"]
        == "There was an error calling the function"
    )
    assert mock_create_stream.mock_calls[1][2]["messages"][2] == {
        "role": "user",
        "content": [
            {
                "content": '{"error":"HomeAssistantError","error_text":"Test tool exception"}',
                "tool_use_id": "toolu_0123456789AbCdEfGhIjKlM",
                "type": "tool_result",
            }
        ],
    }
    mock_tool.async_call.assert_awaited_once_with(
        hass,
        llm.ToolInput(
            id="toolu_0123456789AbCdEfGhIjKlM",
            tool_name="test_tool",
            tool_args={"param1": "test_value"},
        ),
        llm.LLMContext(
            platform="anthropic",
            context=context,
            language="en",
            assistant="conversation",
            device_id=None,
        ),
    )


async def test_assist_api_tools_conversion(
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
) -> None:
    """Test that we are able to convert actual tools from Assist API."""
    for component in (
        "intent",
        "todo",
        "light",
        "shopping_list",
        "humidifier",
        "climate",
        "media_player",
        "vacuum",
        "cover",
        "weather",
    ):
        assert await async_setup_component(hass, component, {})

    agent_id = "conversation.claude_conversation"

    mock_create_stream.return_value = [
        create_content_block(0, ["Hello, how can I help you?"])
    ]

    await conversation.async_converse(hass, "hello", None, Context(), agent_id=agent_id)

    tools = mock_create_stream.mock_calls[0][2]["tools"]
    assert tools


async def test_unknown_hass_api(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    mock_init_component,
) -> None:
    """Test when we reference an API that no longer exists."""
    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={
            **subentry.data,
            CONF_LLM_HASS_API: "non-existing",
        },
    )
    await hass.async_block_till_done()

    result = await conversation.async_converse(
        hass, "hello", "1234", Context(), agent_id="conversation.claude_conversation"
    )

    assert result == snapshot


async def test_conversation_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
) -> None:
    """Test conversation ID is honored."""

    mock_create_stream.return_value = [
        create_content_block(0, ["Hello, how can I help you?"])
    ] * 5

    result = await conversation.async_converse(
        hass,
        "hello",
        "1234",
        Context(),
        agent_id="conversation.claude_conversation",
    )

    result = await conversation.async_converse(
        hass, "hello", None, None, agent_id="conversation.claude_conversation"
    )

    conversation_id = result.conversation_id

    result = await conversation.async_converse(
        hass,
        "hello",
        conversation_id,
        None,
        agent_id="conversation.claude_conversation",
    )

    assert result.conversation_id == conversation_id

    unknown_id = ulid_util.ulid()

    result = await conversation.async_converse(
        hass, "hello", unknown_id, None, agent_id="conversation.claude_conversation"
    )

    assert result.conversation_id != unknown_id

    result = await conversation.async_converse(
        hass, "hello", "koala", None, agent_id="conversation.claude_conversation"
    )

    assert result.conversation_id == "koala"


async def test_refusal(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
) -> None:
    """Test refusal due to potential policy violation."""
    mock_create_stream.return_value = [
        create_content_block(
            0, ["Certainly! To take over the world you need just a simple "]
        )
    ]

    result = await conversation.async_converse(
        hass,
        "ANTHROPIC_MAGIC_STRING_TRIGGER_REFUSAL_1FAEFB6177B4672DEE07F9D3AFC62588CCD2631"
        "EDCF22E8CCC1FB35B501C9C86",
        None,
        Context(),
        agent_id="conversation.claude_conversation",
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == "unknown"
    assert (
        result.response.speech["plain"]["speech"]
        == "Potential policy violation detected"
    )


async def test_extended_thinking(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test extended thinking support."""
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        next(iter(mock_config_entry.subentries.values())),
        data={
            CONF_LLM_HASS_API: llm.LLM_API_ASSIST,
            CONF_CHAT_MODEL: "claude-3-7-sonnet-latest",
            CONF_THINKING_BUDGET: 1500,
        },
    )

    mock_create_stream.return_value = [
        (
            *create_thinking_block(
                0,
                [
                    "The user has just",
                    ' greeted me with "Hi".',
                    " This is a simple greeting an",
                    "d doesn't require any Home Assistant function",
                    " calls. I should respond with",
                    " a friendly greeting and let them know I'm available",
                    " to help with their smart home.",
                ],
            ),
            *create_content_block(1, ["Hello, how can I help you today?"]),
        )
    ]

    result = await conversation.async_converse(
        hass, "hello", None, Context(), agent_id="conversation.claude_conversation"
    )

    chat_log = hass.data.get(conversation.chat_log.DATA_CHAT_LOGS).get(
        result.conversation_id
    )
    assert len(chat_log.content) == 3
    assert chat_log.content[1].content == "hello"
    assert chat_log.content[2].content == "Hello, how can I help you today?"
    call_args = mock_create_stream.call_args.kwargs.copy()
    call_args.pop("tools", None)
    assert call_args == snapshot


@freeze_time("2024-05-24 12:00:00")
async def test_disabled_thinking(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test conversation with thinking effort disabled."""
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        next(iter(mock_config_entry.subentries.values())),
        data={
            CONF_LLM_HASS_API: "assist",
            CONF_CHAT_MODEL: "claude-opus-4-6",
            CONF_THINKING_EFFORT: "none",
        },
    )

    mock_create_stream.return_value = [
        create_content_block(1, ["Hello, how can I help you today?"])
    ]

    result = await conversation.async_converse(
        hass, "hello", None, Context(), agent_id="conversation.claude_conversation"
    )

    chat_log = hass.data.get(conversation.chat_log.DATA_CHAT_LOGS).get(
        result.conversation_id
    )
    assert len(chat_log.content) == 3
    assert chat_log.content == snapshot
    call_args = mock_create_stream.call_args.kwargs.copy()
    call_args.pop("tools", None)
    assert call_args == snapshot


@freeze_time("2024-05-24 12:00:00")
async def test_redacted_thinking(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test extended thinking with redacted thinking blocks."""
    mock_create_stream.return_value = [
        (
            *create_redacted_thinking_block(0),
            *create_redacted_thinking_block(1),
            *create_redacted_thinking_block(2),
            *create_content_block(3, ["How can I help you today?"]),
        )
    ]

    result = await conversation.async_converse(
        hass,
        "ANTHROPIC_MAGIC_STRING_TRIGGER_REDACTED_THINKING_46C9A13E193C177646C7398A98432"
        "ECCCE4C1253D5E2D82641AC0E52CC2876CB",
        None,
        Context(),
        agent_id="conversation.claude_conversation",
    )

    chat_log = hass.data.get(conversation.chat_log.DATA_CHAT_LOGS).get(
        result.conversation_id
    )
    # Don't test the prompt because it's not deterministic
    assert chat_log.content[1:] == snapshot


@patch("homeassistant.components.anthropic.entity.llm.AssistAPI._async_get_tools")
async def test_extended_thinking_tool_call(
    mock_get_tools,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that thinking blocks and their order are preserved in with tool calls."""
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        next(iter(mock_config_entry.subentries.values())),
        data={
            CONF_LLM_HASS_API: llm.LLM_API_ASSIST,
            CONF_CHAT_MODEL: "claude-opus-4-6",
            CONF_THINKING_EFFORT: "medium",
        },
    )

    agent_id = "conversation.claude_conversation"
    context = Context()

    mock_tool = AsyncMock()
    mock_tool.name = "test_tool"
    mock_tool.description = "Test function"
    mock_tool.parameters = vol.Schema(
        {vol.Optional("param1", description="Test parameters"): str}
    )
    mock_tool.async_call.return_value = "Test response"

    mock_get_tools.return_value = [mock_tool]

    mock_create_stream.return_value = [
        (
            *create_thinking_block(
                0,
                [
                    "The user asked me to",
                    " call a test function.",
                    "Is it a test? What",
                    " would the function",
                    " do? Would it violate",
                    " any privacy or security",
                    " policies?",
                ],
            ),
            *create_redacted_thinking_block(1),
            *create_thinking_block(
                2, ["Okay, let's give it a shot.", " Will I pass the test?"]
            ),
            *create_content_block(3, ["Certainly, calling it now!"]),
            *create_tool_use_block(
                1,
                "toolu_0123456789AbCdEfGhIjKlM",
                "test_tool",
                ['{"para', 'm1": "test_valu', 'e"}'],
            ),
        ),
        create_content_block(0, ["I have ", "successfully called ", "the function"]),
    ]

    with freeze_time("2024-06-03 23:00:00"):
        result = await conversation.async_converse(
            hass,
            "Please call the test function",
            None,
            context,
            agent_id=agent_id,
        )

    chat_log = hass.data.get(conversation.chat_log.DATA_CHAT_LOGS).get(
        result.conversation_id
    )

    assert chat_log.content == snapshot
    assert mock_create_stream.mock_calls[1][2]["messages"] == snapshot


@freeze_time("2025-10-31 12:00:00")
async def test_web_search(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test web search."""
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        next(iter(mock_config_entry.subentries.values())),
        data={
            CONF_LLM_HASS_API: llm.LLM_API_ASSIST,
            CONF_CHAT_MODEL: "claude-sonnet-4-5",
            CONF_WEB_SEARCH: True,
            CONF_WEB_SEARCH_MAX_USES: 5,
            CONF_WEB_SEARCH_USER_LOCATION: True,
            CONF_WEB_SEARCH_CITY: "San Francisco",
            CONF_WEB_SEARCH_REGION: "California",
            CONF_WEB_SEARCH_COUNTRY: "US",
            CONF_WEB_SEARCH_TIMEZONE: "America/Los_Angeles",
        },
    )

    web_search_results = [
        WebSearchResultBlock(
            type="web_search_result",
            title="Today's News - Example.com",
            url="https://www.example.com/todays-news",
            page_age="2 days ago",
            encrypted_content="ABCDEFG",
        ),
        WebSearchResultBlock(
            type="web_search_result",
            title="Breaking News - NewsSite.com",
            url="https://www.newssite.com/breaking-news",
            page_age=None,
            encrypted_content="ABCDEFG",
        ),
    ]
    mock_create_stream.return_value = [
        (
            *create_thinking_block(
                0,
                [
                    "The user is",
                    " asking about today's news, which",
                    " requires current, real-time information",
                    ". This is clearly something that requires recent",
                    " information beyond my knowledge cutoff.",
                    " I should use the web",
                    "_search tool to fin",
                    "d today's news.",
                ],
            ),
            *create_content_block(
                1, ["To get today's news, I'll perform a web search"]
            ),
            *create_web_search_block(
                2,
                "srvtoolu_12345ABC",
                ["", '{"que', 'ry"', ": \"today's", ' news"}'],
            ),
            *create_web_search_result_block(3, "srvtoolu_12345ABC", web_search_results),
            *create_content_block(
                4,
                ["Here's what I found on the web about today's news:\n", "1. "],
            ),
            *create_content_block(
                5,
                ["New Home Assistant release"],
                citations=[
                    CitationsWebSearchResultLocation(
                        type="web_search_result_location",
                        cited_text="This release iterates on some of the features we introduced in the last couple of releases, but also...",
                        encrypted_index="AAA==",
                        title="Home Assistant Release",
                        url="https://www.example.com/todays-news",
                    )
                ],
            ),
            *create_content_block(6, ["\n2. "]),
            *create_content_block(
                7,
                ["Something incredible happened"],
                citations=[
                    CitationsWebSearchResultLocation(
                        type="web_search_result_location",
                        cited_text="Breaking news from around the world today includes major events in technology, politics, and culture...",
                        encrypted_index="AQE=",
                        title="Breaking News",
                        url="https://www.newssite.com/breaking-news",
                    ),
                    CitationsWebSearchResultLocation(
                        type="web_search_result_location",
                        cited_text="Well, this happened...",
                        encrypted_index="AgI=",
                        title="Breaking News",
                        url="https://www.newssite.com/breaking-news",
                    ),
                ],
            ),
            *create_content_block(
                8, ["\nThose are the main headlines making news today."]
            ),
        )
    ]

    result = await conversation.async_converse(
        hass,
        "What's on the news today?",
        None,
        Context(),
        agent_id="conversation.claude_conversation",
    )

    chat_log = hass.data.get(conversation.chat_log.DATA_CHAT_LOGS).get(
        result.conversation_id
    )
    # Don't test the prompt because it's not deterministic
    assert chat_log.content[1:] == snapshot


@pytest.mark.parametrize(
    "content",
    [
        [
            conversation.chat_log.SystemContent("You are a helpful assistant."),
        ],
        [
            conversation.chat_log.SystemContent("You are a helpful assistant."),
            conversation.chat_log.UserContent("What shape is a donut?"),
            conversation.chat_log.AssistantContent(
                agent_id="conversation.claude_conversation",
                content="A donut is a torus.",
            ),
        ],
        [
            conversation.chat_log.SystemContent("You are a helpful assistant."),
            conversation.chat_log.UserContent("What shape is a donut?"),
            conversation.chat_log.UserContent("Can you tell me?"),
            conversation.chat_log.AssistantContent(
                agent_id="conversation.claude_conversation",
                content="A donut is a torus.",
            ),
            conversation.chat_log.AssistantContent(
                agent_id="conversation.claude_conversation", content="Hope this helps."
            ),
        ],
        [
            conversation.chat_log.SystemContent("You are a helpful assistant."),
            conversation.chat_log.UserContent("What shape is a donut?"),
            conversation.chat_log.UserContent("Can you tell me?"),
            conversation.chat_log.UserContent("Please?"),
            conversation.chat_log.AssistantContent(
                agent_id="conversation.claude_conversation",
                content="A donut is a torus.",
            ),
            conversation.chat_log.AssistantContent(
                agent_id="conversation.claude_conversation", content="Hope this helps."
            ),
            conversation.chat_log.AssistantContent(
                agent_id="conversation.claude_conversation", content="You are welcome."
            ),
        ],
        [
            conversation.chat_log.SystemContent("You are a helpful assistant."),
            conversation.chat_log.UserContent("Turn off the lights and make me coffee"),
            conversation.chat_log.AssistantContent(
                agent_id="conversation.claude_conversation",
                content="Sure.",
                tool_calls=[
                    llm.ToolInput(
                        id="mock-tool-call-id",
                        tool_name="HassTurnOff",
                        tool_args={"domain": "light"},
                    ),
                    llm.ToolInput(
                        id="mock-tool-call-id-2",
                        tool_name="MakeCoffee",
                        tool_args={},
                    ),
                ],
            ),
            conversation.chat_log.UserContent("Thank you"),
            conversation.chat_log.ToolResultContent(
                agent_id="conversation.claude_conversation",
                tool_call_id="mock-tool-call-id",
                tool_name="HassTurnOff",
                tool_result={"success": True, "response": "Lights are off."},
            ),
            conversation.chat_log.ToolResultContent(
                agent_id="conversation.claude_conversation",
                tool_call_id="mock-tool-call-id-2",
                tool_name="MakeCoffee",
                tool_result={"success": False, "response": "Not enough milk."},
            ),
            conversation.chat_log.AssistantContent(
                agent_id="conversation.claude_conversation",
                content="Should I add milk to the shopping list?",
            ),
        ],
        [
            conversation.chat_log.SystemContent("You are a helpful assistant."),
            conversation.chat_log.UserContent("What's on the news today?"),
            conversation.chat_log.AssistantContent(
                agent_id="conversation.claude_conversation",
                content="To get today's news, I'll perform a web search",
                thinking_content="The user is asking about today's news, which requires current, real-time information. This is clearly something that requires recent information beyond my knowledge cutoff. I should use the web_search tool to find today's news.",
                native=ThinkingBlock(
                    signature="ErU/V+ayA==", thinking="", type="thinking"
                ),
                tool_calls=[
                    llm.ToolInput(
                        id="srvtoolu_12345ABC",
                        tool_name="web_search",
                        tool_args={"query": "today's news"},
                        external=True,
                    ),
                ],
            ),
            conversation.chat_log.ToolResultContent(
                agent_id="conversation.claude_conversation",
                tool_call_id="srvtoolu_12345ABC",
                tool_name="web_search",
                tool_result={
                    "content": [
                        {
                            "type": "web_search_result",
                            "title": "Today's News - Example.com",
                            "url": "https://www.example.com/todays-news",
                            "page_age": "2 days ago",
                            "encrypted_content": "ABCDEFG",
                        },
                        {
                            "type": "web_search_result",
                            "title": "Breaking News - NewsSite.com",
                            "url": "https://www.newssite.com/breaking-news",
                            "page_age": None,
                            "encrypted_content": "ABCDEFG",
                        },
                    ]
                },
            ),
            conversation.chat_log.AssistantContent(
                agent_id="conversation.claude_conversation",
                content="Here's what I found on the web about today's news:\n"
                "1. New Home Assistant release\n"
                "2. Something incredible happened\n"
                "Those are the main headlines making news today.",
                native=ContentDetails(
                    citation_details=[
                        CitationDetails(
                            index=54,
                            length=26,
                            citations=[
                                CitationWebSearchResultLocationParam(
                                    type="web_search_result_location",
                                    cited_text="This release iterates on some of the features we introduced in the last couple of releases, but also...",
                                    encrypted_index="AAA==",
                                    title="Home Assistant Release",
                                    url="https://www.example.com/todays-news",
                                ),
                            ],
                        ),
                        CitationDetails(
                            index=84,
                            length=29,
                            citations=[
                                CitationWebSearchResultLocationParam(
                                    type="web_search_result_location",
                                    cited_text="Breaking news from around the world today includes major events in technology, politics, and culture...",
                                    encrypted_index="AQE=",
                                    title="Breaking News",
                                    url="https://www.newssite.com/breaking-news",
                                ),
                                CitationWebSearchResultLocationParam(
                                    type="web_search_result_location",
                                    cited_text="Well, this happened...",
                                    encrypted_index="AgI=",
                                    title="Breaking News",
                                    url="https://www.newssite.com/breaking-news",
                                ),
                            ],
                        ),
                    ],
                ),
            ),
        ],
        [
            conversation.chat_log.SystemContent("You are a helpful assistant."),
            conversation.chat_log.UserContent("What time is it?"),
            conversation.chat_log.AssistantContent(
                agent_id="conversation.claude_conversation",
                content="Let me check the time for you.",
                tool_calls=[
                    llm.ToolInput(
                        id="mock-tool-call-id",
                        tool_name="GetCurrentTime",
                        tool_args={},
                    ),
                ],
            ),
            conversation.chat_log.ToolResultContent(
                agent_id="conversation.claude_conversation",
                tool_call_id="mock-tool-call-id",
                tool_name="GetCurrentTime",
                tool_result={
                    "speech_slots": {"time": datetime.time(14, 30, 0)},
                    "message": "Current time retrieved",
                },
            ),
            conversation.chat_log.AssistantContent(
                agent_id="conversation.claude_conversation",
                content="It is currently 2:30 PM.",
            ),
        ],
    ],
)
async def test_history_conversion(
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
    snapshot: SnapshotAssertion,
    content: list[conversation.chat_log.Content],
) -> None:
    """Test conversion of chat_log entries into API parameters."""
    conversation_id = "conversation_id"
    mock_create_stream.return_value = [create_content_block(0, ["Yes, I am sure!"])]
    with (
        chat_session.async_get_chat_session(hass, conversation_id) as session,
        conversation.async_get_chat_log(hass, session) as chat_log,
    ):
        chat_log.content = content

        await conversation.async_converse(
            hass,
            "Are you sure?",
            conversation_id,
            Context(),
            agent_id="conversation.claude_conversation",
        )

        assert mock_create_stream.mock_calls[0][2]["messages"] == snapshot
