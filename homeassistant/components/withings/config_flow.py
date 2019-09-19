"""Config flow for Withings."""
from collections import OrderedDict
import logging
from typing import Optional

import aiohttp
import nokia
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback

from . import const

DATA_FLOW_IMPL = "withings_flow_implementation"

_LOGGER = logging.getLogger(__name__)


@callback
def register_flow_implementation(hass, client_id, client_secret, base_url, profiles):
    """Register a flow implementation.

    hass: Home assistant object.
    client_id: Client id.
    client_secret: Client secret.
    base_url: Base url of home assistant instance.
    profiles: The profiles to work with.
    """
    if DATA_FLOW_IMPL not in hass.data:
        hass.data[DATA_FLOW_IMPL] = OrderedDict()

    hass.data[DATA_FLOW_IMPL] = {
        const.CLIENT_ID: client_id,
        const.CLIENT_SECRET: client_secret,
        const.BASE_URL: base_url,
        const.PROFILES: profiles,
    }


@config_entries.HANDLERS.register(const.DOMAIN)
class WithingsFlowHandler(config_entries.ConfigFlow):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize flow."""
        self.flow_profile = None
        self.data = None

    def async_profile_config_entry(self, profile: str) -> Optional[ConfigEntry]:
        """Get a profile config entry."""
        entries = self.hass.config_entries.async_entries(const.DOMAIN)
        for entry in entries:
            if entry.data.get(const.PROFILE) == profile:
                return entry

        return None

    def get_auth_client(self, profile: str):
        """Get a new auth client."""
        flow = self.hass.data[DATA_FLOW_IMPL]
        client_id = flow[const.CLIENT_ID]
        client_secret = flow[const.CLIENT_SECRET]
        base_url = flow[const.BASE_URL].rstrip("/")

        callback_uri = "{}/{}?flow_id={}&profile={}".format(
            base_url.rstrip("/"),
            const.AUTH_CALLBACK_PATH.lstrip("/"),
            self.flow_id,
            profile,
        )

        return nokia.NokiaAuth(
            client_id,
            client_secret,
            callback_uri,
            scope=",".join(["user.info", "user.metrics", "user.activity"]),
        )

    async def async_step_import(self, user_input=None):
        """Create user step."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Create an entry for selecting a profile."""
        flow = self.hass.data.get(DATA_FLOW_IMPL)

        if not flow:
            return self.async_abort(reason="no_flows")

        if user_input:
            return await self.async_step_auth(user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(const.PROFILE): vol.In(flow.get(const.PROFILES))}
            ),
        )

    async def async_step_auth(self, user_input=None):
        """Create an entry for auth."""
        if user_input.get(const.CODE):
            self.data = user_input
            return self.async_external_step_done(next_step_id="finish")

        profile = user_input.get(const.PROFILE)

        auth_client = self.get_auth_client(profile)

        url = auth_client.get_authorize_url()

        return self.async_external_step(step_id="auth", url=url)

    async def async_step_finish(self, user_input=None):
        """Received code for authentication."""
        data = user_input or self.data or {}

        _LOGGER.debug(
            "Should close all flows below %s",
            self.hass.config_entries.flow.async_progress(),
        )

        profile = data[const.PROFILE]
        code = data[const.CODE]

        return await self._async_create_session(profile, code)

    async def _async_create_session(self, profile, code):
        """Create withings session and entries."""
        auth_client = self.get_auth_client(profile)

        _LOGGER.debug("Requesting credentials with code: %s.", code)
        credentials = auth_client.get_credentials(code)

        return self.async_create_entry(
            title=profile,
            data={const.PROFILE: profile, const.CREDENTIALS: credentials.__dict__},
        )


class WithingsAuthCallbackView(HomeAssistantView):
    """Withings Authorization Callback View."""

    requires_auth = False
    url = const.AUTH_CALLBACK_PATH
    name = const.AUTH_CALLBACK_NAME

    def __init__(self):
        """Constructor."""

    async def get(self, request):
        """Receive authorization code."""
        hass = request.app["hass"]

        code = request.query.get("code")
        profile = request.query.get("profile")
        flow_id = request.query.get("flow_id")

        if not flow_id:
            return aiohttp.web_response.Response(
                status=400, text="'flow_id' argument not provided in url."
            )

        if not profile:
            return aiohttp.web_response.Response(
                status=400, text="'profile' argument not provided in url."
            )

        if not code:
            return aiohttp.web_response.Response(
                status=400, text="'code' argument not provided in url."
            )

        try:
            await hass.config_entries.flow.async_configure(
                flow_id, {const.PROFILE: profile, const.CODE: code}
            )

            return aiohttp.web_response.Response(
                status=200,
                headers={"content-type": "text/html"},
                text="<script>window.close()</script>",
            )

        except data_entry_flow.UnknownFlow:
            return aiohttp.web_response.Response(status=400, text="Unknown flow")
