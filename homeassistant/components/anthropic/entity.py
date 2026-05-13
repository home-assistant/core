"""Base entity for Anthropic."""

import base64
from collections import deque
from collections.abc import AsyncIterator, Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
from mimetypes import guess_file_type
from pathlib import Path
from typing import Any, Literal, cast

import anthropic
from anthropic import AsyncStream
from anthropic.types import (
    Base64ImageSourceParam,
    Base64PDFSourceParam,
    BashCodeExecutionToolResultBlock,
    CitationsDelta,
    CitationsWebSearchResultLocation,
    CitationWebSearchResultLocationParam,
    CodeExecutionTool20250825Param,
    CodeExecutionToolResultBlock,
    CodeExecutionToolResultBlockContent,
    CodeExecutionToolResultBlockParamContentParam,
    Container,
    ContentBlock,
    ContentBlockParam,
    DocumentBlockParam,
    ImageBlockParam,
    InputJSONDelta,
    JSONOutputFormatParam,
    Message,
    MessageDeltaUsage,
    MessageParam,
    MessageStreamEvent,
    ModelInfo,
    OutputConfigParam,
    RawContentBlockDelta,
    RawContentBlockDeltaEvent,
    RawContentBlockStartEvent,
    RawContentBlockStopEvent,
    RawMessageDeltaEvent,
    RawMessageStartEvent,
    RawMessageStopEvent,
    RedactedThinkingBlock,
    RedactedThinkingBlockParam,
    ServerToolUseBlock,
    ServerToolUseBlockParam,
    SignatureDelta,
    TextBlock,
    TextBlockParam,
    TextCitation,
    TextCitationParam,
    TextDelta,
    TextEditorCodeExecutionToolResultBlock,
    ThinkingBlock,
    ThinkingBlockParam,
    ThinkingConfigAdaptiveParam,
    ThinkingConfigDisabledParam,
    ThinkingConfigEnabledParam,
    ThinkingDelta,
    ToolChoiceAnyParam,
    ToolChoiceAutoParam,
    ToolChoiceToolParam,
    ToolParam,
    ToolSearchToolBm25_20251119Param,
    ToolSearchToolResultBlock,
    ToolUnionParam,
    ToolUseBlock,
    ToolUseBlockParam,
    Usage,
    WebSearchTool20250305Param,
    WebSearchTool20260209Param,
    WebSearchToolResultBlock,
    WebSearchToolResultBlockContent,
    WebSearchToolResultBlockParamContentParam,
)
from anthropic.types.bash_code_execution_tool_result_block import (
    Content as BashCodeExecutionToolResultBlockContent,
)
from anthropic.types.bash_code_execution_tool_result_block_param import (
    Content as BashCodeExecutionToolResultBlockParamContentParam,
)
from anthropic.types.message_create_params import MessageCreateParamsStreaming
from anthropic.types.raw_message_delta_event import Delta
from anthropic.types.text_editor_code_execution_tool_result_block import (
    Content as TextEditorCodeExecutionToolResultBlockContent,
)
from anthropic.types.text_editor_code_execution_tool_result_block_param import (
    Content as TextEditorCodeExecutionToolResultBlockParamContentParam,
)
from anthropic.types.tool_search_tool_result_block import (
    Content as ToolSearchToolResultBlockContent,
)
from anthropic.types.tool_search_tool_result_block_param import (
    Content as ToolSearchToolResultBlockParamContentParam,
)
from anthropic.types.tool_use_block import Caller
import voluptuous as vol
from voluptuous_openapi import convert

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, llm
from homeassistant.helpers.json import json_dumps
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify
from homeassistant.util.json import JsonArrayType, JsonObjectType

from .const import (
    CONF_CHAT_MODEL,
    CONF_CODE_EXECUTION,
    CONF_MAX_TOKENS,
    CONF_PROMPT_CACHING,
    CONF_THINKING_BUDGET,
    CONF_THINKING_EFFORT,
    CONF_TOOL_SEARCH,
    CONF_WEB_SEARCH,
    CONF_WEB_SEARCH_CITY,
    CONF_WEB_SEARCH_COUNTRY,
    CONF_WEB_SEARCH_MAX_USES,
    CONF_WEB_SEARCH_REGION,
    CONF_WEB_SEARCH_TIMEZONE,
    CONF_WEB_SEARCH_USER_LOCATION,
    DEFAULT,
    DOMAIN,
    LOGGER,
    MIN_THINKING_BUDGET,
    PromptCaching,
)
from .coordinator import AnthropicConfigEntry, AnthropicCoordinator

# Max number of back and forth with the LLM to generate a response
MAX_TOOL_ITERATIONS = 10


def _format_tool(
    tool: llm.Tool, custom_serializer: Callable[[Any], Any] | None
) -> ToolParam:
    """Format tool specification."""
    unsupported_keys = {"oneOf", "anyOf", "allOf"}
    schema = convert(tool.parameters, custom_serializer=custom_serializer)
    schema = {k: v for k, v in schema.items() if k not in unsupported_keys}

    return ToolParam(
        name=tool.name,
        description=tool.description or "",
        input_schema=schema,
    )


