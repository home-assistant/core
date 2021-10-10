"""Config flow for Solcast Solar integration."""
from __future__ import annotations

import datetime
import json
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_APIKEY, CONF_POLL_INTERVAL, CONF_ROOFTOP, DOMAIN


class SolcastSolarFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solcast Solar."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SolcastSolarOptionFlowHandler:
        """Get the options flow for this handler."""
        return SolcastSolarOptionFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={
                    "apiremaining": 50,
                    "data": json.dumps(dict({"forecasts": []})),
                    "last_update": int(
                        datetime.date(1980, 4, 13).strftime("%Y%m%d%H%M%S")
                    ),
                },
                options={
                    CONF_APIKEY: user_input[CONF_APIKEY],
                    CONF_ROOFTOP: user_input[CONF_ROOFTOP],
                    CONF_POLL_INTERVAL: user_input[CONF_POLL_INTERVAL],
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=self.hass.config.location_name
                    ): str,
                    vol.Required(CONF_APIKEY, default=""): str,
                    vol.Required(CONF_ROOFTOP, default=""): str,
                    vol.Required(CONF_POLL_INTERVAL, default=1): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=6)
                    ),
                }
            ),
        )


class SolcastSolarOptionFlowHandler(OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_APIKEY,
                        default=self.config_entry.options.get(CONF_APIKEY),
                    ): str,
                    vol.Required(
                        CONF_ROOFTOP,
                        default=self.config_entry.options.get(CONF_ROOFTOP),
                    ): str,
                    vol.Required(
                        CONF_POLL_INTERVAL,
                        default=self.config_entry.options[CONF_POLL_INTERVAL],
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=6)),
                }
            ),
        )
