"""Tests for the Anthropic integration."""

import datetime
from typing import Any

from anthropic.types import (
    BashCodeExecutionOutputBlock,
    BashCodeExecutionResultBlock,
    BashCodeExecutionToolResultBlock,
    BashCodeExecutionToolResultError,
    BashCodeExecutionToolResultErrorCode,
    CapabilitySupport,
    CitationsDelta,
    CodeExecutionToolResultBlock,
    CodeExecutionToolResultBlockContent,
    ContextManagementCapability,
    DirectCaller,
    EffortCapability,
    InputJSONDelta,
    ModelCapabilities,
    ModelInfo,
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
    TextEditorCodeExecutionToolResultBlock,
    ThinkingBlock,
    ThinkingCapability,
    ThinkingDelta,
    ThinkingTypes,
    ToolSearchToolResultBlock,
    ToolUseBlock,
    WebSearchResultBlock,
    WebSearchToolResultBlock,
    WebSearchToolResultError,
)
from anthropic.types.server_tool_use_block import Caller
from anthropic.types.text_editor_code_execution_tool_result_block import (
    Content as TextEditorCodeExecutionToolResultBlockContent,
)
from anthropic.types.tool_search_tool_result_block import (
    Content as ToolSearchToolResultBlockContent,
)

model_list = [
    ModelInfo(
        id="claude-opus-4-7",
        capabilities=ModelCapabilities(
            batch=CapabilitySupport(supported=True),
            citations=CapabilitySupport(supported=True),
            code_execution=CapabilitySupport(supported=True),
            context_management=ContextManagementCapability(
                clear_thinking_20251015=CapabilitySupport(supported=True),
                clear_tool_uses_20250919=CapabilitySupport(supported=True),
                compact_20260112=CapabilitySupport(supported=True),
                supported=True,
            ),
            effort=EffortCapability(
                high=CapabilitySupport(supported=True),
                low=CapabilitySupport(supported=True),
                max=CapabilitySupport(supported=True),
                medium=CapabilitySupport(supported=True),
                supported=True,
                xhigh=CapabilitySupport(supported=True),
            ),
            image_input=CapabilitySupport(supported=True),
            pdf_input=CapabilitySupport(supported=True),
            structured_outputs=CapabilitySupport(supported=True),
            thinking=ThinkingCapability(
                supported=True,
                types=ThinkingTypes(
                    adaptive=CapabilitySupport(supported=True),
                    enabled=CapabilitySupport(supported=False),
                ),
            ),
        ),
        created_at=datetime.datetime(2026, 4, 14, 0, 0, tzinfo=datetime.UTC),
        display_name="Claude Opus 4.7",
        max_input_tokens=1000000,
        max_tokens=128000,
        type="model",
    ),
    ModelInfo(
        id="claude-sonnet-4-6",
        capabilities=ModelCapabilities(
            batch=CapabilitySupport(supported=True),
            citations=CapabilitySupport(supported=True),
            code_execution=CapabilitySupport(supported=True),
            context_management=ContextManagementCapability(
                clear_thinking_20251015=CapabilitySupport(supported=True),
                clear_tool_uses_20250919=CapabilitySupport(supported=True),
                compact_20260112=CapabilitySupport(supported=True),
                supported=True,
            ),
            effort=EffortCapability(
                high=CapabilitySupport(supported=True),
                low=CapabilitySupport(supported=True),
                max=CapabilitySupport(supported=True),
                medium=CapabilitySupport(supported=True),
                supported=True,
                xhigh=None,
            ),
            image_input=CapabilitySupport(supported=True),
            pdf_input=CapabilitySupport(supported=True),
            structured_outputs=CapabilitySupport(supported=True),
            thinking=ThinkingCapability(
                supported=True,
                types=ThinkingTypes(
                    adaptive=CapabilitySupport(supported=True),
                    enabled=CapabilitySupport(supported=True),
                ),
            ),
        ),
        created_at=datetime.datetime(2026, 2, 17, 0, 0, tzinfo=datetime.UTC),
        display_name="Claude Sonnet 4.6",
        max_input_tokens=1000000,
        max_tokens=128000,
        type="model",
    ),
    ModelInfo(
        id="claude-opus-4-6",
        capabilities=ModelCapabilities(
            batch=CapabilitySupport(supported=True),
            citations=CapabilitySupport(supported=True),
            code_execution=CapabilitySupport(supported=True),
            context_management=ContextManagementCapability(
                clear_thinking_20251015=CapabilitySupport(supported=True),
                clear_tool_uses_20250919=CapabilitySupport(supported=True),
                compact_20260112=CapabilitySupport(supported=True),
                supported=True,
            ),
            effort=EffortCapability(
                high=CapabilitySupport(supported=True),
                low=CapabilitySupport(supported=True),
                max=CapabilitySupport(supported=True),
                medium=CapabilitySupport(supported=True),
                supported=True,
                xhigh=None,
            ),
            image_input=CapabilitySupport(supported=True),
            pdf_input=CapabilitySupport(supported=True),
            structured_outputs=CapabilitySupport(supported=True),
            thinking=ThinkingCapability(
                supported=True,
                types=ThinkingTypes(
                    adaptive=CapabilitySupport(supported=True),
                    enabled=CapabilitySupport(supported=True),
                ),
            ),
        ),
        created_at=datetime.datetime(2026, 2, 4, 0, 0, tzinfo=datetime.UTC),
        display_name="Claude Opus 4.6",
        max_input_tokens=1000000,
        max_tokens=128000,
        type="model",
    ),
    ModelInfo(
        id="claude-opus-4-5-20251101",
        capabilities=ModelCapabilities(
            batch=CapabilitySupport(supported=True),
            citations=CapabilitySupport(supported=True),
            code_execution=CapabilitySupport(supported=True),
            context_management=ContextManagementCapability(
                clear_thinking_20251015=CapabilitySupport(supported=True),
                clear_tool_uses_20250919=CapabilitySupport(supported=True),
                compact_20260112=CapabilitySupport(supported=False),
                supported=True,
            ),
            effort=EffortCapability(
                high=CapabilitySupport(supported=True),
                low=CapabilitySupport(supported=True),
                max=CapabilitySupport(supported=False),
                medium=CapabilitySupport(supported=True),
                supported=True,
                xhigh=None,
            ),
            image_input=CapabilitySupport(supported=True),
            pdf_input=CapabilitySupport(supported=True),
            structured_outputs=CapabilitySupport(supported=True),
            thinking=ThinkingCapability(
                supported=True,
                types=ThinkingTypes(
                    adaptive=CapabilitySupport(supported=False),
                    enabled=CapabilitySupport(supported=True),
                ),
            ),
        ),
        created_at=datetime.datetime(2025, 11, 24, 0, 0, tzinfo=datetime.UTC),
        display_name="Claude Opus 4.5",
        max_input_tokens=200000,
        max_tokens=64000,
        type="model",
    ),
    ModelInfo(
        id="claude-haiku-4-5-20251001",
        capabilities=ModelCapabilities(
            batch=CapabilitySupport(supported=True),
            citations=CapabilitySupport(supported=True),
            code_execution=CapabilitySupport(supported=False),
            context_management=ContextManagementCapability(
                clear_thinking_20251015=CapabilitySupport(supported=True),
                clear_tool_uses_20250919=CapabilitySupport(supported=True),
                compact_20260112=CapabilitySupport(supported=False),
                supported=True,
            ),
            effort=EffortCapability(
                high=CapabilitySupport(supported=False),
                low=CapabilitySupport(supported=False),
                max=CapabilitySupport(supported=False),
                medium=CapabilitySupport(supported=False),
                supported=False,
                xhigh=None,
            ),
            image_input=CapabilitySupport(supported=True),
            pdf_input=CapabilitySupport(supported=True),
            structured_outputs=CapabilitySupport(supported=True),
            thinking=ThinkingCapability(
                supported=True,
                types=ThinkingTypes(
                    adaptive=CapabilitySupport(supported=False),
                    enabled=CapabilitySupport(supported=True),
                ),
            ),
        ),
        created_at=datetime.datetime(2025, 10, 15, 0, 0, tzinfo=datetime.UTC),
        display_name="Claude Haiku 4.5",
        max_input_tokens=200000,
        max_tokens=64000,
        type="model",
    ),
    ModelInfo(
        id="claude-sonnet-4-5-20250929",
        capabilities=ModelCapabilities(
            batch=CapabilitySupport(supported=True),
            citations=CapabilitySupport(supported=True),
            code_execution=CapabilitySupport(supported=True),
            context_management=ContextManagementCapability(
                clear_thinking_20251015=CapabilitySupport(supported=True),
                clear_tool_uses_20250919=CapabilitySupport(supported=True),
                compact_20260112=CapabilitySupport(supported=False),
                supported=True,
            ),
            effort=EffortCapability(
                high=CapabilitySupport(supported=False),
                low=CapabilitySupport(supported=False),
                max=CapabilitySupport(supported=False),
                medium=CapabilitySupport(supported=False),
                supported=False,
                xhigh=None,
            ),
            image_input=CapabilitySupport(supported=True),
            pdf_input=CapabilitySupport(supported=True),
            structured_outputs=CapabilitySupport(supported=True),
            thinking=ThinkingCapability(
                supported=True,
                types=ThinkingTypes(
                    adaptive=CapabilitySupport(supported=False),
                    enabled=CapabilitySupport(supported=True),
                ),
            ),
        ),
        created_at=datetime.datetime(2025, 9, 29, 0, 0, tzinfo=datetime.UTC),
        display_name="Claude Sonnet 4.5",
        max_input_tokens=1000000,
        max_tokens=64000,
        type="model",
    ),
    ModelInfo(
        id="claude-opus-4-1-20250805",
        capabilities=ModelCapabilities(
            batch=CapabilitySupport(supported=True),
            citations=CapabilitySupport(supported=True),
            code_execution=CapabilitySupport(supported=False),
            context_management=ContextManagementCapability(
                clear_thinking_20251015=CapabilitySupport(supported=True),
                clear_tool_uses_20250919=CapabilitySupport(supported=True),
                compact_20260112=CapabilitySupport(supported=False),
                supported=True,
            ),
            effort=EffortCapability(
                high=CapabilitySupport(supported=False),
                low=CapabilitySupport(supported=False),
                max=CapabilitySupport(supported=False),
                medium=CapabilitySupport(supported=False),
                supported=False,
                xhigh=None,
            ),
            image_input=CapabilitySupport(supported=True),
            pdf_input=CapabilitySupport(supported=True),
            structured_outputs=CapabilitySupport(supported=True),
            thinking=ThinkingCapability(
                supported=True,
                types=ThinkingTypes(
                    adaptive=CapabilitySupport(supported=False),
                    enabled=CapabilitySupport(supported=True),
                ),
            ),
        ),
        created_at=datetime.datetime(2025, 8, 5, 0, 0, tzinfo=datetime.UTC),
        display_name="Claude Opus 4.1",
        max_input_tokens=200000,
        max_tokens=32000,
        type="model",
    ),
    ModelInfo(
        id="claude-opus-4-20250514",
        capabilities=ModelCapabilities(
            batch=CapabilitySupport(supported=True),
            citations=CapabilitySupport(supported=True),
            code_execution=CapabilitySupport(supported=False),
            context_management=ContextManagementCapability(
                clear_thinking_20251015=CapabilitySupport(supported=True),
                clear_tool_uses_20250919=CapabilitySupport(supported=True),
                compact_20260112=CapabilitySupport(supported=False),
                supported=True,
            ),
            effort=EffortCapability(
                high=CapabilitySupport(supported=False),
                low=CapabilitySupport(supported=False),
                max=CapabilitySupport(supported=False),
                medium=CapabilitySupport(supported=False),
                supported=False,
                xhigh=None,
            ),
            image_input=CapabilitySupport(supported=True),
            pdf_input=CapabilitySupport(supported=True),
            structured_outputs=CapabilitySupport(supported=False),
            thinking=ThinkingCapability(
                supported=True,
                types=ThinkingTypes(
                    adaptive=CapabilitySupport(supported=False),
                    enabled=CapabilitySupport(supported=True),
                ),
            ),
        ),
        created_at=datetime.datetime(2025, 5, 22, 0, 0, tzinfo=datetime.UTC),
        display_name="Claude Opus 4",
        max_input_tokens=200000,
        max_tokens=32000,
        type="model",
    ),
    ModelInfo(
        id="claude-sonnet-4-20250514",
        capabilities=ModelCapabilities(
            batch=CapabilitySupport(supported=True),
            citations=CapabilitySupport(supported=True),
            code_execution=CapabilitySupport(supported=False),
            context_management=ContextManagementCapability(
                clear_thinking_20251015=CapabilitySupport(supported=True),
                clear_tool_uses_20250919=CapabilitySupport(supported=True),
                compact_20260112=CapabilitySupport(supported=False),
                supported=True,
            ),
            effort=EffortCapability(
                high=CapabilitySupport(supported=False),
                low=CapabilitySupport(supported=False),
                max=CapabilitySupport(supported=False),
                medium=CapabilitySupport(supported=False),
                supported=False,
                xhigh=None,
            ),
            image_input=CapabilitySupport(supported=True),
            pdf_input=CapabilitySupport(supported=True),
            structured_outputs=CapabilitySupport(supported=False),
            thinking=ThinkingCapability(
                supported=True,
                types=ThinkingTypes(
                    adaptive=CapabilitySupport(supported=False),
                    enabled=CapabilitySupport(supported=True),
                ),
            ),
        ),
        created_at=datetime.datetime(2025, 5, 22, 0, 0, tzinfo=datetime.UTC),
        display_name="Claude Sonnet 4",
        max_input_tokens=1000000,
        max_tokens=64000,
        type="model",
    ),
    ModelInfo(
        id="claude-3-haiku-20240307",
        capabilities=ModelCapabilities(
            batch=CapabilitySupport(supported=True),
            citations=CapabilitySupport(supported=False),
            code_execution=CapabilitySupport(supported=False),
            context_management=ContextManagementCapability(
                clear_thinking_20251015=CapabilitySupport(supported=False),
                clear_tool_uses_20250919=CapabilitySupport(supported=False),
                compact_20260112=CapabilitySupport(supported=False),
                supported=False,
            ),
            effort=EffortCapability(
                high=CapabilitySupport(supported=False),
                low=CapabilitySupport(supported=False),
                max=CapabilitySupport(supported=False),
                medium=CapabilitySupport(supported=False),
                supported=False,
                xhigh=None,
            ),
            image_input=CapabilitySupport(supported=True),
            pdf_input=CapabilitySupport(supported=False),
            structured_outputs=CapabilitySupport(supported=False),
            thinking=ThinkingCapability(
                supported=False,
                types=ThinkingTypes(
                    adaptive=CapabilitySupport(supported=False),
                    enabled=CapabilitySupport(supported=False),
                ),
            ),
        ),
        created_at=datetime.datetime(2024, 3, 7, 0, 0, tzinfo=datetime.UTC),
        display_name="Claude Haiku 3",
        max_input_tokens=200000,
        max_tokens=4096,
        type="model",
    ),
]


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


