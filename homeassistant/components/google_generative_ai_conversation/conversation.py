"""Conversation support for the Google Generative AI Conversation integration."""

from __future__ import annotations

import codecs
from collections.abc import Callable
from typing import Any, Literal

from google.api_core.exceptions import GoogleAPIError
import google.generativeai as genai
from google.generativeai import protos
import google.generativeai.types as genai_types
from google.protobuf.json_format import MessageToDict
import voluptuous as vol
from voluptuous_openapi import convert

from homeassistant.components import assist_pipeline, conversation
from homeassistant.components.conversation import trace
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LLM_HASS_API, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.helpers import device_registry as dr, intent, llm, template
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import ulid

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
    async_add_entities: AddEntitiesCallback,
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


class GoogleGenerativeAIConversationEntity(
    conversation.ConversationEntity, conversation.AbstractConversationAgent
):
    """Google Generative AI conversation agent."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self.entry = entry
        self.history: dict[str, list[genai_types.ContentType]] = {}
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
        result = conversation.ConversationResult(
            response=intent.IntentResponse(language=user_input.language),
            conversation_id=user_input.conversation_id
            if user_input.conversation_id in self.history
            else ulid.ulid_now(),
        )
        assert result.conversation_id

        llm_context = llm.LLMContext(
            platform=DOMAIN,
            context=user_input.context,
            user_prompt=user_input.text,
            language=user_input.language,
            assistant=conversation.DOMAIN,
            device_id=user_input.device_id,
        )
        llm_api: llm.APIInstance | None = None
        tools: list[dict[str, Any]] | None = None
        if self.entry.options.get(CONF_LLM_HASS_API):
            try:
                llm_api = await llm.async_get_api(
                    self.hass,
                    self.entry.options[CONF_LLM_HASS_API],
                    llm_context,
                )
            except HomeAssistantError as err:
                LOGGER.error("Error getting LLM API: %s", err)
                result.response.async_set_error(
                    intent.IntentResponseErrorCode.UNKNOWN,
                    f"Error preparing LLM API: {err}",
                )
                return result
            tools = [
                _format_tool(tool, llm_api.custom_serializer) for tool in llm_api.tools
            ]

        try:
            prompt = await self._async_render_prompt(user_input, llm_api, llm_context)
        except TemplateError as err:
            LOGGER.error("Error rendering prompt: %s", err)
            result.response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                f"Sorry, I had a problem with my template: {err}",
            )
            return result

        model_name = self.entry.options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL)
        # Gemini 1.0 doesn't support system_instruction while 1.5 does.
        # Assume future versions will support it (if not, the request fails with a
        # clear message at which point we can fix).
        supports_system_instruction = (
            "gemini-1.0" not in model_name and "gemini-pro" not in model_name
        )

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

        messages = self.history.get(result.conversation_id, [])
        if not supports_system_instruction:
            if not messages:
                messages = [{}, {"role": "model", "parts": "Ok"}]
            messages[0] = {"role": "user", "parts": prompt}

        LOGGER.debug("Input: '%s' with history: %s", user_input.text, messages)
        trace.async_conversation_trace_append(
            trace.ConversationTraceEventType.AGENT_DETAIL,
            {
                # Make a copy to attach it to the trace event.
                "messages": messages[:]
                if supports_system_instruction
                else messages[2:],
                "prompt": prompt,
                "tools": [*llm_api.tools] if llm_api else None,
            },
        )

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

                result.response.async_set_error(
                    intent.IntentResponseErrorCode.UNKNOWN,
                    error,
                )
                return result

            LOGGER.debug("Response: %s", chat_response.parts)
            if not chat_response.parts:
                result.response.async_set_error(
                    intent.IntentResponseErrorCode.UNKNOWN,
                    "Sorry, I had a problem getting a response from Google Generative AI.",
                )
                return result
            self.history[result.conversation_id] = chat.history
            function_calls = [
                part.function_call for part in chat_response.parts if part.function_call
            ]
            if not function_calls or not llm_api:
                break

            tool_responses = []
            for function_call in function_calls:
                tool_call = MessageToDict(function_call._pb)  # noqa: SLF001
                tool_name = tool_call["name"]
                tool_args = _escape_decode(tool_call["args"])
                LOGGER.debug("Tool call: %s(%s)", tool_name, tool_args)
                tool_input = llm.ToolInput(tool_name=tool_name, tool_args=tool_args)
                try:
                    function_response = await llm_api.async_call_tool(tool_input)
                except (HomeAssistantError, vol.Invalid) as e:
                    function_response = {"error": type(e).__name__}
                    if str(e):
                        function_response["error_text"] = str(e)

                LOGGER.debug("Tool response: %s", function_response)
                tool_responses.append(
                    protos.Part(
                        function_response=protos.FunctionResponse(
                            name=tool_name, response=function_response
                        )
                    )
                )
            chat_request = protos.Content(parts=tool_responses)

        result.response.async_set_speech(
            " ".join([part.text.strip() for part in chat_response.parts if part.text])
        )
        return result

    async def _async_render_prompt(
        self,
        user_input: conversation.ConversationInput,
        llm_api: llm.APIInstance | None,
        llm_context: llm.LLMContext,
    ) -> str:
        user_name: str | None = None
        if (
            user_input.context
            and user_input.context.user_id
            and (
                user := await self.hass.auth.async_get_user(user_input.context.user_id)
            )
        ):
            user_name = user.name

        parts = [
            template.Template(
                llm.BASE_PROMPT
                + self.entry.options.get(CONF_PROMPT, llm.DEFAULT_INSTRUCTIONS_PROMPT),
                self.hass,
            ).async_render(
                {
                    "ha_name": self.hass.config.location_name,
                    "user_name": user_name,
                    "llm_context": llm_context,
                },
                parse_result=False,
            )
        ]

        if llm_api:
            parts.append(llm_api.api_prompt)

        return "\n".join(parts)

    async def _async_entry_update_listener(
        self, hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Handle options update."""
        # Reload as we update device info + entity name + supported features
        await hass.config_entries.async_reload(entry.entry_id)
