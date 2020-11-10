"""Config flow to configure the AIS Google Calendar Service component."""

import datetime
import json
import logging

import aiohttp
import yarl

from homeassistant import config_entries
from homeassistant.components import ais_cloud
from homeassistant.components.ais_dom import ais_global
from homeassistant.components.http import current_request
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.const import CONF_NAME
from homeassistant.core import callback

from . import CONF_TRACK_NEW, DOMAIN, TOKEN_FILE, async_do_setup

_LOGGER = logging.getLogger(__name__)
CONF_OAUTH_INFO = "oauth_info"
AUTH_CALLBACK_PATH = "/api/ais_calendar_service/authorize"
AUTH_CALLBACK_NAME = "ais_calendar_service:authorize"


@callback
def configured_google_calendar(hass):
    """Return a set of configured Google Calendar instances."""
    return {
        entry.data.get(CONF_NAME) for entry in hass.config_entries.async_entries(DOMAIN)
    }


class AuthorizationCallbackView(HomeAssistantView):
    requires_auth = False
    url = AUTH_CALLBACK_PATH
    name = AUTH_CALLBACK_NAME

    async def get(self, request):
        hass = request.app["hass"]
        flow_id = request.query["flow_id"]
        flow_id = flow_id.replace("google-calendar-", "")
        conf = {
            "client_id": "ASK_AIS_DOM",
            "client_secret": "ASK_AIS_DOM",
            CONF_TRACK_NEW: True,
        }
        # finish the integration
        await hass.config_entries.flow.async_configure(flow_id=flow_id, user_input=conf)
        return aiohttp.web_response.Response(
            headers={"content-type": "text/html"},
            text="<script>window.close()</script>Success! This window can be closed",
        )


class GoogleHomeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Drive config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize google home configuration flow."""
        pass

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        if user_input is not None:
            # register view
            self.hass.http.register_view(AuthorizationCallbackView)
            return self.async_show_form(
                step_id="oauth",
                errors=None,
                description_placeholders=None,
            )

        return self.async_show_form(step_id="confirm", errors=errors)

    async def async_step_oauth(self, user_input=None):
        request = current_request.get()
        url_host = yarl.URL(request.url).host

        """Handle flow external step."""
        ais_dom = ais_cloud.AisCloudWS(self.hass)
        json_ws_resp = ais_dom.key("google_calendar_web_client_id")
        client_id = json_ws_resp["key"]
        gate_id = ais_global.get_sercure_android_id_dom()
        auth_url = (
            "https://accounts.google.com/o/oauth2/auth/oauthchooseaccount?client_id="
            + client_id
            + "&redirect_uri=https://powiedz.co/ords/dom/auth/google_calendar_callback"
            + "&response_type=code&scope=https://www.googleapis.com/auth/calendar"
            + "&access_type=offline"
            + "&state="
            + gate_id
            + "ais0dom"
            + url_host
            + "ais0domgoogle-calendar-"
            + self.flow_id
        )
        return self.async_external_step(step_id="obtain_token", url=auth_url)

    async def async_step_obtain_token(self, user_input=None):
        """Obtain token after external auth completed."""
        # get token from cloud
        try:
            ais_dom = ais_cloud.AisCloudWS(self.hass)
            json_ws_resp = await ais_dom.async_key("google_calendar_user_token")
            calendar_token = json_ws_resp["key"]
            json_ws_resp = await ais_dom.async_key("google_calendar_web_client_id")
            client_id = json_ws_resp["key"]
            json_ws_resp = await ais_dom.async_key("google_calendar_web_secret")
            client_secret = json_ws_resp["key"]

            token_response = json.loads(calendar_token)
            json_token = json.loads(calendar_token)
            json_token["token_response"] = token_response
            json_token["_module"] = "oauth2client.client"
            json_token["_class"] = "OAuth2Credentials"
            json_token["client_id"] = client_id
            json_token["client_secret"] = client_secret
            delta = datetime.timedelta(seconds=token_response["expires_in"])
            now = datetime.datetime.utcnow()
            json_token["token_expiry"] = str(now + delta)
            json_token["token_uri"] = "https://www.googleapis.com/oauth2/v4/token"
            json_token["user_agent"] = None
            json_token["invalid"] = False

            with open(self.hass.config.path(TOKEN_FILE), "w") as json_file:
                json.dump(json_token, json_file)

        except Exception as e:
            return self.async_abort(
                reason="abort_by_error", description_placeholders={"error_info": str(e)}
            )

        return self.async_external_step_done(next_step_id="use_external_token")

    async def async_step_use_external_token(self, user_input=None):
        """Continue server validation with external token."""
        await async_do_setup(self.hass, self.hass.config.as_dict())

        self.hass.components.frontend.async_register_built_in_panel(
            "calendar", "calendar", "hass:calendar", update=True
        )
        conf = {
            "client_id": "ASK_AIS_DOM",
            "client_secret": "ASK_AIS_DOM",
            CONF_TRACK_NEW: True,
        }
        return self.async_create_entry(title="AIS Google Calendars", data=conf)
