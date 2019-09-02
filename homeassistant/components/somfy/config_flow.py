"""Config flow for Somfy."""
import asyncio
import logging

import async_timeout

from homeassistant import config_entries
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import callback
from .const import CLIENT_ID, CLIENT_SECRET, DOMAIN

AUTH_CALLBACK_PATH = "/auth/somfy/callback"
AUTH_CALLBACK_NAME = "auth:somfy:callback"

_LOGGER = logging.getLogger(__name__)


@callback
def register_flow_implementation(hass, client_id, client_secret):
    """Register a flow implementation.

    client_id: Client id.
    client_secret: Client secret.
    """
    hass.data[DOMAIN][CLIENT_ID] = client_id
    hass.data[DOMAIN][CLIENT_SECRET] = client_secret


@config_entries.HANDLERS.register("somfy")
class SomfyFlowHandler(config_entries.ConfigFlow):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Instantiate config flow."""
        self.code = None

    async def async_step_import(self, user_input=None):
        """Handle external yaml configuration."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason="already_setup")
        return await self.async_step_auth()

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason="already_setup")

        if DOMAIN not in self.hass.data:
            return self.async_abort(reason="missing_configuration")

        return await self.async_step_auth()

    async def async_step_auth(self, user_input=None):
        """Create an entry for auth."""
        # Flow has been triggered from Somfy website
        if user_input:
            return await self.async_step_code(user_input)

        try:
            with async_timeout.timeout(10):
                url, _ = await self._get_authorization_url()
        except asyncio.TimeoutError:
            return self.async_abort(reason="authorize_url_timeout")

        return self.async_external_step(step_id="auth", url=url)

    async def _get_authorization_url(self):
        """Get Somfy authorization url."""
        from pymfy.api.somfy_api import SomfyApi

        client_id = self.hass.data[DOMAIN][CLIENT_ID]
        client_secret = self.hass.data[DOMAIN][CLIENT_SECRET]
        redirect_uri = "{}{}".format(self.hass.config.api.base_url, AUTH_CALLBACK_PATH)
        api = SomfyApi(client_id, client_secret, redirect_uri)

        self.hass.http.register_view(SomfyAuthCallbackView())
        # Thanks to the state, we can forward the flow id to Somfy that will
        # add it in the callback.
        return await self.hass.async_add_executor_job(
            api.get_authorization_url, self.flow_id
        )

    async def async_step_code(self, code):
        """Received code for authentication."""
        self.code = code
        return self.async_external_step_done(next_step_id="creation")

    async def async_step_creation(self, user_input=None):
        """Create Somfy api and entries."""
        client_id = self.hass.data[DOMAIN][CLIENT_ID]
        client_secret = self.hass.data[DOMAIN][CLIENT_SECRET]
        code = self.code
        from pymfy.api.somfy_api import SomfyApi

        redirect_uri = "{}{}".format(self.hass.config.api.base_url, AUTH_CALLBACK_PATH)
        api = SomfyApi(client_id, client_secret, redirect_uri)
        token = await self.hass.async_add_executor_job(api.request_token, None, code)
        _LOGGER.info("Successfully authenticated Somfy")
        return self.async_create_entry(
            title="Somfy",
            data={
                "token": token,
                "refresh_args": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            },
        )


class SomfyAuthCallbackView(HomeAssistantView):
    """Somfy Authorization Callback View."""

    requires_auth = False
    url = AUTH_CALLBACK_PATH
    name = AUTH_CALLBACK_NAME

    @staticmethod
    async def get(request):
        """Receive authorization code."""
        from aiohttp import web_response

        if "code" not in request.query or "state" not in request.query:
            return web_response.Response(
                text="Missing code or state parameter in " + request.url
            )

        hass = request.app["hass"]
        hass.async_create_task(
            hass.config_entries.flow.async_configure(
                flow_id=request.query["state"], user_input=request.query["code"]
            )
        )

        return web_response.Response(
            headers={"content-type": "text/html"},
            text="<script>window.close()</script>",
        )
