"""Support for Google Assistant SDK."""

import asyncio
from typing import override

from aiohttp import ClientError
from gassist_text import TextAssistantAsync
from google.oauth2.credentials import Credentials

from homeassistant.components import conversation
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import config_validation as cv, discovery, intent
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.typing import ConfigType

from .const import CONF_LANGUAGE_CODE, DOMAIN, SUPPORTED_LANGUAGE_CODES
from .helpers import (
    GoogleAssistantSDKAudioView,
    GoogleAssistantSDKConfigEntry,
    GoogleAssistantSDKRuntimeData,
    InMemoryStorage,
    best_matching_language_code,
)
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Google Assistant SDK component."""
    hass.async_create_task(
        discovery.async_load_platform(
            hass, Platform.NOTIFY, DOMAIN, {CONF_NAME: DOMAIN}, config
        )
    )

    async_setup_services(hass)

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: GoogleAssistantSDKConfigEntry
) -> bool:
    """Set up Google Assistant SDK from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)
    try:
        await session.async_ensure_token_valid()
    except OAuth2TokenRequestReauthError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="reauth_required"
        ) from err
    except (OAuth2TokenRequestError, ClientError) as err:
        raise ConfigEntryNotReady from err

    mem_storage = InMemoryStorage(hass)
    hass.http.register_view(GoogleAssistantSDKAudioView(mem_storage))

    entry.runtime_data = GoogleAssistantSDKRuntimeData(
        session=session, mem_storage=mem_storage
    )
    agent = GoogleAssistantConversationAgent(hass, entry)
    entry.async_on_unload(agent.async_close)
    conversation.async_set_agent(hass, entry, agent)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GoogleAssistantSDKConfigEntry
) -> bool:
    """Unload a config entry."""
    conversation.async_unset_agent(hass, entry)

    return True


class GoogleAssistantConversationAgent(conversation.AbstractConversationAgent):
    """Google Assistant SDK conversation agent."""

    def __init__(
        self, hass: HomeAssistant, entry: GoogleAssistantSDKConfigEntry
    ) -> None:
        """Initialize the agent."""
        self.hass = hass
        self.entry = entry
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

    async def async_close(self) -> None:
        """Close the assistant, releasing its gRPC channel."""
        async with self._lock:
            await self._async_close_assistant()

    async def _async_close_assistant(self) -> None:
        """Close the assistant. The caller must hold the lock."""
        if self.assistant:
            await self.assistant.close()
            self.assistant = None

    @override
    async def async_process(
        self, user_input: conversation.ConversationInput
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

        intent_response = intent.IntentResponse(language=language)
        intent_response.async_set_speech(text_response)
        return conversation.ConversationResult(
            response=intent_response, conversation_id=user_input.conversation_id
        )
