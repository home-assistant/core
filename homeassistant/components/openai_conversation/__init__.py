"""The OpenAI Conversation integration."""
from __future__ import annotations

from functools import partial
import inspect
import json
import logging
from typing import Literal

import openai
from openai import error

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, TemplateError
from homeassistant.helpers import intent, template
from homeassistant.util import ulid

from .actions import Actions
from .const import (
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    DEFAULT_CHAT_MODEL,
    DEFAULT_MAX_TOKENS,
    DEFAULT_PROMPT,
)
from .queries import Queries

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OpenAI Conversation from a config entry."""
    openai.api_key = entry.data[CONF_API_KEY]

    try:
        await hass.async_add_executor_job(
            partial(openai.Engine.list, request_timeout=10)
        )
    except error.AuthenticationError as err:
        _LOGGER.error("Invalid API key: %s", err)
        return False
    except error.OpenAIError as err:
        raise ConfigEntryNotReady(err) from err

    conversation.async_set_agent(hass, entry, OpenAIAgent(hass, entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload OpenAI."""
    openai.api_key = None
    conversation.async_unset_agent(hass, entry)
    return True


class OpenAIAgent(conversation.AbstractConversationAgent):
    """OpenAI conversation agent."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self.hass = hass
        self.entry = entry
        self.queries = Queries(hass, entry)
        self.actions = Actions(hass, entry)
        self.history: dict[str, list[dict]] = {}

        _LOGGER.debug(
            "Functions for openai conversation: %s",
            json.dumps(self._get_methods_and_descriptions()),
        )

    @property
    def attribution(self):
        """Return the attribution."""
        return {"name": "Powered by OpenAI", "url": "https://www.openai.com"}

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Process a sentence."""
        raw_prompt = self.entry.options.get(CONF_PROMPT, DEFAULT_PROMPT)

        if user_input.conversation_id in self.history:
            conversation_id = user_input.conversation_id
            messages = self.history[conversation_id]
        else:
            conversation_id = ulid.ulid()
            try:
                prompt = self._async_generate_prompt(raw_prompt)
            except TemplateError as err:
                _LOGGER.error("Error rendering prompt: %s", err)
                intent_response = intent.IntentResponse(language=user_input.language)
                intent_response.async_set_error(
                    intent.IntentResponseErrorCode.UNKNOWN,
                    f"Sorry, I had a problem with my template: {err}",
                )
                return conversation.ConversationResult(
                    response=intent_response, conversation_id=conversation_id
                )
            messages = [{"role": "system", "content": prompt}]

        messages.append({"role": "user", "content": user_input.text})

        return await self._call_gpt(
            messages,
            conversation_id,
            language=user_input.language,
        )

    async def _call_gpt(self, messages, conversation_id, language):
        model = self.entry.options.get(CONF_CHAT_MODEL, DEFAULT_CHAT_MODEL)
        max_tokens = self.entry.options.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS)
        # top_p = self.entry.options.get(CONF_TOP_P, DEFAULT_TOP_P)
        # temperature = self.entry.options.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE)

        _LOGGER.debug("Prompt for %s: %s", model, messages)

        try:
            result = await openai.ChatCompletion.acreate(
                model=model,
                messages=messages,
                functions=self.queries.functions + self.actions.functions,
                function_call="auto",
                max_tokens=max_tokens,
                # top_p=top_p,
                # temperature=temperature,
                user=conversation_id,
            )
        except error.OpenAIError as err:
            intent_response = intent.IntentResponse(language=language)
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                f"Sorry, I had a problem talking to OpenAI: {err}",
            )
            return conversation.ConversationResult(
                response=intent_response, conversation_id=conversation_id
            )

        _LOGGER.debug("Response is this: %s", result)
        response = result["choices"][0]["message"]

        messages.append(response)
        self.history[conversation_id] = messages

        if response.get("function_call"):
            function_name = response["function_call"]["name"]
            try:
                function_response_s = await self._process_query_or_action(response)
            except Exception:  # pylint: disable=broad-exception-caught
                intent_response = intent.IntentResponse(language=language)
                intent_response.async_set_error(
                    intent.IntentResponseErrorCode.UNKNOWN,
                    "Error executing a function",
                )
                return conversation.ConversationResult(
                    response=intent_response, conversation_id=conversation_id
                )

            messages.append(
                {
                    "role": "function",
                    "name": function_name,
                    "content": function_response_s,
                }
            )
            return await self._call_gpt(messages, conversation_id, language)

        if response["content"]:
            intent_response = intent.IntentResponse(language=language)
            intent_response.async_set_speech(response["content"])
            return conversation.ConversationResult(
                response=intent_response, conversation_id=conversation_id
            )

        intent_response = intent.IntentResponse(language=language)
        intent_response.async_set_speech("Something went wrong.")
        return conversation.ConversationResult(
            response=intent_response, conversation_id=conversation_id
        )

    async def _process_query_or_action(self, response):
        function_name = response["function_call"]["name"]
        function_args = response["function_call"]["arguments"]

        _LOGGER.debug("GPT calling function %s: %s", function_name, function_args)
        if function_name == "query_all_entities":
            return await self.queries.query_all_entities()
        if function_name == "query_weather_report":
            return await self.queries.query_weather_report()
        if function_name == "exec_control_switch":
            args = json.loads(function_args)
            return await self.actions.exec_control_switch(
                entity=args.get("entity"),
                action=args.get("action"),
            )
        if function_name == "exec_manage_shopping_list":
            args = json.loads(function_args)
            return await self.actions.exec_manage_shopping_list(
                action=args.get("action"),
                items=args.get("items"),
            )

    def _get_methods_and_descriptions(self):
        """Take a class object as an argument and returns a dictionary where keys are method names and values are their docstrings."""
        methods = []
        for class_obj in (Queries, Actions):
            for name, member in inspect.getmembers(class_obj):
                if (
                    inspect.isfunction(member) or inspect.ismethod(member)
                ) and name != "__init__":
                    methods.append(
                        {
                            "name": name,
                            "description": member.__doc__,
                        }
                    )
        return methods

    def _async_generate_prompt(self, raw_prompt: str) -> str:
        """Generate a prompt for the user."""
        return template.Template(raw_prompt, self.hass).async_render(
            {
                "ha_name": self.hass.config.location_name,
                "functions": self._get_methods_and_descriptions(),
            },
            parse_result=False,
        )
