"""Conversation support for AWS Bedrock."""

from typing import Literal

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_LLM_HASS_API, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AWSBedrockConfigEntry
from .const import CONF_PROMPT, DOMAIN, LOGGER
from .entity import AWSBedrockBaseLLMEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AWSBedrockConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up conversation entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "conversation":
            continue

        async_add_entities(
            [AWSBedrockConversationEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class AWSBedrockConversationEntity(
    conversation.ConversationEntity,
    conversation.AbstractConversationAgent,
    AWSBedrockBaseLLMEntity,
):
    """AWS Bedrock conversation agent."""

    def __init__(self, entry: AWSBedrockConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the agent."""
        super().__init__(entry, subentry)
        if self.subentry.data.get(CONF_LLM_HASS_API):
            self._attr_supported_features = (
                conversation.ConversationEntityFeature.CONTROL
            )

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Call the API."""
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

        try:
            await self._async_handle_chat_log(chat_log)
        except conversation.ConverseError as err:
            return err.as_conversation_result()

        return conversation.async_get_result_from_chat_log(user_input, chat_log)
