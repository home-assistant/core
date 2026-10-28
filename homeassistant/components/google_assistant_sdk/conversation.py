"""Conversation platform for the Google Assistant SDK integration."""

import asyncio
from typing import override

from gassist_text import TextAssistantAsync
from google.oauth2.credentials import Credentials

from homeassistant.components import conversation
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, intent
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_LANGUAGE_CODE, DOMAIN, SUPPORTED_LANGUAGE_CODES
from .helpers import GoogleAssistantSDKConfigEntry, best_matching_language_code

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GoogleAssistantSDKConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the conversation entity."""
    async_add_entities([GoogleAssistantConversationEntity(entry)])


class GoogleAssistantConversationEntity(
    conversation.ConversationEntity, conversation.AbstractConversationAgent
):
    """Google Assistant SDK conversation agent."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: GoogleAssistantSDKConfigEntry) -> None:
        """Initialize the agent."""
        self.entry = entry
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Google",
            entry_type=dr.DeviceEntryType.SERVICE,
        )
        self.assistant: TextAssistantAsync | None = None
        self.session: OAuth2Session | None = None
        self.language: str | None = None
        # The assistant holds the state of a single conversation and is shared
        # by every request, so the requests have to be serialized. This also
        # keeps a replacement from closing a channel that is still in use.
        self._lock = asyncio.Lock()

    @property
    @override
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return SUPPORTED_LANGUAGE_CODES

    @override
    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self.entry, self)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Close the assistant, releasing its gRPC channel."""
        conversation.async_unset_agent(self.hass, self.entry)
        async with self._lock:
            await self._async_close_assistant()
        await super().async_will_remove_from_hass()

    async def _async_close_assistant(self) -> None:
        """Close the assistant. The caller must hold the lock."""
        if self.assistant:
            await self.assistant.close()
            self.assistant = None

    @override
    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Process a sentence."""
        async with self._lock:
            if self.session:
                session = self.session
            else:
                session = self.entry.runtime_data.session
                self.session = session
            if not session.valid_token:
                await session.async_ensure_token_valid()
                await self._async_close_assistant()

            language = best_matching_language_code(
                self.hass,
                user_input.language,
                self.entry.options.get(CONF_LANGUAGE_CODE),
            )

            if not self.assistant or language != self.language:
                await self._async_close_assistant()
                credentials = Credentials(session.token[CONF_ACCESS_TOKEN])  # type: ignore[no-untyped-call]
                self.language = language
                self.assistant = TextAssistantAsync(credentials, self.language)

            resp = await self.assistant.assist(user_input.text)
        text_response = resp[0] or "<empty response>"

        chat_log.async_add_assistant_content_without_tools(
            conversation.AssistantContent(
                agent_id=user_input.agent_id, content=text_response
            )
        )
        intent_response = intent.IntentResponse(language=language)
        intent_response.async_set_speech(text_response)
        return conversation.ConversationResult(
            response=intent_response, conversation_id=chat_log.conversation_id
        )
