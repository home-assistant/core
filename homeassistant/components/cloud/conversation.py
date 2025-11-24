"""Conversation support for Home Assistant Cloud."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from enum import Enum
import json
import logging
import re
from typing import Any, Literal, cast

from hass_nabucasa import Cloud
from hass_nabucasa.llm import (
    LLMAuthenticationError,
    LLMError,
    LLMRateLimitError,
    LLMResponseError,
    LLMServiceError,
)
from litellm import ResponseFunctionToolCall, ResponsesAPIStreamEvents
from openai.types.responses import ResponseReasoningItem

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .client import CloudClient
from .const import CONVERSATION_ENTITY_UNIQUE_ID, DATA_CLOUD, DOMAIN
from .helpers import LLMChatHelper

_LOGGER = logging.getLogger(__name__)


class ResponseItemType(str, Enum):
    """Response item types."""

    FUNCTION_CALL = "function_call"
    MESSAGE = "message"
    REASONING = "reasoning"
    WEB_SEARCH_CALL = "web_search_call"
    IMAGE = "image"


# Borrowed and adapted from openai_conversation component
async def _transform_stream(  # noqa: C901 - This is complex, but better to have it in one place
    chat_log: conversation.ChatLog,
    stream: Any,
    remove_citations: bool = False,
) -> AsyncGenerator[
    conversation.AssistantContentDeltaDict | conversation.ToolResultContentDeltaDict
]:
    """Transform an OpenAI delta stream into HA format."""
    last_summary_index = None
    last_role: Literal["assistant", "tool_result"] | None = None
    current_tool_call: ResponseFunctionToolCall | None = None

    # Non-reasoning models don't follow our request to remove citations, so we remove
    # them manually here. They always follow the same pattern: the citation is always
    # in parentheses in Markdown format, the citation is always in a single delta event,
    # and sometimes the closing parenthesis is split into a separate delta event.
    remove_parentheses: bool = False
    citation_regexp = re.compile(r"\(\[([^\]]+)\]\((https?:\/\/[^\)]+)\)")

    async for event in stream:
        event_type = getattr(event, "type", None)
        event_item = getattr(event, "item", None)
        event_item_type = getattr(event_item, "type", None) if event_item else None

        _LOGGER.debug(
            "Event[%s] | item: %s",
            event_type,
            event_item_type,
        )

        if event_type == ResponsesAPIStreamEvents.OUTPUT_ITEM_ADDED:
            # Detect function_call even when it's a BaseLiteLLMOpenAIResponseObject
            if event_item_type == ResponseItemType.FUNCTION_CALL:
                # OpenAI has tool calls as individual events
                # while HA puts tool calls inside the assistant message.
                # We turn them into individual assistant content for HA
                # to ensure that tools are called as soon as possible.
                yield {"role": "assistant"}
                last_role = "assistant"
                last_summary_index = None
                current_tool_call = cast(ResponseFunctionToolCall, event.item)
            elif (
                event_item_type == ResponseItemType.MESSAGE
                or (
                    event_item_type == ResponseItemType.REASONING
                    and last_summary_index is not None
                )  # Subsequent ResponseReasoningItem
                or last_role != "assistant"
            ):
                yield {"role": "assistant"}
                last_role = "assistant"
                last_summary_index = None

        elif event_type == ResponsesAPIStreamEvents.OUTPUT_ITEM_DONE:
            if event_item_type == ResponseItemType.REASONING:
                encrypted_content = getattr(event.item, "encrypted_content", None)
                summary = getattr(event.item, "summary", []) or []

                yield {
                    "native": ResponseReasoningItem(
                        type="reasoning",
                        id=event.item.id,
                        summary=[],
                        encrypted_content=encrypted_content,
                    )
                }

                last_summary_index = len(summary) - 1 if summary else None
            elif event_item_type == ResponseItemType.WEB_SEARCH_CALL:
                action = getattr(event.item, "action", None)
                if isinstance(action, dict):
                    action_dict = action
                elif action is not None:
                    action_dict = action.to_dict()
                else:
                    action_dict = {}
                yield {
                    "tool_calls": [
                        llm.ToolInput(
                            id=event.item.id,
                            tool_name="web_search_call",
                            tool_args={"action": action_dict},
                            external=True,
                        )
                    ]
                }
                yield {
                    "role": "tool_result",
                    "tool_call_id": event.item.id,
                    "tool_name": "web_search_call",
                    "tool_result": {"status": event.item.status},
                }
                last_role = "tool_result"
            elif event_item_type == ResponseItemType.IMAGE:
                yield {"native": event.item}
                last_summary_index = -1  # Trigger new assistant message on next turn

        elif event_type == ResponsesAPIStreamEvents.OUTPUT_TEXT_DELTA:
            data = event.delta
            if remove_parentheses:
                data = data.removeprefix(")")
                remove_parentheses = False
            elif remove_citations and (match := citation_regexp.search(data)):
                match_start, match_end = match.span()
                # remove leading space if any
                if data[match_start - 1 : match_start] == " ":
                    match_start -= 1
                # remove closing parenthesis:
                if data[match_end : match_end + 1] == ")":
                    match_end += 1
                else:
                    remove_parentheses = True
                data = data[:match_start] + data[match_end:]
            if data:
                yield {"content": data}

        elif event_type == ResponsesAPIStreamEvents.REASONING_SUMMARY_TEXT_DELTA:
            # OpenAI can output several reasoning summaries
            # in a single ResponseReasoningItem. We split them as separate
            # AssistantContent messages. Only last of them will have
            # the reasoning `native` field set.
            if (
                last_summary_index is not None
                and event.summary_index != last_summary_index
            ):
                yield {"role": "assistant"}
                last_role = "assistant"
            last_summary_index = event.summary_index
            yield {"thinking_content": event.delta}

        elif event_type == ResponsesAPIStreamEvents.FUNCTION_CALL_ARGUMENTS_DELTA:
            if current_tool_call is not None:
                current_tool_call.arguments += event.delta

        elif event_type == ResponsesAPIStreamEvents.WEB_SEARCH_CALL_SEARCHING:
            yield {"role": "assistant"}

        elif event_type == ResponsesAPIStreamEvents.FUNCTION_CALL_ARGUMENTS_DONE:
            if current_tool_call is not None:
                current_tool_call.status = "completed"

                raw_args = json.loads(current_tool_call.arguments)
                for key in ("area", "floor"):
                    if key in raw_args and not raw_args[key]:
                        # Remove keys that are "" or None
                        raw_args.pop(key, None)

                yield {
                    "tool_calls": [
                        llm.ToolInput(
                            id=current_tool_call.call_id,
                            tool_name=current_tool_call.name,
                            tool_args=raw_args,
                        )
                    ]
                }

        elif event_type == ResponsesAPIStreamEvents.RESPONSE_COMPLETED:
            if event.response.usage is not None:
                chat_log.async_trace(
                    {
                        "stats": {
                            "input_tokens": event.response.usage.input_tokens,
                            "output_tokens": event.response.usage.output_tokens,
                        }
                    }
                )

        elif event_type == ResponsesAPIStreamEvents.RESPONSE_INCOMPLETE:
            if event.response.usage is not None:
                chat_log.async_trace(
                    {
                        "stats": {
                            "input_tokens": event.response.usage.input_tokens,
                            "output_tokens": event.response.usage.output_tokens,
                        }
                    }
                )

            if (
                event.response.incomplete_details
                and event.response.incomplete_details.reason
            ):
                reason: str = event.response.incomplete_details.reason
            else:
                reason = "unknown reason"

            if reason == "max_output_tokens":
                reason = "max output tokens reached"
            elif reason == "content_filter":
                reason = "content filter triggered"

            raise HomeAssistantError(f"OpenAI response incomplete: {reason}")

        elif event_type == ResponsesAPIStreamEvents.RESPONSE_FAILED:
            if event.response.usage is not None:
                chat_log.async_trace(
                    {
                        "stats": {
                            "input_tokens": event.response.usage.input_tokens,
                            "output_tokens": event.response.usage.output_tokens,
                        }
                    }
                )
            reason = "unknown reason"
            if event.response.error is not None:
                reason = event.response.error.message
            raise HomeAssistantError(f"OpenAI response failed: {reason}")

        elif event_type == ResponsesAPIStreamEvents.ERROR:
            raise HomeAssistantError(f"OpenAI response error: {event.message}")


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Home Assistant Cloud conversation entity."""
    cloud = hass.data[DATA_CLOUD]
    try:
        await cloud.llm.async_ensure_token()
    except LLMError:
        return

    async_add_entities([CloudConversationEntity(cloud, config_entry)])


