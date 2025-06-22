"""Conversation support for OpenRouter."""

from typing import Literal

import openai

from homeassistant.components import assist_pipeline, conversation
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_MODEL, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import intent, template
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import ulid as ulid_util

from . import OpenRouterConfigEntry
from .const import CONF_PROMPT, DEFAULT_PROMPT, LOGGER


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OpenRouterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up conversation entities."""
    for subentry_id, subentry in config_entry.subentries.items():
        async_add_entities(
            [OpenRouterConversationEntity(config_entry, subentry)],
            config_subentry_id=subentry_id,
        )


class OpenRouterConversationEntity(
    conversation.ConversationEntity, conversation.AbstractConversationAgent
):
    """OpenRouter conversation agent."""

    def __init__(self, entry: OpenRouterConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the agent."""
        self.entry = entry
        self.model = subentry.data[CONF_MODEL]
        self.history: dict[str, list[dict]] = {}
        self._attr_name = subentry.title
        self._attr_unique_id = subentry.subentry_id

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
        raw_prompt = self.entry.options.get(CONF_PROMPT, DEFAULT_PROMPT)

        if user_input.conversation_id in self.history:
            conversation_id = user_input.conversation_id
            messages = self.history[conversation_id]
        else:
            conversation_id = ulid_util.ulid_now()
            try:
                prompt = self._async_generate_prompt(raw_prompt)
            except TemplateError as err:
                LOGGER.error("Error rendering prompt: %s", err)
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

        client = self.entry.runtime_data

        try:
            result = await client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore[arg-type]
                user=conversation_id,
                extra_headers={
                    "X-Title": "Home Assistant",
                    "HTTP-Referer": "https://www.home-assistant.io/integrations/open_router",
                },
            )
        except openai.OpenAIError as err:
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                f"Sorry, I had a problem talking to OpenRouter: {err}",
            )
            return conversation.ConversationResult(
                response=intent_response, conversation_id=conversation_id
            )

        LOGGER.debug("Response %s", result)
        response = result.choices[0].message.model_dump(include={"role", "content"})
        messages.append(response)
        self.history[conversation_id] = messages

        intent_response = intent.IntentResponse(language=user_input.language)
        intent_response.async_set_speech(response["content"])
        return conversation.ConversationResult(
            response=intent_response, conversation_id=conversation_id
        )

    def _async_generate_prompt(self, raw_prompt: str) -> str:
        """Generate a prompt for the user."""
        return template.Template(raw_prompt, self.hass).async_render(  # type: ignore[no-any-return]
            {
                "ha_name": self.hass.config.location_name,
            },
            parse_result=False,
        )
