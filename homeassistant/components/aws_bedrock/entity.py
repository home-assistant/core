"""Base entity for AWS Bedrock."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from functools import partial
import re
from typing import Any

from voluptuous_openapi import convert

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigSubentry
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, llm
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

from . import AWSBedrockConfigEntry
from .const import (
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_TEMPERATURE,
    DEFAULT,
    DOMAIN,
    LOGGER,
    MAX_TOOL_ITERATIONS,
)


def _clean_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Clean JSON schema to only include AWS Bedrock supported fields.

    AWS Bedrock requirements:
    - Top level ONLY: type (must be "object"), properties, required
    - Property level: type, items, enum, description, properties, required

    Remove unsupported top-level fields: $schema, title, additionalProperties
    """
    if not isinstance(schema, dict):
        return schema

    cleaned: dict[str, Any] = {}

    # Top-level only gets these three fields
    top_level_allowed = {"type", "properties", "required"}
    # Property-level can have additional fields like description
    property_level_allowed = {
        "type",
        "properties",
        "required",
        "items",
        "enum",
        "description",
    }

    # Check if this is top-level (has properties key) or a property definition
    is_top_level = "properties" in schema and isinstance(schema.get("properties"), dict)
    allowed_fields = top_level_allowed if is_top_level else property_level_allowed

    for key, value in schema.items():
        if key not in allowed_fields:
            continue

        if key == "properties" and isinstance(value, dict):
            # Recursively clean nested properties
            cleaned_properties: dict[str, Any] = {}
            for prop_name, prop_value in value.items():
                cleaned_prop = _clean_schema(prop_value)
                # Drop properties that become empty after cleaning.
                if cleaned_prop:
                    cleaned_properties[prop_name] = cleaned_prop
            cleaned[key] = cleaned_properties
        elif key == "items" and isinstance(value, dict):
            # Recursively clean array items
            cleaned_items = _clean_schema(value)
            if cleaned_items:
                cleaned[key] = cleaned_items
        else:
            cleaned[key] = value

    # If this is an object schema, ensure required exists (Nova is picky here)
    # and ensure required only references properties that exist.
    if cleaned.get("type") == "object" or "properties" in cleaned:
        properties = cleaned.get("properties")
        if isinstance(properties, dict):
            cleaned.setdefault("required", [])
            if isinstance(cleaned.get("required"), list):
                cleaned["required"] = [
                    req for req in cleaned["required"] if req in properties
                ]

    return cleaned


def _format_tool(
    tool: llm.Tool,
    custom_serializer: Callable[[Any], Any] | None,
    tool_name: str | None = None,
    is_nova_model: bool = False,
) -> dict[str, Any]:
    """Format tool specification for Bedrock."""
    # Convert the voluptuous schema to JSON schema
    schema = convert(tool.parameters, custom_serializer=custom_serializer)

    # AWS Bedrock Nova models have specific schema requirements
    # Only apply cleaning for Nova models to avoid breaking Claude
    # See: https://docs.aws.amazon.com/nova/latest/userguide/tools-troubleshooting.html
    if is_nova_model:
        schema = _clean_schema(schema)

    # Ensure top-level type is object (required by all Converse API models)
    if "type" not in schema:
        schema["type"] = "object"

    # Nova models: ensure required exists (empty is fine)
    if schema.get("type") == "object":
        schema.setdefault("required", [])

    return {
        "toolSpec": {
            "name": tool_name or tool.name,
            "description": tool.description or "",
            "inputSchema": {
                "json": schema,
            },
        }
    }


def _sanitize_bedrock_tool_name(name: str) -> str:
    """Return a Bedrock/Nova-compatible tool name.

    Nova tool use is picky about tool names; in practice, using only letters,
    digits, and underscores avoids ModelErrorException tool-use failures.
    """
    # Replace any non-alphanumeric/underscore with underscore.
    sanitized = re.sub(r"[^0-9A-Za-z_]", "_", name)
    # Avoid leading digits.
    if sanitized and sanitized[0].isdigit():
        sanitized = f"t_{sanitized}"
    return sanitized or "tool"


def _build_tool_name_maps(
    tools: Sequence[llm.Tool],
) -> tuple[dict[str, str], dict[str, str]]:
    """Build HA<->Bedrock tool name mappings.

    Returns:
        Tuple of (ha_to_bedrock, bedrock_to_ha)
    """
    ha_to_bedrock: dict[str, str] = {}
    bedrock_to_ha: dict[str, str] = {}

    for tool in tools:
        base = _sanitize_bedrock_tool_name(tool.name)
        candidate = base
        suffix = 1
        while candidate in bedrock_to_ha and bedrock_to_ha[candidate] != tool.name:
            suffix += 1
            candidate = f"{base}_{suffix}"

        ha_to_bedrock[tool.name] = candidate
        bedrock_to_ha[candidate] = tool.name

    return ha_to_bedrock, bedrock_to_ha


