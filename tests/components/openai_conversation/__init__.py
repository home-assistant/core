"""Tests for the OpenAI Conversation integration."""

from openai.types.responses import (
    ResponseContentPartAddedEvent,
    ResponseContentPartDoneEvent,
    ResponseFunctionCallArgumentsDeltaEvent,
    ResponseFunctionCallArgumentsDoneEvent,
    ResponseFunctionToolCall,
    ResponseFunctionWebSearch,
    ResponseOutputItemAddedEvent,
    ResponseOutputItemDoneEvent,
    ResponseOutputMessage,
    ResponseOutputText,
    ResponseReasoningItem,
    ResponseStreamEvent,
    ResponseTextDeltaEvent,
    ResponseTextDoneEvent,
    ResponseWebSearchCallCompletedEvent,
    ResponseWebSearchCallInProgressEvent,
    ResponseWebSearchCallSearchingEvent,
)
from openai.types.responses.response_function_web_search import ActionSearch


def create_message_item(
    id: str, text: str | list[str], output_index: int
) -> list[ResponseStreamEvent]:
    """Create a message item."""
    if isinstance(text, str):
        text = [text]

    content = ResponseOutputText(annotations=[], text="", type="output_text")
    events = [
        ResponseOutputItemAddedEvent(
            item=ResponseOutputMessage(
                id=id,
                content=[],
                type="message",
                role="assistant",
                status="in_progress",
            ),
            output_index=output_index,
            sequence_number=0,
            type="response.output_item.added",
        ),
        ResponseContentPartAddedEvent(
            content_index=0,
            item_id=id,
            output_index=output_index,
            part=content,
            sequence_number=0,
            type="response.content_part.added",
        ),
    ]

    content.text = "".join(text)
    events.extend(
        ResponseTextDeltaEvent(
            content_index=0,
            delta=delta,
            item_id=id,
            output_index=output_index,
            sequence_number=0,
            type="response.output_text.delta",
        )
        for delta in text
    )

    events.extend(
        [
            ResponseTextDoneEvent(
                content_index=0,
                item_id=id,
                output_index=output_index,
                text="".join(text),
                sequence_number=0,
                type="response.output_text.done",
            ),
            ResponseContentPartDoneEvent(
                content_index=0,
                item_id=id,
                output_index=output_index,
                part=content,
                sequence_number=0,
                type="response.content_part.done",
            ),
            ResponseOutputItemDoneEvent(
                item=ResponseOutputMessage(
                    id=id,
                    content=[content],
                    role="assistant",
                    status="completed",
                    type="message",
                ),
                output_index=output_index,
                sequence_number=0,
                type="response.output_item.done",
            ),
        ]
    )

    return events


def create_function_tool_call_item(
    id: str, arguments: str | list[str], call_id: str, name: str, output_index: int
) -> list[ResponseStreamEvent]:
    """Create a function tool call item."""
    if isinstance(arguments, str):
        arguments = [arguments]

    events = [
        ResponseOutputItemAddedEvent(
            item=ResponseFunctionToolCall(
                id=id,
                arguments="",
                call_id=call_id,
                name=name,
                type="function_call",
                status="in_progress",
            ),
            output_index=output_index,
            sequence_number=0,
            type="response.output_item.added",
        )
    ]

    events.extend(
        ResponseFunctionCallArgumentsDeltaEvent(
            delta=delta,
            item_id=id,
            output_index=output_index,
            sequence_number=0,
            type="response.function_call_arguments.delta",
        )
        for delta in arguments
    )

    events.append(
        ResponseFunctionCallArgumentsDoneEvent(
            arguments="".join(arguments),
            item_id=id,
            output_index=output_index,
            sequence_number=0,
            type="response.function_call_arguments.done",
        )
    )

    events.append(
        ResponseOutputItemDoneEvent(
            item=ResponseFunctionToolCall(
                id=id,
                arguments="".join(arguments),
                call_id=call_id,
                name=name,
                type="function_call",
                status="completed",
            ),
            output_index=output_index,
            sequence_number=0,
            type="response.output_item.done",
        )
    )

    return events


def create_reasoning_item(id: str, output_index: int) -> list[ResponseStreamEvent]:
    """Create a reasoning item."""
    return [
        ResponseOutputItemAddedEvent(
            item=ResponseReasoningItem(
                id=id,
                summary=[],
                type="reasoning",
                status=None,
                encrypted_content="AAA",
            ),
            output_index=output_index,
            sequence_number=0,
            type="response.output_item.added",
        ),
        ResponseOutputItemDoneEvent(
            item=ResponseReasoningItem(
                id=id,
                summary=[],
                type="reasoning",
                status=None,
                encrypted_content="AAABBB",
            ),
            output_index=output_index,
            sequence_number=0,
            type="response.output_item.done",
        ),
    ]


def create_web_search_item(id: str, output_index: int) -> list[ResponseStreamEvent]:
    """Create a web search call item."""
    return [
        ResponseOutputItemAddedEvent(
            item=ResponseFunctionWebSearch(
                id=id,
                status="in_progress",
                action=ActionSearch(query="query", type="search"),
                type="web_search_call",
            ),
            output_index=output_index,
            sequence_number=0,
            type="response.output_item.added",
        ),
        ResponseWebSearchCallInProgressEvent(
            item_id=id,
            output_index=output_index,
            sequence_number=0,
            type="response.web_search_call.in_progress",
        ),
        ResponseWebSearchCallSearchingEvent(
            item_id=id,
            output_index=output_index,
            sequence_number=0,
            type="response.web_search_call.searching",
        ),
        ResponseWebSearchCallCompletedEvent(
            item_id=id,
            output_index=output_index,
            sequence_number=0,
            type="response.web_search_call.completed",
        ),
        ResponseOutputItemDoneEvent(
            item=ResponseFunctionWebSearch(
                id=id,
                status="completed",
                action=ActionSearch(query="query", type="search"),
                type="web_search_call",
            ),
            output_index=output_index,
            sequence_number=0,
            type="response.output_item.done",
        ),
    ]
