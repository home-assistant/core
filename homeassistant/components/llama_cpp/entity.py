"""Base entity for llama.cpp Conversation."""

import base64
from collections.abc import AsyncGenerator, Callable
import json
import logging
import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

from openai import AsyncOpenAI
from openai._streaming import AsyncStream
from openai._types import Omit
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionAssistantMessageParam,
    ChatCompletionChunk,
    ChatCompletionContentPartParam,
    ChatCompletionContentPartTextParam,
    ChatCompletionFunctionToolParam,
    ChatCompletionMessage,
    ChatCompletionMessageFunctionToolCall,
    ChatCompletionMessageParam,
    ChatCompletionMessageToolCallParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionToolMessageParam,
    ChatCompletionUserMessageParam,
)
from openai.types.chat.chat_completion_message_function_tool_call_param import Function
from openai.types.shared_params import FunctionDefinition, ResponseFormatJSONSchema
from probatio import to_openapi
import voluptuous as vol

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, llm
from homeassistant.helpers.entity import Entity

from .api import api_error_handler
from .const import (
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_STREAMING,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    DEFAULT_MODEL,
    DOMAIN,
    LOGGER,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_P,
)

if TYPE_CHECKING:
    from . import LlamaCppConfigEntry

# Max number of back and forth with the LLM to generate a response
MAX_TOOL_ITERATIONS = 10

_LOGGER = logging.getLogger(__name__)


def _format_structured_output(
    name: str, structure: vol.Schema, llm_api: llm.APIInstance | None
) -> ResponseFormatJSONSchema:
    """Format structured output specification."""
    schema = to_openapi(
        structure, custom_serializer=llm_api.custom_serializer if llm_api else None
    )
    return ResponseFormatJSONSchema(
        type="json_schema",
        json_schema={
            "name": name,
            "strict": True,
            "schema": cast(dict[str, object], schema),
        },
    )


def _format_tool(
    tool: llm.Tool,
    custom_serializer: Callable[[Any], Any] | None,
) -> ChatCompletionFunctionToolParam:
    """Format tool specification."""
    tool_spec = FunctionDefinition(
        name=tool.name,
        parameters=to_openapi(tool.parameters, custom_serializer=custom_serializer),
    )
    if tool.description:
        tool_spec["description"] = tool.description
    return ChatCompletionFunctionToolParam(type="function", function=tool_spec)


def _convert_content_to_chat_message(
    content: conversation.Content,
) -> ChatCompletionMessageParam | None:
    """Convert any native chat message for this agent to the native format."""
    _LOGGER.debug("_convert_content_to_chat_message=%s", content)
    if isinstance(content, conversation.ToolResultContent):
        return ChatCompletionToolMessageParam(
            role="tool",
            tool_call_id=content.tool_call_id,
            content=json.dumps(content.tool_result),
        )

    role: Literal["user", "assistant", "system"] = content.role
    if role == "system" and content.content:
        return ChatCompletionSystemMessageParam(role="system", content=content.content)

    if role == "user" and content.content:
        return ChatCompletionUserMessageParam(role="user", content=content.content)

    if role == "assistant":
        param = ChatCompletionAssistantMessageParam(
            role="assistant",
            content=content.content,
        )
        if isinstance(content, conversation.AssistantContent) and content.tool_calls:
            param["tool_calls"] = [
                ChatCompletionMessageToolCallParam(
                    type="function",
                    id=tool_call.id,
                    function=Function(
                        arguments=json.dumps(tool_call.tool_args),
                        name=tool_call.tool_name,
                    ),
                )
                for tool_call in content.tool_calls
            ]
        return param
    LOGGER.warning("Could not convert message to OpenAI API: %s", content)
    return None


def _decode_tool_arguments(arguments: str) -> Any:
    """Decode tool call arguments."""
    try:
        return json.loads(arguments)
    except json.JSONDecodeError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="json_parse_error",
            translation_placeholders={"message": str(err)},
        ) from err


