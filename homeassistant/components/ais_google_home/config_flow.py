"""Config flow to configure the AIS Drive Service component."""

import json
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ais_cloud
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_NAME
from homeassistant.core import callback

from .const import CONF_OAUTH_JSON, DOMAIN

aisCloudWS = None

_LOGGER = logging.getLogger(__name__)
DRIVE_NAME_INPUT = None
DRIVE_TYPE_INPUT = None
AUTH_URL = None


@callback
def configured_google_homes(hass):
    """Return a set of configured Google Homes instances."""
    return {
        entry.data.get(CONF_NAME) for entry in hass.config_entries.async_entries(DOMAIN)
    }


@config_entries.HANDLERS.register(DOMAIN)
class DriveFlowHandler(config_entries.ConfigFlow):
    """Drive config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize google home configuration flow."""
        global aisCloudWS
        aisCloudWS = ais_cloud.AisCloudWS(self.hass)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        if user_input is not None:
            return await self.async_step_oauth(user_input=None)
        return self.async_show_form(step_id="confirm", errors=errors)

    async def async_step_oauth(self, user_input=None):
        """Handle a flow start."""
        global AUTH_URL
        errors = {}
        description_placeholders = {"error_info": ""}
        data_schema = vol.Schema({vol.Required(CONF_OAUTH_JSON): str})
        if user_input is not None:
            json_from_user = user_input.get(CONF_OAUTH_JSON)
            oauth_json = {}
            try:
                oauth_json = json.loads(json_from_user)
            except ValueError as e:
                errors = {CONF_OAUTH_JSON: "oauth_error"}
                description_placeholders = {"error_info": str(e)}

            if errors == {}:
                try:
                    ws_ret = aisCloudWS.gh_ais_add_device(oauth_json)
                    response = ws_ret.json()
                    AUTH_URL = response["message"]
                except Exception as e:
                    errors = {CONF_OAUTH_JSON: "oauth_error"}
                    description_placeholders = {"error_info": str(e)}

            if errors == {}:
                return await self.async_step_token(user_input=None)

        return self.async_show_form(
            step_id="oauth",
            errors=errors,
            data_schema=data_schema,
            description_placeholders=description_placeholders,
        )

    async def async_step_token(self, user_input=None):
        """Handle a flow start."""
        global AUTH_URL
        description_placeholders = {"error_info": "", "auth_url": AUTH_URL}
        errors = {}
        data_schema = vol.Schema({vol.Required(CONF_ACCESS_TOKEN): str})
        if user_input is not None and CONF_ACCESS_TOKEN in user_input:
            # save token
            ws_ret = aisCloudWS.gh_ais_add_token(user_input[CONF_ACCESS_TOKEN])
            try:
                response = ws_ret.json()
                ret = response["message"]
                return self.async_create_entry(title="Google Home", data=user_input)
            except Exception as e:
                errors = {CONF_ACCESS_TOKEN: "token_error"}
                description_placeholders = {"auth_url": AUTH_URL, "error_info": str(e)}

        return self.async_show_form(
            step_id="token",
            errors=errors,
            description_placeholders=description_placeholders,
            data_schema=data_schema,
        )
