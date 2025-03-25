import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_SCAN_INTERVAL
import ipaddress

_LOGGER = logging.getLogger(__name__)

class TheSilentWaveConfigFlow(config_entries.ConfigFlow, domain="thesilentwave"):
    """Handle a config flow for TheSilentWave integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the user input for the configuration."""
        errors = {}
        
        if user_input is not None:
            try:
                # Validate IP address
                ipaddress.ip_address(user_input[CONF_HOST])
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL, 10)
                    }
                )
            except ValueError:
                errors[CONF_HOST] = "invalid_ip"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_NAME, default="TheSilentWaveSensor"): str,
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_SCAN_INTERVAL, default=10): vol.All(
                    vol.Coerce(int), vol.Range(min=5, max=300)
                ),
            }),
            errors=errors
        )
