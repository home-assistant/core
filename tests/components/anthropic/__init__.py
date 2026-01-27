"""Tests for the Anthropic integration."""

from anthropic.types import (
    CitationsDelta,
    InputJSONDelta,
    RawContentBlockDeltaEvent,
    RawContentBlockStartEvent,
    RawContentBlockStopEvent,
    RawMessageStreamEvent,
    RedactedThinkingBlock,
    ServerToolUseBlock,
    SignatureDelta,
    TextBlock,
    TextCitation,
    TextDelta,
    ThinkingBlock,
    ThinkingDelta,
    ToolUseBlock,
    WebSearchResultBlock,
    WebSearchToolResultBlock,
)


def create_content_block(
    index: int, text_parts: list[str], citations: list[TextCitation] | None = None
) -> list[RawMessageStreamEvent]:
    """Create a text content block with the specified deltas."""
    return [
        RawContentBlockStartEvent(
            type="content_block_start",
            content_block=TextBlock(
                text="", type="text", citations=[] if citations else None
            ),
            index=index,
        ),
        *[
            RawContentBlockDeltaEvent(
                delta=CitationsDelta(citation=citation, type="citations_delta"),
                index=index,
                type="content_block_delta",
            )
            for citation in (citations or [])
        ],
        *[
            RawContentBlockDeltaEvent(
                delta=TextDelta(text=text_part, type="text_delta"),
                index=index,
                type="content_block_delta",
            )
            for text_part in text_parts
        ],
        RawContentBlockStopEvent(index=index, type="content_block_stop"),
    ]


def create_thinking_block(
    index: int, thinking_parts: list[str]
) -> list[RawMessageStreamEvent]:
    """Create a thinking block with the specified deltas."""
    return [
        RawContentBlockStartEvent(
            type="content_block_start",
            content_block=ThinkingBlock(signature="", thinking="", type="thinking"),
            index=index,
        ),
        *[
            RawContentBlockDeltaEvent(
                delta=ThinkingDelta(thinking=thinking_part, type="thinking_delta"),
                index=index,
                type="content_block_delta",
            )
            for thinking_part in thinking_parts
        ],
        RawContentBlockDeltaEvent(
            delta=SignatureDelta(
                signature="ErUBCkYIARgCIkCYXaVNJShe3A86Hp7XUzh9YsCYBbJTbQsrklTAPtJ2sP/N"
                "oB6tSzpK/nTL6CjSo2R6n0KNBIg5MH6asM2R/kmaEgyB/X1FtZq5OQAC7jUaDEPWCdcwGQ"
                "4RaBy5wiIwmRxExIlDhoY6tILoVPnOExkC/0igZxHEwxK8RU/fmw0b+o+TwAarzUitwzbo"
                "21E5Kh3pa3I6yqVROf1t2F8rFocNUeCegsWV/ytwYV+ayA==",
                type="signature_delta",
            ),
            index=index,
            type="content_block_delta",
        ),
        RawContentBlockStopEvent(index=index, type="content_block_stop"),
    ]


def create_redacted_thinking_block(index: int) -> list[RawMessageStreamEvent]:
    """Create a redacted thinking block."""
    return [
        RawContentBlockStartEvent(
            type="content_block_start",
            content_block=RedactedThinkingBlock(
                data="EroBCkYIARgCKkBJDytPJhw//4vy3t7aE+LfIkxvkAh51cBPrAvBCo6AjgI57Zt9K"
                "WPnUVV50OQJ0KZzUFoGZG5sxg95zx4qMwkoEgz43Su3myJKckvj03waDBZLIBSeoAeRUeV"
                "sJCIwQ5edQN0sa+HNeB/KUBkoMUwV+IT0eIhcpFxnILdvxUAKM4R1o4KG3x+yO0eo/kyOK"
                "iKfrCPFQhvBVmTZPFhgA2Ow8L9gGDVipcz6x3Uu9YETGEny",
                type="redacted_thinking",
            ),
            index=index,
        ),
        RawContentBlockStopEvent(index=index, type="content_block_stop"),
    ]


def create_tool_use_block(
    index: int, tool_id: str, tool_name: str, json_parts: list[str]
) -> list[RawMessageStreamEvent]:
    """Create a tool use content block with the specified deltas."""
    return [
        RawContentBlockStartEvent(
            type="content_block_start",
            content_block=ToolUseBlock(
                id=tool_id, name=tool_name, input={}, type="tool_use"
            ),
            index=index,
        ),
        *[
            RawContentBlockDeltaEvent(
                delta=InputJSONDelta(partial_json=json_part, type="input_json_delta"),
                index=index,
                type="content_block_delta",
            )
            for json_part in json_parts
        ],
        RawContentBlockStopEvent(index=index, type="content_block_stop"),
    ]


def create_web_search_block(
    index: int, id: str, query_parts: list[str]
) -> list[RawMessageStreamEvent]:
    """Create a server tool use block for web search."""
    return [
        RawContentBlockStartEvent(
            type="content_block_start",
            content_block=ServerToolUseBlock(
                type="server_tool_use", id=id, input={}, name="web_search"
            ),
            index=index,
        ),
        *[
            RawContentBlockDeltaEvent(
                delta=InputJSONDelta(type="input_json_delta", partial_json=query_part),
                index=index,
                type="content_block_delta",
            )
            for query_part in query_parts
        ],
        RawContentBlockStopEvent(index=index, type="content_block_stop"),
    ]


def create_web_search_result_block(
    index: int, id: str, results: list[WebSearchResultBlock]
) -> list[RawMessageStreamEvent]:
    """Create a server tool result block for web search results."""
    return [
        RawContentBlockStartEvent(
            type="content_block_start",
            content_block=WebSearchToolResultBlock(
                type="web_search_tool_result", tool_use_id=id, content=results
            ),
            index=index,
        ),
        RawContentBlockStopEvent(index=index, type="content_block_stop"),
    ]
