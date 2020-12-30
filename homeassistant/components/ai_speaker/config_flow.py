"""Config flow to configure AI-Speaker."""
import logging

import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.helpers import aiohttp_client

_LOGGER = logging.getLogger(__name__)
AIS_CONFIG = {
    vol.Required(CONF_HOST): str,
}


class AisConfigFlow(config_entries.ConfigFlow, domain="ai_speaker"):
    """Handle a AI-Speaker config flow."""

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
            # check the connection
            web_session = aiohttp_client.async_get_clientsession(self.hass)
            url = user_input["host"]
            if not url.startswith("http"):
                url = "http://" + url
            if not url.endswith(":8122"):
                url = url + ":8122"
            try:
                with async_timeout.timeout(3):
                    ws_resp = await web_session.get(url)
                    json_info = await ws_resp.json()
                    gate_id = json_info["gate_id"]
                    # Complete and save configuration
                    user_input["ais_url"] = url
                    user_input["ais_info"] = json_info
                    return self.async_create_entry(
                        title="AI-Speaker connection " + gate_id, data=user_input
                    )

            except Exception as e:
                _LOGGER.error("AI-Speaker connection error: " + str(e))
                errors = {CONF_HOST: "discovery_error"}
                return self.async_show_form(
                    step_id="settings",
                    data_schema=vol.Schema(AIS_CONFIG),
                    data=user_input,
                    errors=errors,
                )
        return self.async_show_form(step_id="settings")
