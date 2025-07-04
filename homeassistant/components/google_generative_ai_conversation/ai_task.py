"""AI Task integration for Google Generative AI Conversation."""

from __future__ import annotations

from homeassistant.components import ai_task, conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LOGGER
from .entity import ERROR_GETTING_RESPONSE, GoogleGenerativeAILLMBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AI Task entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "ai_task_data":
            continue

        async_add_entities(
            [GoogleGenerativeAITaskEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class GoogleGenerativeAITaskEntity(
    ai_task.AITaskEntity,
    GoogleGenerativeAILLMBaseEntity,
):
    """Google Generative AI AI Task entity."""

    _attr_supported_features = ai_task.AITaskEntityFeature.GENERATE_DATA

    async def _async_generate_data(
        self,
        task: ai_task.GenDataTask,
        chat_log: conversation.ChatLog,
    ) -> ai_task.GenDataTaskResult:
        """Handle a generate data task."""
        await self._async_handle_chat_log(chat_log)

        if not isinstance(chat_log.content[-1], conversation.AssistantContent):
            LOGGER.error(
                "Last content in chat log is not an AssistantContent: %s. This could be due to the model not returning a valid response",
                chat_log.content[-1],
            )
            raise HomeAssistantError(ERROR_GETTING_RESPONSE)

        return ai_task.GenDataTaskResult(
            conversation_id=chat_log.conversation_id,
            data=chat_log.content[-1].content or "",
        )
