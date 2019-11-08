"""Support for Almond."""
import asyncio
from datetime import timedelta
import logging
import time
from typing import Optional

import async_timeout
from aiohttp import ClientSession, ClientError
from pyalmond import AlmondLocalAuth, AbstractAlmondWebAuth, WebAlmondAPI
import voluptuous as vol

from homeassistant import core
from homeassistant.const import CONF_TYPE, CONF_HOST
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.helpers import (
    config_validation as cv,
    config_entry_oauth2_flow,
    intent,
    aiohttp_client,
    storage,
)
from homeassistant import config_entries
from homeassistant.components import conversation

from . import config_flow
from .const import DOMAIN, TYPE_LOCAL, TYPE_OAUTH2

CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"

STORAGE_VERSION = 1
STORAGE_KEY = DOMAIN

DEFAULT_OAUTH2_HOST = "https://almond.stanford.edu"
DEFAULT_LOCAL_HOST = "http://localhost:3000"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Any(
            vol.Schema(
                {
                    vol.Required(CONF_TYPE): TYPE_OAUTH2,
                    vol.Required(CONF_CLIENT_ID): cv.string,
                    vol.Required(CONF_CLIENT_SECRET): cv.string,
                    vol.Optional(CONF_HOST, default=DEFAULT_OAUTH2_HOST): cv.url,
                }
            ),
            vol.Schema(
                {vol.Required(CONF_TYPE): TYPE_LOCAL, vol.Required(CONF_HOST): cv.url}
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the Almond component."""
    hass.data[DOMAIN] = {}

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    host = conf[CONF_HOST]

    if conf[CONF_TYPE] == TYPE_OAUTH2:
        config_flow.AlmondFlowHandler.async_register_implementation(
            hass,
            config_entry_oauth2_flow.LocalOAuth2Implementation(
                hass,
                DOMAIN,
                conf[CONF_CLIENT_ID],
                conf[CONF_CLIENT_SECRET],
                f"{host}/me/api/oauth2/authorize",
                f"{host}/me/api/oauth2/token",
            ),
        )
        return True

    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data={"type": TYPE_LOCAL, "host": conf[CONF_HOST]},
            )
        )
    return True


async def async_setup_entry(hass, entry):
    """Set up Almond config entry."""
    websession = aiohttp_client.async_get_clientsession(hass)

    if entry.data["type"] == TYPE_LOCAL:
        auth = AlmondLocalAuth(entry.data["host"], websession)
    else:
        # OAuth2
        implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
        oauth_session = config_entry_oauth2_flow.OAuth2Session(
            hass, entry, implementation
        )
        auth = AlmondOAuth(entry.data["host"], websession, oauth_session)

    api = WebAlmondAPI(auth)
    agent = AlmondAgent(hass, api, entry)

    # Hass.io does its own configuration of Almond.
    if entry.data.get("is_hassio") or entry.data["type"] != TYPE_LOCAL:
        conversation.async_set_agent(hass, agent)
        return True

    # Configure Almond to connect to Home Assistant
    store = storage.Store(hass, STORAGE_VERSION, STORAGE_KEY)
    data = await store.async_load()

    if data is None:
        data = {}

    user = None
    if "almond_user" in data:
        user = await hass.auth.async_get_user(data["almond_user"])

    if user is None:
        user = await hass.auth.async_create_system_user("Almond", [GROUP_ID_ADMIN])
        data["almond_user"] = user.id
        await store.async_save(data)

    refresh_token = await hass.auth.async_create_refresh_token(
        user,
        # Almond will be fine as long as we restart once every 5 years
        access_token_expiration=timedelta(days=365 * 5),
    )

    # Create long lived access token
    access_token = hass.auth.async_create_access_token(refresh_token)

    # Store token in Almond
    try:
        with async_timeout.timeout(10):
            await api.async_create_device(
                {
                    "kind": "io.home-assistant",
                    "hassUrl": hass.config.api.base_url,
                    "accessToken": access_token,
                    "refreshToken": "",
                    # 5 years from now in ms.
                    "accessTokenExpires": (time.time() + 60 * 60 * 24 * 365 * 5) * 1000,
                }
            )
    except (asyncio.TimeoutError, ClientError) as err:
        if isinstance(err, asyncio.TimeoutError):
            msg = "Request timeout"
        else:
            msg = err
        _LOGGER.warning("Unable to configure Almond: %s", msg)
        await hass.auth.async_remove_refresh_token(refresh_token)
        raise ConfigEntryNotReady

    # Clear all other refresh tokens
    for token in list(user.refresh_tokens.values()):
        if token.id != refresh_token.id:
            await hass.auth.async_remove_refresh_token(token)

    conversation.async_set_agent(hass, agent)
    return True


async def async_unload_entry(hass, entry):
    """Unload Almond."""
    conversation.async_set_agent(hass, None)
    return True


class AlmondOAuth(AbstractAlmondWebAuth):
    """Almond Authentication using OAuth2."""

    def __init__(
        self,
        host: str,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ):
        """Initialize Almond auth."""
        super().__init__(host, websession)
        self._oauth_session = oauth_session

    async def async_get_access_token(self):
        """Return a valid access token."""
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()

        return self._oauth_session.token["access_token"]


class AlmondAgent(conversation.AbstractConversationAgent):
    """Almond conversation agent."""

    def __init__(self, hass: core.HomeAssistant, api: WebAlmondAPI, entry):
        """Initialize the agent."""
        self.hass = hass
        self.api = api
        self.entry = entry

    @property
    def attribution(self):
        """Return the attribution."""
        return {"name": "Powered by Almond", "url": "https://almond.stanford.edu/"}

    async def async_get_onboarding(self):
        """Get onboard url if not onboarded."""
        if self.entry.data.get("onboarded"):
            return None

        host = self.entry.data["host"]
        if self.entry.data.get("is_hassio"):
            host = "/core_almond"
        elif self.entry.data["type"] != TYPE_LOCAL:
            host = f"{host}/me"
        return {
            "text": "Would you like to opt-in to share your anonymized commands with Stanford to improve Almond's responses?",
            "url": f"{host}/conversation",
        }

    async def async_set_onboarding(self, shown):
        """Set onboarding status."""
        self.hass.config_entries.async_update_entry(
            self.entry, data={**self.entry.data, "onboarded": shown}
        )

        return True

    async def async_process(
        self, text: str, conversation_id: Optional[str] = None
    ) -> intent.IntentResponse:
        """Process a sentence."""
        response = await self.api.async_converse_text(text, conversation_id)

        buffer = ""
        for message in response["messages"]:
            if message["type"] == "text":
                buffer += "\n" + message["text"]
            elif message["type"] == "picture":
                buffer += "\n Picture: " + message["url"]
            elif message["type"] == "rdl":
                buffer += (
                    "\n Link: "
                    + message["rdl"]["displayTitle"]
                    + " "
                    + message["rdl"]["webCallback"]
                )
            elif message["type"] == "choice":
                buffer += "\n Choice: " + message["title"]

        intent_result = intent.IntentResponse()
        intent_result.async_set_speech(buffer.strip())
        return intent_result
