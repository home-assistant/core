"""Base entity for Open Router."""

from __future__ import annotations

from typing import Literal

import openai
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_MODEL
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import Entity

from . import OpenRouterConfigEntry
from .const import DOMAIN, LOGGER


def _convert_content_to_chat_message(
    content: conversation.Content,
) -> ChatCompletionMessageParam | None:
    """Convert any native chat message for this agent to the native format."""
    LOGGER.debug("_convert_content_to_chat_message=%s", content)
    if isinstance(content, conversation.ToolResultContent):
        return None

    role: Literal["user", "assistant", "system"] = content.role
    if role == "system" and content.content:
        return ChatCompletionSystemMessageParam(role="system", content=content.content)

    if role == "user" and content.content:
        return ChatCompletionUserMessageParam(role="user", content=content.content)

    if role == "assistant":
        return ChatCompletionAssistantMessageParam(
            role="assistant", content=content.content
        )
    LOGGER.warning("Could not convert message to Completions API: %s", content)
    return None


class OpenRouterEntity(Entity):
    """Base entity for Open Router."""

    _attr_has_entity_name = True

    def __init__(self, entry: OpenRouterConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the entity."""
        self.entry = entry
        self.subentry = subentry
        self.model = subentry.data[CONF_MODEL]
        self._attr_unique_id = subentry.subentry_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    async def _async_handle_chat_log(
        self, user_input: conversation.ConversationInput, chat_log: conversation.ChatLog
    ) -> None:
        """Generate an answer for the chat log."""
        messages = [
            m
            for content in chat_log.content
            if (m := _convert_content_to_chat_message(content))
        ]

        client = self.entry.runtime_data

        try:
            result = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                user=chat_log.conversation_id,
                extra_headers={
                    "X-Title": "Home Assistant",
                    "HTTP-Referer": "https://www.home-assistant.io/integrations/open_router",
                },
            )
        except openai.OpenAIError as err:
            LOGGER.error("Error talking to API: %s", err)
            raise HomeAssistantError("Error talking to API") from err

        result_message = result.choices[0].message

        chat_log.async_add_assistant_content_without_tools(
            conversation.AssistantContent(
                agent_id=user_input.agent_id,
                content=result_message.content,
            )
        )