@dataclass(slots=True)
class CitationDetails:
    """Citation details for a content part."""

    index: int = 0
    """Start position of the text."""

    length: int = 0
    """Length of the relevant data."""

    citations: list[TextCitationParam] = field(default_factory=list)
    """Citations for the content part."""


@dataclass(slots=True)
class ContentDetails:
    """Native data for AssistantContent."""

    citation_details: list[CitationDetails] = field(default_factory=list)
    thinking_signature: str | None = None
    redacted_thinking: str | None = None
    container: Container | None = None

    def has_content(self) -> bool:
        """Check if there is any text content."""
        return any(detail.length > 0 for detail in self.citation_details)

    def __bool__(self) -> bool:
        """Check if there is any thinking content or citations."""
        return (
            self.thinking_signature is not None
            or self.redacted_thinking is not None
            or self.container is not None
            or self.has_citations()
        )

    def has_citations(self) -> bool:
        """Check if there are any citations."""
        return any(detail.citations for detail in self.citation_details)

    def add_citation_detail(self) -> None:
        """Add a new citation detail."""
        if not self.citation_details or self.citation_details[-1].length > 0:
            self.citation_details.append(
                CitationDetails(
                    index=self.citation_details[-1].index
                    + self.citation_details[-1].length
                    if self.citation_details
                    else 0
                )
            )

    def add_citation(self, citation: TextCitation) -> None:
        """Add a citation to the current detail."""
        if not self.citation_details:
            self.citation_details.append(CitationDetails())
        citation_param: TextCitationParam | None = None
        if isinstance(citation, CitationsWebSearchResultLocation):
            citation_param = CitationWebSearchResultLocationParam(
                type="web_search_result_location",
                title=citation.title,
                url=citation.url,
                cited_text=citation.cited_text,
                encrypted_index=citation.encrypted_index,
            )
        if citation_param:
            self.citation_details[-1].citations.append(citation_param)

    def delete_empty(self) -> None:
        """Delete empty citation details."""
        self.citation_details = [
            detail for detail in self.citation_details if detail.citations
        ]


