"""Tests for the Open Responses conversation entity."""

from collections.abc import Generator
from unittest.mock import MagicMock

from freezegun import freeze_time
from openresponses_client import (
    APIConnectionError,
    AuthenticationError,
    ErrorEvent,
    FunctionCall,
    InternalServerError,
    ReasoningItem,
    Response,
    StreamingEvent,
    UnknownItem,
)
from openresponses_client.models import (
    ErrorPayload,
    IncompleteDetails,
    ResponseCompletedEvent,
    ResponseError,
    ResponseFailedEvent,
    ResponseIncompleteEvent,
    ResponseOutputItemAddedEvent,
    ResponseOutputItemDoneEvent,
    ResponseOutputTextDeltaEvent,
    ResponseReasoningDeltaEvent,
    ResponseReasoningSummaryTextDeltaEvent,
    ResponseRefusalDeltaEvent,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import conversation
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry as er, intent

from . import MockStream

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.conversation import MockChatLog, mock_chat_log  # noqa: F401

AGENT_ID = "conversation.gpt_oss_20b"


@pytest.fixture(autouse=True)
def freeze_the_time() -> Generator[None]:
    """Freeze the time so the system prompt is stable."""
    with freeze_time("2026-09-28 12:00:00", tz_offset=0):
        yield


async def test_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the conversation entity."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_conversation(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_chat_log: MockChatLog,  # noqa: F811
    snapshot: SnapshotAssertion,
) -> None:
    """Test a streamed answer is added to the chat log."""
    result = await conversation.async_converse(
        hass, "hello", mock_chat_log.conversation_id, Context(), agent_id=AGENT_ID
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert result.response.speech["plain"]["speech"] == "Hello, how can I help?"
    assert mock_chat_log.content[1:] == snapshot
    kwargs = mock_client.stream.call_args.kwargs
    assert kwargs["model"] == "gpt-oss:20b"
    assert kwargs["store"] is False
    assert kwargs["safety_identifier"] == mock_chat_log.conversation_id
    assert kwargs["prompt_cache_key"] == "ulid-conversation"
    assert kwargs["input"][0]["role"] == "system"
    assert kwargs["input"][1:] == snapshot(name="input")
    assert kwargs["tools"]
    assert all(
        tool["type"] == "function" and tool["strict"] is False
        for tool in kwargs["tools"]
    )


@pytest.mark.usefixtures("init_integration")
async def test_function_call(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_chat_log: MockChatLog,  # noqa: F811
    snapshot: SnapshotAssertion,
) -> None:
    """Test function calls are run and output items are sent back in order."""
    reasoning = ReasoningItem(id="rs_1", encrypted_content="encrypted")
    provider_item = UnknownItem.from_dict({"type": "acme:search", "id": "acme_1"})
    function_call_1 = FunctionCall(
        call_id="call_1", name="test_tool", arguments='{"param1": "value1"}'
    )
    function_call_2 = FunctionCall(call_id="call_2", name="test_tool", arguments="")
    mock_client.stream.side_effect = [
        MockStream(
            [
                ResponseOutputItemAddedEvent(item=reasoning),
                ResponseReasoningDeltaEvent(delta="Let me "),
                ResponseReasoningSummaryTextDeltaEvent(delta="check."),
                ResponseOutputItemDoneEvent(item=reasoning),
                ResponseOutputItemAddedEvent(item=provider_item),
                ResponseOutputItemDoneEvent(item=provider_item),
                ResponseOutputItemAddedEvent(item=function_call_1),
                ResponseOutputItemDoneEvent(item=function_call_1),
                ResponseOutputItemAddedEvent(item=function_call_2),
                ResponseOutputItemDoneEvent(item=function_call_2),
                ResponseCompletedEvent(),
            ]
        ),
        MockStream(
            [ResponseOutputTextDeltaEvent(delta="Done"), ResponseCompletedEvent()]
        ),
    ]
    mock_chat_log.mock_tool_results({"call_1": "result1", "call_2": "result2"})

    result = await conversation.async_converse(
        hass,
        "Please call the test tool",
        mock_chat_log.conversation_id,
        Context(),
        agent_id=AGENT_ID,
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert result.response.speech["plain"]["speech"] == "Done"
    assert mock_chat_log.content[1:] == snapshot
    assert mock_client.stream.call_count == 2
    assert mock_client.stream.call_args.kwargs["input"][1:] == snapshot(name="input")


@pytest.mark.usefixtures("init_integration")
async def test_refusal(
    hass: HomeAssistant,
    mock_client: MagicMock,
) -> None:
    """Test a refusal of the model is returned as the answer."""
    mock_client.stream.return_value = MockStream(
        [ResponseRefusalDeltaEvent(delta="I can't help."), ResponseCompletedEvent()]
    )

    result = await conversation.async_converse(
        hass, "hello", None, Context(), agent_id=AGENT_ID
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert result.response.speech["plain"]["speech"] == "I can't help."


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("events", "message"),
    [
        pytest.param(
            [AuthenticationError("Invalid key", status=401)],
            "Invalid authentication",
            id="invalid_auth",
        ),
        pytest.param(
            [APIConnectionError("Connection refused")],
            "Unable to connect to the server",
            id="cannot_connect",
        ),
        pytest.param(
            [InternalServerError("Server error", status=500)],
            "Error talking to the server: Server error (status=500)",
            id="api_error",
        ),
        pytest.param(
            [
                ResponseFailedEvent(
                    response=Response(error=ResponseError(message="Boom"))
                )
            ],
            "The response failed: Boom",
            id="response_failed",
        ),
        pytest.param(
            [ErrorEvent(error=ErrorPayload(message="Overloaded"))],
            "The response failed: Overloaded",
            id="error_event",
        ),
        pytest.param(
            [
                ResponseIncompleteEvent(
                    response=Response(
                        incomplete_details=IncompleteDetails(reason="max_output_tokens")
                    )
                )
            ],
            "The response is incomplete: max_output_tokens",
            id="response_incomplete",
        ),
        pytest.param(
            [
                ResponseOutputItemDoneEvent(
                    item=FunctionCall(call_id="call_1", name="test", arguments="{")
                )
            ],
            "The model returned invalid tool arguments: Expecting property name "
            "enclosed in double quotes: line 1 column 2 (char 1)",
            id="invalid_tool_arguments",
        ),
        pytest.param(
            [ResponseOutputTextDeltaEvent(delta="Hello")],
            "The server ended the response before it was complete",
            id="stream_ended",
        ),
    ],
)
async def test_errors(
    hass: HomeAssistant,
    mock_client: MagicMock,
    events: list[StreamingEvent | Exception],
    message: str,
) -> None:
    """Test errors while generating an answer."""
    mock_client.stream.return_value = MockStream(events)

    result = await conversation.async_converse(
        hass, "hello", None, Context(), agent_id=AGENT_ID
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert result.response.speech["plain"]["speech"] == message
