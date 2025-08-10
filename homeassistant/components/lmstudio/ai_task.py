"""AI Task platform for LM Studio integration."""

from __future__ import annotations

from homeassistant.components import ai_task, conversation
from homeassistant.components.conversation import AssistantContent
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LMStudioConfigEntry
from .entity import LMStudioBaseLLMEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LMStudioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AI task entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "ai_task_data":
            continue

        async_add_entities(
            [
                LMStudioTaskEntity(
                    config_entry,
                    subentry,
                    config_subentry_id=subentry.subentry_id,
                )
            ]
        )


class LMStudioTaskEntity(
    ai_task.AITaskEntity,
    LMStudioBaseLLMEntity,
):
    """LM Studio AI task entity."""

    _attr_supports_streaming = True
    _attr_has_entity_name = True

    def __init__(
        self,
        entry: LMStudioConfigEntry,
        subentry: ConfigSubentry,
        config_subentry_id: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(entry, subentry)
        self._config_subentry_id = config_subentry_id

    async def _async_generate_data(
        self,
        task: ai_task.GenDataTask,
        chat_log: conversation.ChatLog,
    ) -> ai_task.GenDataTaskResult:
        """Handle the AI task."""
        # Process the chat log
        await self._async_handle_chat_log(chat_log)

        # Return the result from the chat log
        last_message = chat_log.content[-1] if chat_log.content else None
        return ai_task.GenDataTaskResult(
            conversation_id=chat_log.conversation_id,
            data=last_message.content
            if last_message and isinstance(last_message, AssistantContent)
            else "",
        )
