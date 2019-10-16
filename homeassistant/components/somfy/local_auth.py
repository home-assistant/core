"""Local auth implementation for Somfy."""
from functools import partial
from typing import Optional, Any

from aiohttp import web_response
from pymfy.api.somfy_api import SomfyApi, AbstractSomfyApi

from homeassistant.core import HomeAssistant, callback
from homeassistant import config_entries
from homeassistant.components.http import HomeAssistantView

from .const import DOMAIN
from .config_flow import AbstractSomfyImplementation

AUTH_CALLBACK_PATH = "/auth/somfy/callback"


class LocalSomfyImplementation(AbstractSomfyImplementation):
    """Local auth implementation of Somfy."""

    def __init__(self, hass: HomeAssistant, client_id: str, client_secret: str):
        """Initialize local auth implementation."""
        self.hass = hass
        self.client_id = client_id
        self.client_secret = client_secret
        hass.http.register_view(SomfyAuthCallbackView(self))

    @property
    def name(self) -> str:
        """Name of the implementation."""
        return "Configuration.yaml"

    @property
    def domain(self) -> str:
        """Domain providing the implementation."""
        return DOMAIN

    async def async_generate_authorize_url(self, flow_id: str) -> str:
        """Generate a url for the user to authorize."""
        somfy_api = self._create_api()

        # Thanks to the state, we can forward the flow id to Somfy that will
        # add it in the callback.
        auth_url, _state = await self.hass.async_add_executor_job(
            somfy_api.get_authorization_url, flow_id
        )
        return auth_url

    async def async_resolve_external_data(self, data: Any) -> dict:
        """Resolve the authorization code to tokens."""
        somfy_api = self._create_api()
        return await self.hass.async_add_executor_job(
            somfy_api.request_token, None, data
        )

    def async_create_api_auth(
        self, config_entry: config_entries.ConfigEntry
    ) -> AbstractSomfyApi:
        """Create a Somfy API Auth object."""
        return self._create_api(config_entry)

    @callback
    def _create_api(
        self, config_entry: Optional[config_entries.ConfigEntry] = None
    ) -> SomfyApi:
        """Create a Somfy API Auth object."""

        def token_updated(tokens):
            """Handle updated tokens."""
            if config_entry is None:
                return

            self.hass.add_job(
                partial(
                    self.hass.config_entries.async_update_entry,
                    config_entry,
                    data={**config_entry.data, "token": tokens},
                )
            )

        if config_entry is None:
            tokens = {}
        else:
            tokens = config_entry.data["token"]

        return SomfyApi(
            self.client_id,
            self.client_secret,
            f"{self.hass.config.api.base_url}{AUTH_CALLBACK_PATH}",
            tokens,
            token_updated,
        )


class SomfyAuthCallbackView(HomeAssistantView):
    """Somfy Authorization Callback View."""

    requires_auth = False
    url = AUTH_CALLBACK_PATH
    name = "auth:somfy:callback"

    def __init__(self, local_auth: LocalSomfyImplementation):
        """Initialize authorize callback view."""
        self.local_auth = local_auth

    async def get(self, request):
        """Receive authorization code."""
        if "code" not in request.query or "state" not in request.query:
            return web_response.Response(
                text=f"Missing code or state parameter in {request.url}"
            )

        hass = request.app["hass"]

        await hass.config_entries.flow.async_configure(
            flow_id=request.query["state"], user_input=request.query["code"]
        )

        return web_response.Response(
            headers={"content-type": "text/html"},
            text="<script>window.close()</script>",
        )