async def _transform_response(
    message: ChatCompletionMessage,
) -> AsyncGenerator[conversation.AssistantContentDeltaDict]:
    """Transform the OpenAI API message to a ChatLog format."""
    data: conversation.AssistantContentDeltaDict = {
        "role": message.role,
        "content": message.content,
    }
    if message.tool_calls:
        data["tool_calls"] = [
            llm.ToolInput(
                id=tool_call.id,
                tool_name=tool_call.function.name,
                tool_args=_decode_tool_arguments(tool_call.function.arguments),
            )
            for tool_call in message.tool_calls
            if isinstance(tool_call, ChatCompletionMessageFunctionToolCall)
        ]
    yield data


def _convert_content_to_param(
    content: conversation.Content,
) -> ChatCompletionMessageParam:
    """Convert any native chat message for this agent to the native format."""
    if isinstance(content, conversation.ToolResultContent):
        return ChatCompletionToolMessageParam(
            role="tool",
            tool_call_id=content.tool_call_id,
            content=json.dumps(content.tool_result),
        )
    if not isinstance(content, conversation.AssistantContent) or not content.tool_calls:
        if isinstance(content, conversation.SystemContent):
            return ChatCompletionSystemMessageParam(
                role="system",
                content=content.content or "",
            )
        return cast(
            ChatCompletionMessageParam,
            {"role": content.role, "content": content.content or ""},
        )

    return ChatCompletionAssistantMessageParam(
        role="assistant",
        content=content.content,
        tool_calls=[
            ChatCompletionMessageToolCallParam(
                id=tool_call.id,
                function=Function(
                    arguments=json.dumps(tool_call.tool_args),
                    name=tool_call.tool_name,
                ),
                type="function",
            )
            for tool_call in content.tool_calls
        ],
    )


async def _transform_stream(
    result: AsyncStream[ChatCompletionChunk],
) -> AsyncGenerator[conversation.AssistantContentDeltaDict]:
    """Transform an OpenAI delta stream into HA format."""
    current_tool_call: dict[str, Any] | None = None
    yielded_role = False

    async for chunk in result:
        LOGGER.debug("Received chunk: %s", chunk)
        if not chunk.choices:
            continue
        choice = chunk.choices[0]

        if choice.finish_reason:
            if current_tool_call:
                yield {
                    "tool_calls": [
                        llm.ToolInput(
                            id=current_tool_call["id"],
                            tool_name=current_tool_call["tool_name"],
                            tool_args=_decode_tool_arguments(
                                current_tool_call["tool_args"]
                            )
                            if current_tool_call["tool_args"]
                            else {},
                        )
                    ]
                }
            break

        delta = choice.delta

        if current_tool_call is None and not delta.tool_calls:
            yield_dict: conversation.AssistantContentDeltaDict = {}
            if not yielded_role and delta.role == "assistant":
                yield_dict["role"] = "assistant"
                yielded_role = True
            if delta.content is not None:
                yield_dict["content"] = delta.content
            if yield_dict:
                yield yield_dict
            continue

        if (
            not delta.tool_calls
            or not (delta_tool_call := delta.tool_calls[0])
            or not delta_tool_call.function
        ):
            continue

        if current_tool_call and delta_tool_call.index == current_tool_call["index"]:
            current_tool_call["tool_args"] += delta_tool_call.function.arguments or ""
            continue

        if current_tool_call:
            yield {
                "tool_calls": [
                    llm.ToolInput(
                        id=current_tool_call["id"],
                        tool_name=current_tool_call["tool_name"],
                        tool_args=_decode_tool_arguments(
                            current_tool_call["tool_args"]
                        ),
                    )
                ]
            }

        current_tool_call = {
            "index": delta_tool_call.index,
            "id": delta_tool_call.id,
            "tool_name": delta_tool_call.function.name,
            "tool_args": delta_tool_call.function.arguments or "",
        }


