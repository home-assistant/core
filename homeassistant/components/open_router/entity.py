"""Base entity for Open Router."""

import base64
from collections.abc import AsyncGenerator, Callable
from datetime import timedelta
import json
from mimetypes import guess_file_type
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypedDict

import openai
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionContentPartImageParam,
    ChatCompletionFunctionToolParam,
    ChatCompletionMessage,
    ChatCompletionMessageFunctionToolCallParam,
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionToolMessageParam,
    ChatCompletionUserMessageParam,
)
from openai.types.chat.chat_completion_message_function_tool_call_param import Function
from openai.types.shared_params import FunctionDefinition, ResponseFormatJSONSchema
from openai.types.shared_params.response_format_json_schema import JSONSchema
import voluptuous as vol
from voluptuous_openapi import convert

from homeassistant.components import conversation, media_source
from homeassistant.components.http.auth import async_sign_path
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, llm
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.json import json_dumps
from homeassistant.helpers.network import NoURLAvailableError, get_url

from . import OpenRouterConfigEntry
from .const import CONF_WEB_SEARCH, DOMAIN, LOGGER

MAX_TOOL_ITERATIONS = 10


class VideoUrlParam(TypedDict):
    """Content part for a video URL input (OpenRouter extension)."""

    type: Literal["video_url"]
    video_url: dict[str, str]


def _adjust_schema(schema: dict[str, Any]) -> None:
    """Adjust the schema to be compatible with OpenRouter API."""
    if schema["type"] == "object":
        if "properties" not in schema:
            return

        if "required" not in schema:
            schema["required"] = []

        for prop, prop_info in schema["properties"].items():
            _adjust_schema(prop_info)
            if prop not in schema["required"]:
                prop_info["type"] = [prop_info["type"], "null"]
                schema["required"].append(prop)

    elif schema["type"] == "array":
        if "items" not in schema:
            return

        _adjust_schema(schema["items"])


def _format_structured_output(
    name: str, schema: vol.Schema, llm_api: llm.APIInstance | None
) -> JSONSchema:
    """Format the schema to be compatible with OpenRouter API."""
    result: JSONSchema = {
        "name": name,
        "strict": True,
    }
    result_schema = convert(
        schema,
        custom_serializer=(
            llm_api.custom_serializer if llm_api else llm.selector_serializer
        ),
    )

    _adjust_schema(result_schema)

    result["schema"] = result_schema
    return result


def _format_tool(
    tool: llm.Tool,
    custom_serializer: Callable[[Any], Any] | None,
) -> ChatCompletionFunctionToolParam:
    """Format tool specification."""
    unsupported_keys = {"oneOf", "anyOf", "allOf"}
    schema = convert(tool.parameters, custom_serializer=custom_serializer)
    schema = {k: v for k, v in schema.items() if k not in unsupported_keys}

    tool_spec = FunctionDefinition(
        name=tool.name,
        parameters=schema,
    )
    if tool.description:
        tool_spec["description"] = tool.description
    return ChatCompletionFunctionToolParam(type="function", function=tool_spec)


def _convert_content_to_chat_message(
    content: conversation.Content,
) -> ChatCompletionMessageParam | None:
    """Convert any native chat message for this agent to the native format."""
    LOGGER.debug("_convert_content_to_chat_message=%s", content)
    if isinstance(content, conversation.ToolResultContent):
        return ChatCompletionToolMessageParam(
            role="tool",
            tool_call_id=content.tool_call_id,
            content=json_dumps(content.tool_result),
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
                ChatCompletionMessageFunctionToolCallParam(
                    type="function",
                    id=tool_call.id,
                    function=Function(
                        arguments=json_dumps(tool_call.tool_args),
                        name=tool_call.tool_name,
                    ),
                )
                for tool_call in content.tool_calls
            ]
        return param
    LOGGER.warning("Could not convert message to Completions API: %s", content)
    return None


def _decode_tool_arguments(arguments: str) -> Any:
    """Decode tool call arguments."""
    try:
        return json.loads(arguments)
    except json.JSONDecodeError as err:
        raise HomeAssistantError(f"Unexpected tool argument response: {err}") from err


async def _transform_response(
    message: ChatCompletionMessage,
) -> AsyncGenerator[conversation.AssistantContentDeltaDict]:
    """Transform the OpenRouter message to a ChatLog format."""
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
            if tool_call.type == "function"
        ]
    yield data


