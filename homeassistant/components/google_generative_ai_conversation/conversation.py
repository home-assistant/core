"""Conversation support for the Google Generative AI Conversation integration."""

from __future__ import annotations

from typing import Any, Literal

import google.ai.generativelanguage as glm
from google.api_core.exceptions import GoogleAPICallError
import google.generativeai as genai
import google.generativeai.types as genai_types
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
    result = {}
    for key, val in schema.items():
        if key not in SUPPORTED_SCHEMA_KEYS:
            continue
        if key == "type":
            key = "type_"
            val = val.upper()
        elif key == "format":
            key = "format_"
        elif key == "items":
            val = _format_schema(val)
        elif key == "properties":
            val = {k: _format_schema(v) for k, v in val.items()}
        result[key] = val
    return result


def _format_tool(tool: llm.Tool) -> dict[str, Any]:
    """Format tool specification."""

    parameters = _format_schema(convert(tool.parameters))

    return glm.Tool(
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

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from Home Assistant."""
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Process a sentence."""
        intent_response = intent.IntentResponse(language=user_input.language)
        llm_api: llm.APIInstance | None = None
        tools: list[dict[str, Any]] | None = None

        if self.entry.options.get(CONF_LLM_HASS_API):
            try:
                llm_api = await llm.async_get_api(
                    self.hass,
                    self.entry.options[CONF_LLM_HASS_API],
                    llm.ToolContext(
                        platform=DOMAIN,
                        context=user_input.context,
                        user_prompt=user_input.text,
                        language=user_input.language,
                        assistant=conversation.DOMAIN,
                        device_id=user_input.device_id,
                    ),
                )
            except HomeAssistantError as err:
                LOGGER.error("Error getting LLM API: %s", err)
                intent_response.async_set_error(
                    intent.IntentResponseErrorCode.UNKNOWN,
                    f"Error preparing LLM API: {err}",
                )
                return conversation.ConversationResult(
                    response=intent_response, conversation_id=user_input.conversation_id
                )
            tools = [_format_tool(tool) for tool in llm_api.tools]

        model = genai.GenerativeModel(
            model_name=self.entry.options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL),
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
        )

        if user_input.conversation_id in self.history:
            conversation_id = user_input.conversation_id
            messages = self.history[conversation_id]
        else:
            conversation_id = ulid.ulid_now()
            messages = [{}, {}]

        try:
            if llm_api:
                api_prompt = llm_api.api_prompt
            else:
                api_prompt = llm.async_render_no_api_prompt(self.hass)

            prompt = "\n".join(
                (
                    template.Template(
                        self.entry.options.get(
                            CONF_PROMPT, llm.DEFAULT_INSTRUCTIONS_PROMPT
                        ),
                        self.hass,
                    ).async_render(
                        {
                            "ha_name": self.hass.config.location_name,
                        },
                        parse_result=False,
                    ),
                    api_prompt,
                )
            )

        except TemplateError as err:
            LOGGER.error("Error rendering prompt: %s", err)
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                f"Sorry, I had a problem with my template: {err}",
            )
            return conversation.ConversationResult(
                response=intent_response, conversation_id=conversation_id
            )

        messages[0] = {"role": "user", "parts": prompt}
        messages[1] = {"role": "model", "parts": "Ok"}

        LOGGER.debug("Input: '%s' with history: %s", user_input.text, messages)
        trace.async_conversation_trace_append(
            trace.ConversationTraceEventType.AGENT_DETAIL, {"messages": messages}
        )

        chat = model.start_chat(history=messages)
        chat_request = user_input.text
        # To prevent infinite loops, we limit the number of iterations
        for _iteration in range(MAX_TOOL_ITERATIONS):
            try:
                chat_response = await chat.send_message_async(chat_request)
            except (
                GoogleAPICallError,
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

                intent_response.async_set_error(
                    intent.IntentResponseErrorCode.UNKNOWN,
                    error,
                )
                return conversation.ConversationResult(
                    response=intent_response, conversation_id=conversation_id
                )

            LOGGER.debug("Response: %s", chat_response.parts)
            if not chat_response.parts:
                intent_response.async_set_error(
                    intent.IntentResponseErrorCode.UNKNOWN,
                    "Sorry, I had a problem getting a response from Google Generative AI.",
                )
                return conversation.ConversationResult(
                    response=intent_response, conversation_id=conversation_id
                )
            self.history[conversation_id] = chat.history
            tool_calls = [
                part.function_call for part in chat_response.parts if part.function_call
            ]
            if not tool_calls or not llm_api:
                break

            tool_responses = []
            for tool_call in tool_calls:
                tool_input = llm.ToolInput(
                    tool_name=tool_call.name,
                    tool_args=dict(tool_call.args),
                )
                LOGGER.debug(
                    "Tool call: %s(%s)", tool_input.tool_name, tool_input.tool_args
                )
                try:
                    function_response = await llm_api.async_call_tool(tool_input)
                except (HomeAssistantError, vol.Invalid) as e:
                    function_response = {"error": type(e).__name__}
                    if str(e):
                        function_response["error_text"] = str(e)

                LOGGER.debug("Tool response: %s", function_response)
                tool_responses.append(
                    glm.Part(
                        function_response=glm.FunctionResponse(
                            name=tool_call.name, response=function_response
                        )
                    )
                )
            chat_request = glm.Content(parts=tool_responses)

        intent_response.async_set_speech(
            " ".join([part.text for part in chat_response.parts if part.text])
        )
        return conversation.ConversationResult(
            response=intent_response, conversation_id=conversation_id
        )
