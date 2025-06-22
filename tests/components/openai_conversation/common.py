"""Common utilities for OpenAI conversation tests."""

from openai.types.responses import (
    ResponseContentPartAddedEvent,
    ResponseContentPartDoneEvent,
    ResponseOutputItemAddedEvent,
    ResponseOutputItemDoneEvent,
    ResponseOutputMessage,
    ResponseOutputText,
    ResponseStreamEvent,
    ResponseTextDeltaEvent,
    ResponseTextDoneEvent,
)


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
            type="response.output_item.added",
        ),
        ResponseContentPartAddedEvent(
            content_index=0,
            item_id=id,
            output_index=output_index,
            part=content,
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
                type="response.output_text.done",
            ),
            ResponseContentPartDoneEvent(
                content_index=0,
                item_id=id,
                output_index=output_index,
                part=content,
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
                type="response.output_item.done",
            ),
        ]
    )

    return events
