"""Conversation support for the Google Generative AI Conversation integration."""

from __future__ import annotations

import codecs
from collections.abc import Callable
from typing import Any, Literal, cast

from google.api_core.exceptions import GoogleAPIError
import google.generativeai as genai
from google.generativeai import protos
import google.generativeai.types as genai_types
from google.protobuf.json_format import MessageToDict
from voluptuous_openapi import convert

from homeassistant.components import assist_pipeline, conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LLM_HASS_API, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import chat_session, device_registry as dr, intent, llm
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_CHAT_MODEL,
    CONF_DANGEROUS_BLOCK_THRESHOLD,
    CONF_HARASSMENT_BLOCK_THRESHOLD,
    CONF_HATE_BLOCK_THRESHOLD,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_SEXUAL_BLOCK_THRESHOLD,
    CONF_TEMPERATURE,
    CONF_TOP_K,
    CONF_TOP_P,
    DOMAIN,
    LOGGER,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_HARM_BLOCK_THRESHOLD,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_K,
    RECOMMENDED_TOP_P,
)

# Max number of back and forth with the LLM to generate a response
MAX_TOOL_ITERATIONS = 10


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up conversation entities."""
    agent = GoogleGenerativeAIConversationEntity(config_entry)
    async_add_entities([agent])


SUPPORTED_SCHEMA_KEYS = {
    "type",
    "format",
    "description",
    "nullable",
    "enum",
    "items",
    "properties",
    "required",
}


def _format_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Format the schema to protobuf."""
    if (subschemas := schema.get("anyOf")) or (subschemas := schema.get("allOf")):
        for subschema in subschemas:  # Gemini API does not support anyOf and allOf keys
            if "type" in subschema:  # Fallback to first subschema with 'type' field
                return _format_schema(subschema)
        return _format_schema(
            subschemas[0]
        )  # Or, if not found, to any of the subschemas

    result = {}
    for key, val in schema.items():
        if key not in SUPPORTED_SCHEMA_KEYS:
            continue
        if key == "type":
            key = "type_"
            val = val.upper()
        elif key == "format":
            if schema.get("type") == "string" and val != "enum":
                continue
            if schema.get("type") not in ("number", "integer", "string"):
                continue
            key = "format_"
        elif key == "items":
            val = _format_schema(val)
        elif key == "properties":
            val = {k: _format_schema(v) for k, v in val.items()}
        result[key] = val

    if result.get("enum") and result.get("type_") != "STRING":
        # enum is only allowed for STRING type. This is safe as long as the schema
        # contains vol.Coerce for the respective type, for example:
        # vol.All(vol.Coerce(int), vol.In([1, 2, 3]))
        result["type_"] = "STRING"
        result["enum"] = [str(item) for item in result["enum"]]

    if result.get("type_") == "OBJECT" and not result.get("properties"):
        # An object with undefined properties is not supported by Gemini API.
        # Fallback to JSON string. This will probably fail for most tools that want it,
        # but we don't have a better fallback strategy so far.
        result["properties"] = {"json": {"type_": "STRING"}}
        result["required"] = []
    return result


def _format_tool(
    tool: llm.Tool, custom_serializer: Callable[[Any], Any] | None
) -> dict[str, Any]:
    """Format tool specification."""

    if tool.parameters.schema:
        parameters = _format_schema(
            convert(tool.parameters, custom_serializer=custom_serializer)
        )
    else:
        parameters = None

    return protos.Tool(
        {
            "function_declarations": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": parameters,
                }
            ]
        }
    )


def _escape_decode(value: Any) -> Any:
    """Recursively call codecs.escape_decode on all values."""
    if isinstance(value, str):
        return codecs.escape_decode(bytes(value, "utf-8"))[0].decode("utf-8")  # type: ignore[attr-defined]
    if isinstance(value, list):
        return [_escape_decode(item) for item in value]
    if isinstance(value, dict):
        return {k: _escape_decode(v) for k, v in value.items()}
    return value


