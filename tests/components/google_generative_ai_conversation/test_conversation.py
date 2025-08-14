"""Tests for the Google Generative AI Conversation integration conversation platform."""

from unittest.mock import AsyncMock, patch

from freezegun import freeze_time
from google.genai.types import GenerateContentResponse
import pytest

from homeassistant.components import conversation
from homeassistant.components.conversation import UserContent
from homeassistant.components.google_generative_ai_conversation.entity import (
    ERROR_GETTING_RESPONSE,
    _escape_decode,
    _format_schema,
)
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent

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
    assert result.response.response_type == intent.IntentResponseType.ERROR, result
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
) -> None:
    """Test function calling."""
    agent_id = "conversation.google_ai_conversation"
    context = Context()

    messages = [
        # Function call stream
        [
            GenerateContentResponse(
                candidates=[
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": "Hi there!",
                                }
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
                                    "text": "test function with the provided parameters.",
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
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
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
            "response": {
                "result": "Test response",
            },
            "scheduling": None,
            "will_continue": None,
        },
        "inline_data": None,
        "text": None,
        "thought": None,
        "thought_signature": None,
        "video_metadata": None,
    }


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
        # Messages from the model which contain the google search answer (the usage of the Google Search tool is server side)
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
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
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

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
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
    assert result.response.response_type == intent.IntentResponseType.ERROR, result
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

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
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

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
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
    """Tests that in case of an empty entry in the chat history the google API will receive an injected space sign instead."""
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
