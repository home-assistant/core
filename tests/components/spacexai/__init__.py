"""Test helpers for SpaceXAI."""

from collections.abc import AsyncIterator, Iterable, Sequence
from typing import Any, Self

from openai.types import Model
from openai.types.responses import (
    Response,
    ResponseCompletedEvent,
    ResponseErrorEvent,
    ResponseFailedEvent,
    ResponseFunctionCallArgumentsDoneEvent,
    ResponseFunctionToolCall,
    ResponseIncompleteEvent,
    ResponseOutputItemAddedEvent,
    ResponseOutputMessage,
    ResponseStreamEvent,
    ResponseTextDeltaEvent,
)

from homeassistant.components import conversation
from homeassistant.components.conversation import ConversationResult
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import Context, HomeAssistant

AGENT_ID = "conversation.grok"


class AsyncModelPage:
    """Async-iterable models page that can span multiple SDK pages."""

    def __init__(self, *pages: Sequence[Model]) -> None:
        """Store page batches; `.data` mirrors the first page only."""
        self._pages = pages or ((),)
        self.data = list(self._pages[0])

    def __aiter__(self) -> AsyncIterator[Model]:
        """Yield every model across all pages."""
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[Model]:
        """Yield models in page order."""
        for page in self._pages:
            for model in page:
                yield model


def conversation_subentry(entry: ConfigEntry) -> ConfigSubentry:
    """Return the conversation subentry on a SpaceXAI config entry."""
    return next(
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "conversation"
    )


async def converse(
    hass: HomeAssistant,
    text: str,
    conversation_id: str | None = None,
    *,
    agent_id: str = AGENT_ID,
) -> ConversationResult:
    """Run a SpaceXAI conversation turn against the default test agent."""
    return await conversation.async_converse(
        hass,
        text,
        conversation_id,
        Context(),
        agent_id=agent_id,
    )


class EventStream:
    """Deterministic async event stream matching the SDK context-manager shape."""

    def __init__(self, events: Iterable[ResponseStreamEvent]) -> None:
        """Initialize the stream."""
        self._events = iter(events)
        self.closed = False

    async def __aenter__(self) -> Self:
        """Enter the stream context used by the entity chat loop."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Close the stream after consumption or failure."""
        self.closed = True

    def __aiter__(self) -> AsyncIterator[ResponseStreamEvent]:
        """Return the event iterator."""
        return self

    async def __anext__(self) -> ResponseStreamEvent:
        """Return the next event."""
        try:
            return next(self._events)
        except StopIteration as err:
            raise StopAsyncIteration from err


def response_payload(**changes: Any) -> Response:
    """Build a minimal Responses API response object."""
    data: dict[str, Any] = {
        "id": "response-123",
        "created_at": 1,
        "model": "grok-4.5",
        "object": "response",
        "output": [],
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "tools": [],
        "status": "completed",
        "usage": None,
    }
    data.update(changes)
    return Response.model_validate(data)


def completed_event(
    sequence_number: int = 2,
    **response_changes: Any,
) -> ResponseCompletedEvent:
    """Build a terminal completed response event."""
    return ResponseCompletedEvent(
        response=response_payload(**response_changes),
        sequence_number=sequence_number,
        type="response.completed",
    )


def incomplete_event(
    *,
    reason: str | None = "max_output_tokens",
    sequence_number: int = 0,
) -> ResponseIncompleteEvent:
    """Build an incomplete terminal response event."""
    details = None if reason is None else {"reason": reason}
    return ResponseIncompleteEvent(
        response=response_payload(status="incomplete", incomplete_details=details),
        sequence_number=sequence_number,
        type="response.incomplete",
    )


def failed_event(
    code: str,
    message: str,
    *,
    sequence_number: int = 0,
) -> ResponseFailedEvent:
    """Build a failed terminal response event."""
    return ResponseFailedEvent(
        response=response_payload(
            status="failed",
            error={"code": code, "message": message},
        ),
        sequence_number=sequence_number,
        type="response.failed",
    )


def error_event(
    code: str,
    message: str,
    *,
    sequence_number: int = 0,
) -> ResponseErrorEvent:
    """Build a mid-stream error event."""
    return ResponseErrorEvent(
        code=code,
        message=message,
        sequence_number=sequence_number,
        type="error",
    )


def message_events(text: str, *, complete: bool = True) -> list[ResponseStreamEvent]:
    """Build a streaming assistant text response."""
    events: list[ResponseStreamEvent] = [
        ResponseOutputItemAddedEvent(
            item=ResponseOutputMessage(
                id="msg_1",
                content=[],
                role="assistant",
                status="in_progress",
                type="message",
            ),
            output_index=0,
            sequence_number=0,
            type="response.output_item.added",
        ),
        ResponseTextDeltaEvent(
            content_index=0,
            delta=text,
            item_id="msg_1",
            logprobs=[],
            output_index=0,
            sequence_number=1,
            type="response.output_text.delta",
        ),
    ]
    if complete:
        events.append(completed_event(2))
    return events


def tool_call_added(
    *,
    item_id: str | None,
    call_id: str,
    name: str,
    output_index: int = 0,
    sequence_number: int = 0,
) -> ResponseOutputItemAddedEvent:
    """Announce a function tool call on the stream."""
    return ResponseOutputItemAddedEvent(
        item=ResponseFunctionToolCall(
            id=item_id,
            arguments="",
            call_id=call_id,
            name=name,
            status="in_progress",
            type="function_call",
        ),
        output_index=output_index,
        sequence_number=sequence_number,
        type="response.output_item.added",
    )


def tool_args_done(
    *,
    item_id: str,
    name: str | None,
    arguments: str,
    output_index: int = 0,
    sequence_number: int = 1,
) -> ResponseFunctionCallArgumentsDoneEvent:
    """Finish tool-call arguments, optionally omitting name like xAI sometimes does."""
    return ResponseFunctionCallArgumentsDoneEvent.model_construct(
        arguments=arguments,
        item_id=item_id,
        name=name,
        output_index=output_index,
        sequence_number=sequence_number,
        type="response.function_call_arguments.done",
    )


def tool_events(
    *calls: tuple[str, str, str],
    complete: bool = True,
) -> list[ResponseStreamEvent]:
    """Build one assistant response containing one or more tool calls."""
    events: list[ResponseStreamEvent] = []
    for index, (call_id, name, arguments) in enumerate(calls):
        item_id = f"item_{index}"
        events.extend(
            (
                tool_call_added(
                    item_id=item_id,
                    call_id=call_id,
                    name=name,
                    output_index=index,
                    sequence_number=index * 2,
                ),
                tool_args_done(
                    item_id=item_id,
                    name=name,
                    arguments=arguments,
                    output_index=index,
                    sequence_number=index * 2 + 1,
                ),
            )
        )
    if complete:
        events.append(completed_event(len(calls) * 2))
    return events


def usage_completed_events(
    text: str,
    *,
    input_tokens: int,
    cached_tokens: int,
    output_tokens: int,
) -> list[ResponseStreamEvent]:
    """Build a completed text stream that includes usage for Assist tracing."""
    return [
        *message_events(text, complete=False),
        completed_event(
            2,
            usage={
                "input_tokens": input_tokens,
                "input_tokens_details": {
                    "cached_tokens": cached_tokens,
                    "cache_write_tokens": 0,
                },
                "output_tokens": output_tokens,
                "output_tokens_details": {"reasoning_tokens": 0},
                "total_tokens": input_tokens + output_tokens,
            },
        ),
    ]