async def async_prepare_files_for_prompt(
    hass: HomeAssistant,
    attachments: list[conversation.Attachment],
) -> list[ChatCompletionContentPartImageParam | VideoUrlParam]:
    """Prepare files for use in a prompt.

    Caller needs to ensure that the files are allowed.
    """
    content: list[ChatCompletionContentPartImageParam | VideoUrlParam] = []

    for attachment in attachments:
        file_path = attachment.path
        mime_type = attachment.mime_type or guess_file_type(file_path)[0] or ""

        if mime_type.startswith("video/"):
            if file_path.exists():
                def encode_video(
                    path: Path = file_path, mime: str = mime_type
                ) -> VideoUrlParam:
                    base64_file = base64.b64encode(path.read_bytes()).decode("utf-8")
                    return VideoUrlParam(
                        type="video_url",
                        video_url={"url": f"data:{mime};base64,{base64_file}"},
                    )

                content.append(await hass.async_add_executor_job(encode_video))
            else:
                try:
                    external_url = get_url(
                        hass, prefer_external=True, allow_internal=False
                    )
                except NoURLAvailableError as err:
                    raise HomeAssistantError(
                        "An external URL must be configured to serve non-local video files to OpenRouter"
                    ) from err
                media = await media_source.async_resolve_media(
                    hass, attachment.media_content_id, None
                )
                signed_path = async_sign_path(
                    hass, media.url, timedelta(hours=1), use_content_user=True
                )
                content.append(
                    VideoUrlParam(
                        type="video_url",
                        video_url={"url": f"{external_url}{signed_path}"},
                    )
                )
        elif mime_type.startswith(("image/", "application/pdf")):
            def encode_image(
                path: Path = file_path, mime: str = mime_type
            ) -> ChatCompletionContentPartImageParam:
                if not path.exists():
                    raise HomeAssistantError(f"`{path}` does not exist")
                encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
                return ChatCompletionContentPartImageParam(
                    type="image_url",
                    image_url={"url": f"data:{mime};base64,{encoded}"},
                )
            content.append(await hass.async_add_executor_job(encode_image))
        else:
            raise HomeAssistantError(
                "Only images, PDF, and video are supported by the OpenRouter API, "
                f"`{file_path}` has unsupported type: {mime_type}"
            )

    return content


class OpenRouterEntity(Entity):
    """Base entity for Open Router."""

    _attr_has_entity_name = True

    def __init__(self, entry: OpenRouterConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the entity."""
        self.entry = entry
        self.subentry = subentry
        self.model = subentry.data[CONF_MODEL]
        self._attr_unique_id = subentry.subentry_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    async def _async_handle_chat_log(
        self,
        chat_log: conversation.ChatLog,
        structure_name: str | None = None,
        structure: vol.Schema | None = None,
    ) -> None:
        """Generate an answer for the chat log."""

        model = self.model
        if self.subentry.data.get(CONF_WEB_SEARCH):
            model = f"{model}:online"

        extra_body: dict[str, Any] = {"require_parameters": True}

        model_args = {
            "model": model,
            "user": chat_log.conversation_id,
            "extra_headers": {
                "X-Title": "Home Assistant",
                "HTTP-Referer": "https://www.home-assistant.io/integrations/open_router",
            },
            "extra_body": extra_body,
        }

        tools: list[ChatCompletionFunctionToolParam] | None = None
        if chat_log.llm_api:
            tools = [
                _format_tool(tool, chat_log.llm_api.custom_serializer)
                for tool in chat_log.llm_api.tools
            ]

        if tools:
            model_args["tools"] = tools

        model_args["messages"] = [
            m
            for content in chat_log.content
            if (m := _convert_content_to_chat_message(content))
        ]

        last_content = chat_log.content[-1]

        # Handle attachments by adding them to the last user message
        if last_content.role == "user" and last_content.attachments:
            last_message: ChatCompletionMessageParam = model_args["messages"][-1]
            assert last_message["role"] == "user" and isinstance(
                last_message["content"], str
            )
            # Encode files with base64 and append them to the text prompt
            files = await async_prepare_files_for_prompt(
                self.hass,
                list(last_content.attachments),
            )
            last_message["content"] = [
                {"type": "text", "text": last_message["content"]},
                *files,
            ]

        if structure:
            if TYPE_CHECKING:
                assert structure_name is not None
            model_args["response_format"] = ResponseFormatJSONSchema(
                type="json_schema",
                json_schema=_format_structured_output(
                    structure_name, structure, chat_log.llm_api
                ),
            )

        client = self.entry.runtime_data

        for _iteration in range(MAX_TOOL_ITERATIONS):
            try:
                result = await client.chat.completions.create(**model_args)
            except openai.OpenAIError as err:
                LOGGER.error("Error talking to API: %s", err)
                raise HomeAssistantError("Error talking to API") from err

            if not result.choices:
                LOGGER.error("API returned empty choices")
                raise HomeAssistantError("API returned empty response")

            result_message = result.choices[0].message

            model_args["messages"].extend(
                [
                    msg
                    async for content in chat_log.async_add_delta_content_stream(
                        self.entity_id, _transform_response(result_message)
                    )
                    if (msg := _convert_content_to_chat_message(content))
                ]
            )
            if not chat_log.unresponded_tool_results:
                break