class LlamaCppBaseLLMEntity(Entity):
    """llama.cpp base LLM entity."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: LlamaCppConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the entity."""
        self.entry = entry
        self.subentry = subentry
        self._attr_unique_id = subentry.subentry_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="llama.cpp",
            model=subentry.data.get(CONF_CHAT_MODEL, DEFAULT_MODEL),
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    async def _async_handle_chat_log(
        self,
        chat_log: conversation.ChatLog,
        structure_name: str | None = None,
        structure: vol.Schema | None = None,
    ) -> None:
        """Generate an answer for the chat log."""
        options = self.subentry.data

        tools: list[ChatCompletionFunctionToolParam] | None = None
        if chat_log.llm_api:
            tools = [
                _format_tool(tool, chat_log.llm_api.custom_serializer)
                for tool in chat_log.llm_api.tools
            ]

        model: str = options.get(CONF_CHAT_MODEL, DEFAULT_MODEL)
        messages = [
            m
            for content in chat_log.content
            if (m := _convert_content_to_chat_message(content))
        ]

        response_format: ResponseFormatJSONSchema | Omit = Omit()
        if structure and structure_name:
            response_format = _format_structured_output(
                structure_name, structure, chat_log.llm_api
            )

        last_content = chat_log.content[-1]
        if (
            isinstance(last_content, conversation.UserContent)
            and last_content.attachments
        ):
            files = await async_prepare_files_for_prompt(
                self.hass,
                [a.path for a in last_content.attachments],
            )
            for i in range(len(messages) - 1, -1, -1):
                if messages[i]["role"] == "user":
                    user_msg = cast(ChatCompletionUserMessageParam, messages[i])
                    current_content = user_msg.get("content")
                    if isinstance(current_content, str):
                        user_msg["content"] = [
                            ChatCompletionContentPartTextParam(
                                type="text", text=current_content
                            ),
                            *files,
                        ]
                    break

        client: AsyncOpenAI = self.entry.runtime_data
        streaming = bool(
            self.entry.data.get(CONF_STREAMING, options.get(CONF_STREAMING, False))
        )

        for _iteration in range(MAX_TOOL_ITERATIONS):
            with api_error_handler():
                result = await client.chat.completions.create(
                    messages=messages,
                    model=model,
                    tools=tools or Omit(),
                    response_format=response_format,
                    max_tokens=cast(
                        int, options.get(CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS)
                    ),
                    top_p=cast(float, options.get(CONF_TOP_P, RECOMMENDED_TOP_P)),
                    temperature=cast(
                        float, options.get(CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE)
                    ),
                    user=chat_log.conversation_id,
                    stream=cast(Any, streaming),
                )

            convert_message: Callable[[Any], Any]
            async_generator: AsyncGenerator[conversation.AssistantContentDeltaDict]
            if streaming:
                convert_message = _convert_content_to_param
                async_generator = _transform_stream(
                    cast(AsyncStream[ChatCompletionChunk], result)
                )
            else:
                convert_message = _convert_content_to_chat_message
                async_generator = _transform_response(
                    cast(ChatCompletion, result).choices[0].message
                )

            messages.extend(
                [
                    msg
                    async for content in chat_log.async_add_delta_content_stream(
                        self.entity_id, async_generator
                    )
                    if (msg := convert_message(content))
                ]
            )

            if not chat_log.unresponded_tool_results:
                break


async def async_prepare_files_for_prompt(
    hass: HomeAssistant, files: list[Path]
) -> list[ChatCompletionContentPartParam]:
    """Prepare files for OpenAI-compatible API.

    Caller needs to ensure that the files are allowed.
    """

    def guess_file_type(file_path: Path) -> tuple[str | None, str | None]:
        """Guess the file type based on the file extension."""
        return mimetypes.guess_type(str(file_path))

    def append_files_to_content() -> list[ChatCompletionContentPartParam]:
        content: list[ChatCompletionContentPartParam] = []

        for file_path in files:
            if not file_path.exists():
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="file_not_found",
                    translation_placeholders={"file_path": str(file_path)},
                )

            mime_type, _ = guess_file_type(file_path)

            if not mime_type or not mime_type.startswith(("image/", "application/pdf")):
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="unsupported_file_type",
                    translation_placeholders={"file_path": str(file_path)},
                )

            base64_file = base64.b64encode(file_path.read_bytes()).decode("utf-8")

            if mime_type.startswith("image/"):
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_file}",
                            "detail": "auto",
                        },
                    }
                )
            elif mime_type.startswith("application/pdf"):
                content.append(
                    {
                        "type": "text",
                        "text": f"[File: {file_path.name}]\nContent: {base64_file}",
                    }
                )

        return content

    return await hass.async_add_executor_job(append_files_to_content)
