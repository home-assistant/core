"""Utility functions for conversation integration."""

from __future__ import annotations

import logging

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import intent, llm

from .chat_log import AssistantContent, ChatLog, ToolResultContent
from .models import ConversationInput, ConversationResult

_LOGGER = logging.getLogger(__name__)


@callback
def async_get_result_from_chat_log(
    user_input: ConversationInput, chat_log: ChatLog
) -> ConversationResult:
    """Get the result from the chat log."""
    tool_results = [
        content.tool_result
        for content in chat_log.content[chat_log.llm_input_provided_index :]
        if isinstance(content, ToolResultContent)
        and isinstance(content.tool_result, llm.IntentResponseDict)
    ]

    if tool_results:
        intent_response = tool_results[-1].original
    else:
        intent_response = intent.IntentResponse(language=user_input.language)

    if not isinstance((last_content := chat_log.content[-1]), AssistantContent):
        _LOGGER.error(
            "Last content in chat log is not an AssistantContent: %s. This could be due to the model not returning a valid response",
            last_content,
        )
        raise HomeAssistantError("Unable to get response")

    intent_response.async_set_speech(last_content.content or "")

    return ConversationResult(
        response=intent_response,
        conversation_id=chat_log.conversation_id,
        continue_conversation=chat_log.continue_conversation,
    )