def _convert_content(  # noqa: C901
    chat_content: Iterable[conversation.Content],
) -> tuple[list[MessageParam], str | None]:
    """Transform HA chat_log content into Anthropic API format."""
    messages: list[MessageParam] = []
    container_id: str | None = None

    for content in chat_content:
        if isinstance(content, conversation.ToolResultContent):
            external_tool = True
            if content.tool_name == "web_search":
                tool_result_block: ContentBlockParam = {
                    "type": "web_search_tool_result",
                    "tool_use_id": content.tool_call_id,
                    "content": cast(
                        WebSearchToolResultBlockParamContentParam,
                        content.tool_result["content"]
                        if "content" in content.tool_result
                        else {
                            "type": "web_search_tool_result_error",
                            "error_code": content.tool_result.get(
                                "error_code", "unavailable"
                            ),
                        },
                    ),
                }
            elif content.tool_name == "code_execution":
                tool_result_block = {
                    "type": "code_execution_tool_result",
                    "tool_use_id": content.tool_call_id,
                    "content": cast(
                        CodeExecutionToolResultBlockParamContentParam,
                        content.tool_result,
                    ),
                }
            elif content.tool_name == "bash_code_execution":
                tool_result_block = {
                    "type": "bash_code_execution_tool_result",
                    "tool_use_id": content.tool_call_id,
                    "content": cast(
                        BashCodeExecutionToolResultBlockParamContentParam,
                        content.tool_result,
                    ),
                }
            elif content.tool_name == "text_editor_code_execution":
                tool_result_block = {
                    "type": "text_editor_code_execution_tool_result",
                    "tool_use_id": content.tool_call_id,
                    "content": cast(
                        TextEditorCodeExecutionToolResultBlockParamContentParam,
                        content.tool_result,
                    ),
                }
            elif content.tool_name == "tool_search":
                tool_result_block = {
                    "type": "tool_search_tool_result",
                    "tool_use_id": content.tool_call_id,
                    "content": cast(
                        ToolSearchToolResultBlockParamContentParam,
                        content.tool_result,
                    ),
                }
            else:
                tool_result_block = {
                    "type": "tool_result",
                    "tool_use_id": content.tool_call_id,
                    "content": json_dumps(content.tool_result),
                }
                external_tool = False
            if not messages or messages[-1]["role"] != (
                "assistant" if external_tool else "user"
            ):
                messages.append(
                    MessageParam(
                        role="assistant" if external_tool else "user",
                        content=[tool_result_block],
                    )
                )
            elif isinstance(messages[-1]["content"], str):
                messages[-1]["content"] = [
                    TextBlockParam(type="text", text=messages[-1]["content"]),
                    tool_result_block,
                ]
            else:
                messages[-1]["content"].append(tool_result_block)  # type: ignore[attr-defined]
        elif isinstance(content, conversation.UserContent):
            # Combine consequent user messages
            if not messages or messages[-1]["role"] != "user":
                messages.append(
                    MessageParam(
                        role="user",
                        content=content.content,
                    )
                )
            elif isinstance(messages[-1]["content"], str):
                messages[-1]["content"] = [
                    TextBlockParam(type="text", text=messages[-1]["content"]),
                    TextBlockParam(type="text", text=content.content),
                ]
            else:
                messages[-1]["content"].append(  # type: ignore[attr-defined]
                    TextBlockParam(type="text", text=content.content)
                )
        elif isinstance(content, conversation.AssistantContent):
            # Combine consequent assistant messages
            if not messages or messages[-1]["role"] != "assistant":
                messages.append(
                    MessageParam(
                        role="assistant",
                        content=[],
                    )
                )
            elif isinstance(messages[-1]["content"], str):
                messages[-1]["content"] = [
                    TextBlockParam(type="text", text=messages[-1]["content"]),
                ]

            if isinstance(content.native, ContentDetails):
                if content.native.thinking_signature:
                    messages[-1]["content"].append(  # type: ignore[union-attr]
                        ThinkingBlockParam(
                            type="thinking",
                            thinking=content.thinking_content or "",
                            signature=content.native.thinking_signature,
                        )
                    )
                if content.native.redacted_thinking:
                    messages[-1]["content"].append(  # type: ignore[union-attr]
                        RedactedThinkingBlockParam(
                            type="redacted_thinking",
                            data=content.native.redacted_thinking,
                        )
                    )
                if (
                    content.native.container is not None
                    and content.native.container.expires_at > datetime.now(UTC)
                ):
                    container_id = content.native.container.id

            if content.content:
                current_index = 0
                for detail in (
                    content.native.citation_details
                    if isinstance(content.native, ContentDetails)
                    else [CitationDetails(length=len(content.content))]
                ):
                    if detail.index > current_index:
                        # Add text block for any text without citations
                        messages[-1]["content"].append(  # type: ignore[union-attr]
                            TextBlockParam(
                                type="text",
                                text=content.content[current_index : detail.index],
                            )
                        )
                    messages[-1]["content"].append(  # type: ignore[union-attr]
                        TextBlockParam(
                            type="text",
                            text=content.content[
                                detail.index : detail.index + detail.length
                            ],
                            citations=detail.citations,
                        )
                        if detail.citations
                        else TextBlockParam(
                            type="text",
                            text=content.content[
                                detail.index : detail.index + detail.length
                            ],
                        )
                    )
                    current_index = detail.index + detail.length
                if current_index < len(content.content):
                    # Add text block for any remaining text without citations
                    messages[-1]["content"].append(  # type: ignore[union-attr]
                        TextBlockParam(
                            type="text",
                            text=content.content[current_index:],
                        )
                    )

            if content.tool_calls:
                messages[-1]["content"].extend(  # type: ignore[union-attr]
                    [
                        ServerToolUseBlockParam(
                            type="server_tool_use",
                            id=tool_call.id,
                            name=cast(
                                Literal[
                                    "web_search",
                                    "code_execution",
                                    "bash_code_execution",
                                    "text_editor_code_execution",
                                    "tool_search_tool_bm25",
                                ],
                                tool_call.tool_name,
                            ),
                            input=tool_call.tool_args,
                        )
                        if tool_call.external
                        and tool_call.tool_name
                        in [
                            "web_search",
                            "code_execution",
                            "bash_code_execution",
                            "text_editor_code_execution",
                            "tool_search_tool_bm25",
                        ]
                        else ToolUseBlockParam(
                            type="tool_use",
                            id=tool_call.id,
                            name=tool_call.tool_name,
                            input=tool_call.tool_args,
                        )
                        for tool_call in content.tool_calls
                    ]
                )

            if (
                isinstance(messages[-1]["content"], list)
                and len(messages[-1]["content"]) == 1
                and messages[-1]["content"][0]["type"] == "text"
            ):
                # If there is only one text block, simplify the content to a string
                messages[-1]["content"] = messages[-1]["content"][0]["text"]
        else:
            # Note: We don't pass SystemContent here as it's passed to the API as the prompt
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unexpected_chat_log_content",
                translation_placeholders={"type": type(content).__name__},
            )

    return messages, container_id


