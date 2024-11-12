"""Config flow for Automation Device Specification (ADS)."""

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

# Define configuration keys
CONF_DEVICE = "device"
CONF_PORT = "port"
CONF_IP_ADDRESS = "ip_address"


class ADSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ADS."""

    VERSION = 0
    MINOR_VERSION = 1

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Check if AMS NetID is in correct format
            if not self._is_valid_ams_net_id(user_input["device"]):
                errors["device"] = "invalid_ams_net_id"

            if not errors:
                # If validation passes, create entry
                return self.async_create_entry(title="ADS", data=user_input)

        # Define the input schema with required fields for config flow form
        data_schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE, default=""): str,
                vol.Required(CONF_PORT, default=851): cv.port,
                vol.Optional(CONF_IP_ADDRESS, default=""): str,
            }
        )

        # Show the form with schema and errors (if any)
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    def _is_valid_ams_net_id(self, net_id):
        """Check if AMS net ID is in correct format (like '192.168.10.120.1.1'), with all parts between 0 and 255."""
        parts = net_id.split(".")

        if len(parts) != 6:
            return False

        try:
            return all(0 <= int(part) <= 255 for part in parts)
        except ValueError:
            return False
