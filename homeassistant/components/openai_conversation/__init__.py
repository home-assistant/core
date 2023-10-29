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
    Context,
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
from .openai_homeassistant_crossover import HASS_OPENAI_ACTIONS


_LOGGER = logging.getLogger(__name__)
SERVICE_GENERATE_IMAGE = "generate_image"

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


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


class OpenAIAgent(conversation.AbstractConversationAgent):
    """OpenAI conversation agent."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self.hass = hass
        self.entry = entry
        self.history: dict[str, list[dict]] = {}

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    async def async_process(self, user_input: conversation.ConversationInput) -> conversation.ConversationResult:
        """Process a sentence."""
        raw_prompt = self.entry.options.get(CONF_PROMPT, DEFAULT_PROMPT)
        model = self.entry.options.get(CONF_CHAT_MODEL, DEFAULT_CHAT_MODEL)
        max_tokens = self.entry.options.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS)
        top_p = self.entry.options.get(CONF_TOP_P, DEFAULT_TOP_P)
        temperature = self.entry.options.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE)

        if user_input.conversation_id in self.history:
            conversation_id = user_input.conversation_id
            messages = self.history[conversation_id]
        else:
            conversation_id = ulid.ulid()
            try:
                states_str = await self._get_states_str()
                entity_ids_str = "\n".join(self.hass.states.async_entity_ids())
                _LOGGER.warning(f"states_str: {states_str}")
                prompt = self._async_generate_prompt(raw_prompt, states_str, entity_ids_str)
            except TemplateError as err:
                _LOGGER.error("Error rendering prompt: %s", err)
                intent_response = intent.IntentResponse(language=user_input.language)
                intent_response.async_set_error(
                    intent.IntentResponseErrorCode.UNKNOWN,
                    f"Sorry, I had a problem with my template: {err}",
                )
                return conversation.ConversationResult(response=intent_response, conversation_id=conversation_id)
            messages = [{"role": "system", "content": prompt}]

        messages.append({"role": "user", "content": user_input.text})

        await self._get_info_about_devices()

        # Compile a list of OpenAI-compatible functions
        openai_functions = [HASS_OPENAI_ACTIONS[action]["openai_function"] for action in HASS_OPENAI_ACTIONS]
        _LOGGER.warning(f"openai_functions: {openai_functions}")

        try:
            # _LOGGER.info(f"messages: {messages}")
            result = await openai.ChatCompletion.acreate(
                api_key=self.entry.data[CONF_API_KEY],
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                top_p=top_p,
                temperature=temperature,
                user=conversation_id,
                functions=openai_functions,
                function_call="auto",
            )
        except error.OpenAIError as err:
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                f"Sorry, I had a problem talking to OpenAI: {err}",
            )
            return conversation.ConversationResult(response=intent_response, conversation_id=conversation_id)

        _LOGGER.warning("Response %s", result)
        response = result["choices"][0]["message"]
        messages.append(response)
        self.history[conversation_id] = messages

        # if there's a function call in GPT's response, we perform the HASS action that corresponds to it
        if "function_call" in response.keys():
            func_response = dict(response["function_call"])
            name = func_response["name"]
            _LOGGER.warning(f"func_response: {func_response}")
            _LOGGER.warning(f"arguments: {func_response['arguments']}")
            arguments = json.loads(func_response["arguments"])
            _LOGGER.warning(f"arguments: {arguments}")
            _LOGGER.warning(f"arguments: {type(arguments)}")
            await self._perform_hass_action(action_to_perform=name, arguments=arguments)

        intent_response = intent.IntentResponse(language=user_input.language)
        intent_response.async_set_speech(response["content"] or "Done.")

        return conversation.ConversationResult(response=intent_response, conversation_id=conversation_id)

    async def _get_states_str(self) -> str:
        """Return string with all entity states."""
        all_states = self.hass.states.async_all()
        device_str = "\n"
        for device in all_states:
            device_str += f"{device}\n\n"
        return device_str

    async def _get_info_about_devices(self) -> None:
        entity_services = {}

        # Get all entities
        all_entities = self.hass.states.async_all()

        # Get all services
        services = self.hass.services.async_services()

        for entity in all_entities:
            domain = entity.domain  # e.g., 'light', 'switch', etc.

            # Find services for the entity's domain
            entity_services[entity.entity_id] = list(services.get(domain, {}).keys())

        for entity, actions in entity_services.items():
            if actions != []:
                _LOGGER.warn(f"Entity: {entity}, Possible Actions: {actions}")

    def _async_generate_prompt(self, raw_prompt: str, devices_states: str, entity_ids_str: str) -> str:
        """Generate a prompt for the user."""
        full_prompt = raw_prompt.format(devices_states=devices_states, available_entity_ids=entity_ids_str)
        return full_prompt

    async def _perform_hass_action(self, action_to_perform: str, arguments: str) -> None:
        """
        Perform a Home Assistant action.
        """
        _LOGGER.warning(f"action_to_perform: {action_to_perform}")
        action = HASS_OPENAI_ACTIONS[action_to_perform]["hass_action"]
        entity_id = arguments["entity_id"]
        action["service_data"]["entity_id"] = entity_id
        _LOGGER.warning(f"action: {action}")

        service_response = await self.hass.services.async_call(**action)
        _LOGGER.warning(f"service_response: {service_response}")