def create_server_tool_use_block(
    index: int,
    id: str,
    name: str,
    input_parts: list[str] | dict[str, Any],
    caller: Caller | None = None,
) -> list[RawMessageStreamEvent]:
    """Create a server tool use block."""
    if caller is None:
        caller = DirectCaller(type="direct")

    return [
        RawContentBlockStartEvent(
            type="content_block_start",
            content_block=ServerToolUseBlock(
                type="server_tool_use",
                id=id,
                input=input_parts if isinstance(input_parts, dict) else {},
                name=name,
                caller=caller,
            ),
            index=index,
        ),
        *[
            RawContentBlockDeltaEvent(
                delta=InputJSONDelta(type="input_json_delta", partial_json=input_part),
                index=index,
                type="content_block_delta",
            )
            for input_part in (input_parts if isinstance(input_parts, list) else [])
        ],
        RawContentBlockStopEvent(index=index, type="content_block_stop"),
    ]


def create_web_search_result_block(
    index: int,
    id: str,
    results: list[WebSearchResultBlock] | WebSearchToolResultError,
    caller: Caller | None = None,
) -> list[RawMessageStreamEvent]:
    """Create a server tool result block for web search results."""
    if caller is None:
        caller = DirectCaller(type="direct")

    return [
        RawContentBlockStartEvent(
            type="content_block_start",
            content_block=WebSearchToolResultBlock(
                type="web_search_tool_result",
                tool_use_id=id,
                content=results,
                caller=caller,
            ),
            index=index,
        ),
        RawContentBlockStopEvent(index=index, type="content_block_stop"),
    ]


