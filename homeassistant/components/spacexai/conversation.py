"""Conversation support for SpaceXAI."""

from collections.abc import AsyncGenerator, Callable, Iterable
from typing import Any, Literal, override

from probatio import to_openapi
from spacexai_subscription_client import (
    AuthenticationError,
    Completion,
    InputItem,
    InvalidResponseError,
    Message,
    PermissionDeniedError,
    SpaceXAISubscriptionError,
    Tool,
    ToolCall,
    ToolResult,
)

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_LLM_HASS_API, CONF_MODEL, CONF_PROMPT, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import device_registry as dr, llm
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.json import json_dumps

from . import SpaceXAIConfigEntry
from .const import DOMAIN, LOGGER, MAX_TOOL_ITERATIONS

PARALLEL_UPDATES = 0


def _format_tool(
    tool: llm.Tool, custom_serializer: Callable[[Any], Any] | None
) -> Tool:
    """Convert a Home Assistant tool to a client tool."""
    return Tool(
        tool.name,
        tool.description,
        to_openapi(
            tool.parameters,
            custom_serializer=custom_serializer,
        ),
    )


def _convert_content(
    chat_content: Iterable[conversation.Content],
) -> list[InputItem]:
    """Convert Home Assistant chat content to client input."""
    messages: list[InputItem] = []
    for content in chat_content:
        if isinstance(content, conversation.UserContent) and content.attachments:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="attachments_not_supported",
            )
        if isinstance(content, conversation.ToolResultContent):
            messages.append(
                ToolResult(
                    content.tool_call_id,
                    json_dumps(content.tool_result),
                )
            )
            continue
        if content.content:
            role: Literal["user", "assistant", "system", "developer"] = content.role
            if role == "system":
                role = "developer"
            messages.append(Message(role, content.content))
        if isinstance(content, conversation.AssistantContent):
            messages.extend(
                ToolCall(
                    tool_call.id,
                    tool_call.tool_name,
                    tool_call.tool_args,
                )
                for tool_call in content.tool_calls or ()
            )
    return messages


def _tool_input(tool_call: ToolCall) -> llm.ToolInput:
    """Convert a client tool call to Home Assistant input."""
    return llm.ToolInput(
        id=tool_call.id,
        tool_name=tool_call.name,
        tool_args=dict(tool_call.arguments),
    )


async def _transform_response(
    response: Completion,
) -> AsyncGenerator[conversation.AssistantContentDeltaDict]:
    """Transform a client response to Home Assistant content."""
    tool_calls = [_tool_input(item) for item in response.tool_calls]
    yield {
        "role": "assistant",
        "content": response.text or None,
        "tool_calls": tool_calls or None,
    }


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SpaceXAIConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SpaceXAI conversation entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "conversation":
            continue
        async_add_entities(
            [SpaceXAIConversationEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class SpaceXAIConversationEntity(
    conversation.ConversationEntity,
    conversation.AbstractConversationAgent,
):
    """SpaceXAI conversation agent."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: SpaceXAIConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the conversation agent."""
        self.entry = entry
        self.subentry = subentry
        self._attr_unique_id = subentry.subentry_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="SpaceXAI",
            model=subentry.data[CONF_MODEL],
            entry_type=dr.DeviceEntryType.SERVICE,
        )
        if subentry.data.get(CONF_LLM_HASS_API):
            self._attr_supported_features = (
                conversation.ConversationEntityFeature.CONTROL
            )

    @property
    @override
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return supported languages."""
        return MATCH_ALL

    @override
    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Process a conversation message."""
        try:
            await chat_log.async_provide_llm_data(
                user_input.as_llm_context(DOMAIN),
                self.subentry.data.get(CONF_LLM_HASS_API),
                self.subentry.data.get(CONF_PROMPT),
                user_input.extra_system_prompt,
            )
        except conversation.ConverseError as err:
            return err.as_conversation_result()

        await self._async_handle_chat_log(chat_log)
        return conversation.async_get_result_from_chat_log(user_input, chat_log)

    async def _async_handle_chat_log(self, chat_log: conversation.ChatLog) -> None:
        """Send the chat log to SpaceXAI and execute Home Assistant tools."""
        tools = []
        if chat_log.llm_api:
            tools = [
                _format_tool(tool, chat_log.llm_api.custom_serializer)
                for tool in chat_log.llm_api.tools
            ]

        for _iteration in range(MAX_TOOL_ITERATIONS):
            try:
                await self.entry.runtime_data.oauth_session.async_ensure_token_valid()
                response = await self.entry.runtime_data.client.async_create_response(
                    self.entry.runtime_data.oauth_session.token["access_token"],
                    model=self.subentry.data[CONF_MODEL],
                    input_data=_convert_content(chat_log.content),
                    tools=tools,
                )
            except (AuthenticationError, OAuth2TokenRequestReauthError) as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_auth",
                ) from err
            except InvalidResponseError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_response",
                ) from err
            except PermissionDeniedError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="not_entitled",
                ) from err
            except (
                SpaceXAISubscriptionError,
                OAuth2TokenRequestError,
                TimeoutError,
            ) as err:
                LOGGER.error(
                    "Error communicating with SpaceXAI: %s", type(err).__name__
                )
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="api_error",
                ) from err

            async for _content in chat_log.async_add_delta_content_stream(
                self.entity_id, _transform_response(response)
            ):
                pass
            if not chat_log.unresponded_tool_results:
                return

        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="tool_iteration_limit",
        )
