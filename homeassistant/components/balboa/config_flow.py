"""Config flow for Balboa Spa Client integration."""
from __future__ import annotations

import asyncio
from typing import Any

from pybalboa import BalboaSpaWifi
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.device_registry import format_mac

from .const import _LOGGER, CONF_SYNC_TIME, DOMAIN

DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


async def validate_input(data: dict[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect."""
    _LOGGER.debug("Attempting to connect to %s", data[CONF_HOST])
    spa = BalboaSpaWifi(data[CONF_HOST])
    connected = await spa.connect()
    _LOGGER.debug("Got connected = %d", connected)
    if not connected:
        raise CannotConnect

    task = asyncio.create_task(spa.listen())
    await spa.spa_configured()

    mac_addr = format_mac(spa.get_macaddr())
    model = spa.get_model_name()
    task.cancel()
    await spa.disconnect()

    return {"title": model, "formatted_mac": mac_addr}


class BalboaSpaClientFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Balboa Spa Client config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return BalboaSpaClientOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            try:
                info = await validate_input(user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["formatted_mac"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class BalboaSpaClientOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Balboa Spa Client options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize Balboa Spa Client options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage Balboa Spa Client options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SYNC_TIME,
                        default=self.config_entry.options.get(CONF_SYNC_TIME, False),
                    ): bool,
                }
            ),
        )
