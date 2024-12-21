"""Config flow for Automation Device Specification (ADS)."""

import pyads
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .hub import AdsHub

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
            # Check if device (AMS Net ID) is provided and valid
            if not user_input.get(CONF_DEVICE) or not self._is_valid_ams_net_id(
                user_input[CONF_DEVICE]
            ):
                errors[CONF_DEVICE] = (
                    "invalid_ams_net_id" if user_input.get(CONF_DEVICE) else "required"
                )

            # Check if port is in valid range
            if not (1 <= user_input.get(CONF_PORT, 0) <= 65535):
                errors[CONF_PORT] = (
                    "invalid_port" if user_input.get(CONF_PORT) else "required"
                )

            # Test the connection if no validation errors exist
            if not errors:
                # Create a temporary pyads connection client
                ads_client = pyads.Connection(
                    user_input[CONF_DEVICE],
                    user_input[CONF_PORT],
                    user_input.get(CONF_IP_ADDRESS),
                )
                hub = AdsHub(ads_client)

                mac_address = hub.get_mac_address()

                if mac_address is None:
                    raise ValueError("Failed to retrieve MAC address")

                # Check if this MAC address already exists in existing config entries
                for entry in self._async_current_entries():
                    if entry.data.get("mac_address") == mac_address:
                        errors["base"] = "duplicate_mac"
                        break
                # Test the connection
                await self.hass.async_add_executor_job(hub.test_connection)

            if not errors:
                # If validation passes, create entry
                return self.async_create_entry(
                    title=f"ADS Device ({mac_address})",
                    data={
                        CONF_DEVICE: user_input[CONF_DEVICE],
                        CONF_PORT: user_input[CONF_PORT],
                        CONF_IP_ADDRESS: user_input.get(CONF_IP_ADDRESS),
                        "mac_address": mac_address,
                    },
                )

        # Define the input schema with required fields for config flow form
        data_schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE, default=""): str,
                vol.Required(CONF_PORT, default=851): cv.port,
                vol.Optional(CONF_IP_ADDRESS, default=""): str,
            }
        )

        return self.async_show_form(
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
