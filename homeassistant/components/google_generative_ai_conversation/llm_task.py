"""LLM Task integration for Google Generative AI Conversation."""

from __future__ import annotations

from homeassistant.components import conversation, llm_task
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
    """Set up LLM Task entities."""
    agent = GoogleGenerativeAILLMTaskEntity(config_entry)
    async_add_entities([agent])


class GoogleGenerativeAILLMTaskEntity(
    llm_task.LLMTaskEntity,
    GoogleGenerativeAILLMBaseEntity,
):
    """Google Generative AI LLM Task entity."""

    async def _async_handle_llm_task(
        self,
        task: llm_task.LLMTask,
        chat_log: conversation.ChatLog,
    ) -> llm_task.LLMTaskResult:
        """Handle an LLM task."""
        await self._async_handle_chat_log(chat_log)

        if not isinstance(chat_log.content[-1], conversation.AssistantContent):
            LOGGER.error(
                "Last content in chat log is not an AssistantContent: %s. This could be due to the model not returning a valid response",
                chat_log.content[-1],
            )
            raise HomeAssistantError(ERROR_GETTING_RESPONSE)

        return llm_task.LLMTaskResult(
            conversation_id=chat_log.conversation_id,
            result=chat_log.content[-1].content or "",
        )
