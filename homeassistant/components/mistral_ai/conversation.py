"""Conversation support for Mistral AI."""

from typing import TYPE_CHECKING, Literal, override

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_LLM_HASS_API, CONF_PROMPT, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .chat import handle_chat_log
from .const import DOMAIN
from .entity import MistralEntity

if TYPE_CHECKING:
    from . import MistralAIConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MistralAIConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Mistral conversation platform."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "conversation":
            continue

        async_add_entities(
            [MistralConversationEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class MistralConversationEntity(
    conversation.ConversationEntity,
    conversation.AbstractConversationAgent,
    MistralEntity,
):
    """Mistral AI conversation agent."""

    _attr_supports_streaming = True

    def __init__(self, entry: MistralAIConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the conversation entity."""
        super().__init__(entry, subentry)
        if subentry.data.get(CONF_LLM_HASS_API):
            self._attr_supported_features = (
                conversation.ConversationEntityFeature.CONTROL
            )

    @property
    @override
    def supported_languages(self) -> list[str] | Literal["*"]:
        return MATCH_ALL

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self.entry, self)

    @override
    async def async_will_remove_from_hass(self) -> None:
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    @override
    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        options = self.subentry.data

        try:
            await chat_log.async_provide_llm_data(
                user_input.as_llm_context(DOMAIN),
                options.get(CONF_LLM_HASS_API),
                options.get(CONF_PROMPT),
                user_input.extra_system_prompt,
            )
        except conversation.ConverseError as err:
            return err.as_conversation_result()

        await handle_chat_log(self, chat_log)

        return conversation.async_get_result_from_chat_log(user_input, chat_log)
