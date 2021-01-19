"""Config flow to configure the AIS SUPLA MQTT component."""

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

from .const import API_ENDPOINT, AUTH_SCOPE, DOMAIN, OAUTH_URL, REDIRECT_URL, TOKEN_URL

_LOGGER = logging.getLogger(__name__)
AUTH_CALLBACK_PATH = "/api/ais_supla_mqtt/authorize"
AUTH_CALLBACK_NAME = "ais_supla_mqtt:authorize"


@callback
def configured_supla_mqtt(hass):
    """Return a set of configured SUPLA MQTT bridges."""
    return {
        entry.data.get(CONF_NAME) for entry in hass.config_entries.async_entries(DOMAIN)
    }


class AuthorizationCallbackView(HomeAssistantView):
    requires_auth = False
    url = AUTH_CALLBACK_PATH
    name = AUTH_CALLBACK_NAME

    async def get(self, request):
        hass = request.app["hass"]
        flow_id = request.query["flow_id"].replace("supla-mqtt-", "")
        await hass.config_entries.flow.async_configure(flow_id=flow_id, user_input={})
        return aiohttp.web_response.Response(
            headers={"content-type": "text/html"},
            text="<script>window.close()</script>Success! This window can be closed",
        )


class SuplaMqttFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """SUPLA MQTT config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize supla mqtt configuration flow."""
        self.client_id = None
        self.bridge_config = {}
        self.bridge_config_answer_status = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return await self.async_step_oauth(user_input)

    async def async_step_oauth(self, user_input=None):

        if user_input is not None:
            self.hass.http.register_view(AuthorizationCallbackView)
            request = current_request.get()
            url_host = yarl.URL(request.url).host

            """Handle flow external step."""
            ais_dom = ais_cloud.AisCloudWS(self.hass)
            json_ws_resp = ais_dom.key("supla_mqtt_client_id")
            self.client_id = json_ws_resp["key"]
            gate_id = ais_global.get_sercure_android_id_dom()
            auth_url = (
                f"{OAUTH_URL}?client_id={self.client_id}&redirect_uri={REDIRECT_URL}&scope={AUTH_SCOPE}&response_type"
                f"=code&state={gate_id}ais0dom{url_host}ais0domsupla-mqtt-{self.flow_id}"
            )
            return self.async_external_step(step_id="obtain_token", url=auth_url)
        return self.async_show_form(step_id="oauth")

    async def async_step_obtain_token(self, user_input=None):
        """Obtain token after external auth completed."""
        # get token to call SUPLA API
        ais_dom = ais_cloud.AisCloudWS(self.hass)
        json_ws_resp = await ais_dom.async_key("supla_mqtt_bridge_code")
        code = json_ws_resp["key"]
        json_ws_resp = await ais_dom.async_key("supla_mqtt_secret")
        client_secret = json_ws_resp["key"]
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URL,
            "code": code,
        }

        web_session = self.hass.helpers.aiohttp_client.async_get_clientsession()
        token_response = await web_session.post(TOKEN_URL, json=data)
        result = await token_response.json()

        # get mqtt connection info from cloud
        access_token = result["access_token"]
        target_url = result["target_url"]
        bearer_token = f"Bearer {access_token}"
        supla_mqtt_settings_response = await web_session.post(
            f"{target_url}{API_ENDPOINT}",
            headers={"Authorization": bearer_token},
        )
        self.bridge_config_answer_status = supla_mqtt_settings_response.status
        self.bridge_config = await supla_mqtt_settings_response.json()
        return self.async_external_step_done(next_step_id="use_bridge_settings")

    async def async_step_use_bridge_settings(self, user_input=None):
        """Continue broker configuration with external token."""
        if "host" not in self.bridge_config:
            return self.async_abort(
                reason="abort_by_error",
                description_placeholders={
                    "error_info": f"Error code: {self.bridge_config_answer_status}. Response: {self.bridge_config}"
                },
            )
        return self.async_create_entry(
            title="SUPLA MQTT BRIDGE", data=self.bridge_config
        )
