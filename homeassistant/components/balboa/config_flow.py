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
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)

from .const import _LOGGER, CONF_SYNC_TIME, DOMAIN

DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SYNC_TIME, default=False): bool,
    }
)
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA),
}


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
    ) -> SchemaOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)

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
