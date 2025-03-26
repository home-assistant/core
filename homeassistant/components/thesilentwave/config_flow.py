"""Config flow for TheSilentWave integration."""

import ipaddress
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class TheSilentWaveConfigFlow(config_entries.ConfigFlow, domain="thesilentwave"):
    """Handle a config flow for TheSilentWave integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:  # Updated return type to ConfigFlowResult
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
                        CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL, 10),
                    },
                )

            except ValueError:
                _LOGGER.warning("Invalid IP address entered: %s", user_input[CONF_HOST])
                errors[CONF_HOST] = "invalid_ip"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default="TheSilentWave"): str,
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_SCAN_INTERVAL, default=10): vol.All(
                        vol.Coerce(int), vol.Range(min=5, max=300)
                    ),
                }
            ),
            errors=errors,
        )
