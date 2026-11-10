"""Tests for the llama.cpp AI Task platform."""

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx2
import openai
from openai import Omit
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionChunk,
    ChatCompletionMessage,
    ChatCompletionMessageFunctionToolCall,
)
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_chunk import (
    Choice as ChunkChoice,
    ChoiceDelta,
    ChoiceDeltaToolCall,
    ChoiceDeltaToolCallFunction,
)
from openai.types.chat.chat_completion_message_function_tool_call import Function
import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import ai_task, media_source
from homeassistant.components.llama_cpp.const import CONF_STREAMING
from homeassistant.components.llama_cpp.entity import MAX_TOOL_ITERATIONS
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, llm, selector

ENTITY_ID = "ai_task.gpt_3_5_turbo"

pytestmark = pytest.mark.usefixtures("setup_integration")


@pytest.fixture(name="platforms")
def platforms_fixture() -> list[Platform]:
    """Only load the AI task platform."""
    return [Platform.AI_TASK]


def _completion(
    content: str | None,
    tool_calls: list[ChatCompletionMessageFunctionToolCall] | None = None,
) -> ChatCompletion:
    """Build a non-streamed chat completion."""
    return ChatCompletion(
        id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
        choices=[
            Choice(
                finish_reason="tool_calls" if tool_calls else "stop",
                index=0,
                message=ChatCompletionMessage(
                    content=content, role="assistant", tool_calls=tool_calls
                ),
            )
        ],
        created=1700000000,
        model="gpt-3.5-turbo",
        object="chat.completion",
    )


async def _stream(
    chunks: list[ChatCompletionChunk],
) -> AsyncGenerator[ChatCompletionChunk]:
    """Yield streamed chat completion chunks."""
    for chunk in chunks:
        yield chunk


def _chunk(choices: list[ChunkChoice]) -> ChatCompletionChunk:
    """Build a streamed chat completion chunk."""
    return ChatCompletionChunk(
        id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
        choices=choices,
        created=1700000000,
        model="gpt-3.5-turbo",
        object="chat.completion.chunk",
    )


def _streamed_text(*parts: str) -> AsyncGenerator[ChatCompletionChunk]:
    """Build a stream that answers with the given text parts."""
    return _stream(
        [
            _chunk(
                [
                    ChunkChoice(
                        index=0,
                        delta=ChoiceDelta(
                            content=part, role="assistant" if i == 0 else None
                        ),
                        finish_reason="stop" if i == len(parts) - 1 else None,
                    )
                ]
            )
            for i, part in enumerate(parts)
        ]
    )


class TemperatureTool(llm.Tool):
    """Tool returning a fixed temperature."""

    name = "get_temperature"
    description = "Get the living room temperature"
    integration = "test"

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> llm.ToolResult:
        """Return the temperature."""
        return llm.ToolResult(data={"temperature": 21.5})


class TemperatureAPI(llm.API):
    """API without a custom serializer, like the MCP and KNX APIs."""

    async def async_get_api_instance(
        self, llm_context: llm.LLMContext
    ) -> llm.APIInstance:
        """Return the API instance."""
        return llm.APIInstance(self, "", llm_context, [TemperatureTool()])


def _custom_serializer(value: Any) -> Any:
    """Serialize number selectors with a marker description."""
    if isinstance(value, selector.NumberSelector):
        return {"type": "number", "description": "Custom"}
    return llm.selector_serializer(value)


