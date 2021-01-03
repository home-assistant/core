"""Config flow to configure AI-Speaker."""
import logging

from aisapi.ws import AisWebService
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
AIS_CONFIG = {
    vol.Required(CONF_HOST): str,
}


class AisConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a AI-Speaker config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH
    DOMAIN = DOMAIN

    async def async_step_user(self, user_input=None):
        """Commissioning the configuration by the user."""
        return self.async_show_form(step_id="confirm")

    async def async_step_confirm(self, user_input=None):
        """User confirmation step."""
        if user_input is not None:
            return self.async_show_form(
                step_id="settings", data_schema=vol.Schema(AIS_CONFIG)
            )

        return self.async_show_form(step_id="confirm")

    async def async_step_settings(self, user_input=None):
        """Step of the connection settings."""
        if user_input is not None:
            web_session = aiohttp_client.async_get_clientsession(self.hass)
            ais_host = user_input["host"]
            ais_gate = AisWebService(self.hass.loop, web_session, ais_host)
            ais_gate_info = await ais_gate.get_gate_info()
            ais_id = ais_gate_info.get("ais_id")
            if ais_id is None:
                errors = {CONF_HOST: "discovery_error"}
                return self.async_show_form(
                    step_id="settings",
                    data_schema=vol.Schema(AIS_CONFIG),
                    errors=errors,
                )

            # check if this ais id is already configured
            await self.async_set_unique_id(ais_id)
            self._abort_if_unique_id_configured()

            # Complete and save configuration
            user_input["ais_info"] = ais_gate_info
            return self.async_create_entry(
                title="AI-Speaker " + ais_gate_info.get("Product"), data=user_input
            )

        return self.async_show_form(step_id="settings")
