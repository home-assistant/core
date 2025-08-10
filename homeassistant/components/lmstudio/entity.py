"""Base entity for LM Studio integration."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
import json
import logging
from typing import Any

import openai
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from voluptuous_openapi import convert

from homeassistant.components import conversation
from homeassistant.components.conversation import AssistantContent
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.helpers.entity import DeviceInfo, Entity

from . import LMStudioConfigEntry
from .const import CONF_BASE_URL, CONF_MODEL, CONF_STREAM, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _format_tool(
    tool: llm.Tool, custom_serializer: Callable[[Any], Any] | None
) -> dict[str, Any]:
    """Format tool for OpenAI API."""
    tool_spec = {
        "name": tool.name,
        "parameters": convert(tool.parameters, custom_serializer=custom_serializer),
    }
    if tool.description:
        tool_spec["description"] = tool.description

    return {"type": "function", "function": tool_spec}


async def _transform_stream(
    chat_log: conversation.ChatLog,
    result: AsyncGenerator[ChatCompletionChunk],
) -> AsyncGenerator[conversation.AssistantContentDeltaDict]:
    """Transform OpenAI stream to Home Assistant format."""
    async for chunk in result:
        if not chunk.choices:
            continue

        choice = chunk.choices[0]

        if choice.delta.content:
            yield conversation.AssistantContentDeltaDict(
                content=choice.delta.content,
            )

        if choice.delta.tool_calls:
            for tool_call in choice.delta.tool_calls:
                if tool_call.function and tool_call.function.name:
                    yield conversation.AssistantContentDeltaDict(
                        tool_calls=[
                            llm.ToolInput(
                                tool_name=tool_call.function.name,
                                tool_args=json.loads(
                                    tool_call.function.arguments or "{}"
                                ),
                            )
                        ]
                    )


class LMStudioBaseLLMEntity(Entity):
    """Base LM Studio LLM entity."""

    _attr_should_poll = False

    def __init__(self, entry: LMStudioConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the entity."""
        self.entry = entry
        self.subentry = subentry
        self._attr_unique_id = f"{entry.entry_id}-{subentry.subentry_id}"
        self._attr_name = subentry.title
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"LM Studio ({entry.data[CONF_BASE_URL]})",
            manufacturer="LM Studio",
            model="Local LLM Server",
            configuration_url=entry.data[CONF_BASE_URL],
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.entry.runtime_data is not None

    async def _async_handle_chat_log(self, chat_log: conversation.ChatLog) -> None:
        """Handle the chat log and generate response."""
        client = self.entry.runtime_data
        options = {**self.entry.data, **self.subentry.data}

        model = options.get(CONF_MODEL, "")
        if model is None or model == "":
            # If no model specified, use the first available model
            try:
                models_response = await client.with_options(timeout=10.0).models.list()
                if models_response.data:
                    model = models_response.data[0].id
                else:
                    raise HomeAssistantError("No models available on LM Studio server")
            except openai.OpenAIError as err:
                raise HomeAssistantError(f"Failed to get models: {err}") from err

        # Build the messages from the chat log
        messages: list[dict[str, Any]] = []

        for message in chat_log.content:
            if message.role == "system":
                messages.append({"role": "system", "content": message.content})
            elif message.role == "user":
                if isinstance(message.content, str):
                    messages.append({"role": "user", "content": message.content})
                else:
                    # Handle multipart content (text + images)
                    content = []
                    for part in message.content:
                        if part.type == "text":
                            content.append({"type": "text", "text": part.text})
                        elif part.type == "image":
                            content.append(
                                {
                                    "type": "image_url",
                                    "image_url": {"url": part.image_url},
                                }
                            )
                    messages.append({"role": "user", "content": content})
            elif message.role == "assistant":
                msg_content: dict[str, Any] = {
                    "role": "assistant",
                    "content": message.content,
                }
                if message.tool_calls:
                    msg_content["tool_calls"] = [
                        {
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_call.tool_name,
                                "arguments": json.dumps(tool_call.tool_args),
                            },
                        }
                        for tool_call in message.tool_calls
                    ]
                messages.append(msg_content)
            elif message.role == "tool_result":
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": message.tool_call_id,
                        "content": json.dumps(message.tool_result),
                    }
                )

        # Prepare request parameters
        request_params = {
            "model": model,
            "messages": messages,
            "stream": options.get(CONF_STREAM, False),  # Allow streaming if requested
        }

        # Add optional parameters
        for param in ("max_tokens", "temperature", "top_p"):
            if param in options:
                request_params[param] = options[param]

        # Add tools if available
        if chat_log.llm_api and chat_log.llm_api.tools:
            custom_serializer = None
            if options.get(CONF_LLM_HASS_API):
                custom_serializer = (
                    chat_log.llm_api.custom_serializer
                    if chat_log.llm_api
                    else llm.selector_serializer
                )

            request_params["tools"] = [
                _format_tool(tool, custom_serializer) for tool in chat_log.llm_api.tools
            ]

        try:
            response = await client.chat.completions.create(**request_params)

            if request_params.get("stream", False):
                # Handle streaming response
                chat_log.content.extend(
                    [
                        content
                        async for content in chat_log.async_add_delta_content_stream(
                            self.entity_id, _transform_stream(chat_log, response)
                        )
                    ]
                )
            elif isinstance(response, ChatCompletion):
                # Handle non-streaming response
                choice = response.choices[0]

                if choice.message.tool_calls:
                    # Handle tool calls
                    content = AssistantContent(
                        agent_id=self.entity_id,
                        content="",
                        tool_calls=[
                            llm.ToolInput(
                                tool_name=tool_call.function.name,
                                tool_args=json.loads(
                                    tool_call.function.arguments or "{}"
                                ),
                            )
                            for tool_call in choice.message.tool_calls
                            if hasattr(tool_call, "function") and tool_call.function
                        ],
                    )
                    chat_log.async_add_assistant_content_without_tools(content)
                else:
                    # Regular text response
                    content = AssistantContent(
                        agent_id=self.entity_id, content=choice.message.content or ""
                    )
                    chat_log.async_add_assistant_content_without_tools(content)

        except openai.OpenAIError as err:
            _LOGGER.error("LM Studio API error: %s", err)
            raise HomeAssistantError(f"LM Studio API error: {err}") from err
        except Exception as err:
            _LOGGER.error("Unexpected error: %s", err)
            raise HomeAssistantError(f"Unexpected error: {err}") from err
