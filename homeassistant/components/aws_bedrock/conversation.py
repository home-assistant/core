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
    LOGGER.debug(
        "Setting up conversation entities for config entry %s", config_entry.entry_id
    )
    LOGGER.debug("Available subentries: %s", list(config_entry.subentries.keys()))

    conversation_entities = []
    for subentry in config_entry.subentries.values():
        LOGGER.debug(
            "Processing subentry: type=%s, id=%s, title=%s",
            subentry.subentry_type,
            subentry.subentry_id,
            subentry.title,
        )
        if subentry.subentry_type != "conversation":
            continue

        conversation_entities.append(
            AWSBedrockConversationEntity(config_entry, subentry)
        )
        LOGGER.debug(
            "Created conversation entity for subentry %s", subentry.subentry_id
        )

    if conversation_entities:
        LOGGER.debug("Adding %d conversation entities", len(conversation_entities))
        async_add_entities(
            conversation_entities,
            config_subentry_id=conversation_entities[0].subentry.subentry_id
            if conversation_entities
            else None,
        )
    else:
        LOGGER.warning("No conversation subentries found to set up")


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
        LOGGER.debug("Starting _async_handle_message")
        options = self.subentry.data
        LOGGER.debug(
            "Options: %s",
            {k: v for k, v in options.items() if k != "secret_access_key"},
        )

        try:
            LOGGER.debug(
                "Calling async_provide_llm_data with LLM APIs: %s",
                options.get(CONF_LLM_HASS_API),
            )
            await chat_log.async_provide_llm_data(
                user_input.as_llm_context(DOMAIN),
                options.get(CONF_LLM_HASS_API),
                options.get(CONF_PROMPT),
                user_input.extra_system_prompt,
            )
            LOGGER.debug("async_provide_llm_data completed successfully")
        except conversation.ConverseError as err:
            LOGGER.error("ConverseError in async_provide_llm_data: %s", err)
            return err.as_conversation_result()
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected error in async_provide_llm_data")
            return conversation.ConversationResult(
                response=conversation.intent.IntentResponse(
                    language=user_input.language
                ),
                conversation_id=user_input.conversation_id or "unknown",
            )

        try:
            LOGGER.debug("Calling _async_handle_chat_log")
            await self._async_handle_chat_log(chat_log)
            LOGGER.debug("_async_handle_chat_log completed successfully")
        except Exception:  # noqa: BLE001
            LOGGER.exception("Error in _async_handle_chat_log")
            return conversation.ConversationResult(
                response=conversation.intent.IntentResponse(
                    language=user_input.language
                ),
                conversation_id=user_input.conversation_id or "unknown",
            )

        LOGGER.debug("Getting result from chat log")
        return conversation.async_get_result_from_chat_log(user_input, chat_log)
