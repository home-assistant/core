"""Config flow for Minut Point."""
import asyncio
from collections import OrderedDict
import logging

from aiohttp import web_response
from pypoint import MINUT_AUTH_URL, PointSession

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_REDIRECT_URI, DOMAIN

AUTH_CALLBACK_PATH = "/api/minut"
AUTH_CALLBACK_NAME = "api:minut"

DATA_FLOW_IMPL = "point_flow_implementation"

_LOGGER = logging.getLogger(__name__)


@callback
def register_flow_implementation(hass, domain, client_id, client_secret, redirect_uri):
    """Register a flow implementation.

    domain: Domain of the component responsible for the implementation.
    name: Name of the component.
    client_id: Client id.
    client_secret: Client secret.
    redirect_uri: Redirect_uri.
    """
    if DATA_FLOW_IMPL not in hass.data:
        hass.data[DATA_FLOW_IMPL] = OrderedDict()

    hass.data[DATA_FLOW_IMPL][domain] = {
        CONF_CLIENT_ID: client_id,
        CONF_CLIENT_SECRET: client_secret,
        CONF_REDIRECT_URI: redirect_uri,
    }


class PointFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    code: str | None = None

    def __init__(self) -> None:
        """Initialize flow."""
        self.flow_impl = None

    async def async_step_import(self, user_input=None):
        """Handle external yaml configuration."""
        if self._async_current_entries():
            return self.async_abort(reason="already_setup")

        self.flow_impl = DOMAIN

        return await self.async_step_auth()

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        flows = self.hass.data.get(DATA_FLOW_IMPL, {})

        if self._async_current_entries():
            return self.async_abort(reason="already_setup")

        if not flows:
            _LOGGER.debug("no flows")
            return self.async_abort(reason="no_flows")

        self.flow_impl = list(flows)[0]
        return await self.async_step_auth()

    async def async_step_auth(self, user_input=None):
        """Create an entry for auth."""
        if self._async_current_entries():
            return self.async_abort(reason="external_setup")

        if user_input is not None:
            self.code = user_input
            return self.async_external_step_done(next_step_id="finish")
        try:
            async with asyncio.timeout(10):
                url = await self._get_authorization_url()
        except asyncio.TimeoutError:
            return self.async_abort(reason="authorize_url_timeout")
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected error generating auth url")
            return self.async_abort(reason="unknown_authorize_url_generation")
        return self.async_external_step(
            step_id="auth",
            url=url,
        )

    async def _get_authorization_url(self):
        """Create Minut Point session and get authorization url."""
        flow = self.hass.data[DATA_FLOW_IMPL][self.flow_impl]
        client_id = flow[CONF_CLIENT_ID]
        client_secret = flow[CONF_CLIENT_SECRET]
        redirect_uri = flow[CONF_REDIRECT_URI]
        point_session = PointSession(
            async_get_clientsession(self.hass),
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )

        self.hass.http.register_view(MinutAuthCallbackView())
        return point_session.create_authorization_url(
            MINUT_AUTH_URL, state=self.flow_id
        )[0]

    async def async_step_finish(self, user_input=None):
        """Received code for authentication."""
        code = self.code
        if self._async_current_entries():
            return self.async_abort(reason="already_setup")
        if code is None:
            return self.async_abort(reason="no_code")
        return await self._async_create_session(code)

    async def _async_create_session(self, code):
        """Create point session and entries."""

        flow = self.hass.data[DATA_FLOW_IMPL][self.flow_impl]
        client_id = flow[CONF_CLIENT_ID]
        client_secret = flow[CONF_CLIENT_SECRET]
        redirect_uri = flow[CONF_REDIRECT_URI]
        point_session = PointSession(
            async_get_clientsession(self.hass),
            client_id,
            client_secret,
            redirect_uri=redirect_uri,
        )
        token = await point_session.get_access_token(code)
        _LOGGER.debug("Got new token")
        if not point_session.is_authorized:
            _LOGGER.error("Authentication Error")
            return self.async_abort(reason="auth_error")

        _LOGGER.info("Successfully authenticated Point")
        user_email = (await point_session.user()).get("email") or ""

        return self.async_create_entry(
            title=user_email,
            data={
                "token": token,
                "refresh_args": {
                    CONF_CLIENT_ID: client_id,
                    CONF_CLIENT_SECRET: client_secret,
                },
            },
        )


class MinutAuthCallbackView(HomeAssistantView):
    """Minut Authorization Callback View."""

    requires_auth = False
    url = AUTH_CALLBACK_PATH
    name = AUTH_CALLBACK_NAME

    @staticmethod
    async def get(request):
        """Receive authorization code."""
        hass = request.app["hass"]
        if "code" in request.query:
            result = await hass.config_entries.flow.async_configure(
                flow_id=request.query["state"], user_input=request.query["code"]
            )
            if result["type"] == data_entry_flow.FlowResultType.EXTERNAL_STEP_DONE:
                return web_response.Response(
                    headers={"content-type": "text/html"},
                    text="<script>window.close()</script>Success! This window can be closed",
                )
        return "Error authenticating Minut Point."