class AnthropicDeltaStream:
    """Transform the response stream into HA format.

    A typical stream of responses might look something like the following:
    - RawMessageStartEvent with no content
    - RawContentBlockStartEvent with an empty ThinkingBlock (if extended thinking is enabled)
    - RawContentBlockDeltaEvent with a ThinkingDelta
    - RawContentBlockDeltaEvent with a ThinkingDelta
    - RawContentBlockDeltaEvent with a ThinkingDelta
    - ...
    - RawContentBlockDeltaEvent with a SignatureDelta
    - RawContentBlockStopEvent
    - RawContentBlockStartEvent with a RedactedThinkingBlock (occasionally)
    - RawContentBlockStopEvent (RedactedThinkingBlock does not have a delta)
    - RawContentBlockStartEvent with an empty TextBlock
    - RawContentBlockDeltaEvent with a TextDelta
    - RawContentBlockDeltaEvent with a TextDelta
    - RawContentBlockDeltaEvent with a TextDelta
    - ...
    - RawContentBlockStopEvent
    - RawContentBlockStartEvent with ToolUseBlock specifying the function name
    - RawContentBlockDeltaEvent with a InputJSONDelta
    - RawContentBlockDeltaEvent with a InputJSONDelta
    - ...
    - RawContentBlockStopEvent
    - RawMessageDeltaEvent with a stop_reason='tool_use'
    - RawMessageStopEvent(type='message_stop')

    Each message could contain multiple blocks of the same type.
    """

    def __init__(
        self,
        chat_log: conversation.ChatLog,
        stream: AsyncStream[MessageStreamEvent],
        output_tool: str | None = None,
    ) -> None:
        """Initialize the delta stream."""
        self._chat_log: conversation.ChatLog = chat_log
        self._stream: AsyncStream[MessageStreamEvent] = stream
        self._output_tool: str | None = output_tool

        self._buffer: deque[
            conversation.AssistantContentDeltaDict
            | conversation.ToolResultContentDeltaDict
        ] = deque()
        self._stream_iterator: AsyncIterator[MessageStreamEvent] | None = None

        self._current_tool_block: ToolUseBlockParam | ServerToolUseBlockParam | None = (
            None
        )
        self._current_tool_args: str = ""
        self._content_details = ContentDetails()
        self._content_details.add_citation_detail()
        self._input_usage: Usage | None = None
        self._first_block: bool = True

    def __aiter__(
        self,
    ) -> AsyncIterator[
        conversation.AssistantContentDeltaDict | conversation.ToolResultContentDeltaDict
    ]:
        """Initialize the stream and return the async iterator."""
        if self._stream is None or not hasattr(self._stream, "__aiter__"):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="unexpected_stream_object"
            )
        if self._stream_iterator is None:
            self._stream_iterator = self._stream.__aiter__()
        return self

    async def __anext__(
        self,
    ) -> (
        conversation.AssistantContentDeltaDict | conversation.ToolResultContentDeltaDict
    ):
        """Get the next item from the stream."""
        while True:
            if self._buffer:
                return self._buffer.popleft()

            response = await self._stream_iterator.__anext__()  # type: ignore[union-attr]

            LOGGER.debug("Received response: %s", response)
            self.on_message_stream_event(response)

    def on_message_stream_event(self, event: MessageStreamEvent) -> None:
        """Handle MessageStreamEvent."""
        if isinstance(event, RawMessageStartEvent):
            self.on_message_start_event(event.message)
            return
        if isinstance(event, RawContentBlockStartEvent):
            self.on_content_block_start_event(event.content_block, event.index)
            return
        if isinstance(event, RawContentBlockDeltaEvent):
            self.on_content_block_delta_event(event.delta)
            return
        if isinstance(event, RawContentBlockStopEvent):
            self.on_content_block_stop_event(event.index)
            return
        if isinstance(event, RawMessageDeltaEvent):
            self.on_message_delta_event(event.delta, event.usage)
            return
        if isinstance(event, RawMessageStopEvent):
            self.on_message_stop_event()
            return
        LOGGER.debug("Unhandled event type: %s", event.type)  # type: ignore[unreachable]  # pragma: no cover - All types are handled but we want to verify that

    def on_message_start_event(self, message: Message) -> None:
        """Handle RawMessageStartEvent."""
        self._input_usage = message.usage
        self._first_block = True

    def on_content_block_start_event(
        self, content_block: ContentBlock, index: int
    ) -> None:
        """Handle RawContentBlockStartEvent."""
        if isinstance(content_block, ToolUseBlock):
            self.on_tool_use_block(
                content_block.id,
                content_block.input,
                content_block.name,
                content_block.caller,
            )
            return
        if isinstance(content_block, TextBlock):
            self.on_text_block(content_block.text, content_block.citations)
            return
        if isinstance(content_block, ThinkingBlock):
            self.on_thinking_block(content_block.thinking, content_block.signature)
            return
        if isinstance(content_block, RedactedThinkingBlock):
            self.on_redacted_thinking_block(content_block.data)
            return
        if isinstance(content_block, ServerToolUseBlock):
            self.on_server_tool_use_block(
                content_block.id,
                content_block.name,
                content_block.input,
                content_block.caller,
            )
            return
        if isinstance(
            content_block,
            (
                WebSearchToolResultBlock,
                CodeExecutionToolResultBlock,
                BashCodeExecutionToolResultBlock,
                TextEditorCodeExecutionToolResultBlock,
                ToolSearchToolResultBlock,
            ),
        ):
            self.on_server_tool_result_block(
                content_block.tool_use_id,
                content_block.type,
                content_block.content,
                content_block.caller if hasattr(content_block, "caller") else None,
            )
            return
        LOGGER.debug("Unhandled content block type: %s", content_block.type)

    def on_tool_use_block(
        self, id: str, input: dict[str, Any], name: str, caller: Caller | None
    ) -> None:
        """Handle ToolUseBlock."""
        self._current_tool_block = ToolUseBlockParam(
            type="tool_use",
            id=id,
            name=name,
            input=input,
        )
        self._current_tool_args = ""
        if name == self._output_tool:
            if self._first_block or self._content_details.has_content():
                if self._content_details:
                    self._content_details.delete_empty()
                    self._buffer.append({"native": self._content_details})
                self._content_details = ContentDetails()
                self._content_details.add_citation_detail()
                self._buffer.append({"role": "assistant"})
                self._first_block = False

    def on_text_block(self, text: str, citations: list[TextCitation] | None) -> None:
        """Handle TextBlock."""
        if (  # Do not start a new assistant content just for citations, concatenate consecutive blocks with citations instead.
            self._first_block
            or (
                not self._content_details.has_citations()
                and citations is None
                and self._content_details.has_content()
            )
        ):
            if self._content_details:
                self._content_details.delete_empty()
                self._buffer.append({"native": self._content_details})
            self._content_details = ContentDetails()
            self._buffer.append({"role": "assistant"})
            self._first_block = False
        self._content_details.add_citation_detail()
        if text:
            self._content_details.citation_details[-1].length += len(text)
            self._buffer.append({"content": text})

    def on_thinking_block(self, thinking: str, signature: str) -> None:
        """Handle ThinkingBlock."""
        if self._first_block or self._content_details.thinking_signature:
            if self._content_details:
                self._content_details.delete_empty()
                self._buffer.append({"native": self._content_details})
            self._content_details = ContentDetails()
            self._content_details.add_citation_detail()
            self._buffer.append({"role": "assistant"})
            self._first_block = False

    def on_redacted_thinking_block(self, data: str) -> None:
        """Handle RedactedThinkingBlock."""
        LOGGER.debug(
            "Some of Claude’s internal reasoning has been automatically "
            "encrypted for safety reasons. This doesn’t affect the quality of "
            "responses"
        )
        if self._first_block or self._content_details.redacted_thinking:
            if self._content_details:
                self._content_details.delete_empty()
                self._buffer.append({"native": self._content_details})
            self._content_details = ContentDetails()
            self._content_details.add_citation_detail()
            self._buffer.append({"role": "assistant"})
            self._first_block = False
        self._content_details.redacted_thinking = data

    def on_server_tool_use_block(
        self,
        id: str,
        name: Literal[
            "web_search",
            "web_fetch",
            "code_execution",
            "bash_code_execution",
            "text_editor_code_execution",
            "tool_search_tool_regex",
            "tool_search_tool_bm25",
        ],
        input: dict[str, Any],
        caller: Caller | None,
    ) -> None:
        """Handle ServerToolUseBlock."""
        self._current_tool_block = ServerToolUseBlockParam(
            type="server_tool_use",
            id=id,
            name=name,
            input=input,
        )
        self._current_tool_args = ""

    def on_server_tool_result_block(
        self,
        tool_use_id: str,
        tool_name: Literal[
            "web_search_tool_result",
            "code_execution_tool_result",
            "bash_code_execution_tool_result",
            "text_editor_code_execution_tool_result",
            "tool_search_tool_result",
        ],
        content: WebSearchToolResultBlockContent
        | CodeExecutionToolResultBlockContent
        | BashCodeExecutionToolResultBlockContent
        | TextEditorCodeExecutionToolResultBlockContent
        | ToolSearchToolResultBlockContent,
        caller: Caller | None,
    ) -> None:
        """Handle various server tool result blocks."""
        if self._content_details:
            self._content_details.delete_empty()
            self._buffer.append({"native": self._content_details})
        self._content_details = ContentDetails()
        self._content_details.add_citation_detail()
        self._buffer.append(
            {
                "role": "tool_result",
                "tool_call_id": tool_use_id,
                "tool_name": tool_name.removesuffix("_tool_result"),
                "tool_result": {
                    "content": cast(JsonArrayType, [x.to_dict() for x in content])
                }
                if isinstance(content, list)
                else cast(JsonObjectType, content.to_dict()),
            }
        )
        self._first_block = True

    def on_content_block_delta_event(self, delta: RawContentBlockDelta) -> None:
        """Handle RawContentBlockDeltaEvent."""
        if isinstance(delta, InputJSONDelta):
            self.on_input_json_delta(delta.partial_json)
            return
        if isinstance(delta, TextDelta):
            self.on_text_delta(delta.text)
            return
        if isinstance(delta, ThinkingDelta):
            self.on_thinking_delta(delta.thinking)
            return
        if isinstance(delta, SignatureDelta):
            self.on_signature_delta(delta.signature)
            return
        if isinstance(delta, CitationsDelta):
            self.on_citations_delta(delta.citation)
            return
        LOGGER.debug("Unhandled content delta type: %s", delta.type)  # type: ignore[unreachable]  # pragma: no cover - All types are handled but we want to verify that

    def on_input_json_delta(self, partial_json: str) -> None:
        """Handle InputJSONDelta."""
        if (
            self._current_tool_block is not None
            and self._current_tool_block["name"] == self._output_tool
        ):
            self._content_details.citation_details[-1].length += len(partial_json)
            self._buffer.append({"content": partial_json})
        else:
            self._current_tool_args += partial_json

    def on_text_delta(self, text: str) -> None:
        """Handle TextDelta."""
        if text:
            self._content_details.citation_details[-1].length += len(text)
            self._buffer.append({"content": text})

    def on_thinking_delta(self, thinking: str) -> None:
        """Handle ThinkingDelta."""
        if thinking:
            self._buffer.append({"thinking_content": thinking})

    def on_signature_delta(self, signature: str) -> None:
        """Handle SignatureDelta."""
        self._content_details.thinking_signature = signature

    def on_citations_delta(self, citation: TextCitation) -> None:
        """Handle CitationsDelta."""
        self._content_details.add_citation(citation)

    def on_content_block_stop_event(self, index: int) -> None:
        """Handle RawContentBlockStopEvent."""
        if self._current_tool_block is not None:
            if self._current_tool_block["name"] == self._output_tool:
                self._current_tool_block = None
                return
            tool_args = (
                json.loads(self._current_tool_args) if self._current_tool_args else {}
            )
            self._current_tool_block["input"] |= tool_args
            self._buffer.append(
                {
                    "tool_calls": [
                        llm.ToolInput(
                            id=self._current_tool_block["id"],
                            tool_name=self._current_tool_block["name"],
                            tool_args=self._current_tool_block["input"],
                            external=self._current_tool_block["type"]
                            == "server_tool_use",
                        )
                    ]
                }
            )
            self._current_tool_block = None

    def on_message_delta_event(self, delta: Delta, usage: MessageDeltaUsage) -> None:
        """Handle RawMessageDeltaEvent."""
        self._chat_log.async_trace(self._create_token_stats(self._input_usage, usage))
        self._content_details.container = delta.container
        if delta.stop_reason == "refusal":
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="api_refusal"
            )

    def on_message_stop_event(self) -> None:
        """Handle RawMessageStopEvent."""
        if self._content_details:
            self._content_details.delete_empty()
            self._buffer.append({"native": self._content_details})
        self._content_details = ContentDetails()
        self._content_details.add_citation_detail()

    def _create_token_stats(
        self, input_usage: Usage | None, response_usage: MessageDeltaUsage
    ) -> dict[str, Any]:
        """Create token stats for conversation agent tracing."""
        input_tokens = 0
        cached_input_tokens = 0
        if input_usage:
            input_tokens = input_usage.input_tokens
            cached_input_tokens = input_usage.cache_creation_input_tokens or 0
        output_tokens = response_usage.output_tokens
        return {
            "stats": {
                "input_tokens": input_tokens,
                "cached_input_tokens": cached_input_tokens,
                "output_tokens": output_tokens,
            }
        }


