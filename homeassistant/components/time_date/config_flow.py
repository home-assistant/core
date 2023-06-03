"""Adds config flow for Time & Date integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlow,
    OptionsFlowWithConfigEntry,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_DISPLAY_OPTIONS, DOMAIN, OPTION_TYPES

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DISPLAY_OPTIONS): SelectSelector(
            SelectSelectorConfig(
                options=[
                    SelectOptionDict(label=label, value=value)
                    for value, label in OPTION_TYPES.items()
                ],
                mode=SelectSelectorMode.DROPDOWN,
                multiple=True,
                translation_key="display_options",
            )
        ),
    }
)

_LOGGER = logging.getLogger(__name__)


class TimeDateConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Time & Date integration."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get option flow."""
        return TimeDateOptionsFlowHandler(config_entry)

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Import a configuration from config.yaml."""
        display_options = {
            CONF_DISPLAY_OPTIONS: config[CONF_DISPLAY_OPTIONS],
        }
        self._async_abort_entries_match(display_options)
        return await self.async_step_user(user_input=display_options)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user initial step."""
        errors: dict[str, str] = {}

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if self.hass.config.time_zone is None:
            errors["timezone_not_exist"] = "timezone_not_exist"
        elif user_input is not None:
            return self.async_create_entry(
                title="", data=user_input, options=user_input
            )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class TimeDateOptionsFlowHandler(OptionsFlowWithConfigEntry):
    """Handle option."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(DATA_SCHEMA, self.options),
        )
