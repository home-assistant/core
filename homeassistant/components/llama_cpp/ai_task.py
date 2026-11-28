"""AI Task integration for llama.cpp."""

from json import JSONDecodeError
from typing import override

from homeassistant.components import ai_task, conversation
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.json import json_loads

from . import LlamaCppConfigEntry
from .const import DOMAIN
from .entity import LlamaCppBaseLLMEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LlamaCppConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AI Task entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "ai_task_data":
            continue

        async_add_entities(
            [LlamaCppTaskEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class LlamaCppTaskEntity(
    ai_task.AITaskEntity,
    LlamaCppBaseLLMEntity,
):
    """llama.cpp AI Task entity."""

    _attr_supported_features = (
        ai_task.AITaskEntityFeature.GENERATE_DATA
        | ai_task.AITaskEntityFeature.SUPPORT_ATTACHMENTS
    )

    @override
    async def _async_generate_data(
        self,
        task: ai_task.GenDataTask,
        chat_log: conversation.ChatLog,
    ) -> ai_task.GenDataTaskResult:
        """Handle a generate data task."""
        await self._async_handle_chat_log(chat_log, task.name, task.structure)

        if not isinstance(chat_log.content[-1], conversation.AssistantContent) or not (
            text := chat_log.content[-1].content
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="response_not_found"
            )

        if not task.structure:
            return ai_task.GenDataTaskResult(
                conversation_id=chat_log.conversation_id,
                data=text,
            )
        try:
            data = json_loads(text)
        except JSONDecodeError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="structured_response_error"
            ) from err
        if not isinstance(data, dict):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="structured_response_error"
            )

        return ai_task.GenDataTaskResult(
            conversation_id=chat_log.conversation_id,
            data=data,
        )
