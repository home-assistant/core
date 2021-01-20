"""Config flow to configure the AIS MQTT SOFT BRIDGE component."""

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ais_cloud
from homeassistant.components.ais_dom import ais_global
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
        self.client_id = None
        self.bridge_config = {}
        self.bridge_config_answer_status = None

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
            # logowanie do serwisu
            _LOGGER.info("User input: " + str(user_input))
            # Zakończenie i zapis konfiguracji
            return self.async_external_step_done(next_step_id="use_bridge_settings")
        return self.async_show_form(step_id="authentication")

    async def async_step_use_bridge_settings(self, user_input=None):
        """Continue broker configuration with external token."""
        if "host" not in self.bridge_config:
            return self.async_abort(
                reason="abort_by_error",
                description_placeholders={
                    "error_info": f"Error code: {self.bridge_config_answer_status}. Response: {self.bridge_config}"
                },
            )
        return self.async_create_entry(title="AIS MQTT BRIDGE", data=self.bridge_config)
