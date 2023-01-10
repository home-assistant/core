"""Support for Google Assistant SDK."""
from __future__ import annotations

import aiohttp
from gassist_text import TextAssistant
from google.oauth2.credentials import Credentials
import voluptuous as vol

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_NAME, Platform
from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import discovery, intent
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.typing import ConfigType

from .const import CONF_ENABLE_CONVERSATION_AGENT, CONF_LANGUAGE_CODE, DOMAIN
from .helpers import async_send_text_commands, default_language_code

SERVICE_SEND_TEXT_COMMAND = "send_text_command"
SERVICE_SEND_TEXT_COMMAND_FIELD_COMMAND = "command"
SERVICE_SEND_TEXT_COMMAND_SCHEMA = vol.All(
    {
        vol.Required(SERVICE_SEND_TEXT_COMMAND_FIELD_COMMAND): vol.All(
            str, vol.Length(min=1)
        ),
    },
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Google Assistant SDK component."""
    hass.async_create_task(
        discovery.async_load_platform(
            hass, Platform.NOTIFY, DOMAIN, {CONF_NAME: DOMAIN}, config
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Google Assistant SDK from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)
    try:
        await session.async_ensure_token_valid()
    except aiohttp.ClientResponseError as err:
        if 400 <= err.status < 500:
            raise ConfigEntryAuthFailed(
                "OAuth session is not valid, reauth required"
            ) from err
        raise ConfigEntryNotReady from err
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady from err
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = session

    await async_setup_service(hass)

    entry.async_on_unload(entry.add_update_listener(update_listener))
    await update_listener(hass, entry)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)
    loaded_entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state == ConfigEntryState.LOADED
    ]
    if len(loaded_entries) == 1:
        for service_name in hass.services.async_services()[DOMAIN]:
            hass.services.async_remove(DOMAIN, service_name)

    return True


async def async_setup_service(hass: HomeAssistant) -> None:
    """Add the services for Google Assistant SDK."""

    async def send_text_command(call: ServiceCall) -> None:
        """Send a text command to Google Assistant SDK."""
        command: str = call.data[SERVICE_SEND_TEXT_COMMAND_FIELD_COMMAND]
        await async_send_text_commands([command], hass)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_TEXT_COMMAND,
        send_text_command,
        schema=SERVICE_SEND_TEXT_COMMAND_SCHEMA,
    )


async def update_listener(hass, entry):
    """Handle options update."""
    if entry.options.get(CONF_ENABLE_CONVERSATION_AGENT, False):
        agent = GoogleAssistantConversationAgent(hass, entry)
        conversation.async_set_agent(hass, agent)
    else:
        conversation.async_set_agent(hass, None)


class GoogleAssistantConversationAgent(conversation.AbstractConversationAgent):
    """Google Assistant SDK conversation agent."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self.hass = hass
        self.entry = entry
        self.assistant: TextAssistant | None = None
        self.session: OAuth2Session | None = None

    @property
    def attribution(self):
        """Return the attribution."""
        return {
            "name": "Powered by Google Assistant SDK",
            "url": "https://www.home-assistant.io/integrations/google_assistant_sdk/",
        }

    async def async_process(
        self,
        text: str,
        context: Context,
        conversation_id: str | None = None,
        language: str | None = None,
    ) -> conversation.ConversationResult | None:
        """Process a sentence."""
        if self.session:
            session = self.session
        else:
            session = self.hass.data[DOMAIN].get(self.entry.entry_id)
            self.session = session
        if not session.valid_token:
            await session.async_ensure_token_valid()
            self.assistant = None
        if not self.assistant:
            credentials = Credentials(session.token[CONF_ACCESS_TOKEN])
            language_code = self.entry.options.get(
                CONF_LANGUAGE_CODE, default_language_code(self.hass)
            )
            self.assistant = TextAssistant(credentials, language_code)

        resp = self.assistant.assist(text)
        text_response = resp[0]

        language = language or self.hass.config.language
        intent_response = intent.IntentResponse(language=language)
        intent_response.async_set_speech(text_response)
        return conversation.ConversationResult(
            response=intent_response, conversation_id=conversation_id
        )