def _create_google_tool_response_content(
    content: list[conversation.ToolResultContent],
) -> protos.Content:
    """Create a Google tool response content."""
    return protos.Content(
        parts=[
            protos.Part(
                function_response=protos.FunctionResponse(
                    name=tool_result.tool_name, response=tool_result.tool_result
                )
            )
            for tool_result in content
        ]
    )


def _convert_content(
    content: conversation.UserContent
    | conversation.AssistantContent
    | conversation.SystemContent,
) -> genai_types.ContentDict:
    """Convert HA content to Google content."""
    if content.role != "assistant" or not content.tool_calls:  # type: ignore[union-attr]
        role = "model" if content.role == "assistant" else content.role
        return {"role": role, "parts": content.content}

    # Handle the Assistant content with tool calls.
    assert type(content) is conversation.AssistantContent
    parts = []

    if content.content:
        parts.append(protos.Part(text=content.content))

    if content.tool_calls:
        parts.extend(
            [
                protos.Part(
                    function_call=protos.FunctionCall(
                        name=tool_call.tool_name,
                        args=_escape_decode(tool_call.tool_args),
                    )
                )
                for tool_call in content.tool_calls
            ]
        )

    return protos.Content({"role": "model", "parts": parts})


class GoogleGenerativeAIConversationEntity(
    conversation.ConversationEntity, conversation.AbstractConversationAgent
):
    """Google Generative AI conversation agent."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self.entry = entry
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Google",
            model="Generative AI",
            entry_type=dr.DeviceEntryType.SERVICE,
        )
        if self.entry.options.get(CONF_LLM_HASS_API):
            self._attr_supported_features = (
                conversation.ConversationEntityFeature.CONTROL
            )

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()
        assist_pipeline.async_migrate_engine(
            self.hass, "conversation", self.entry.entry_id, self.entity_id
        )
        conversation.async_set_agent(self.hass, self.entry, self)
        self.entry.async_on_unload(
            self.entry.add_update_listener(self._async_entry_update_listener)
        )

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from Home Assistant."""
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Process a sentence."""
        with (
            chat_session.async_get_chat_session(
                self.hass, user_input.conversation_id
            ) as session,
            conversation.async_get_chat_log(self.hass, session, user_input) as chat_log,
        ):
            return await self._async_handle_message(user_input, chat_log)

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Call the API."""
        options = self.entry.options

        try:
            await chat_log.async_update_llm_data(
                DOMAIN,
                user_input,
                options.get(CONF_LLM_HASS_API),
                options.get(CONF_PROMPT),
            )
        except conversation.ConverseError as err:
            return err.as_conversation_result()

        tools: list[dict[str, Any]] | None = None
        if chat_log.llm_api:
            tools = [
                _format_tool(tool, chat_log.llm_api.custom_serializer)
                for tool in chat_log.llm_api.tools
            ]

        model_name = self.entry.options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL)
        # Gemini 1.0 doesn't support system_instruction while 1.5 does.
        # Assume future versions will support it (if not, the request fails with a
        # clear message at which point we can fix).
        supports_system_instruction = (
            "gemini-1.0" not in model_name and "gemini-pro" not in model_name
        )

        prompt = chat_log.content[0].content  # type: ignore[union-attr]
        messages: list[genai_types.ContentDict] = []

        # Google groups tool results, we do not. Group them before sending.
        tool_results: list[conversation.ToolResultContent] = []

        for chat_content in chat_log.content[1:]:
            if chat_content.role == "tool_result":
                # mypy doesn't like picking a type based on checking shared property 'role'
                tool_results.append(cast(conversation.ToolResultContent, chat_content))
                continue

            if tool_results:
                messages.append(_create_google_tool_response_content(tool_results))
                tool_results.clear()

            messages.append(
                _convert_content(
                    cast(
                        conversation.UserContent
                        | conversation.SystemContent
                        | conversation.AssistantContent,
                        chat_content,
                    )
                )
            )

        if tool_results:
            messages.append(_create_google_tool_response_content(tool_results))

        model = genai.GenerativeModel(
            model_name=model_name,
            generation_config={
                "temperature": self.entry.options.get(
                    CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE
                ),
                "top_p": self.entry.options.get(CONF_TOP_P, RECOMMENDED_TOP_P),
                "top_k": self.entry.options.get(CONF_TOP_K, RECOMMENDED_TOP_K),
                "max_output_tokens": self.entry.options.get(
                    CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS
                ),
            },
            safety_settings={
                "HARASSMENT": self.entry.options.get(
                    CONF_HARASSMENT_BLOCK_THRESHOLD, RECOMMENDED_HARM_BLOCK_THRESHOLD
                ),
                "HATE": self.entry.options.get(
                    CONF_HATE_BLOCK_THRESHOLD, RECOMMENDED_HARM_BLOCK_THRESHOLD
                ),
                "SEXUAL": self.entry.options.get(
                    CONF_SEXUAL_BLOCK_THRESHOLD, RECOMMENDED_HARM_BLOCK_THRESHOLD
                ),
                "DANGEROUS": self.entry.options.get(
                    CONF_DANGEROUS_BLOCK_THRESHOLD, RECOMMENDED_HARM_BLOCK_THRESHOLD
                ),
            },
            tools=tools or None,
            system_instruction=prompt if supports_system_instruction else None,
        )

        if not supports_system_instruction:
            messages = [
                {"role": "user", "parts": prompt},
                {"role": "model", "parts": "Ok"},
                *messages,
            ]

        chat = model.start_chat(history=messages)
        chat_request = user_input.text
        # To prevent infinite loops, we limit the number of iterations
        for _iteration in range(MAX_TOOL_ITERATIONS):
            try:
                chat_response = await chat.send_message_async(chat_request)
            except (
                GoogleAPIError,
                ValueError,
                genai_types.BlockedPromptException,
                genai_types.StopCandidateException,
            ) as err:
                LOGGER.error("Error sending message: %s %s", type(err), err)

                if isinstance(
                    err, genai_types.StopCandidateException
                ) and "finish_reason: SAFETY\n" in str(err):
                    error = "The message got blocked by your safety settings"
                else:
                    error = (
                        f"Sorry, I had a problem talking to Google Generative AI: {err}"
                    )

                raise HomeAssistantError(error) from err

            LOGGER.debug("Response: %s", chat_response.parts)
            if not chat_response.parts:
                raise HomeAssistantError(
                    "Sorry, I had a problem getting a response from Google Generative AI."
                )
            content = " ".join(
                [part.text.strip() for part in chat_response.parts if part.text]
            )

            tool_calls = []
            for part in chat_response.parts:
                if not part.function_call:
                    continue
                tool_call = MessageToDict(part.function_call._pb)  # noqa: SLF001
                tool_name = tool_call["name"]
                tool_args = _escape_decode(tool_call["args"])
                tool_calls.append(
                    llm.ToolInput(tool_name=tool_name, tool_args=tool_args)
                )

            chat_request = _create_google_tool_response_content(
                [
                    tool_response
                    async for tool_response in chat_log.async_add_assistant_content(
                        conversation.AssistantContent(
                            agent_id=user_input.agent_id,
                            content=content,
                            tool_calls=tool_calls or None,
                        )
                    )
                ]
            )

            if not tool_calls:
                break

        response = intent.IntentResponse(language=user_input.language)
        response.async_set_speech(
            " ".join([part.text.strip() for part in chat_response.parts if part.text])
        )
        return conversation.ConversationResult(
            response=response, conversation_id=chat_log.conversation_id
        )

    async def _async_entry_update_listener(
        self, hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Handle options update."""
        # Reload as we update device info + entity name + supported features
        await hass.config_entries.async_reload(entry.entry_id)
