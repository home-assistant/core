"""Conversation entity for Cloudflare Workers AI."""

from __future__ import annotations

from collections.abc import Callable
import json
import logging
from typing import Any, Literal
import uuid

import voluptuous as vol
from voluptuous_openapi import convert

from homeassistant.components import conversation
from homeassistant.components.conversation import (
    AssistantContent,
    ChatLog,
    ConversationEntity,
    ConversationInput,
    ConversationResult,
    ToolResultContent,
)
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_LLM_HASS_API, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .client import CloudflareAIAuthError, CloudflareAIClient, CloudflareAIError
from .const import (
    CONF_CHAT_MODEL,
    CONF_ENABLE_THINKING,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_TEMPERATURE,
    DEFAULT_CHAT_MODEL,
    DEFAULT_ENABLE_THINKING,
    DEFAULT_MAX_TOKENS,
    DEFAULT_PROMPT,
    DEFAULT_TEMPERATURE,
    DOMAIN,
    FUNCTION_CALLING_MODELS,
    MAX_TOOL_ITERATIONS,
    MAX_TOOL_ITERATIONS_EXCEEDED_MSG,
    SUBENTRY_CONVERSATION,
)
from .entity import CloudflareAIBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up conversation entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type == SUBENTRY_CONVERSATION:
            async_add_entities(
                [CloudflareConversationEntity(config_entry, subentry)],
                config_subentry_id=subentry.subentry_id,
            )


def _format_tool(
    tool: llm.Tool, custom_serializer: Callable[[Any], Any] | None
) -> dict[str, Any]:
    """Format tool specification."""
    tool_spec: dict[str, Any] = {
        "name": tool.name,
        "parameters": convert(tool.parameters, custom_serializer=custom_serializer),
    }
    if tool.description:
        tool_spec["description"] = tool.description
    return {"type": "function", "function": tool_spec}


