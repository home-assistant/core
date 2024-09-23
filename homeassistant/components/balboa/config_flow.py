"""Config flow for Balboa Spa Client integration."""

from __future__ import annotations

import logging
from typing import Any

from pybalboa import SpaClient
from pybalboa.exceptions import SpaConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)

from .const import CONF_SYNC_TIME, DOMAIN

_LOGGER = logging.getLogger(__name__)

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
    try:
        async with SpaClient(data[CONF_HOST]) as spa:
            if not await spa.async_configuration_loaded():
                raise CannotConnect
            mac = format_mac(spa.mac_address)
            model = spa.model
    except SpaConnectionError as err:
        raise CannotConnect from err

    return {"title": model, "formatted_mac": mac}


class BalboaSpaClientFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Balboa Spa Client config flow."""

    VERSION = 1

    _host: str | None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SchemaOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            try:
                info = await validate_input(user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["formatted_mac"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
