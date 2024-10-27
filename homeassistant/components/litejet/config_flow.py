"""Config flow for the LiteJet lighting system."""

from __future__ import annotations

from typing import Any

import pylitejet
from serial import SerialException
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PORT
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import CONF_DEFAULT_TRANSITION, DOMAIN


class LiteJetOptionsFlow(OptionsFlow):
    """Handle LiteJet options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize LiteJet options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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


class LiteJetConfigFlow(ConfigFlow, domain=DOMAIN):
    """LiteJet config flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create a LiteJet config entry based upon user input."""
        errors = {}
        if user_input is not None:
            port = user_input[CONF_PORT]

            try:
                system = await pylitejet.open(port)
            except SerialException:
                errors[CONF_PORT] = "open_failed"
            else:
                await system.close()
                return self.async_create_entry(
                    title=port,
                    data={CONF_PORT: port},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_PORT): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> LiteJetOptionsFlow:
        """Get the options flow for this handler."""
        return LiteJetOptionsFlow(config_entry)
