"""Config flow for Ambiclimate."""
import logging

from aiohttp import web
import ambiclimate

from homeassistant import config_entries
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import get_url
from homeassistant.helpers.storage import Store

from .const import (
    AUTH_CALLBACK_NAME,
    AUTH_CALLBACK_PATH,
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
)

DATA_AMBICLIMATE_IMPL = "ambiclimate_flow_implementation"

_LOGGER = logging.getLogger(__name__)


@callback
def register_flow_implementation(hass, client_id, client_secret):
    """Register a ambiclimate implementation.

    client_id: Client id.
    client_secret: Client secret.
    """
    hass.data.setdefault(DATA_AMBICLIMATE_IMPL, {})

    hass.data[DATA_AMBICLIMATE_IMPL] = {
        CONF_CLIENT_ID: client_id,
        CONF_CLIENT_SECRET: client_secret,
    }


class AmbiclimateFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize flow."""
        self._registered_view = False
        self._oauth = None

    async def async_step_user(self, user_input=None):
        """Handle external yaml configuration."""
        self._async_abort_entries_match()

        config = self.hass.data.get(DATA_AMBICLIMATE_IMPL, {})

        if not config:
            _LOGGER.debug("No config")
            return self.async_abort(reason="missing_configuration")

        return await self.async_step_auth()

    async def async_step_auth(self, user_input=None):
        """Handle a flow start."""
        self._async_abort_entries_match()

        errors = {}

        if user_input is not None:
            errors["base"] = "follow_link"

        if not self._registered_view:
            self._generate_view()

        return self.async_show_form(
            step_id="auth",
            description_placeholders={
                "authorization_url": await self._get_authorize_url(),
                "cb_url": self._cb_url(),
            },
            errors=errors,
        )

    async def async_step_code(self, code=None):
        """Received code for authentication."""
        self._async_abort_entries_match()

        if await self._get_token_info(code) is None:
            return self.async_abort(reason="access_token")

        config = self.hass.data[DATA_AMBICLIMATE_IMPL].copy()
        config["callback_url"] = self._cb_url()

        return self.async_create_entry(title="Ambiclimate", data=config)

    async def _get_token_info(self, code):
        oauth = self._generate_oauth()
        try:
            token_info = await oauth.get_access_token(code)
        except ambiclimate.AmbiclimateOauthError:
            _LOGGER.error("Failed to get access token", exc_info=True)
            return None

        store = Store(self.hass, STORAGE_VERSION, STORAGE_KEY)
        await store.async_save(token_info)

        return token_info

    def _generate_view(self):
        self.hass.http.register_view(AmbiclimateAuthCallbackView())
        self._registered_view = True

    def _generate_oauth(self):
        config = self.hass.data[DATA_AMBICLIMATE_IMPL]
        clientsession = async_get_clientsession(self.hass)
        callback_url = self._cb_url()

        return ambiclimate.AmbiclimateOAuth(
            config.get(CONF_CLIENT_ID),
            config.get(CONF_CLIENT_SECRET),
            callback_url,
            clientsession,
        )

    def _cb_url(self):
        return f"{get_url(self.hass, prefer_external=True)}{AUTH_CALLBACK_PATH}"

    async def _get_authorize_url(self):
        oauth = self._generate_oauth()
        return oauth.get_authorize_url()


class AmbiclimateAuthCallbackView(HomeAssistantView):
    """Ambiclimate Authorization Callback View."""

    requires_auth = False
    url = AUTH_CALLBACK_PATH
    name = AUTH_CALLBACK_NAME

    async def get(self, request: web.Request) -> str:
        """Receive authorization token."""
        if (code := request.query.get("code")) is None:
            return "No code"
        hass = request.app["hass"]
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "code"}, data=code
            )
        )
        return "OK!"