class CloudflareConversationEntity(
    ConversationEntity,
    conversation.AbstractConversationAgent,
    CloudflareAIBaseEntity,
):
    """Cloudflare Workers AI conversation agent."""

    _attr_supports_streaming = False

    def __init__(
        self,
        config_entry: ConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize the conversation entity."""
        super().__init__(config_entry, subentry, CONF_CHAT_MODEL)
        model = subentry.data.get(CONF_CHAT_MODEL, DEFAULT_CHAT_MODEL)
        self._model = model
        self._supports_tools = model in FUNCTION_CALLING_MODELS
        if self._supports_tools and subentry.data.get(CONF_LLM_HASS_API):
            self._attr_supported_features = (
                conversation.ConversationEntityFeature.CONTROL
            )

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return supported languages."""
        return MATCH_ALL

    async def async_added_to_hass(self) -> None:
        """Register as a conversation agent when added to hass."""
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self.entry, self)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister as a conversation agent when removed."""
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    async def _async_handle_message(
        self,
        user_input: ConversationInput,
        chat_log: ChatLog,
    ) -> ConversationResult:
        """Handle an incoming chat message."""
        client: CloudflareAIClient = self.entry.runtime_data
        options = self.subentry.data

        # Provide LLM data (tools + system prompt) if configured
        try:
            await chat_log.async_provide_llm_data(
                user_input.as_llm_context(DOMAIN),
                options.get(CONF_LLM_HASS_API),
                options.get(CONF_PROMPT, DEFAULT_PROMPT),
                user_input.extra_system_prompt,
            )
        except conversation.ConverseError as err:
            return err.as_conversation_result()

        # Build tools list
        tools: list[dict[str, Any]] | None = None
        if self._supports_tools and chat_log.llm_api:
            tools = [
                _format_tool(tool, chat_log.llm_api.custom_serializer)
                for tool in chat_log.llm_api.tools
            ]
            _LOGGER.debug("Sending %d tools to model %s", len(tools), self._model)

        # Convert chat log to OpenAI-compatible messages
        messages = self._build_messages(chat_log)

        model = options.get(CONF_CHAT_MODEL, DEFAULT_CHAT_MODEL)
        max_tokens = int(options.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS))
        temperature = float(options.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE))
        enable_thinking = bool(
            options.get(CONF_ENABLE_THINKING, DEFAULT_ENABLE_THINKING)
        )

        try:
            for _iteration in range(MAX_TOOL_ITERATIONS):
                request_body: dict[str, Any] = {
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "chat_template_kwargs": {
                        "enable_thinking": enable_thinking,
                    },
                }
                if tools:
                    request_body["tools"] = tools

                response_data = await client.run_model(
                    model, request_body, timeout=120.0
                )
                assistant_message = self._parse_response(response_data)
                self._trace_usage(chat_log, response_data)

                if assistant_message.get("tool_calls"):
                    self._append_tool_call_messages(messages, assistant_message)
                    tool_results = await self._execute_tool_calls(
                        assistant_message["tool_calls"],
                        chat_log,
                        user_input,
                    )
                    messages.extend(tool_results)
                    continue

                # Model responded with text — done
                chat_log.async_add_assistant_content_without_tools(
                    AssistantContent(
                        agent_id=user_input.agent_id,
                        content=assistant_message.get("content", ""),
                    )
                )
                break
            else:
                chat_log.async_add_assistant_content_without_tools(
                    AssistantContent(
                        agent_id=user_input.agent_id,
                        content=MAX_TOOL_ITERATIONS_EXCEEDED_MSG,
                    )
                )

        except CloudflareAIAuthError as err:
            _LOGGER.error("Authentication error: %s", err)
            self.entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from err
        except CloudflareAIError as err:
            _LOGGER.error("Cloudflare AI error: %s", err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="api_error",
                translation_placeholders={"error": str(err)},
            ) from err

        return conversation.async_get_result_from_chat_log(user_input, chat_log)

    def _build_messages(self, chat_log: ChatLog) -> list[dict[str, Any]]:
        """Convert chat log content to OpenAI-compatible messages."""
        messages: list[dict[str, Any]] = []

        for content in chat_log.content:
            if isinstance(content, conversation.SystemContent):
                messages.append(
                    {
                        "role": "system",
                        "content": content.content or "",
                    }
                )
            elif isinstance(content, conversation.UserContent):
                messages.append(
                    {
                        "role": "user",
                        "content": content.content or "",
                    }
                )
            elif isinstance(content, conversation.AssistantContent):
                msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": content.content or "",
                }
                if content.tool_calls:
                    msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.tool_name,
                                "arguments": json.dumps(tc.tool_args),
                            },
                        }
                        for tc in content.tool_calls
                    ]
                messages.append(msg)
            elif isinstance(content, ToolResultContent):
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": content.tool_call_id,
                        "content": json.dumps(content.tool_result),
                    }
                )

        return messages

    def _parse_response(self, data: Any) -> dict[str, Any]:
        """Parse the model response into an assistant message dict."""
        # Workers AI text-generation returns:
        # {"response": "text"} for non-tool responses
        # or OpenAI-compatible format with choices
        if isinstance(data, dict):
            # OpenAI-compatible format (from gateway or newer models)
            if "choices" in data:
                choice = data["choices"][0]
                return choice.get("message", {"content": "", "role": "assistant"})

            # Workers AI native format
            # Response may contain both "response" (text) and "tool_calls"
            if "response" in data:
                result: dict[str, Any] = {
                    "role": "assistant",
                    "content": data["response"] or "",
                }
                if data.get("tool_calls"):
                    result["tool_calls"] = data["tool_calls"]
                return result

            # Direct tool_calls format from some CF models
            if "tool_calls" in data:
                return {
                    "role": "assistant",
                    "content": data.get("content", ""),
                    "tool_calls": data["tool_calls"],
                }

        # Fallback
        return {
            "role": "assistant",
            "content": str(data) if data else "",
        }

    @staticmethod
    def _trace_usage(chat_log: ChatLog, response_data: Any) -> None:
        """Track token usage from the model response."""
        if not isinstance(response_data, dict):
            return
        usage = response_data.get("usage")
        if not usage:
            return
        stats: dict[str, int] = {}
        if "prompt_tokens" in usage:
            stats["input_tokens"] = usage["prompt_tokens"]
        if "completion_tokens" in usage:
            stats["output_tokens"] = usage["completion_tokens"]
        if stats:
            chat_log.async_trace({"stats": stats})

    @staticmethod
    def _append_tool_call_messages(
        messages: list[dict[str, Any]],
        assistant_message: dict[str, Any],
    ) -> None:
        """Normalize and append an assistant tool-call message to the history.

        Generates a unique fallback ID for tool calls that don't have one
        and writes it back to the original tool_call dict so subsequent
        tool result messages reference the correct tool_call_id.
        """
        normalized_tcs = []
        for tc in assistant_message["tool_calls"]:
            if "id" not in tc:
                tc["id"] = f"call_{uuid.uuid4().hex[:8]}"

            if "function" not in tc:
                # CF native format -> normalize to OpenAI format.
                normalized_tcs.append(
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc.get("name", ""),
                            "arguments": json.dumps(tc.get("arguments", {}))
                            if not isinstance(tc.get("arguments"), str)
                            else tc.get("arguments", "{}"),
                        },
                    }
                )
            else:
                normalized_tcs.append(tc)

        messages.append(
            {
                "role": "assistant",
                "content": assistant_message.get("content", ""),
                "tool_calls": normalized_tcs,
            }
        )

    async def _execute_tool_calls(
        self,
        tool_calls: list[dict[str, Any]],
        chat_log: ChatLog,
        user_input: ConversationInput,
    ) -> list[dict[str, Any]]:
        """Execute tool calls and return tool result messages."""
        results: list[dict[str, Any]] = []

        for tc in tool_calls:
            # Ensure each tool call has a stable ID. _append_tool_call_messages
            # may have already assigned one; if not, generate one here so the
            # tool result message references a consistent tool_call_id.
            if "id" not in tc:
                tc["id"] = f"call_{uuid.uuid4().hex[:8]}"
            tool_call_id = tc["id"]

            # CF Workers AI uses {"name": ..., "arguments": ...} directly
            # OpenAI uses {"function": {"name": ..., "arguments": ...}}
            if "function" in tc:
                function = tc["function"]
                tool_name = function.get("name", "")
                raw_args = function.get("arguments", "{}")
            else:
                tool_name = tc.get("name", "")
                raw_args = tc.get("arguments", "{}")
            try:
                tool_args = (
                    json.loads(raw_args)
                    if isinstance(raw_args, str)
                    else (raw_args or {})
                )
            except json.JSONDecodeError:
                tool_args = {}

            _LOGGER.debug("Executing tool %s with args: %s", tool_name, tool_args)

            if chat_log.llm_api:
                try:
                    tool_input = llm.ToolInput(
                        tool_name=tool_name,
                        tool_args=tool_args,
                    )
                    tool_response = await chat_log.llm_api.async_call_tool(tool_input)
                    result_str = json.dumps(tool_response)
                except (HomeAssistantError, vol.Invalid) as err:
                    _LOGGER.error("Tool call %s failed: %s", tool_name, err)
                    result_str = json.dumps({"error": str(err)})
            else:
                result_str = json.dumps({"error": "No LLM API configured"})

            results.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": result_str,
                }
            )

        return results
