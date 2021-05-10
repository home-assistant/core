"""Config flow for Minut Point."""
import asyncio
from collections import OrderedDict
import logging

import async_timeout
from pypoint import PointSession
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import callback

from .const import DOMAIN

AUTH_CALLBACK_PATH = "/api/minut"
AUTH_CALLBACK_NAME = "api:minut"

DATA_FLOW_IMPL = "point_flow_implementation"

_LOGGER = logging.getLogger(__name__)


@callback
def register_flow_implementation(hass, domain, client_id, client_secret):
    """Register a flow implementation.

    domain: Domain of the component responsible for the implementation.
    name: Name of the component.
    client_id: Client id.
    client_secret: Client secret.
    """
    if DATA_FLOW_IMPL not in hass.data:
        hass.data[DATA_FLOW_IMPL] = OrderedDict()

    hass.data[DATA_FLOW_IMPL][domain] = {
        CONF_CLIENT_ID: client_id,
        CONF_CLIENT_SECRET: client_secret,
    }


class PointFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize flow."""
        self.flow_impl = None

    async def async_step_import(self, user_input=None):
        """Handle external yaml configuration."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason="already_setup")

        self.flow_impl = DOMAIN

        return await self.async_step_auth()

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        flows = self.hass.data.get(DATA_FLOW_IMPL, {})

        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason="already_setup")

        if not flows:
            _LOGGER.debug("no flows")
            return self.async_abort(reason="no_flows")

        if len(flows) == 1:
            self.flow_impl = list(flows)[0]
            return await self.async_step_auth()

        if user_input is not None:
            self.flow_impl = user_input["flow_impl"]
            return await self.async_step_auth()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("flow_impl"): vol.In(list(flows))}),
        )

    async def async_step_auth(self, user_input=None):
        """Create an entry for auth."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason="external_setup")

        errors = {}

        if user_input is not None:
            errors["base"] = "follow_link"

        try:
            with async_timeout.timeout(10):
                url = await self._get_authorization_url()
        except asyncio.TimeoutError:
            return self.async_abort(reason="authorize_url_timeout")
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected error generating auth url")
            return self.async_abort(reason="unknown_authorize_url_generation")
        return self.async_show_form(
            step_id="auth",
            description_placeholders={"authorization_url": url},
            errors=errors,
        )

    async def _get_authorization_url(self):
        """Create Minut Point session and get authorization url."""
        flow = self.hass.data[DATA_FLOW_IMPL][self.flow_impl]
        client_id = flow[CONF_CLIENT_ID]
        client_secret = flow[CONF_CLIENT_SECRET]
        point_session = PointSession(
            self.hass.helpers.aiohttp_client.async_get_clientsession(),
            client_id,
            client_secret,
        )

        self.hass.http.register_view(MinutAuthCallbackView())

        return point_session.get_authorization_url

    async def async_step_code(self, code=None):
        """Received code for authentication."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason="already_setup")

        if code is None:
            return self.async_abort(reason="no_code")

        _LOGGER.debug(
            "Should close all flows below %s",
            self.hass.config_entries.flow.async_progress(),
        )
        # Remove notification if no other discovery config entries in progress

        return await self._async_create_session(code)

    async def _async_create_session(self, code):
        """Create point session and entries."""

        flow = self.hass.data[DATA_FLOW_IMPL][DOMAIN]
        client_id = flow[CONF_CLIENT_ID]
        client_secret = flow[CONF_CLIENT_SECRET]
        point_session = PointSession(
            self.hass.helpers.aiohttp_client.async_get_clientsession(),
            client_id,
            client_secret,
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
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": "code"}, data=request.query["code"]
                )
            )
        return "OK!"