class CustomSerializerTemperatureAPI(llm.API):
    """API with its own custom serializer."""

    async def async_get_api_instance(
        self, llm_context: llm.LLMContext
    ) -> llm.APIInstance:
        """Return the API instance."""
        return llm.APIInstance(
            self,
            "",
            llm_context,
            [TemperatureTool()],
            custom_serializer=_custom_serializer,
        )


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the AI task entity and its device."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("config_entry_data", "response", "streaming"),
    [
        pytest.param({}, _completion("The test data"), False, id="non_streaming"),
        pytest.param(
            {CONF_STREAMING: True},
            _streamed_text("The test", " data"),
            True,
            id="streaming",
        ),
    ],
)
async def test_generate_data(
    hass: HomeAssistant,
    mock_completion: AsyncMock,
    response: ChatCompletion | AsyncGenerator[ChatCompletionChunk],
    streaming: bool,
) -> None:
    """Test generating text data."""
    mock_completion.return_value = response

    result = await ai_task.async_generate_data(
        hass,
        task_name="Test Task",
        entity_id=ENTITY_ID,
        instructions="Generate test data",
    )

    assert result.data == "The test data"
    assert mock_completion.call_args.kwargs["stream"] is streaming
    assert isinstance(mock_completion.call_args.kwargs["response_format"], Omit)


@pytest.mark.parametrize(
    ("config_entry_data", "response"),
    [
        pytest.param({CONF_STREAMING: True}, _stream([_chunk([])]), id="no_choices"),
        # A thinking model cut off by max_tokens only produces reasoning
        pytest.param(
            {CONF_STREAMING: True}, _streamed_text(""), id="streamed_empty_content"
        ),
        pytest.param({}, _completion(None), id="no_content"),
    ],
)
async def test_generate_data_empty_response(
    hass: HomeAssistant,
    mock_completion: AsyncMock,
    response: ChatCompletion | AsyncGenerator[ChatCompletionChunk],
) -> None:
    """Test an error is raised when the model returns no answer."""
    mock_completion.return_value = response

    with pytest.raises(HomeAssistantError, match="No response was returned"):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=ENTITY_ID,
            instructions="Generate test data",
        )


@pytest.mark.parametrize(
    ("task_name", "schema_name"),
    [
        pytest.param("Test Task", "test_task", id="slugified"),
        pytest.param("", "response", id="empty"),
        pytest.param("a" * 100, "a" * 64, id="truncated"),
    ],
)
async def test_generate_structured_data(
    hass: HomeAssistant,
    mock_completion: AsyncMock,
    task_name: str,
    schema_name: str,
) -> None:
    """Test generating structured data built from selectors."""
    mock_completion.return_value = _completion('{"characters": ["Mario", "Luigi"]}')

    result = await ai_task.async_generate_data(
        hass,
        task_name=task_name,
        entity_id=ENTITY_ID,
        instructions="Generate test data",
        structure=probatio.Schema(
            {
                probatio.Required("characters"): selector.selector(
                    {"text": {"multiple": True}}
                )
            }
        ),
    )

    assert result.data == {"characters": ["Mario", "Luigi"]}
    assert mock_completion.call_args.kwargs["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": schema_name,
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "characters": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["characters"],
                "additionalProperties": False,
            },
        },
    }


def _tool_call_response(
    call_id: str, streaming: bool
) -> ChatCompletion | AsyncGenerator[ChatCompletionChunk]:
    """Build a response calling the temperature tool."""
    if not streaming:
        return _completion(
            None,
            [
                ChatCompletionMessageFunctionToolCall(
                    id=call_id,
                    type="function",
                    function=Function(name="get_temperature", arguments="{}"),
                )
            ],
        )
    return _stream(
        [
            _chunk(
                [
                    ChunkChoice(
                        index=0,
                        delta=ChoiceDelta(
                            role="assistant",
                            tool_calls=[
                                ChoiceDeltaToolCall(
                                    index=0,
                                    id=call_id,
                                    type="function",
                                    function=ChoiceDeltaToolCallFunction(
                                        name="get_temperature", arguments="{}"
                                    ),
                                )
                            ],
                        ),
                        finish_reason="tool_calls",
                    )
                ]
            )
        ]
    )


def _text_response(
    text: str, streaming: bool
) -> ChatCompletion | AsyncGenerator[ChatCompletionChunk]:
    """Build a response answering with text."""
    return _streamed_text(text) if streaming else _completion(text)


