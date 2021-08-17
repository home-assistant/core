"""Config flow for P1 Monitor integration."""
from __future__ import annotations

from typing import Any

from p1monitor import P1Monitor, P1MonitorError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_TIME_BETWEEN_UPDATE, DEFAULT_TIME_BETWEEN_UPDATE, DOMAIN


class P1MonitorFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for P1 Monitor."""

    VERSION = 1

    entry: ConfigEntry | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> P1MonitorOptionFlowHandler:
        """Get the options flow for this handler."""
        return P1MonitorOptionFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""

        errors = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            try:
                client = P1Monitor(host=user_input[CONF_HOST], session=session)
                await client.smartmeter()
            except P1MonitorError:
                errors["base"] = "cannot_connect"
                await client.close()
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_NAME, default=self.hass.config.location_name
                    ): str,
                    vol.Required(CONF_HOST): str,
                }
            ),
            errors=errors,
        )


class P1MonitorOptionFlowHandler(OptionsFlow):
    """Handle options."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.entry = entry

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
                    vol.Optional(
                        CONF_TIME_BETWEEN_UPDATE,
                        default=self.entry.options.get(
                            CONF_TIME_BETWEEN_UPDATE, DEFAULT_TIME_BETWEEN_UPDATE
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=5)),
                }
            ),
        )