def create_code_execution_result_block(
    index: int, id: str, content: CodeExecutionToolResultBlockContent
) -> list[RawMessageStreamEvent]:
    """Create a server tool result block for code execution results."""
    return [
        RawContentBlockStartEvent(
            type="content_block_start",
            content_block=CodeExecutionToolResultBlock(
                type="code_execution_tool_result", tool_use_id=id, content=content
            ),
            index=index,
        ),
        RawContentBlockStopEvent(index=index, type="content_block_stop"),
    ]


def create_bash_code_execution_result_block(
    index: int,
    id: str,
    error_code: BashCodeExecutionToolResultErrorCode | None = None,
    content: list[BashCodeExecutionOutputBlock] | None = None,
    return_code: int = 0,
    stderr: str = "",
    stdout: str = "",
) -> list[RawMessageStreamEvent]:
    """Create a server tool result block for bash code execution results."""
    return [
        RawContentBlockStartEvent(
            type="content_block_start",
            content_block=BashCodeExecutionToolResultBlock(
                type="bash_code_execution_tool_result",
                content=BashCodeExecutionToolResultError(
                    type="bash_code_execution_tool_result_error",
                    error_code=error_code,
                )
                if error_code is not None
                else BashCodeExecutionResultBlock(
                    type="bash_code_execution_result",
                    content=content or [],
                    return_code=return_code,
                    stderr=stderr,
                    stdout=stdout,
                ),
                tool_use_id=id,
            ),
            index=index,
        ),
        RawContentBlockStopEvent(index=index, type="content_block_stop"),
    ]


def create_text_editor_code_execution_result_block(
    index: int,
    id: str,
    content: TextEditorCodeExecutionToolResultBlockContent,
) -> list[RawMessageStreamEvent]:
    """Create a server tool result block for text editor code execution results."""
    return [
        RawContentBlockStartEvent(
            type="content_block_start",
            content_block=TextEditorCodeExecutionToolResultBlock(
                type="text_editor_code_execution_tool_result",
                content=content,
                tool_use_id=id,
            ),
            index=index,
        ),
        RawContentBlockStopEvent(index=index, type="content_block_stop"),
    ]


def create_tool_search_result_block(
    index: int,
    id: str,
    results: ToolSearchToolResultBlockContent,
) -> list[RawMessageStreamEvent]:
    """Create a server tool result block for tool search results."""
    return [
        RawContentBlockStartEvent(
            type="content_block_start",
            content_block=ToolSearchToolResultBlock(
                type="tool_search_tool_result",
                tool_use_id=id,
                content=results,
            ),
            index=index,
        ),
        RawContentBlockStopEvent(index=index, type="content_block_stop"),
    ]
