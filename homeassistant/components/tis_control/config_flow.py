"""Config flow for TISControl integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PORT
from homeassistant.core import callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_PORT): int}, required=True)


class TISConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TISControl."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is not None:
            logging.debug("recieved user input %s", user_input)
            # Assuming a function `validate_port` that returns True if the port is valid
            is_valid = await self.validate_port(user_input[CONF_PORT])
            if not is_valid:
                errors["base"] = "invalid_port"  # Custom error key
                logging.error("Provided port is invalid: %s", user_input[CONF_PORT])

            if not errors:
                return self.async_create_entry(
                    title="TIS Control Bridge", data=user_input
                )
            else:  # noqa: RET505
                # If there are errors, show the form again with the error message
                logging.warning("Errors occurred: %s", errors)
                return self._show_setup_form(errors)

        # If user_input is None (initial step), show the setup form
        return self._show_setup_form(errors)

    @callback
    def _show_setup_form(self, errors=None) -> ConfigFlowResult:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors if errors else {},
            description_placeholders={CONF_PORT: "Port"},
        )

    async def validate_port(self, port: int) -> bool:
        """Validate the port."""
        if isinstance(port, int):
            if 1 <= port <= 65535:
                return True
        return False