def _record_requests(
    mock_completion: AsyncMock,
    responses: list[ChatCompletion | AsyncGenerator[ChatCompletionChunk] | Exception],
) -> list[dict[str, Any]]:
    """Answer each request in turn and record a copy of its arguments."""
    requests: list[dict[str, Any]] = []

    def create(**kwargs: Any) -> ChatCompletion | AsyncGenerator[ChatCompletionChunk]:
        # The messages list is extended after each call, so keep a copy
        requests.append({**kwargs, "messages": list(kwargs["messages"])})
        response = responses[len(requests) - 1]
        if isinstance(response, Exception):
            raise response
        return response

    mock_completion.side_effect = create
    return requests


@pytest.mark.parametrize(
    ("config_entry_data", "streaming", "tool_turns", "prose_turns", "roles"),
    [
        pytest.param(
            {},
            False,
            1,
            1,
            ["system", "user", "assistant", "tool"],
            id="non_streaming",
        ),
        pytest.param(
            {CONF_STREAMING: True},
            True,
            1,
            1,
            ["system", "user", "assistant", "tool"],
            id="streaming",
        ),
        pytest.param(
            {},
            False,
            MAX_TOOL_ITERATIONS - 1,
            1,
            ["system", "user"] + ["assistant", "tool"] * (MAX_TOOL_ITERATIONS - 1),
            id="tools_done_on_last_iteration",
        ),
        pytest.param(
            {},
            False,
            MAX_TOOL_ITERATIONS,
            0,
            ["system", "user"] + ["assistant", "tool"] * MAX_TOOL_ITERATIONS,
            id="tool_iterations_exhausted",
        ),
    ],
)
async def test_generate_structured_data_with_tools(
    hass: HomeAssistant,
    mock_completion: AsyncMock,
    streaming: bool,
    tool_turns: int,
    prose_turns: int,
    roles: list[str],
) -> None:
    """Test tools and the structured answer are requested in separate calls."""
    responses = [
        *(_tool_call_response(f"call_{turn}", streaming) for turn in range(tool_turns)),
        *(_text_response("It is 21.5 degrees.", streaming) for _ in range(prose_turns)),
        _text_response('{"temperature": 21.5}', streaming),
    ]
    requests = _record_requests(mock_completion, responses)

    result = await ai_task.async_generate_data(
        hass,
        task_name="Temperature",
        entity_id=ENTITY_ID,
        instructions="What is the living room temperature?",
        structure=probatio.Schema(
            {probatio.Required("temperature"): selector.selector({"number": {}})}
        ),
        llm_api=TemperatureAPI(hass=hass, id="temperature", name="Temperature"),
    )

    assert result.data == {"temperature": 21.5}
    assert len(requests) == len(responses)
    for request in requests[:-1]:
        assert [tool["function"]["name"] for tool in request["tools"]] == [
            "get_temperature"
        ]
        assert isinstance(request["response_format"], Omit)
    structured_request = requests[-1]
    assert isinstance(structured_request["tools"], Omit)
    assert structured_request["response_format"]["json_schema"]["schema"] == {
        "type": "object",
        "properties": {"temperature": {"type": "number"}},
        "required": ["temperature"],
        "additionalProperties": False,
    }
    # The prose answer is left out: llama.cpp rejects a trailing assistant
    # message with a structured format
    assert [message["role"] for message in structured_request["messages"]] == roles


async def test_generate_structured_data_with_tools_api_error(
    hass: HomeAssistant,
    mock_completion: AsyncMock,
) -> None:
    """Test an API error on the structured call after tool use is translated."""
    requests = _record_requests(
        mock_completion,
        [
            _tool_call_response("call_1", False),
            _completion("It is 21.5 degrees."),
            openai.BadRequestError(
                message="Bad request",
                response=httpx2.Response(
                    status_code=400,
                    request=httpx2.Request(method="POST", url="test"),
                ),
                body=None,
            ),
        ],
    )

    with pytest.raises(HomeAssistantError, match="API error"):
        await ai_task.async_generate_data(
            hass,
            task_name="Temperature",
            entity_id=ENTITY_ID,
            instructions="What is the living room temperature?",
            structure=probatio.Schema(
                {probatio.Required("temperature"): selector.selector({"number": {}})}
            ),
            llm_api=TemperatureAPI(hass=hass, id="temperature", name="Temperature"),
        )

    assert len(requests) == 3


