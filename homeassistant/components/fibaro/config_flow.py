"""Config flow to configure the AIS Drive Service component."""

import voluptuous as vol
import logging
from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_USERNAME, CONF_PASSWORD, CONF_URL
from homeassistant.core import callback
from homeassistant.components import ais_cloud
from fiblary3.client.v4.client import Client as FibaroClient


aisCloudWS = ais_cloud.AisCloudWS()

_LOGGER = logging.getLogger(__name__)
DRIVE_NAME_INPUT = None
DRIVE_TYPE_INPUT = None
DOMAIN = "fibaro"
CONF_OAUTH_JSON = ""


@callback
def configured_google_homes(hass):
    """Return a set of configured Google Homes instances."""
    return set(
        entry.data.get(CONF_NAME) for entry in hass.config_entries.async_entries(DOMAIN)
    )


@config_entries.HANDLERS.register(DOMAIN)
class DriveFlowHandler(config_entries.ConfigFlow):
    """Drive config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize zone configuration flow."""
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
            return await self.async_step_auth(user_input=None)
        return self.async_show_form(step_id="confirm", errors=errors)

    async def async_step_auth(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        description_placeholders = {"error_info": ""}
        data_schema = vol.Schema(
            {
                vol.Required(CONF_URL): str,
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        if user_input is not None and CONF_URL in user_input:
            # test the connection
            try:
                fibaro_client = FibaroClient(
                    user_input[CONF_URL],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
                login = fibaro_client.login.get()
                info = fibaro_client.info.get()
                _LOGGER.warning("Fibaro login: " + str(login))
                _LOGGER.warning("Fibaro info: " + str(info))
                _LOGGER.warning("Fibaro serialNumber: " + info.serialNumber)
                return self.async_create_entry(title="Fibaro Hub", data=user_input)
            except Exception as e:
                errors = {CONF_URL: "auth_error"}
                description_placeholders = {
                    "error_info": "Can not connect to Fibaro HC. Fibaro info: " + str(e)
                }

        return self.async_show_form(
            step_id="auth",
            errors=errors,
            description_placeholders=description_placeholders,
            data_schema=data_schema,
        )