class AnthropicBaseLLMEntity(CoordinatorEntity[AnthropicCoordinator]):
    """Anthropic base LLM entity."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: AnthropicConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the entity."""
        super().__init__(entry.runtime_data)
        self.entry = entry
        self.subentry = subentry
        coordinator = entry.runtime_data
        self.model_info, _ = coordinator.get_model_info(
            subentry.data.get(CONF_CHAT_MODEL, DEFAULT[CONF_CHAT_MODEL])
        )
        self._attr_unique_id = subentry.subentry_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="Anthropic",
            model=self.model_info.display_name,
            model_id=self.model_info.id,
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    async def _get_model_args(  # noqa: C901
        self,
        chat_log: conversation.ChatLog,
        structure_name: str | None = None,
        structure: vol.Schema | None = None,
    ) -> tuple[MessageCreateParamsStreaming, str | None]:
        """Get the model arguments."""
        options: dict[str, Any] = DEFAULT | self.subentry.data

        preloaded_tools = [
            "HassTurnOn",
            "HassTurnOff",
            "GetLiveContext",
            "code_execution",
            "web_search",
        ]

        system = chat_log.content[0]
        if not isinstance(system, conversation.SystemContent):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="system_message_not_found"
            )

        messages, container_id = _convert_content(chat_log.content[1:])

        model = options[CONF_CHAT_MODEL]

        model_args = MessageCreateParamsStreaming(
            model=model,
            messages=messages,
            max_tokens=options[CONF_MAX_TOKENS],
            system=system.content,
            stream=True,
            container=container_id,
        )

        if options[CONF_PROMPT_CACHING] == PromptCaching.PROMPT:
            model_args["system"] = [
                {
                    "type": "text",
                    "text": system.content,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        elif options[CONF_PROMPT_CACHING] == PromptCaching.AUTOMATIC:
            model_args["cache_control"] = {"type": "ephemeral"}

        if (
            self.model_info.capabilities
            and self.model_info.capabilities.thinking.types.adaptive.supported
        ):
            thinking_effort = options[CONF_THINKING_EFFORT]
            if thinking_effort != "none":
                model_args["thinking"] = ThinkingConfigAdaptiveParam(
                    type="adaptive", display="summarized"
                )
                model_args["output_config"] = OutputConfigParam(effort=thinking_effort)
            else:
                model_args["thinking"] = ThinkingConfigDisabledParam(type="disabled")
        else:
            thinking_budget = options[CONF_THINKING_BUDGET]
            if (
                self.model_info.capabilities
                and self.model_info.capabilities.thinking.types.enabled.supported
                and thinking_budget >= MIN_THINKING_BUDGET
            ):
                model_args["thinking"] = ThinkingConfigEnabledParam(
                    type="enabled", display="summarized", budget_tokens=thinking_budget
                )
            else:
                model_args["thinking"] = ThinkingConfigDisabledParam(type="disabled")

            if (
                self.model_info.capabilities
                and self.model_info.capabilities.effort.supported
            ):
                model_args["output_config"] = OutputConfigParam(
                    effort=options[CONF_THINKING_EFFORT]
                )

        tools: list[ToolUnionParam] = []
        if chat_log.llm_api:
            tools = [
                _format_tool(tool, chat_log.llm_api.custom_serializer)
                for tool in chat_log.llm_api.tools
            ]

        if options[CONF_CODE_EXECUTION]:
            # The `web_search_20260209` tool automatically enables `code_execution_20260120` tool
            if (
                not self.model_info.capabilities
                or not self.model_info.capabilities.code_execution.supported
                or not options[CONF_WEB_SEARCH]
            ):
                tools.append(
                    CodeExecutionTool20250825Param(
                        name="code_execution",
                        type="code_execution_20250825",
                    ),
                )

        if options[CONF_WEB_SEARCH]:
            if (
                not self.model_info.capabilities
                or not self.model_info.capabilities.code_execution.supported
                or not options[CONF_CODE_EXECUTION]
            ):
                web_search: WebSearchTool20250305Param | WebSearchTool20260209Param = (
                    WebSearchTool20250305Param(
                        name="web_search",
                        type="web_search_20250305",
                        max_uses=options[CONF_WEB_SEARCH_MAX_USES],
                    )
                )
            else:
                web_search = WebSearchTool20260209Param(
                    name="web_search",
                    type="web_search_20260209",
                    max_uses=options[CONF_WEB_SEARCH_MAX_USES],
                )
            if options[CONF_WEB_SEARCH_USER_LOCATION]:
                web_search["user_location"] = {
                    "type": "approximate",
                    "city": options.get(CONF_WEB_SEARCH_CITY, ""),
                    "region": options.get(CONF_WEB_SEARCH_REGION, ""),
                    "country": options.get(CONF_WEB_SEARCH_COUNTRY, ""),
                    "timezone": options.get(CONF_WEB_SEARCH_TIMEZONE, ""),
                }
            tools.append(web_search)

        # Handle attachments by adding them to the last user message
        last_content = chat_log.content[-1]
        if last_content.role == "user" and last_content.attachments:
            last_message = messages[-1]
            if last_message["role"] != "user":
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="user_message_not_found"
                )
            if isinstance(last_message["content"], str):
                last_message["content"] = [
                    TextBlockParam(type="text", text=last_message["content"])
                ]
            last_message["content"].extend(  # type: ignore[union-attr]
                await async_prepare_files_for_prompt(
                    self.hass,
                    self.model_info,
                    [(a.path, a.mime_type) for a in last_content.attachments],
                )
            )

        if structure and structure_name:
            if (
                self.model_info.capabilities
                and self.model_info.capabilities.structured_outputs.supported
            ):
                # Native structured output for those models who support it.
                structure_name = None
                model_args.setdefault("output_config", OutputConfigParam())[
                    "format"
                ] = JSONOutputFormatParam(
                    type="json_schema",
                    schema={
                        **convert(
                            structure,
                            custom_serializer=chat_log.llm_api.custom_serializer
                            if chat_log.llm_api
                            else llm.selector_serializer,
                        ),
                        "additionalProperties": False,
                    },
                )
            elif model_args["thinking"]["type"] == "disabled":
                structure_name = slugify(structure_name)
                if not tools:
                    # Simplest case: no tools and no extended thinking
                    # Add a tool and force its use
                    model_args["tool_choice"] = ToolChoiceToolParam(
                        type="tool",
                        name=structure_name,
                    )
                else:
                    # Second case: tools present but no extended thinking
                    # Allow the model to use any tool but not text response
                    # The model should know to use the right tool by its description
                    model_args["tool_choice"] = ToolChoiceAnyParam(
                        type="any",
                    )
            else:
                # Extended thinking is enabled. With extended thinking, we cannot
                # force tool use or disable text responses, so we add a hint to the
                # system prompt instead. With extended thinking, the model should be
                # smart enough to use the tool.
                structure_name = slugify(structure_name)
                model_args["tool_choice"] = ToolChoiceAutoParam(
                    type="auto",
                )

                model_args["system"].append(  # type: ignore[union-attr]
                    TextBlockParam(
                        type="text",
                        text=f"Claude MUST use the '{structure_name}' tool to provide "
                        "the final answer instead of plain text.",
                    )
                )

            if structure_name:
                tools.append(
                    ToolParam(
                        name=structure_name,
                        description="Use this tool to reply to the user",
                        input_schema=convert(
                            structure,
                            custom_serializer=chat_log.llm_api.custom_serializer
                            if chat_log.llm_api
                            else llm.selector_serializer,
                        ),
                    )
                )
                preloaded_tools.append(structure_name)

        if tools:
            if options[CONF_TOOL_SEARCH] and len(tools) > len(preloaded_tools) + 1:
                for tool in tools:
                    if not tool["name"].endswith(tuple(preloaded_tools)):
                        tool["defer_loading"] = True
                tools.append(
                    ToolSearchToolBm25_20251119Param(
                        type="tool_search_tool_bm25_20251119",
                        name="tool_search_tool_bm25",
                    )
                )

            model_args["tools"] = tools

        return model_args, structure_name

    async def _async_handle_chat_log(
        self,
        chat_log: conversation.ChatLog,
        structure_name: str | None = None,
        structure: vol.Schema | None = None,
        max_iterations: int = MAX_TOOL_ITERATIONS,
    ) -> None:
        """Generate an answer for the chat log."""
        model_args, structure_name = await self._get_model_args(
            chat_log, structure_name, structure
        )
        coordinator = self.entry.runtime_data
        client = coordinator.client

        # To prevent infinite loops, we limit the number of iterations
        for _iteration in range(max_iterations):
            try:
                stream = await client.messages.create(**model_args)

                new_messages, model_args["container"] = _convert_content(
                    [
                        content
                        async for content in chat_log.async_add_delta_content_stream(
                            self.entity_id,
                            AnthropicDeltaStream(
                                chat_log,
                                stream,
                                output_tool=structure_name or None,
                            ),
                        )
                    ]
                )
                cast(list[MessageParam], model_args["messages"]).extend(new_messages)
            except anthropic.AuthenticationError as err:
                # Trigger coordinator to confirm the auth failure and trigger the reauth flow.
                await coordinator.async_request_refresh()
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="api_authentication_error",
                    translation_placeholders={"message": err.message},
                ) from err
            except anthropic.APIConnectionError as err:
                LOGGER.info("Connection error while talking to Anthropic: %s", err)
                coordinator.mark_connection_error()
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="api_error",
                    translation_placeholders={"message": err.message},
                ) from err
            except anthropic.AnthropicError as err:
                # Non-connection error, mark connection as healthy
                coordinator.async_set_updated_data(coordinator.data)
                LOGGER.error("Error while talking to Anthropic: %s", err)
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="api_error",
                    translation_placeholders={
                        "message": err.message
                        if isinstance(err, anthropic.APIError)
                        else str(err)
                    },
                ) from err

            if not chat_log.unresponded_tool_results:
                coordinator.async_set_updated_data(coordinator.data)
                break