async def test_generate_structured_data_custom_serializer(
    hass: HomeAssistant,
    mock_completion: AsyncMock,
) -> None:
    """Test the structure uses the custom serializer of the LLM API."""
    _record_requests(
        mock_completion,
        [_completion("It is 21.5 degrees."), _completion('{"temperature": 21.5}')],
    )

    await ai_task.async_generate_data(
        hass,
        task_name="Temperature",
        entity_id=ENTITY_ID,
        instructions="What is the living room temperature?",
        structure=probatio.Schema(
            {probatio.Required("temperature"): selector.selector({"number": {}})}
        ),
        llm_api=CustomSerializerTemperatureAPI(
            hass=hass, id="temperature", name="Temperature"
        ),
    )

    assert mock_completion.call_args.kwargs["response_format"]["json_schema"]["schema"][
        "properties"
    ] == {"temperature": {"type": "number", "description": "Custom"}}


@pytest.mark.parametrize(
    "content",
    [
        pytest.param("INVALID JSON RESPONSE", id="not_json"),
        pytest.param("21.5", id="not_an_object"),
    ],
)
async def test_generate_invalid_structured_data(
    hass: HomeAssistant,
    mock_completion: AsyncMock,
    content: str,
) -> None:
    """Test an error is raised when the structured response is not a JSON object."""
    mock_completion.return_value = _completion(content)

    with pytest.raises(HomeAssistantError, match="did not return valid JSON"):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=ENTITY_ID,
            instructions="Generate test data",
            structure=probatio.Schema(
                {probatio.Required("characters"): selector.selector({"text": {}})}
            ),
        )


async def test_generate_data_with_attachments(
    hass: HomeAssistant,
    mock_completion: AsyncMock,
) -> None:
    """Test image attachments are sent with the user message."""
    mock_completion.return_value = _completion("A person at the door")

    with (
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            return_value=media_source.PlayMedia(
                url="http://example.com/doorbell_snapshot.jpg",
                mime_type="image/jpeg",
                path=Path("doorbell_snapshot.jpg"),
            ),
        ),
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=b"fake_image_data"),
    ):
        result = await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=ENTITY_ID,
            instructions="Describe the image",
            attachments=[
                {"media_content_id": "media-source://media/doorbell_snapshot.jpg"}
            ],
        )

    assert result.data == "A person at the door"
    messages = mock_completion.call_args.kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert messages[1] == {
        "role": "user",
        "content": [
            {"type": "text", "text": "Describe the image"},
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/jpeg;base64,ZmFrZV9pbWFnZV9kYXRh",
                    "detail": "auto",
                },
            },
        ],
    }


@pytest.mark.parametrize(
    ("mime_type", "exists", "error"),
    [
        pytest.param(
            "application/pdf", True, "Only image attachments", id="unsupported_type"
        ),
        pytest.param("image/jpeg", False, "File does not exist", id="file_not_found"),
    ],
)
async def test_generate_data_with_invalid_attachment(
    hass: HomeAssistant,
    mock_completion: AsyncMock,
    mime_type: str,
    exists: bool,
    error: str,
) -> None:
    """Test invalid attachments are rejected before calling the API."""
    with (
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            return_value=media_source.PlayMedia(
                url="http://example.com/attachment",
                mime_type=mime_type,
                path=Path("attachment"),
            ),
        ),
        patch("pathlib.Path.exists", return_value=exists),
        pytest.raises(HomeAssistantError, match=error),
    ):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=ENTITY_ID,
            instructions="Describe the attachment",
            attachments=[{"media_content_id": "media-source://media/attachment"}],
        )

    mock_completion.assert_not_called()
