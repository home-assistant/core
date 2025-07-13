"""Conversation support for OpenRouter."""

from collections.abc import AsyncGenerator
import json
from typing import Literal

import openai
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessage,
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionToolMessageParam,
    ChatCompletionUserMessageParam,
)

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_LLM_HASS_API, CONF_MODEL, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import intent, template
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OpenRouterConfigEntry
from .const import CONF_PROMPT, DOMAIN, LOGGER


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OpenRouterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up conversation entities."""
    for subentry_id, subentry in config_entry.subentries.items():
        async_add_entities(
            [OpenRouterConversationEntity(config_entry, subentry)],
            config_subentry_id=subentry_id,
        )


def _convert_content_to_chat_message(
    content: conversation.Content,
) -> ChatCompletionMessageParam | None:
    """Convert any native chat message for this agent to the native format."""
    LOGGER.debug("_convert_content_to_chat_message=%s", content)
    if isinstance(content, conversation.ToolResultContent):
        return ChatCompletionToolMessageParam(
            # Note: The functionary 'tool' role expects a name which is
            # not supported in llama cpp python and the openai protos.
            role="tool",
            tool_call_id=content.tool_call_id,
            content=json.dumps(content.tool_result),
        )

    role: Literal["user", "assistant", "system"] = content.role
    if role == "system" and content.content:
        return ChatCompletionSystemMessageParam(role="system", content=content.content)

    if role == "user" and content.content:
        return ChatCompletionUserMessageParam(role="user", content=content.content)

    if role == "assistant":
        return ChatCompletionAssistantMessageParam(
            role="assistant", content=content.content
        )
    LOGGER.warning("Could not convert message to OpenAI API: %s", content)
    return None


async def _transform_response(
    message: ChatCompletionMessage,
) -> AsyncGenerator[conversation.AssistantContentDeltaDict]:
    """Transform the OpenAI API message to a ChatLog format."""
    data: conversation.AssistantContentDeltaDict = {
        "role": message.role,
        "content": message.content,
    }
    yield data


class OpenRouterConversationEntity(
    conversation.ConversationEntity, conversation.AbstractConversationAgent
):
    """OpenRouter conversation agent."""

    def __init__(self, entry: OpenRouterConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the agent."""
        self.entry = entry
        self.model = subentry.data[CONF_MODEL]
        self.history: dict[str, list[dict]] = {}
        self._attr_name = subentry.title
        self._attr_unique_id = subentry.subentry_id

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self.entry, self)

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from Home Assistant."""
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    # async def _async_handle_message(
    #     self,
    #     user_input: conversation.ConversationInput,
    #     chat_log: conversation.ChatLog,
    # ) -> conversation.ConversationResult:
    #     """Process a sentence."""
    #     options = self.entry.options
    #
    #     try:
    #         await chat_log.async_provide_llm_data(
    #             user_input.as_llm_context(DOMAIN),
    #             options.get(CONF_LLM_HASS_API),
    #             options.get(CONF_PROMPT),
    #             user_input.extra_system_prompt,
    #         )
    #     except conversation.ConverseError as err:
    #         return err.as_conversation_result()
    #
    #     await self._async_handle_chat_log(chat_log)
    #
    #     intent_response = intent.IntentResponse(language=user_input.language)
    #     assert type(chat_log.content[-1]) is conversation.AssistantContent
    #     intent_response.async_set_speech(chat_log.content[-1].content or "")
    #     return conversation.ConversationResult(
    #         response=intent_response,
    #         conversation_id=chat_log.conversation_id,
    #         continue_conversation=chat_log.continue_conversation,
    #     )

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Process a sentence."""
        options = self.entry.data

        try:
            await chat_log.async_update_llm_data(
                DOMAIN,
                user_input,
                options.get(CONF_LLM_HASS_API),
                options.get(CONF_PROMPT),
            )
        except conversation.ConverseError as err:
            return err.as_conversation_result()

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
            )
        except openai.OpenAIError as err:
            LOGGER.error("Error talking to API: %s", err)
            raise HomeAssistantError("Error talking to API") from err

        convert_message = _convert_content_to_chat_message
        result_message = result.choices[0].message

        messages.extend(
            [
                msg
                async for content in chat_log.async_add_delta_content_stream(
                    user_input.agent_id,
                    _transform_response(result_message),
                )
                if (msg := convert_message(content))
            ]
        )

        intent_response = intent.IntentResponse(language=user_input.language)
        assert type(chat_log.content[-1]) is conversation.AssistantContent
        intent_response.async_set_speech(chat_log.content[-1].content or "")
        return conversation.ConversationResult(
            response=intent_response,
            conversation_id=chat_log.conversation_id,
            continue_conversation=chat_log.continue_conversation,
        )

    # async def _async_handle_chat_log(
    #     self,
    #     chat_log: conversation.ChatLog,
    # ) -> None:
    #     """Generate an answer for the chat log."""
    #     options = self.entry.options
    #
    #     client = self.entry.runtime_data
    #
    #     if chat_log.conversation_id in self.history:
    #         conversation_id = chat_log.conversation_id
    #         messages = self.history[conversation_id]
    #     else:
    #         conversation_id = ulid_util.ulid_now()
    #         try:
    #             prompt = self._async_generate_prompt(raw_prompt)
    #         except TemplateError as err:
    #             LOGGER.error("Error rendering prompt: %s", err)
    #             intent_response = intent.IntentResponse(language=user_input.language)
    #             intent_response.async_set_error(
    #                 intent.IntentResponseErrorCode.UNKNOWN,
    #                 f"Sorry, I had a problem with my template: {err}",
    #             )
    #             return conversation.ConversationResult(
    #                 response=intent_response, conversation_id=conversation_id
    #             )
    #         messages = [{"role": "system", "content": prompt}]
    #
    #     messages.append({"role": "user", "content": user_input.text})
    #
    #     client = self.entry.runtime_data
    #
    #     try:
    #         result = await client.chat.completions.create(
    #             model=self.model,
    #             messages=messages,  # type: ignore[arg-type]
    #             user=conversation_id,
    #             extra_headers={
    #                 "X-Title": "Home Assistant",
    #                 "HTTP-Referer": "https://www.home-assistant.io/integrations/open_router",
    #             },
    #         )
    #     except openai.OpenAIError as err:
    #         intent_response = intent.IntentResponse(language=user_input.language)
    #         intent_response.async_set_error(
    #             intent.IntentResponseErrorCode.UNKNOWN,
    #             f"Sorry, I had a problem talking to OpenRouter: {err}",
    #         )
    #         return conversation.ConversationResult(
    #             response=intent_response, conversation_id=conversation_id
    #         )
    #
    #     LOGGER.debug("Response %s", result)
    #     response = result.choices[0].message.model_dump(include={"role", "content"})
    #     messages.append(response)
    #     self.history[conversation_id] = messages
    #
    #     intent_response = intent.IntentResponse(language=user_input.language)
    #     intent_response.async_set_speech(response["content"])
    #     return conversation.ConversationResult(
    #         response=intent_response, conversation_id=conversation_id
    #     )

    def _async_generate_prompt(self, raw_prompt: str) -> str:
        """Generate a prompt for the user."""
        return template.Template(raw_prompt, self.hass).async_render(  # type: ignore[no-any-return]
            {
                "ha_name": self.hass.config.location_name,
            },
            parse_result=False,
        )
