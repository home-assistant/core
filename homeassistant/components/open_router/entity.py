"""Base entity for Open Router."""

from __future__ import annotations

import base64
from collections.abc import AsyncGenerator, Callable
import json
import uuid
from mimetypes import guess_file_type
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

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

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, llm
from homeassistant.helpers.entity import Entity

from . import OpenRouterConfigEntry
from .const import DOMAIN, LOGGER

# Max number of back and forth with the LLM to generate a response
MAX_TOOL_ITERATIONS = 10


def _adjust_schema(schema: dict[str, Any]) -> None:
    """Adjust the schema to be compatible with OpenRouter API."""
    if schema["type"] == "object":
        if "properties" not in schema:
            return

        if "required" not in schema:
            schema["required"] = []

        # Ensure all properties are required
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
    tool_spec = FunctionDefinition(
        name=tool.name,
        parameters=convert(tool.parameters, custom_serializer=custom_serializer),
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
                ChatCompletionMessageFunctionToolCallParam(
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
    LOGGER.warning("Could not convert message to Completions API: %s", content)
    return None


def _decode_tool_arguments(arguments: Any) -> Any:
    """Decode tool call arguments safely."""
    if arguments is None:
        LOGGER.warning("Tool arguments is None, defaulting to {}")
        return {}
    if isinstance(arguments, (bytes, bytearray)):
        try:
            return arguments.decode("utf-8", "ignore")
        except Exception:
            LOGGER.warning("Failed to decode bytes arguments")
            return {}
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        s = arguments.strip()
        if not s:
            LOGGER.warning("Empty string arguments")
            return {}
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            try:
                inner = json.loads(s)
                if isinstance(inner, str):
                    return json.loads(inner)
                return inner
            except Exception:
                raise HomeAssistantError(f"Unparsable tool arguments: {s}")
    try:
        return json.loads(str(arguments))
    except Exception:
        LOGGER.warning("Unexpected tool argument type: %s", type(arguments))
        return {}


async def _transform_response(
    message: ChatCompletionMessage,
) -> AsyncGenerator[conversation.AssistantContentDeltaDict, None]:
    """Transform provider message to conversation deltas, including tool calls."""
    data: conversation.AssistantContentDeltaDict = {
        "role": message.role,
        "content": message.content,
    }

    if getattr(message, "tool_calls", None):
        calls: list[llm.ToolInput] = []
        for tc in message.tool_calls:
            if getattr(tc, "type", None) != "function" or not getattr(tc, "function", None):
                LOGGER.warning("Skipping malformed tool_call: %s", tc)
                continue
            raw = getattr(tc.function, "arguments", None) or getattr(tc.function, "parameters", None)
            args = _decode_tool_arguments(raw)
            calls.append(llm.ToolInput(id=tc.id, tool_name=tc.function.name, tool_args=args))
        if calls:
            data["tool_calls"] = calls
        yield data
        return

    # Fallback: parse JSON in content for tool_calls
    try:
        txt = message.content
        if isinstance(txt, str):
            s = txt.strip()
            if s.startswith("{") and "tool_calls" in s:
                obj = json.loads(s)
                tc_list = obj.get("tool_calls")
                if isinstance(tc_list, list):
                    calls: list[llm.ToolInput] = []
                    for tc in tc_list:
                        if not isinstance(tc, dict) or tc.get("type") != "function" or "function" not in tc:
                            continue
                        fn = tc["function"]
                        name = fn.get("name")
                        raw = fn.get("arguments") or fn.get("parameters")
                        args = _decode_tool_arguments(raw)
                        calls.append(
                            llm.ToolInput(
                                id=tc.get("id") or str(uuid.uuid4()),
                                tool_name=name,
                                tool_args=args,
                            )
                        )
                    if calls:
                        data["tool_calls"] = calls
                        data["content"] = None
    except Exception as ex:
        LOGGER.debug("Fallback JSON parse failed: %s", ex)

    yield data


async def async_prepare_files_for_prompt(
    hass: HomeAssistant, files: list[tuple[Path, str | None]]
) -> list[ChatCompletionContentPartImageParam]:
    """Append files to a prompt.

    Caller needs to ensure that the files are allowed.
    """

    def append_files_to_content() -> list[ChatCompletionContentPartImageParam]:
        content: list[ChatCompletionContentPartImageParam] = []

        for file_path, mime_type in files:
            if not file_path.exists():
                raise HomeAssistantError(f"`{file_path}` does not exist")

            if mime_type is None:
                mime_type = guess_file_type(file_path)[0]

            if not mime_type or not mime_type.startswith(("image/", "application/pdf")):
                raise HomeAssistantError(
                    "Only images and PDF are supported by the OpenRouter API, "
                    f"`{file_path}` is not an image file or PDF"
                )

            base64_file = base64.b64encode(file_path.read_bytes()).decode("utf-8")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{base64_file}"},
                }
            )

        return content

    return await hass.async_add_executor_job(append_files_to_content)


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

        model_args = {
            "model": self.model,
            "user": chat_log.conversation_id,
            "extra_headers": {
                "X-Title": "Home Assistant",
                "HTTP-Referer": "https://www.home-assistant.io/integrations/open_router",
            },
            "extra_body": {"require_parameters": True},
        }

        tools: list[ChatCompletionFunctionToolParam] | None = None
        if chat_log.llm_api:
            tools = [
                _format_tool(tool, chat_log.llm_api.custom_serializer)
                for tool in chat_log.llm_api.tools
            ]

        def _add_query_property(params: dict[str, Any]) -> dict[str, Any]:
            if not isinstance(params, dict):
                params = {"type": "object", "properties": {}, "additionalProperties": True}
            props = params.get("properties")
            if not isinstance(props, dict):
                props = {}
                params["properties"] = props
            if "query" not in props:
                props["query"] = {"type": "string", "description": "Free-form query string optional"}
            params.setdefault("additionalProperties", True)
            params.setdefault("type", "object")
            return params

        def _to_fn_dict(t: dict | Any) -> dict | None:
            if isinstance(t, dict):
                fn = t.get("function")
                if isinstance(fn, dict):
                    fn["parameters"] = _add_query_property(fn.get("parameters") or {})
                    return {"type": "function", "function": fn}
                return None
            try:
                fn = getattr(t, "function", None)
                name = getattr(fn, "name", None) if fn else None
                params = getattr(fn, "parameters", None) if fn else None
                if hasattr(params, "model_dump"):
                    params = params.model_dump()
                if hasattr(fn, "model_dump"):
                    fn_dict = fn.model_dump()
                else:
                    fn_dict = {"name": name, "parameters": params}
                fn_dict["parameters"] = _add_query_property(fn_dict.get("parameters") or {})
                return {"type": "function", "function": fn_dict}
            except Exception:
                return None

        def _normalize_tools(tlist: list[dict]) -> list[dict]:
            out: list[dict] = []
            for t in tlist or []:
                d = _to_fn_dict(t)
                if d and d.get("type") == "function" and d["function"].get("name"):
                    out.append(d)
            return out

        def _ensure_tool(name: str | None) -> None:
            if not name:
                return
            for t in tools:
                fn = t.get("function")
                if fn and fn.get("name") == name:
                    return
            tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": "Dynamic tool from history",
                    "parameters": _add_query_property({}),
                },
            })

        model_args["messages"] = [
            m
            for content in chat_log.content
            if (m := _convert_content_to_chat_message(content))
        ]

        # Discover tools from history messages
        for content in chat_log.content:
            if isinstance(content, conversation.AssistantContent) and content.tool_calls:
                for tc in content.tool_calls:
                    _ensure_tool(tc.tool_name)
            if isinstance(content, conversation.ToolResultContent):
                _ensure_tool(content.tool_name)

        norm = _normalize_tools(tools)
        if norm:
            model_args["tools"] = norm
            model_args["tool_choice"] = "auto"

        if structure:
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

            result_message = result.choices[0].message

            new_msgs: list[ChatCompletionMessageParam] = [
                msg
                async for content in chat_log.async_add_delta_content_stream(
                    self.entity_id, _transform_response(result_message)
                )
                if (msg := _convert_content_to_chat_message(content))
            ]

            model_args.setdefault("messages", []).extend(new_msgs)

            # Convert any tool messages into assistant content
            assistant_items: list[conversation.AssistantContent] = []
            for m in new_msgs:
                if isinstance(m, dict) and m.get("role") == "tool":
                    # parse the tool result
                    try:
                        payload = json.loads(m.get("content") or "{}")
                        speech = None
                        sp = payload.get("speech")
                        if isinstance(sp, dict):
                            plain = sp.get("plain")
                            if isinstance(plain, dict) and "speech" in plain:
                                speech = plain["speech"]
                        if speech is None:
                            continue
                    except Exception:
                        speech = m.get("content")
                    assistant_items.append(conversation.AssistantContent(agent_id=chat_log.conversation_id, content=speech, tool_calls=[]))

            for ac in assistant_items:
                chat_log.async_add_assistant_content_without_tools(ac)

            # Discover new tools in this round
            for m in new_msgs:
                if isinstance(m, dict) and m.get("role") == "tool":
                    _ensure_tool(m.get("name"))

            norm = _normalize_tools(tools)
            if norm:
                model_args["tools"] = norm
                model_args["tool_choice"] = "auto"

            if not chat_log.unresponded_tool_results:
                break
