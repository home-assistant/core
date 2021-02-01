"""Config flow to configure the AIS MQTT SOFT BRIDGE component."""

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ais_cloud
from homeassistant.const import CONF_NAME
from homeassistant.core import callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@callback
def configured_ais_mqtt(hass):
    """Return a set of configured AIS MQTT bridges."""
    return {
        entry.data.get(CONF_NAME) for entry in hass.config_entries.async_entries(DOMAIN)
    }


class AisMqttFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """AIS MQTT config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize ais mqtt configuration flow."""

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return await self.async_step_info(user_input)

    async def async_step_info(self, user_input=None):
        if user_input is not None:
            return self.async_show_form(
                step_id="authentication",
                data_schema=vol.Schema(
                    {vol.Required("username"): str, vol.Required("password"): str}
                ),
            )
        return self.async_show_form(step_id="info")

    async def async_step_authentication(self, user_input=None):
        """authentication"""
        if user_input is not None:
            ais_cloud_ws = ais_cloud.AisCloudWS(self.hass)
            broker_config = await ais_cloud_ws.async_get_mqtt_settings(
                user_input["username"], user_input["password"]
            )
            if "server" not in broker_config:
                error = "error"
                if "error" in broker_config:
                    error = broker_config["error"]
                return self.async_abort(
                    reason="abort_by_error",
                    description_placeholders={"error_info": f"Exception: {error}."},
                )
            """Continue bridge configuration with broker settings."""
            return self.async_create_entry(title="AIS MQTT Bridge", data=broker_config)
        return self.async_show_form(step_id="authentication")
