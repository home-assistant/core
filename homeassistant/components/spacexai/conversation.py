"""Conversation platform for SpaceXAI."""

from typing import Literal, cast, override

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import (
    CONF_LLM_HASS_API,
    CONF_MODEL,
    CONF_PROMPT,
    MATCH_ALL,
    __version__ as HA_VERSION,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform, llm
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SpaceXAIConfigEntry
from .const import DOMAIN
from .entity import SpaceXAIBaseLLMEntity
from .errors import SpaceXAIError
from .issue import async_delete_subscription_issue

PARALLEL_UPDATES = 0

_RUNTIME_IDENTITY_PROMPT = (
    "Runtime identity (answer truthfully when asked about versions):\n"
    "- Home Assistant Core: {ha_version}\n"
    "- Provider: SpaceXAI (Grok)\n"
    "- Conversation model: {model}"
)


def _prompt_safe_literal(value: str) -> str:
    """Strip Jinja delimiter characters from provider-controlled literals."""
    return value.replace("{", "").replace("}", "").replace("%", "").replace("#", "")


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SpaceXAIConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SpaceXAI conversation entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "conversation":
            continue
        async_add_entities(
            [SpaceXAIConversationEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class SpaceXAIConversationEntity(
    conversation.ConversationEntity,
    conversation.AbstractConversationAgent,
    SpaceXAIBaseLLMEntity,
):
    """SpaceXAI Grok conversation agent."""

    _attr_supports_streaming = False
    _attr_translation_key = "conversation"

    def __init__(self, entry: SpaceXAIConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the conversation entity."""
        super().__init__(entry, subentry)
        if subentry.data.get(CONF_LLM_HASS_API):
            self._attr_supported_features = (
                conversation.ConversationEntityFeature.CONTROL
            )

    @property
    @override
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return supported languages."""
        return MATCH_ALL

    @override
    async def async_added_to_hass(self) -> None:
        """Register the conversation agent when the entity is added."""
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self.entry, self)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Keep an entry-id agent alias when sibling conversation entities remain."""
        conversation.async_unset_agent(self.hass, self.entry)
        for platform in entity_platform.async_get_platforms(self.hass, DOMAIN):
            for entity in platform.entities.values():
                if (
                    entity is not self
                    and isinstance(entity, conversation.AbstractConversationAgent)
                    and getattr(entity, "entry", None) is self.entry
                ):
                    conversation.async_set_agent(self.hass, self.entry, entity)
                    break
        await super().async_will_remove_from_hass()

    @override
    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Process a message using Home Assistant-owned chat state."""
        base_prompt = (
            self.subentry.data.get(CONF_PROMPT) or llm.DEFAULT_INSTRUCTIONS_PROMPT
        )
        identity = _RUNTIME_IDENTITY_PROMPT.format(
            ha_version=HA_VERSION,
            model=_prompt_safe_literal(cast(str, self.subentry.data[CONF_MODEL])),
        )
        prompt = f"{base_prompt}\n\n{identity}"

        try:
            await chat_log.async_provide_llm_data(
                user_input.as_llm_context(DOMAIN),
                self.subentry.data.get(CONF_LLM_HASS_API),
                prompt,
                user_input.extra_system_prompt,
            )
        except conversation.ConverseError as err:
            return err.as_conversation_result()

        try:
            await self._async_handle_chat_log(chat_log)
        except SpaceXAIError as err:
            self._raise_provider_home_assistant_error(err)
        except HomeAssistantError:
            raise
        except Exception as err:  # noqa: BLE001
            self._raise_unexpected_provider_failure(err)

        if self._mark_available():
            async_delete_subscription_issue(self.hass, self.entry.entry_id)
            self._restore_entitled_entry_agents()
        return conversation.async_get_result_from_chat_log(user_input, chat_log)
