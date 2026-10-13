"""Tests for the Google Generative AI Conversation integration conversation platform."""

import datetime
from unittest.mock import AsyncMock, patch

from freezegun import freeze_time
from google.genai import Client
from google.genai.types import (
    GenerateContentConfig,
    GenerateContentResponse,
    ThinkingConfig,
    ThinkingLevel,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import conversation
from homeassistant.components.conversation import (
    AssistantContent,
    ToolResultContent,
    UserContent,
    trace,
)
from homeassistant.components.google_generative_ai_conversation.const import (
    CONF_CHAT_MODEL,
    CONF_TEMPERATURE,
    CONF_THINKING_BUDGET,
    CONF_THINKING_LEVEL,
    CONF_TOP_K,
    CONF_TOP_P,
)
from homeassistant.components.google_generative_ai_conversation.entity import (
    ERROR_GETTING_RESPONSE,
    GoogleGenerativeAILLMBaseEntity,
    _create_thinking_config,
    _escape_decode,
    _format_schema,
)
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent, llm
from homeassistant.helpers.llm import ToolInput

from . import API_ERROR_500, CLIENT_ERROR_BAD_REQUEST

from tests.common import MockConfigEntry
from tests.components.conversation import (
    MockChatLog,
    mock_chat_log,  # noqa: F401
)


@pytest.fixture(autouse=True)
def freeze_the_time():
    """Freeze the time."""
    with freeze_time("2024-05-24 12:00:00", tz_offset=0):
        yield


@pytest.fixture(autouse=True)
def mock_ulid_tools():
    """Mock generated ULIDs for tool calls."""
    with patch("homeassistant.helpers.llm.ulid_now", return_value="mock-tool-call"):
        yield


@pytest.mark.parametrize(
    ("error"),
    [
        (API_ERROR_500,),
        (CLIENT_ERROR_BAD_REQUEST,),
    ],
)
async def test_error_handling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    error,
) -> None:
    """Test that client errors are caught."""
    with patch(
        "google.genai.chats.AsyncChat.send_message_stream",
        new_callable=AsyncMock,
        side_effect=error,
    ):
        result = await conversation.async_converse(
            hass,
            "hello",
            None,
            Context(),
            agent_id="conversation.google_ai_conversation",
        )
    assert result.response.response_type is intent.IntentResponseType.ERROR, result
    assert result.response.error_code == "unknown", result
    assert (
        result.response.as_dict()["speech"]["plain"]["speech"] == ERROR_GETTING_RESPONSE
    )


