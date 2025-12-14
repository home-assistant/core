"""Conversation support for Home Assistant Cloud."""

from __future__ import annotations

from typing import Literal

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONVERSATION_ENTITY_UNIQUE_ID, DATA_CLOUD, DOMAIN
from .entity import BaseCloudLLMEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Home Assistant Cloud conversation entity."""
    cloud = hass.data[DATA_CLOUD]
    async_add_entities([CloudConversationEntity(cloud, config_entry)])


class CloudConversationEntity(
    BaseCloudLLMEntity,
    conversation.ConversationEntity,
):
    """Home Assistant Cloud conversation agent."""

    _attr_has_entity_name = True
    _attr_name = "Home Assistant Cloud"
    _attr_translation_key = "cloud_conversation"
    _attr_unique_id = CONVERSATION_ENTITY_UNIQUE_ID
    _attr_supported_features = conversation.ConversationEntityFeature.CONTROL

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return self._cloud.is_logged_in and self._cloud.valid_subscription

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Process a user input."""
        try:
            await chat_log.async_provide_llm_data(
                user_input.as_llm_context(DOMAIN),
                llm.LLM_API_ASSIST,
                None,
                user_input.extra_system_prompt,
            )
        except conversation.ConverseError as err:
            return err.as_conversation_result()

        await self._async_handle_chat_log("conversation", chat_log)

        return conversation.async_get_result_from_chat_log(user_input, chat_log)