_MAX_TOOL_ITERATIONS = 10


class CloudConversationEntity(
    conversation.ConversationEntity, conversation.AbstractConversationAgent
):
    """Home Assistant Cloud conversation agent."""

    _attr_has_entity_name = True
    _attr_name = "Home Assistant Cloud"
    _attr_translation_key = "cloud_conversation"
    _attr_unique_id = CONVERSATION_ENTITY_UNIQUE_ID

    def __init__(self, cloud: Cloud[CloudClient], config_entry: ConfigEntry) -> None:
        """Initialize the entity."""
        self._cloud = cloud
        self._entry = config_entry
        self._attr_supported_features = conversation.ConversationEntityFeature.CONTROL

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return self._cloud.is_logged_in and self._cloud.valid_subscription

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    async def async_added_to_hass(self) -> None:
        """Register the conversation agent when added."""
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self._entry, self)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister the conversation agent when removed."""
        conversation.async_unset_agent(self.hass, self._entry)
        await super().async_will_remove_from_hass()

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

        await self._async_handle_chat_log(chat_log)

        return conversation.async_get_result_from_chat_log(user_input, chat_log)

    async def _async_handle_chat_log(self, chat_log: conversation.ChatLog) -> None:
        """Generate a response for the chat log."""

        for _ in range(_MAX_TOOL_ITERATIONS):
            response_kwargs = await LLMChatHelper.prepare_chat_for_generation(
                self.hass,
                chat_log,
            )
            response_kwargs["stream"] = True

            try:
                raw_stream = await self._cloud.llm.async_process_conversation(
                    **response_kwargs,
                )

                async for _ in chat_log.async_add_delta_content_stream(
                    agent_id=self.entity_id,
                    stream=_transform_stream(
                        chat_log,
                        raw_stream,
                        True,
                    ),
                ):
                    pass

            except LLMAuthenticationError as err:
                raise ConfigEntryAuthFailed("Cloud LLM authentication failed") from err
            except LLMRateLimitError as err:
                raise HomeAssistantError("Cloud LLM is rate limited") from err
            except LLMResponseError as err:
                raise HomeAssistantError(str(err)) from err
            except LLMServiceError as err:
                raise HomeAssistantError("Error talking to Cloud LLM") from err
            except LLMError as err:
                raise HomeAssistantError(str(err)) from err

            if not chat_log.unresponded_tool_results:
                break