@pytest.mark.usefixtures("mock_init_component")
@pytest.mark.usefixtures("mock_ulid_tools")
async def test_function_call(
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_chat_log: MockChatLog,  # noqa: F811
    mock_send_message_stream: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test function calling."""
    agent_id = "conversation.google_ai_conversation"
    context = Context()

    # Add some pre-existing content from conversation.default_agent
    mock_chat_log.async_add_user_content(UserContent(content="What time is it?"))
    mock_chat_log.async_add_assistant_content_without_tools(
        AssistantContent(
            agent_id=agent_id,
            tool_calls=[
                ToolInput(
                    tool_name="HassGetCurrentTime",
                    tool_args={},
                    id="01KGW7TFC1VVVK7ANHVMDA4DJ6",
                    external=True,
                )
            ],
        )
    )
    mock_chat_log.async_add_assistant_content_without_tools(
        ToolResultContent(
            agent_id=agent_id,
            tool_call_id="01KGW7TFC1VVVK7ANHVMDA4DJ6",
            tool_name="HassGetCurrentTime",
            result=llm.ToolResult(
                data={
                    "speech": {"plain": {"speech": "4:24 PM", "extra_data": None}},
                    "response_type": "action_done",
                    "speech_slots": {"time": datetime.time(16, 24, 17, 813343)},
                    "data": {"success": [], "failed": []},
                }
            ),
        )
    )
    mock_chat_log.async_add_assistant_content_without_tools(
        AssistantContent(
            agent_id=agent_id,
            content="4:24 PM",
        )
    )

    messages = [
        # Function call stream
        [
            GenerateContentResponse(
                candidates=[
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": "The user asked me to call a function",
                                    "thought": True,
                                    "thought_signature": b"_thought_signature_1",
                                },
                                {
                                    "text": "Hi there!",
                                    "thought_signature": b"_thought_signature_2",
                                },
                            ],
                            "role": "model",
                        }
                    }
                ]
            ),
            GenerateContentResponse(
                candidates=[
                    {
                        "content": {
                            "parts": [
                                {
                                    "function_call": {
                                        "name": "test_tool",
                                        "args": {
                                            "param1": [
                                                "test_value",
                                                "param1\\'s value",
                                            ],
                                            "param2": 2.7,
                                        },
                                    },
                                    "thought_signature": b"_thought_signature_3",
                                }
                            ],
                            "role": "model",
                        },
                        "finish_reason": "STOP",
                    }
                ]
            ),
        ],
        # Messages after function response is sent
        [
            GenerateContentResponse(
                candidates=[
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": "I've called the ",
                                    "thought_signature": b"_thought_signature_4",
                                }
                            ],
                            "role": "model",
                        },
                    }
                ],
            ),
            GenerateContentResponse(
                candidates=[
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": "test function with the"
                                    " provided parameters.",
                                    "thought_signature": b"_thought_signature_5",
                                }
                            ],
                            "role": "model",
                        },
                        "finish_reason": "STOP",
                    }
                ],
            ),
        ],
        # Follow-up response
        [
            GenerateContentResponse(
                candidates=[
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": "You are welcome!",
                                }
                            ],
                            "role": "model",
                        },
                        "finish_reason": "STOP",
                    }
                ],
            ),
        ],
    ]

    mock_send_message_stream.return_value = messages

    mock_chat_log.mock_tool_results(
        {
            "mock-tool-call": {"result": "Test response"},
        }
    )

    result = await conversation.async_converse(
        hass,
        "Please call the test function",
        mock_chat_log.conversation_id,
        context,
        agent_id=agent_id,
        device_id="test_device",
    )
    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert (
        result.response.as_dict()["speech"]["plain"]["speech"]
        == "I've called the test function with the provided parameters."
    )
    mock_tool_response_parts = mock_send_message_stream.mock_calls[1][2]["message"]
    assert len(mock_tool_response_parts) == 1
    assert mock_tool_response_parts[0].model_dump() == {
        "code_execution_result": None,
        "executable_code": None,
        "file_data": None,
        "function_call": None,
        "function_response": {
            "id": None,
            "name": "test_tool",
            "parts": None,
            "response": {
                "data": {"result": "Test response"},
                "error": False,
            },
            "scheduling": None,
            "will_continue": None,
        },
        "inline_data": None,
        "media_processing": None,
        "media_resolution": None,
        "part_metadata": None,
        "speech_metadata": None,
        "text": None,
        "thought": None,
        "thought_signature": None,
        "tool_call": None,
        "tool_response": None,
        "video_metadata": None,
        "audio_transcription": None,
    }

    # Test history conversion for multi-turn conversation
    with patch(
        "google.genai.chats.AsyncChats.create", return_value=AsyncMock()
    ) as mock_create:
        mock_create.return_value.send_message_stream = mock_send_message_stream
        await conversation.async_converse(
            hass,
            "Thank you!",
            mock_chat_log.conversation_id,
            context,
            agent_id=agent_id,
            device_id="test_device",
        )

    assert mock_create.call_args[1].get("history") == snapshot


@pytest.mark.usefixtures("mock_init_component")
@pytest.mark.usefixtures("mock_ulid_tools")
async def test_google_search_tool_is_sent(
    hass: HomeAssistant,
    mock_config_entry_with_google_search: MockConfigEntry,
    mock_chat_log: MockChatLog,  # noqa: F811
    mock_send_message_stream: AsyncMock,
) -> None:
    """Test if the Google Search tool is sent to the model."""
    agent_id = "conversation.google_ai_conversation"
    context = Context()

    messages = [
        # Messages from the model which contain the google search
        # answer (the usage of the Google Search tool is server side)
        [
            GenerateContentResponse(
                candidates=[
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": "The last winner ",
                                }
                            ],
                            "role": "model",
                        },
                    }
                ],
            ),
            GenerateContentResponse(
                candidates=[
                    {
                        "content": {
                            "parts": [
                                {"text": "of the 2024 FIFA World Cup was Argentina."}
                            ],
                            "role": "model",
                        },
                        "finish_reason": "STOP",
                    }
                ],
            ),
        ],
    ]

    mock_send_message_stream.return_value = messages

    with patch(
        "google.genai.chats.AsyncChats.create", return_value=AsyncMock()
    ) as mock_create:
        mock_create.return_value.send_message_stream = mock_send_message_stream
        result = await conversation.async_converse(
            hass,
            "Who won the 2024 FIFA World Cup?",
            mock_chat_log.conversation_id,
            context,
            agent_id=agent_id,
            device_id="test_device",
        )
    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert (
        result.response.as_dict()["speech"]["plain"]["speech"]
        == "The last winner of the 2024 FIFA World Cup was Argentina."
    )
    assert mock_create.mock_calls[0][2]["config"].tools[-1].google_search is not None


@pytest.mark.usefixtures("mock_init_component")
async def test_blocked_response(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_chat_log: MockChatLog,  # noqa: F811
    mock_send_message_stream: AsyncMock,
) -> None:
    """Test blocked response."""
    agent_id = "conversation.google_ai_conversation"
    context = Context()

    messages = [
        [
            GenerateContentResponse(
                candidates=[
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": "I've called the ",
                                }
                            ],
                            "role": "model",
                        },
                    }
                ],
            ),
            GenerateContentResponse(prompt_feedback={"block_reason_message": "SAFETY"}),
        ],
    ]

    mock_send_message_stream.return_value = messages

    result = await conversation.async_converse(
        hass,
        "Please call the test function",
        mock_chat_log.conversation_id,
        context,
        agent_id=agent_id,
        device_id="test_device",
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR, result
    assert result.response.error_code == "unknown", result
    assert result.response.as_dict()["speech"]["plain"]["speech"] == (
        "The message got blocked due to content violations, reason: SAFETY"
    )


@pytest.mark.usefixtures("mock_init_component")
async def test_empty_response(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_chat_log: MockChatLog,  # noqa: F811
    mock_send_message_stream: AsyncMock,
) -> None:
    """Test empty response."""

    agent_id = "conversation.google_ai_conversation"
    context = Context()

    messages = [
        [
            GenerateContentResponse(
                candidates=[
                    {
                        "content": {
                            "parts": [],
                            "role": "model",
                        },
                    }
                ],
            ),
        ],
    ]

    mock_send_message_stream.return_value = messages

    result = await conversation.async_converse(
        hass,
        "Hello",
        mock_chat_log.conversation_id,
        context,
        agent_id=agent_id,
        device_id="test_device",
    )
    assert result.response.response_type is intent.IntentResponseType.ERROR, result
    assert result.response.error_code == "unknown", result
    assert result.response.as_dict()["speech"]["plain"]["speech"] == (
        "Unable to get response"
    )


@pytest.mark.usefixtures("mock_init_component")
async def test_none_response(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_chat_log: MockChatLog,  # noqa: F811
    mock_send_message_stream: AsyncMock,
) -> None:
    """Test None response."""
    agent_id = "conversation.google_ai_conversation"
    context = Context()

    messages = [
        [
            GenerateContentResponse(),
        ],
    ]

    mock_send_message_stream.return_value = messages

    result = await conversation.async_converse(
        hass,
        "Hello",
        mock_chat_log.conversation_id,
        context,
        agent_id=agent_id,
        device_id="test_device",
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR, result
    assert result.response.error_code == "unknown", result
    assert result.response.as_dict()["speech"]["plain"]["speech"] == (
        "The message got blocked due to content violations, reason: unknown"
    )


@pytest.mark.usefixtures("mock_init_component")
async def test_converse_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test handling ChatLog raising ConverseError."""
    subentry = next(iter(mock_config_entry.subentries.values()))
    with patch("google.genai.models.AsyncModels.get"):
        hass.config_entries.async_update_subentry(
            mock_config_entry,
            next(iter(mock_config_entry.subentries.values())),
            data={**subentry.data, CONF_LLM_HASS_API: "invalid_llm_api"},
        )
        await hass.async_block_till_done()

    result = await conversation.async_converse(
        hass,
        "hello",
        None,
        Context(),
        agent_id="conversation.google_ai_conversation",
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR, result
    assert result.response.error_code == "unknown", result
    assert result.response.as_dict()["speech"]["plain"]["speech"] == (
        "Error preparing LLM API"
    )


@pytest.mark.usefixtures("mock_init_component")
async def test_conversation_agent(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test GoogleGenerativeAIAgent."""
    agent = conversation.get_agent_manager(hass).async_get_agent(
        mock_config_entry.entry_id
    )
    assert agent.supported_languages == "*"


async def test_escape_decode() -> None:
    """Test _escape_decode."""
    assert _escape_decode(
        {
            "param1": ["test_value", "param1\\'s value"],
            "param2": "param2\\'s value",
            "param3": {"param31": "Cheminée", "param32": "Chemin\\303\\251e"},
        }
    ) == {
        "param1": ["test_value", "param1's value"],
        "param2": "param2's value",
        "param3": {"param31": "Cheminée", "param32": "Cheminée"},
    }


@pytest.mark.parametrize(
    ("openapi", "genai_schema"),
    [
        (
            {"type": "string", "enum": ["a", "b", "c"]},
            {"type": "STRING", "enum": ["a", "b", "c"]},
        ),
        (
            {"type": "string", "default": "default"},
            {"type": "STRING"},
        ),
        (
            {"type": "string", "pattern": "default"},
            {"type": "STRING"},
        ),
        (
            {"type": "string", "maxLength": 10},
            {"type": "STRING"},
        ),
        (
            {"type": "string", "minLength": 10},
            {"type": "STRING"},
        ),
        (
            {"type": "string", "title": "title"},
            {"type": "STRING"},
        ),
        (
            {"type": "string", "format": "enum", "enum": ["a", "b", "c"]},
            {"type": "STRING", "format": "enum", "enum": ["a", "b", "c"]},
        ),
        (
            {"type": "string", "format": "date-time"},
            {"type": "STRING", "format": "date-time"},
        ),
        (
            {"type": "string", "format": "byte"},
            {"type": "STRING"},
        ),
        (
            {"type": "number", "format": "float"},
            {"type": "NUMBER", "format": "float"},
        ),
        (
            {"type": "number", "format": "double"},
            {"type": "NUMBER", "format": "double"},
        ),
        (
            {"type": "number", "format": "hex"},
            {"type": "NUMBER"},
        ),
        (
            {"type": "number", "minimum": 1},
            {"type": "NUMBER"},
        ),
        (
            {"type": "integer", "format": "int32"},
            {"type": "INTEGER", "format": "int32"},
        ),
        (
            {"type": "integer", "format": "int64"},
            {"type": "INTEGER", "format": "int64"},
        ),
        (
            {"type": "integer", "format": "int8"},
            {"type": "INTEGER"},
        ),
        (
            {"type": "integer", "enum": [1, 2, 3]},
            {"type": "STRING", "enum": ["1", "2", "3"]},
        ),
        (
            {"anyOf": [{"type": "integer"}, {"type": "number"}]},
            {},
        ),
        ({"type": "string", "format": "lower"}, {"type": "STRING"}),
        ({"type": "boolean", "format": "bool"}, {"type": "BOOLEAN"}),
        (
            {"type": "number", "format": "percent"},
            {"type": "NUMBER"},
        ),
        (
            {
                "type": "object",
                "properties": {"var": {"type": "string"}},
                "required": [],
            },
            {
                "type": "OBJECT",
                "properties": {"var": {"type": "STRING"}},
                "required": [],
            },
        ),
        (
            {"type": "object", "additionalProperties": True, "minProperties": 1},
            {
                "type": "OBJECT",
                "properties": {"json": {"type": "STRING"}},
                "required": [],
            },
        ),
        (
            {"type": "object", "additionalProperties": True, "maxProperties": 1},
            {
                "type": "OBJECT",
                "properties": {"json": {"type": "STRING"}},
                "required": [],
            },
        ),
        (
            {"type": "array", "items": {"type": "string"}},
            {"type": "ARRAY", "items": {"type": "STRING"}},
        ),
        (
            {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 2,
            },
            {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "min_items": 1,
                "max_items": 2,
            },
        ),
    ],
)
async def test_format_schema(openapi, genai_schema) -> None:
    """Test _format_schema."""
    assert _format_schema(openapi) == genai_schema


@pytest.mark.usefixtures("mock_init_component")
async def test_empty_content_in_chat_history(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_chat_log: MockChatLog,  # noqa: F811
    mock_send_message_stream: AsyncMock,
) -> None:
    """Test empty chat history entries get an injected space for the API."""
    agent_id = "conversation.google_ai_conversation"
    context = Context()

    messages = [
        [
            GenerateContentResponse(
                candidates=[
                    {
                        "content": {
                            "parts": [{"text": "Hi there!"}],
                            "role": "model",
                        },
                    }
                ],
            ),
        ],
    ]

    mock_send_message_stream.return_value = messages

    # Chat preparation with two inputs, one being an empty string
    first_input = "First request"
    second_input = ""
    mock_chat_log.async_add_user_content(UserContent(first_input))
    mock_chat_log.async_add_user_content(UserContent(second_input))

    with patch(
        "google.genai.chats.AsyncChats.create", return_value=AsyncMock()
    ) as mock_create:
        mock_create.return_value.send_message_stream = mock_send_message_stream
        await conversation.async_converse(
            hass,
            "Hello",
            mock_chat_log.conversation_id,
            context,
            agent_id=agent_id,
            device_id="test_device",
        )

    _, kwargs = mock_create.call_args
    actual_history = kwargs.get("history")

    assert actual_history[0].parts[0].text == first_input
    assert actual_history[1].parts[0].text == " "


@pytest.mark.usefixtures("mock_init_component")
async def test_history_always_user_first_turn(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_chat_log: MockChatLog,  # noqa: F811
    mock_send_message_stream: AsyncMock,
) -> None:
    """Test that the user is always first in the chat history."""

    agent_id = "conversation.google_ai_conversation"
    context = Context()

    messages = [
        [
            GenerateContentResponse(
                candidates=[
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": " Yes, I can help with that. ",
                                }
                            ],
                            "role": "model",
                        },
                    }
                ],
            ),
        ],
    ]

    mock_send_message_stream.return_value = messages

    mock_chat_log.async_add_assistant_content_without_tools(
        conversation.AssistantContent(
            agent_id="conversation.google_ai_conversation",
            content="Garage door left open, do you want to close it?",
        )
    )

    with patch(
        "google.genai.chats.AsyncChats.create", return_value=AsyncMock()
    ) as mock_create:
        mock_create.return_value.send_message_stream = mock_send_message_stream
        await conversation.async_converse(
            hass,
            "Hello",
            mock_chat_log.conversation_id,
            context,
            agent_id=agent_id,
            device_id="test_device",
        )

    _, kwargs = mock_create.call_args
    actual_history = kwargs.get("history")

    assert actual_history[0].parts[0].text == " "
    assert actual_history[0].role == "user"
    assert (
        actual_history[1].parts[0].text
        == "Garage door left open, do you want to close it?"
    )
    assert actual_history[1].role == "model"


# --- Tests for _create_thinking_config ---


@pytest.mark.parametrize(
    ("model", "thinking_budget", "thinking_level", "expected"),
    [
        # Non-thinking models return None
        ("models/gemini-1.5-flash", -1, None, None),
        ("gemini-2.0-flash", -1, None, None),
        # TTS/image models are excluded even if prefix matches
        ("models/gemini-2.5-flash-preview-tts", -1, None, None),
        ("models/gemini-2.5-pro-image", -1, None, None),
        ("models/gemini-3-flash-tts", -1, None, None),
    ],
)
def test_create_thinking_config_non_thinking_models(
    model: str,
    thinking_budget: int,
    thinking_level: str | None,
    expected: None,
) -> None:
    """Test that non-thinking models return None."""
    assert _create_thinking_config(model, thinking_budget, thinking_level) is expected


@pytest.mark.parametrize(
    ("model", "thinking_level"),
    [
        ("models/gemini-3-flash", "minimal"),
        ("models/gemini-3-flash", "low"),
        ("gemini-3-pro", "medium"),
        ("models/gemini-3-ultra", "high"),
    ],
)
def test_create_thinking_config_gemini3_levels(
    model: str,
    thinking_level: str,
) -> None:
    """Test Gemini 3 models with explicit thinking levels."""
    level_map = {
        "minimal": ThinkingLevel.MINIMAL,
        "low": ThinkingLevel.LOW,
        "medium": ThinkingLevel.MEDIUM,
        "high": ThinkingLevel.HIGH,
    }

    result = _create_thinking_config(model, -1, thinking_level)
    assert result is not None
    assert result.include_thoughts is True
    assert result.thinking_level == level_map[thinking_level]


@pytest.mark.parametrize(
    ("model", "thinking_level"),
    [
        ("models/gemini-3-flash", "auto"),
        ("models/gemini-3-flash", None),
        ("gemini-3-pro", "minimal"),
    ],
)
def test_create_thinking_config_gemini3_auto(
    model: str,
    thinking_level: str | None,
) -> None:
    """Test Gemini 3 with 'auto' or unset level defers to the API."""
    result = _create_thinking_config(model, -1, thinking_level)
    assert result is not None
    assert result.include_thoughts is True
    assert result.thinking_level is None


@pytest.mark.parametrize(
    ("model", "thinking_level", "expected"),
    [
        pytest.param(
            "models/gemma-4-26b-a4b-it",
            "minimal",
            ThinkingConfig(thinking_level=ThinkingLevel.MINIMAL),
            id="minimal",
        ),
        pytest.param(
            "gemma-4-31b-it",
            "high",
            ThinkingConfig(thinking_level=ThinkingLevel.HIGH),
            id="high",
        ),
        # The API rejects any other thinking level for Gemma 4
        pytest.param("models/gemma-4-31b-it", "low", None, id="low"),
        pytest.param("models/gemma-4-31b-it", "medium", None, id="medium"),
        pytest.param("models/gemma-4-31b-it", "auto", None, id="auto"),
        pytest.param("models/gemma-4-31b-it", None, None, id="unset"),
    ],
)
def test_create_thinking_config_gemma4(
    model: str,
    thinking_level: str | None,
    expected: ThinkingConfig | None,
) -> None:
    """Test Gemma 4 models only send the supported thinking levels."""
    assert _create_thinking_config(model, 0, thinking_level) == expected


@pytest.mark.parametrize(
    ("model", "thinking_budget", "expected_budget"),
    [
        # Pro: budget < 128 is clamped to 128
        ("models/gemini-2.5-pro", 0, 128),
        ("models/gemini-2.5-pro", 1, 128),
        ("models/gemini-2.5-pro", 127, 128),
        ("models/gemini-2.5-pro-preview-05-06", 50, 128),
        # Pro: budget >= 128 is passed through
        ("models/gemini-2.5-pro", 128, 128),
        ("models/gemini-2.5-pro", 1000, 1000),
        ("models/gemini-2.5-pro", 8192, 8192),
    ],
)
def test_create_thinking_config_gemini25_pro_clamping(
    model: str,
    thinking_budget: int,
    expected_budget: int,
) -> None:
    """Test Gemini 2.5 Pro clamps budgets below 128."""
    result = _create_thinking_config(model, thinking_budget)
    assert result is not None
    assert result.include_thoughts is True
    assert result.thinking_budget == expected_budget


def test_create_thinking_config_gemini25_pro_automatic() -> None:
    """Test Gemini 2.5 Pro with automatic budget (-1)."""
    result = _create_thinking_config("models/gemini-2.5-pro", -1)
    assert result is not None
    assert result.include_thoughts is True
    assert result.thinking_budget is None


@pytest.mark.parametrize(
    "model",
    [
        "models/gemini-2.5-flash",
        "gemini-2.5-flash-preview-04-17",
    ],
)
def test_create_thinking_config_gemini25_flash_disable(model: str) -> None:
    """Test Gemini 2.5 Flash with budget 0 disables thinking."""
    result = _create_thinking_config(model, 0)
    assert result is not None
    assert result.include_thoughts is False
    assert result.thinking_budget == 0


def test_create_thinking_config_gemini25_flash_automatic() -> None:
    """Test Gemini 2.5 Flash with automatic budget (-1)."""
    result = _create_thinking_config("models/gemini-2.5-flash", -1)
    assert result is not None
    assert result.include_thoughts is True
    assert result.thinking_budget is None


def test_create_thinking_config_gemini25_flash_custom() -> None:
    """Test Gemini 2.5 Flash with a custom budget passes through."""
    result = _create_thinking_config("models/gemini-2.5-flash", 2048)
    assert result is not None
    assert result.include_thoughts is True
    assert result.thinking_budget == 2048


@pytest.mark.usefixtures("mock_init_component")
async def test_token_stats_reported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_chat_log: MockChatLog,  # noqa: F811
    mock_send_message_stream: AsyncMock,
) -> None:
    """Test that token stats are reported to the chat log."""
    trace.async_clear_traces()

    agent_id = "conversation.google_ai_conversation"
    context = Context()

    messages = [
        [
            GenerateContentResponse(
                candidates=[
                    {
                        "content": {
                            "parts": [{"text": "Hello! "}],
                            "role": "model",
                        },
                    }
                ],
            ),
            GenerateContentResponse(
                candidates=[
                    {
                        "content": {
                            "parts": [{"text": "How can I help you?"}],
                            "role": "model",
                        },
                        "finish_reason": "STOP",
                    }
                ],
                usage_metadata={
                    "prompt_token_count": 10,
                    "candidates_token_count": 20,
                    "cached_content_token_count": 5,
                },
            ),
        ],
    ]

    mock_send_message_stream.return_value = messages

    await conversation.async_converse(
        hass,
        "Hello",
        mock_chat_log.conversation_id,
        context,
        agent_id=agent_id,
    )

    traces = trace.async_get_traces()
    trace_obj = next(iter(traces))
    events = trace_obj.as_dict().get("events", [])
    stats = next(
        e["data"]["stats"]
        for e in events
        if e.get("event_type") == "agent_detail" and e.get("data", {}).get("stats")
    )
    assert stats == {
        "input_tokens": 10,
        "cached_input_tokens": 5,
        "output_tokens": 20,
    }


@pytest.mark.parametrize("prefix", ["", "models/"])
@pytest.mark.parametrize(
    ("model", "sampling"),
    [
        ("gemini-2.0-flash", True),
        ("gemini-2.5-pro", True),
        ("gemini-3-flash", True),
        ("gemini-3.1-flash-lite", True),
        ("gemini-3.1-pro", True),
        ("gemini-3.5-flash", True),
        ("gemini-3.5-flash-preview-x", True),
        ("gemini-3.5-flash-lite", False),
        ("gemini-3.5-flash-lite-preview-x", False),
        ("gemini-3.5-flash-liteish", True),
        ("gemini-robotics-er-1.60-preview", False),
        ("models/models/gemini-3.8-flash", True),
        ("gemini-3.5-transcribe", False),
        ("gemini-3.6-flash", False),
        ("gemini-3.8-flash", False),
        ("gemini-3.10-flash", False),
        ("gemini-4-flash", False),
        ("gemini-10-pro", False),
        ("gemini-30-flash", False),
        ("gemini-flash-latest", False),
        ("gemini-pro-latest", False),
        ("gemini-flash-lite-latest", False),
        ("gemini-unknown-latest", False),
        ("gemini-nano-banana-2.1", False),
        ("gemini-robotics-er-2-preview", False),
        ("gemini-robotics-er-1.6-preview", True),
        ("gemini-3.1-flash-image", True),
        ("gemini-3.8-flash-image", False),
        ("gemini-3foo", False),
        ("gemini-2.50-flash", True),
        ("gemma-4-31b-it", True),
        ("custom-latest", True),
    ],
)
async def test_generation_sampling_request(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_genai_transport: AsyncMock,
    prefix: str,
    model: str,
    sampling: bool,
) -> None:
    """Prove field omission through the real SDK converter and request builder."""
    subentry = mock_config_entry.subentries["ulid-conversation"]
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={
            CONF_CHAT_MODEL: prefix + model,
            CONF_TEMPERATURE: 0.2,
            CONF_TOP_P: 0.7,
            CONF_TOP_K: 17,
            CONF_THINKING_BUDGET: 512,
            CONF_THINKING_LEVEL: "low",
        },
    )
    client = Client(api_key="test-api-key")
    mock_config_entry.runtime_data = client
    entity = GoogleGenerativeAILLMBaseEntity(mock_config_entry, subentry)
    try:
        await client.aio.models.generate_content(
            model=prefix + model,
            contents="Hello",
            config=entity.create_generate_content_config(),
        )
    finally:
        await client.aio.aclose()
        client.close()
    request = mock_genai_transport.call_args.kwargs["http_request"]
    config = request.data["generationConfig"]
    assert {
        key: config[key] for key in ("temperature", "topP", "topK") if key in config
    } == ({"temperature": 0.2, "topP": 0.7, "topK": 17} if sampling else {})
    assert config["maxOutputTokens"] == 3000
    assert len(request.data["safetySettings"]) == 4
    assert subentry.data[CONF_TEMPERATURE] == 0.2


@pytest.mark.parametrize("prefix", ["", "models/"])
@pytest.mark.parametrize(
    ("model", "level", "expected"),
    [
        ("gemini-3.6-flash", "minimal", ThinkingLevel.MINIMAL),
        ("gemini-3.5-flash-lite", "minimal", ThinkingLevel.MINIMAL),
        ("gemini-3.5-flash", "minimal", ThinkingLevel.MINIMAL),
        ("gemini-3.8-flash", "minimal", None),
        ("gemini-3.8-flash", "low", ThinkingLevel.LOW),
        ("gemini-3.8-flash", "medium", ThinkingLevel.MEDIUM),
        ("gemini-3.8-flash", "high", ThinkingLevel.HIGH),
        ("gemini-flash-latest", "low", ThinkingLevel.LOW),
        ("gemini-pro-latest", "medium", ThinkingLevel.MEDIUM),
        ("gemini-flash-lite-latest", "high", ThinkingLevel.HIGH),
        ("gemini-flash-lite-latest", "minimal", None),
        ("gemini-flash-latest", "auto", None),
        ("gemini-pro-latest", None, None),
        ("gemini-3.10-flash", "low", ThinkingLevel.LOW),
        ("gemini-4-flash", "high", ThinkingLevel.HIGH),
        ("gemini-4-pro", "minimal", None),
        ("gemini-10-pro", "medium", ThinkingLevel.MEDIUM),
        ("gemini-30-flash", "low", ThinkingLevel.LOW),
        ("gemini-3.5-transcribe", "low", ThinkingLevel.LOW),
    ],
)
async def test_generation_thinking_levels(
    mock_genai_transport: AsyncMock,
    prefix: str,
    model: str,
    level: str | None,
    expected: ThinkingLevel | None,
) -> None:
    """Supported configured levels survive; budgets never leak into level models."""
    config = _create_thinking_config(prefix + model, 512, level)
    assert config is not None
    assert config.include_thoughts is True
    assert config.thinking_level == expected
    assert config.thinking_budget is None
    client = Client(api_key="test-api-key")
    try:
        await client.aio.models.generate_content(
            model=prefix + model,
            contents="Hello",
            config=GenerateContentConfig(thinking_config=config),
        )
    finally:
        await client.aio.aclose()
        client.close()
    body = mock_genai_transport.call_args.kwargs["http_request"].data[
        "generationConfig"
    ]
    assert body["thinkingConfig"] == config.model_dump(exclude_none=True)
    assert "thinking_budget" not in body["thinkingConfig"]


@pytest.mark.parametrize(
    "model",
    [
        "gemini-3foo",
        "gemini-2.50-flash",
        "gemini-4-flash-tts-preview",
        "gemini-4-flash-image-preview",
        "gemini-4-live",
        "gemini-robotics-er-2-preview",
        "gemini-nano-banana-2.1",
        "custom-latest",
    ],
)
def test_no_new_specialized_thinking(model: str) -> None:
    """Do not invent thinking capability for specialized or unknown model names."""
    assert _create_thinking_config(model, 512, "low") is None


@pytest.mark.usefixtures("mock_init_component")
@pytest.mark.parametrize(
    "model", ["gemini-3.8-flash", "gemini-flash-latest", "gemini-4-flash"]
)
async def test_conversation_wire_tool_continuation(
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_chat_log: MockChatLog,  # noqa: F811
    mock_genai_transport: AsyncMock,
    model: str,
) -> None:
    """Exercise both streamed HTTP bodies with a real SDK chat and a tool result."""
    subentry = mock_config_entry_with_assist.subentries["ulid-conversation"]
    hass.config_entries.async_update_subentry(
        mock_config_entry_with_assist,
        subentry,
        data={**subentry.data, CONF_CHAT_MODEL: model, CONF_THINKING_LEVEL: "low"},
    )
    await hass.async_block_till_done()
    mock_genai_transport.return_value = [
        {
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [{"functionCall": {"name": "test_tool", "args": {}}}],
                    },
                    "finishReason": "STOP",
                }
            ]
        },
        {
            "candidates": [
                {
                    "content": {"role": "model", "parts": [{"text": "Done"}]},
                    "finishReason": "STOP",
                }
            ]
        },
    ]
    mock_chat_log.mock_tool_results({"mock-tool-call": {"result": "Done"}})
    result = await conversation.async_converse(
        hass,
        "Call the test tool",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.google_ai_conversation",
    )
    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert mock_genai_transport.call_count == 2
    for call in mock_genai_transport.call_args_list:
        assert call.kwargs["stream"] is True
        body = call.kwargs["http_request"].data
        config = body["generationConfig"]
        assert not {"temperature", "topP", "topK"}.intersection(config)
        assert config["thinkingConfig"] == {
            "include_thoughts": True,
            "thinking_level": "LOW",
        }
        assert config["maxOutputTokens"] == 3000
        assert body["tools"]
    assert (
        "functionResponse"
        in mock_genai_transport.call_args_list[1]
        .kwargs["http_request"]
        .data["contents"][-1]["parts"][0]
    )
