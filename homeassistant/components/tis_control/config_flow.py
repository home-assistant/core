"""Config flow for TIS Control integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PORT
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class TISConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TIS Control."""

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            unique_id = f"tis_control:{user_input[CONF_PORT]}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            _LOGGER.info("Received user input %s", user_input)

            return self.async_create_entry(title="TIS Control Bridge", data=user_input)

        # If user_input is None (initial step), show the setup form
        return self._show_setup_form(errors=errors)

    @callback
    def _show_setup_form(self, errors=None) -> ConfigFlowResult:
        """Show the setup form to the user."""

        schema = vol.Schema(
            {vol.Required(CONF_PORT, default=6000): cv.port},
            required=True,
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors if errors else {},
        )
