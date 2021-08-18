"""Config flow for the LiteJet lighting system."""
from __future__ import annotations

import logging
from typing import Any

import pylitejet
from serial import SerialException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import CONF_DEFAULT_TRANSITION, DOMAIN

_LOGGER = logging.getLogger(__name__)


class LiteJetOptionsFlow(config_entries.OptionsFlow):
    """Handle LiteJet options."""

    def __init__(self, config_entry):
        """Initialize LiteJet options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Manage LiteJet options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_DEFAULT_TRANSITION,
                        default=self.config_entry.options.get(
                            CONF_DEFAULT_TRANSITION, 0
                        ),
                    ): cv.positive_int,
                }
            ),
        )


class LiteJetConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """LiteJet config flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Create a LiteJet config entry based upon user input."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors = {}
        if user_input is not None:
            port = user_input[CONF_PORT]

            await self.async_set_unique_id(port)
            self._abort_if_unique_id_configured()

            try:
                system = pylitejet.LiteJet(port)
                system.close()
            except SerialException:
                errors[CONF_PORT] = "open_failed"
            else:
                return self.async_create_entry(
                    title=port,
                    data={CONF_PORT: port},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_PORT): str}),
            errors=errors,
        )

    async def async_step_import(self, import_data):
        """Import litejet config from configuration.yaml."""
        return self.async_create_entry(title=import_data[CONF_PORT], data=import_data)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return LiteJetOptionsFlow(config_entry)
