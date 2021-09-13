"""Config flow to configure Dynalite hub."""
from __future__ import annotations

import copy
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .bridge import DynaliteBridge
from .const import DEFAULT_PORT, DOMAIN, LOGGER
from .convert_config import convert_config


class DynaliteFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Dynalite config flow."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the Dynalite flow."""
        self.host = None

    async def _validate_connection(
        self, config: dict[str, Any], options: dict[str, Any]
    ) -> None:
        bridge = DynaliteBridge(self.hass, convert_config(config, options))
        if not await bridge.async_setup():
            raise CannotConnect

    async def async_step_import(self, import_info: dict[str, Any]) -> Any:
        """Import a new bridge as a config entry."""
        LOGGER.debug("Starting async_step_import - %s", import_info)
        host = import_info[CONF_HOST]
        data = {CONF_HOST: host, CONF_PORT: import_info.get(CONF_PORT, DEFAULT_PORT)}
        options = copy.deepcopy(import_info)
        options.pop(CONF_HOST)
        if CONF_PORT in options:
            options.pop(CONF_PORT)
        for entry in self._async_current_entries():
            if entry.data[CONF_HOST] == host:
                self.hass.config_entries.async_update_entry(
                    entry, data=data, options=options
                )
                return self.async_abort(reason="already_configured")

        # New entry
        try:
            await self._validate_connection(data, options)
        except CannotConnect:
            LOGGER.error("Unable to setup bridge - import info=%s", import_info)
            return self.async_abort(reason="no_connection")
        else:
            LOGGER.debug("Creating entry for the bridge - %s", import_info)
            return self.async_create_entry(title=host, data=data, options=options)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""

        dict_input = user_input or {}
        step_schema = vol.Schema(
            {
                vol.Required(
                    CONF_HOST, default=dict_input.get(CONF_HOST, "")
                ): cv.string,
                vol.Required(
                    CONF_PORT, default=dict_input.get(CONF_PORT, DEFAULT_PORT)
                ): cv.positive_int,
            }
        )

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=step_schema)

        errors = {}

        try:
            host = user_input[CONF_HOST]
            data = {CONF_HOST: host, CONF_PORT: user_input[CONF_PORT]}
            options: dict[str, Any] = {}
            await self._validate_connection(data, options)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=host, data=data, options=options)

        return self.async_show_form(
            step_id="user", data_schema=step_schema, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
