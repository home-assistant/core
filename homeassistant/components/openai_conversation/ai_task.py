"""AI Task integration for OpenAI Conversation."""

from __future__ import annotations

from homeassistant.components import ai_task, conversation
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OpenAIConfigEntry
from .const import DEFAULT_AI_TASK_NAME, LOGGER
from .entity import OpenAILLMBaseEntity

ERROR_GETTING_RESPONSE = "Sorry, I had a problem getting a response from OpenAI."


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AI Task entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "ai_task":
            continue

        async_add_entities(
            [OpenAILLMTaskEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class OpenAILLMTaskEntity(ai_task.AITaskEntity, OpenAILLMBaseEntity):
    """OpenAI AI Task entity."""

    _attr_supported_features = ai_task.AITaskEntityFeature.GENERATE_TEXT

    def __init__(self, entry: OpenAIConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the agent."""
        super().__init__(entry, subentry)
        self._attr_name = subentry.title or DEFAULT_AI_TASK_NAME

    async def _async_generate_text(
        self,
        task: ai_task.GenTextTask,
        chat_log: conversation.ChatLog,
    ) -> ai_task.GenTextTaskResult:
        """Handle a generate text task."""
        await self._async_handle_chat_log(chat_log)

        if not isinstance(chat_log.content[-1], conversation.AssistantContent):
            LOGGER.error(
                "Last content in chat log is not an AssistantContent: %s. This could be due to the model not returning a valid response",
                chat_log.content[-1],
            )
            raise HomeAssistantError(ERROR_GETTING_RESPONSE)

        return ai_task.GenTextTaskResult(
            conversation_id=chat_log.conversation_id,
            text=chat_log.content[-1].content or "",
        )
