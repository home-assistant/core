"""Conversation support for the Google Generative AI Conversation integration."""

from __future__ import annotations

from typing import Any, Literal

import google.ai.generativelanguage as glm
from google.api_core.exceptions import ClientError
import google.generativeai as genai
import google.generativeai.types as genai_types
import voluptuous as vol
from voluptuous_openapi import convert

from homeassistant.components import assist_pipeline, conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LLM_HASS_API, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.helpers import intent, llm, template
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import ulid

from .const import (
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_TEMPERATURE,
    CONF_TOP_K,
    CONF_TOP_P,
    DEFAULT_CHAT_MODEL,
    DEFAULT_MAX_TOKENS,
    DEFAULT_PROMPT,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_K,
    DEFAULT_TOP_P,
    DOMAIN,
    LOGGER,
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

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self.entry = entry
        self.history: dict[str, list[genai_types.ContentType]] = {}
        self._attr_name = entry.title
        self._attr_unique_id = entry.entry_id

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
        llm_api: llm.API | None = None
        tools: list[dict[str, Any]] | None = None

        if self.entry.options.get(CONF_LLM_HASS_API):
            try:
                llm_api = llm.async_get_api(
                    self.hass, self.entry.options[CONF_LLM_HASS_API]
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
            tools = [_format_tool(tool) for tool in llm_api.async_get_tools()]

        raw_prompt = self.entry.options.get(CONF_PROMPT, DEFAULT_PROMPT)
        model = genai.GenerativeModel(
            model_name=self.entry.options.get(CONF_CHAT_MODEL, DEFAULT_CHAT_MODEL),
            generation_config={
                "temperature": self.entry.options.get(
                    CONF_TEMPERATURE, DEFAULT_TEMPERATURE
                ),
                "top_p": self.entry.options.get(CONF_TOP_P, DEFAULT_TOP_P),
                "top_k": self.entry.options.get(CONF_TOP_K, DEFAULT_TOP_K),
                "max_output_tokens": self.entry.options.get(
                    CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS
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
            prompt = self._async_generate_prompt(raw_prompt, llm_api)
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

        chat = model.start_chat(history=messages)
        chat_request = user_input.text
        # To prevent infinite loops, we limit the number of iterations
        for _iteration in range(MAX_TOOL_ITERATIONS):
            try:
                chat_response = await chat.send_message_async(chat_request)
            except (
                ClientError,
                ValueError,
                genai_types.BlockedPromptException,
                genai_types.StopCandidateException,
            ) as err:
                LOGGER.error("Error sending message: %s", err)
                intent_response.async_set_error(
                    intent.IntentResponseErrorCode.UNKNOWN,
                    f"Sorry, I had a problem talking to Google Generative AI: {err}",
                )
                return conversation.ConversationResult(
                    response=intent_response, conversation_id=conversation_id
                )

            LOGGER.debug("Response: %s", chat_response.parts)
            if not chat_response.parts:
                intent_response.async_set_error(
                    intent.IntentResponseErrorCode.UNKNOWN,
                    "Sorry, I had a problem talking to Google Generative AI. Likely blocked",
                )
                return conversation.ConversationResult(
                    response=intent_response, conversation_id=conversation_id
                )
            self.history[conversation_id] = chat.history
            tool_call = chat_response.parts[0].function_call

            if not tool_call or not llm_api:
                break

            tool_input = llm.ToolInput(
                tool_name=tool_call.name,
                tool_args=dict(tool_call.args),
                platform=DOMAIN,
                context=user_input.context,
                user_prompt=user_input.text,
                language=user_input.language,
                assistant=conversation.DOMAIN,
                device_id=user_input.device_id,
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
            chat_request = glm.Content(
                parts=[
                    glm.Part(
                        function_response=glm.FunctionResponse(
                            name=tool_call.name, response=function_response
                        )
                    )
                ]
            )

        intent_response.async_set_speech(chat_response.text)
        return conversation.ConversationResult(
            response=intent_response, conversation_id=conversation_id
        )

    def _async_generate_prompt(self, raw_prompt: str, llm_api: llm.API | None) -> str:
        """Generate a prompt for the user."""
        raw_prompt += "\n"
        if llm_api:
            raw_prompt += llm_api.prompt_template
        else:
            raw_prompt += llm.PROMPT_NO_API_CONFIGURED

        return template.Template(raw_prompt, self.hass).async_render(
            {
                "ha_name": self.hass.config.location_name,
            },
            parse_result=False,
        )
