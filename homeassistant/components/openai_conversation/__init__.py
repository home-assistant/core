"""The OpenAI Conversation integration."""
from __future__ import annotations

from functools import partial
import json
import logging
from typing import Literal

import openai
from openai import error
import voluptuous as vol

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, MATCH_ALL
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    HomeAssistantError,
    TemplateError,
)
from homeassistant.helpers import config_validation as cv, intent, selector, template
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import ulid

from .const import (
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    DEFAULT_CHAT_MODEL,
    DEFAULT_MAX_TOKENS,
    DEFAULT_PROMPT,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    DOMAIN,
)
from .crossover_dict import HASS_OPENAI_ACTIONS


_LOGGER = logging.getLogger(__name__)
SERVICE_GENERATE_IMAGE = "generate_image"

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


class OpenAIAgent(conversation.AbstractConversationAgent):
    """OpenAI conversation agent."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self.hass = hass
        self.entry = entry
        self.history: dict[str, list[dict]] = {}
        self.raw_prompt = self.entry.options.get(CONF_PROMPT, DEFAULT_PROMPT)
        self.model = self.entry.options.get(CONF_CHAT_MODEL, DEFAULT_CHAT_MODEL)
        self.max_tokens = self.entry.options.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS)
        self.top_p = self.entry.options.get(CONF_TOP_P, DEFAULT_TOP_P)
        self.temperature = self.entry.options.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE)
        # a list of OpenAI-compatible functions
        self.openai_functions = [HASS_OPENAI_ACTIONS[action]["openai_function"] for action in HASS_OPENAI_ACTIONS]

    async def async_process(self, user_input: conversation.ConversationInput) -> conversation.ConversationResult:
        """Process user's input."""

        conversation_id, messages = await self._handle_conv_history(user_input)

        # add user's input to the conversation history
        messages.append({"role": "user", "content": user_input.text})

        # make a request to OpenAI
        success, response = await self._make_request_openai(user_input, messages, conversation_id)
        if not success:
            return response

        # add GPT's response to the conversation history
        messages.append(response)
        self.history[conversation_id] = messages

        # if there's a function call in GPT's response, call the corresponding function
        if "function_call" in response.keys():
            await self._handle_function_call(response=response)

        # return GPT's response to the user
        # if there's no response (because a function was called), return "Done."
        intent_response = intent.IntentResponse(language=user_input.language)
        intent_response.async_set_speech(response["content"] or "Done.")
        return conversation.ConversationResult(response=intent_response, conversation_id=conversation_id)

    async def _make_request_openai(self, user_input, messages: list[dict], conversation_id: str) -> dict:
        """Make a request to OpenAI."""
        try:
            result = await openai.ChatCompletion.acreate(
                api_key=self.entry.data[CONF_API_KEY],
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                top_p=self.top_p,
                temperature=self.temperature,
                user=conversation_id,
                functions=self.openai_functions,
                function_call="auto",
            )
            response = result["choices"][0]["message"]
            return True, response
        except error.OpenAIError as err:
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                f"Sorry, I had a problem talking to OpenAI: {err}",
            )
            return False, conversation.ConversationResult(response=intent_response, conversation_id=conversation_id)

    async def _handle_function_call(self, response: dict) -> None:
        """Handle a function call from OpenAI by calling the corresponding function."""
        func_response = dict(response["function_call"])
        name = func_response["name"]
        arguments = json.loads(func_response["arguments"])
        await self._perform_hass_action(action_to_perform=name, arguments=arguments)

    async def _handle_conv_history(self, user_input: conversation.ConversationInput) -> None:
        if user_input.conversation_id in self.history:
            conversation_id = user_input.conversation_id
            messages = self.history[conversation_id]
        else:
            conversation_id = ulid.ulid()
            states_str = await self._get_states_str()
            entity_ids_str = "\n".join(self.hass.states.async_entity_ids())
            prompt = self.raw_prompt.format(devices_states=states_str, available_entity_ids=entity_ids_str)
            messages = [{"role": "system", "content": prompt}]
        return conversation_id, messages

    async def _get_states_str(self) -> str:
        """Return string with all entity states."""
        all_states = self.hass.states.async_all()
        device_str = "\n"
        for device in all_states:
            device_str += f"{device}\n\n"
        return device_str

    async def _perform_hass_action(self, action_to_perform: str, arguments: str) -> None:
        """Perform a Home Assistant action."""
        action = HASS_OPENAI_ACTIONS[action_to_perform]["hass_action"]
        entity_id = arguments["entity_id"]
        action["service_data"]["entity_id"] = entity_id
        service_response = await self.hass.services.async_call(**action)

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up OpenAI Conversation."""

    async def render_image(call: ServiceCall) -> ServiceResponse:
        """Render an image with dall-e."""
        try:
            response = await openai.Image.acreate(
                api_key=hass.data[DOMAIN][call.data["config_entry"]],
                prompt=call.data["prompt"],
                n=1,
                size=f'{call.data["size"]}x{call.data["size"]}',
            )
        except error.OpenAIError as err:
            raise HomeAssistantError(f"Error generating image: {err}") from err

        return response["data"][0]

    hass.services.async_register(
        DOMAIN,
        SERVICE_GENERATE_IMAGE,
        render_image,
        schema=vol.Schema(
            {
                vol.Required("config_entry"): selector.ConfigEntrySelector(
                    {
                        "integration": DOMAIN,
                    }
                ),
                vol.Required("prompt"): cv.string,
                vol.Optional("size", default="512"): vol.In(("256", "512", "1024")),
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OpenAI Conversation from a config entry."""
    try:
        await hass.async_add_executor_job(
            partial(
                openai.Engine.list,
                api_key=entry.data[CONF_API_KEY],
                request_timeout=10,
            )
        )
    except error.AuthenticationError as err:
        _LOGGER.error("Invalid API key: %s", err)
        return False
    except error.OpenAIError as err:
        raise ConfigEntryNotReady(err) from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.data[CONF_API_KEY]

    conversation.async_set_agent(hass, entry, OpenAIAgent(hass, entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload OpenAI."""
    hass.data[DOMAIN].pop(entry.entry_id)
    conversation.async_unset_agent(hass, entry)
    return True