async def async_prepare_files_for_prompt(
    hass: HomeAssistant, model_info: ModelInfo, files: list[tuple[Path, str | None]]
) -> Iterable[ImageBlockParam | DocumentBlockParam]:
    """Append files to a prompt.

    Caller needs to ensure that the files are allowed.
    """

    def append_files_to_content() -> Iterable[ImageBlockParam | DocumentBlockParam]:
        content: list[ImageBlockParam | DocumentBlockParam] = []

        for file_path, mime_type in files:
            if not file_path.exists():
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="wrong_file_path",
                    translation_placeholders={"file_path": file_path.as_posix()},
                )

            if mime_type is None:
                mime_type = guess_file_type(file_path)[0]

            if (
                not mime_type
                or not mime_type.startswith(("image/", "application/pdf"))
                or not model_info.capabilities
                or (
                    mime_type.startswith("image/")
                    and not model_info.capabilities.image_input.supported
                )
                or (
                    mime_type.startswith("application/pdf")
                    and not model_info.capabilities.pdf_input.supported
                )
            ):
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="wrong_file_type",
                    translation_placeholders={
                        "file_path": file_path.as_posix(),
                        "mime_type": mime_type or "unknown",
                        "model": model_info.display_name,
                    },
                )
            if mime_type == "image/jpg":
                mime_type = "image/jpeg"

            base64_file = base64.b64encode(file_path.read_bytes()).decode("utf-8")

            if mime_type.startswith("image/"):
                content.append(
                    ImageBlockParam(
                        type="image",
                        source=Base64ImageSourceParam(
                            type="base64",
                            media_type=mime_type,  # type: ignore[typeddict-item]
                            data=base64_file,
                        ),
                    )
                )
            elif mime_type.startswith("application/pdf"):
                content.append(
                    DocumentBlockParam(
                        type="document",
                        source=Base64PDFSourceParam(
                            type="base64",
                            media_type=mime_type,  # type: ignore[typeddict-item]
                            data=base64_file,
                        ),
                    )
                )

        return content

    return await hass.async_add_executor_job(append_files_to_content)
