"""Tests for the OpenAI Conversation integration."""

from openai.types.responses import (
    ResponseCodeInterpreterCallCodeDeltaEvent,
    ResponseCodeInterpreterCallCodeDoneEvent,
    ResponseCodeInterpreterCallCompletedEvent,
    ResponseCodeInterpreterCallInProgressEvent,
    ResponseCodeInterpreterCallInterpretingEvent,
    ResponseCodeInterpreterToolCall,
    ResponseContentPartAddedEvent,
    ResponseContentPartDoneEvent,
    ResponseFunctionCallArgumentsDeltaEvent,
    ResponseFunctionCallArgumentsDoneEvent,
    ResponseFunctionToolCall,
    ResponseFunctionWebSearch,
    ResponseImageGenCallCompletedEvent,
    ResponseImageGenCallPartialImageEvent,
    ResponseOutputItemAddedEvent,
    ResponseOutputItemDoneEvent,
    ResponseOutputMessage,
    ResponseOutputText,
    ResponseReasoningItem,
    ResponseReasoningSummaryPartAddedEvent,
    ResponseReasoningSummaryPartDoneEvent,
    ResponseReasoningSummaryTextDeltaEvent,
    ResponseReasoningSummaryTextDoneEvent,
    ResponseStreamEvent,
    ResponseTextDeltaEvent,
    ResponseTextDoneEvent,
    ResponseWebSearchCallCompletedEvent,
    ResponseWebSearchCallInProgressEvent,
    ResponseWebSearchCallSearchingEvent,
)
from openai.types.responses.response_code_interpreter_tool_call import OutputLogs
from openai.types.responses.response_function_web_search import ActionSearch
from openai.types.responses.response_output_item import ImageGenerationCall
from openai.types.responses.response_reasoning_item import Summary


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
            logprobs=[],
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
                logprobs=[],
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
            name=name,
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


def create_reasoning_item(
    id: str,
    output_index: int,
    reasoning_summary: list[list[str]] | list[str] | str | None = None,
) -> list[ResponseStreamEvent]:
    """Create a reasoning item."""

    if reasoning_summary is None:
        reasoning_summary = [[]]
    elif isinstance(reasoning_summary, str):
        reasoning_summary = [reasoning_summary]
    if isinstance(reasoning_summary, list) and all(
        isinstance(item, str) for item in reasoning_summary
    ):
        reasoning_summary = [reasoning_summary]

    events = [
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
        )
    ]

    for summary_index, summary in enumerate(reasoning_summary):
        events.append(
            ResponseReasoningSummaryPartAddedEvent(
                item_id=id,
                output_index=output_index,
                part={"text": "", "type": "summary_text"},
                sequence_number=0,
                summary_index=summary_index,
                type="response.reasoning_summary_part.added",
            )
        )
        events.extend(
            ResponseReasoningSummaryTextDeltaEvent(
                delta=delta,
                item_id=id,
                output_index=output_index,
                sequence_number=0,
                summary_index=summary_index,
                type="response.reasoning_summary_text.delta",
            )
            for delta in summary
        )
        events.extend(
            [
                ResponseReasoningSummaryTextDoneEvent(
                    item_id=id,
                    output_index=output_index,
                    sequence_number=0,
                    summary_index=summary_index,
                    text="".join(summary),
                    type="response.reasoning_summary_text.done",
                ),
                ResponseReasoningSummaryPartDoneEvent(
                    item_id=id,
                    output_index=output_index,
                    part={"text": "".join(summary), "type": "summary_text"},
                    sequence_number=0,
                    summary_index=summary_index,
                    type="response.reasoning_summary_part.done",
                ),
            ]
        )

    events.append(
        ResponseOutputItemDoneEvent(
            item=ResponseReasoningItem(
                id=id,
                summary=[
                    Summary(text="".join(summary), type="summary_text")
                    for summary in reasoning_summary
                ],
                type="reasoning",
                status=None,
                encrypted_content="AAABBB",
            ),
            output_index=output_index,
            sequence_number=0,
            type="response.output_item.done",
        ),
    )

    return events


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


def create_code_interpreter_item(
    id: str, code: str | list[str], output_index: int, logs: str | None = None
) -> list[ResponseStreamEvent]:
    """Create a message item."""
    if isinstance(code, str):
        code = [code]

    container_id = "cntr_A"
    events = [
        ResponseOutputItemAddedEvent(
            item=ResponseCodeInterpreterToolCall(
                id=id,
                code="",
                container_id=container_id,
                outputs=None,
                type="code_interpreter_call",
                status="in_progress",
            ),
            output_index=output_index,
            sequence_number=0,
            type="response.output_item.added",
        ),
        ResponseCodeInterpreterCallInProgressEvent(
            item_id=id,
            output_index=output_index,
            sequence_number=0,
            type="response.code_interpreter_call.in_progress",
        ),
    ]

    events.extend(
        ResponseCodeInterpreterCallCodeDeltaEvent(
            delta=delta,
            item_id=id,
            output_index=output_index,
            sequence_number=0,
            type="response.code_interpreter_call_code.delta",
        )
        for delta in code
    )

    code = "".join(code)

    events.extend(
        [
            ResponseCodeInterpreterCallCodeDoneEvent(
                item_id=id,
                output_index=output_index,
                code=code,
                sequence_number=0,
                type="response.code_interpreter_call_code.done",
            ),
            ResponseCodeInterpreterCallInterpretingEvent(
                item_id=id,
                output_index=output_index,
                sequence_number=0,
                type="response.code_interpreter_call.interpreting",
            ),
            ResponseCodeInterpreterCallCompletedEvent(
                item_id=id,
                output_index=output_index,
                sequence_number=0,
                type="response.code_interpreter_call.completed",
            ),
            ResponseOutputItemDoneEvent(
                item=ResponseCodeInterpreterToolCall(
                    id=id,
                    code=code,
                    container_id=container_id,
                    outputs=[OutputLogs(type="logs", logs=logs)] if logs else None,
                    status="completed",
                    type="code_interpreter_call",
                ),
                output_index=output_index,
                sequence_number=0,
                type="response.output_item.done",
            ),
        ]
    )

    return events


def create_image_gen_call_item(
    id: str, output_index: int, logs: str | None = None
) -> list[ResponseStreamEvent]:
    """Create a message item."""
    return [
        ResponseImageGenCallPartialImageEvent(
            item_id=id,
            output_index=output_index,
            partial_image_b64="QQ==",
            partial_image_index=0,
            sequence_number=0,
            type="response.image_generation_call.partial_image",
            size="1536x1024",
            quality="medium",
            background="transparent",
            output_format="png",
        ),
        ResponseImageGenCallCompletedEvent(
            item_id=id,
            output_index=output_index,
            sequence_number=0,
            type="response.image_generation_call.completed",
        ),
        ResponseOutputItemDoneEvent(
            item=ImageGenerationCall(
                id=id,
                result="QQ==",
                status="completed",
                type="image_generation_call",
                background="transparent",
                output_format="png",
                quality="medium",
                revised_prompt="Mock revised prompt.",
                size="1536x1024",
            ),
            output_index=output_index,
            sequence_number=0,
            type="response.output_item.done",
        ),
    ]