def _process_thinking_content(text: str) -> tuple[str, bool]:
    """Process text content, removing thinking tags and detecting if thinking occurred.

    Args:
        text: The text content to process

    Returns:
        Tuple of (cleaned_text, had_thinking_tags)
    """
    # Pattern to match <thinking>...</thinking> tags (case insensitive, multiline)
    thinking_pattern = re.compile(
        r"<thinking>.*?</thinking>", re.IGNORECASE | re.DOTALL
    )

    # Check if thinking tags exist
    had_thinking = bool(thinking_pattern.search(text))

    # Remove thinking tags and content
    cleaned_text = thinking_pattern.sub("", text)

    # Clean up extra whitespace that may be left
    cleaned_text = re.sub(r"\n\s*\n\s*\n", "\n\n", cleaned_text)
    cleaned_text = cleaned_text.strip()

    return cleaned_text, had_thinking


def _convert_messages(
    chat_content: Sequence[conversation.Content],
    ha_to_bedrock_tool_name: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Transform HA chat_log content into Bedrock Converse API format.

    Skips assistant messages that contain only text feedback with no tool calls,
    as these are UI-only messages during tool execution that should not be sent to Bedrock.
    """
    messages: list[dict[str, Any]] = []
    pending_tool_results: list[dict[str, Any]] = []
    awaiting_tool_results = False

    def flush_tool_results():
        """Add pending tool results as a single user message."""
        nonlocal awaiting_tool_results
        if pending_tool_results:
            messages.append(
                {
                    "role": "user",
                    "content": pending_tool_results.copy(),
                }
            )
            pending_tool_results.clear()
            # We have now provided the tool results back to the model.
            awaiting_tool_results = False

    for content in chat_content:
        if isinstance(content, conversation.SystemContent):
            # System content is handled separately in Bedrock
            continue
        if isinstance(content, conversation.UserContent):
            flush_tool_results()
            messages.append(
                {
                    "role": "user",
                    "content": [{"text": content.content}],
                }
            )
        elif isinstance(content, conversation.AssistantContent):
            # If we are waiting for tool results, Home Assistant may inject UI-only
            # assistant messages (text-only) while tools run. These must NOT be sent
            # back to the model because Bedrock expects toolResult(s) to directly
            # follow the assistant toolUse message.
            if (
                awaiting_tool_results
                and not content.tool_calls
                and not pending_tool_results
            ):
                continue

            flush_tool_results()
            message_content: list[dict[str, Any]] = []
            if content.content:
                message_content.append({"text": content.content})
            if content.tool_calls:
                awaiting_tool_results = True
                message_content.extend(
                    {
                        "toolUse": {
                            "toolUseId": tool_call.id,
                            "name": (ha_to_bedrock_tool_name or {}).get(
                                tool_call.tool_name, tool_call.tool_name
                            ),
                            "input": tool_call.tool_args,
                        }
                    }
                    for tool_call in content.tool_calls
                )
            # Only add message if there's actual content or tool calls
            if message_content:
                messages.append(
                    {
                        "role": "assistant",
                        "content": message_content,
                    }
                )
        elif isinstance(content, conversation.ToolResultContent):
            # Accumulate tool results to group them in a single user message
            pending_tool_results.append(
                {
                    "toolResult": {
                        "toolUseId": content.tool_call_id,
                        "content": [
                            {"json": content.tool_result}
                            if isinstance(content.tool_result, dict)
                            else {"text": str(content.tool_result)}
                        ],
                    }
                }
            )

    # Flush any remaining tool results
    flush_tool_results()

    return messages


class AWSBedrockBaseLLMEntity(Entity):
    """Base entity for AWS Bedrock LLM."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False

    def __init__(self, entry: AWSBedrockConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the entity."""
        self.entry = entry
        self.subentry = subentry
        self._attr_unique_id = subentry.subentry_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="AWS",
            model="Bedrock",
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    async def _async_handle_chat_log(
        self,
        chat_log: conversation.ChatLog,
        structure_name: str | None = None,
        structure: dict[str, Any] | None = None,
    ) -> None:
        """Handle a chat log."""
        options = self.subentry.data
        model_id = options.get(CONF_CHAT_MODEL, DEFAULT[CONF_CHAT_MODEL])
        temperature = options.get(CONF_TEMPERATURE, DEFAULT[CONF_TEMPERATURE])
        max_tokens = options.get(CONF_MAX_TOKENS, DEFAULT[CONF_MAX_TOKENS])

        # Extract system message
        system_content = ""
        if chat_log.content and isinstance(
            chat_log.content[0], conversation.SystemContent
        ):
            system_content = chat_log.content[0].content

        # Detect if using Nova model for model-specific configurations
        is_nova_model = "nova" in model_id.lower()

        # Build tool configuration if LLM API is available
        tools: list[dict[str, Any]] = []
        ha_to_bedrock_tool_name: dict[str, str] | None = None
        bedrock_to_ha_tool_name: dict[str, str] | None = None

        if chat_log.llm_api and chat_log.llm_api.tools:
            ha_to_bedrock_tool_name, bedrock_to_ha_tool_name = _build_tool_name_maps(
                chat_log.llm_api.tools
            )
            tools = [
                _format_tool(
                    tool,
                    chat_log.llm_api.custom_serializer,
                    tool_name=ha_to_bedrock_tool_name.get(tool.name, tool.name),
                    is_nova_model=is_nova_model,
                )
                for tool in chat_log.llm_api.tools
            ]

        # AWS Bedrock Nova models: Use temperature=0 for greedy decoding with tools
        # Claude models work fine with normal temperature settings
        # See: https://docs.aws.amazon.com/nova/latest/userguide/tools-troubleshooting.html
        if tools and is_nova_model:
            temperature = 0

        # Ensure max tokens is large enough for tool use
        # Tool outputs can be large, minimum recommended is 3000
        if tools and max_tokens < 3000:
            LOGGER.debug("Increasing maxTokens to 3000 for tool use")
            max_tokens = 3000

        inference_config = {
            "maxTokens": max_tokens,
            "temperature": temperature,
        }

        # Handle structured output - add to tools before loop
        if structure and structure_name:
            structure_name = slugify(structure_name)

            # Nova models require a restricted JSON schema shape.
            # Ensure we do not pass unsupported fields in structured output schemas.
            schema = structure
            if is_nova_model:
                schema = _clean_schema(schema)
            if "type" not in schema:
                schema = {**schema, "type": "object"}
            if schema.get("type") == "object":
                schema.setdefault("required", [])

            tools.append(
                {
                    "toolSpec": {
                        "name": structure_name,
                        "description": "Use this tool to reply to the user",
                        "inputSchema": {
                            "json": schema,
                        },
                    }
                }
            )

        client = self.entry.runtime_data

        # To prevent infinite loops, we limit the number of iterations
        for _iteration in range(MAX_TOOL_ITERATIONS):
            # Convert chat log content to messages at the start of each iteration
            # This ensures tool results are included in the conversation
            content_to_process = chat_log.content
            if chat_log.content and isinstance(
                chat_log.content[0], conversation.SystemContent
            ):
                content_to_process = chat_log.content[1:]

            messages: list[dict[str, Any]] = _convert_messages(
                content_to_process,
                ha_to_bedrock_tool_name=ha_to_bedrock_tool_name or None,
            )

            request_params: dict[str, Any] = {
                "modelId": model_id,
                "messages": messages,
                "inferenceConfig": inference_config,
            }

            # AWS Bedrock Nova models: Add topK=1 for greedy decoding
            # This is specific to Nova and must be in additionalModelRequestFields
            # See: https://docs.aws.amazon.com/nova/latest/userguide/tools-troubleshooting.html
            if tools and is_nova_model:
                request_params["additionalModelRequestFields"] = {
                    "inferenceConfig": {"topK": 1}
                }

            if system_content:
                request_params["system"] = [{"text": system_content}]

            if tools:
                request_params["toolConfig"] = {"tools": tools}
                LOGGER.debug(
                    "Iteration %d: Sending %d messages with %d tools to Bedrock (model=%s)",
                    _iteration,
                    len(messages),
                    len(tools),
                    model_id,
                )

            try:
                response = await self.hass.async_add_executor_job(
                    partial(client.converse, **request_params)
                )
            except Exception as err:
                LOGGER.exception("Error calling Bedrock")
                raise HomeAssistantError(
                    f"Sorry, I had a problem talking to AWS Bedrock: {err}"
                ) from err

            LOGGER.debug("Received response: %s", response)

            # Process response
            output = response.get("output", {})
            message_content = output.get("message", {}).get("content", [])

            content_parts = []
            tool_calls = []
            had_thinking = False

            for content_item in message_content:
                if "text" in content_item:
                    raw_text = content_item["text"]
                    # Process thinking tags
                    cleaned_text, has_thinking = _process_thinking_content(raw_text)
                    if has_thinking:
                        had_thinking = True
                    if cleaned_text:  # Only add non-empty cleaned text
                        content_parts.append(cleaned_text)
                elif "toolUse" in content_item:
                    tool_use = content_item["toolUse"]
                    raw_tool_name = tool_use.get("name")
                    if not isinstance(raw_tool_name, str) or not raw_tool_name:
                        raise HomeAssistantError(
                            "Received toolUse without a valid tool name"
                        )

                    tool_name = (
                        bedrock_to_ha_tool_name.get(raw_tool_name, raw_tool_name)
                        if bedrock_to_ha_tool_name
                        else raw_tool_name
                    )
                    tool_calls.append(
                        llm.ToolInput(
                            id=tool_use["toolUseId"],
                            tool_name=tool_name,
                            tool_args=tool_use["input"],
                        )
                    )

            # Handle case where model only produced thinking content
            # Don't add to chat log, just continue to next iteration to call model again
            if had_thinking and not content_parts and not tool_calls:
                LOGGER.debug(
                    "Model produced only thinking content, calling model again"
                )
                # Don't add message to history, just continue loop
                continue

            # Add assistant content and execute tool calls
            # Must consume the async generator to trigger tool execution
            async for _ in chat_log.async_add_assistant_content(
                conversation.AssistantContent(
                    agent_id=self.entity_id,
                    content=" ".join(content_parts) if content_parts else None,
                    tool_calls=tool_calls or None,
                )
            ):
                pass

            # Check if we need to continue processing tool results
            if not chat_log.unresponded_tool_results:
                break
