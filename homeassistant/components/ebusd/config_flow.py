"""Config flow for ebusd integration."""
from __future__ import annotations

import logging
from typing import Any

import ebusdpy
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PORT,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import CONF_CACHE_TTL, CONF_CIRCUIT, DOMAIN, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "ebusd"
DEFAULT_PORT = 8888
DEFAULT_CACHE_TTL = 9000

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_CIRCUIT): vol.In(SENSOR_TYPES.keys()),
        vol.Optional(CONF_CACHE_TTL, default=DEFAULT_CACHE_TTL): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=24 * 60 * 60)
        ),
    }
)


async def async_check_ebusd_connection(hass: HomeAssistant, data: dict[str, Any]):
    """Check ebusd connection."""
    server_address = (data[CONF_HOST], data[CONF_PORT])
    try:
        await hass.async_add_executor_job(ebusdpy.init, server_address)
    except Exception as ebusd_error:
        raise CannotConnect from ebusd_error
    _LOGGER.debug(
        "ebusd connection to %s:%s succeeded", data[CONF_HOST], data[CONF_PORT]
    )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ebusd."""

    VERSION = 1

    def __init__(self):
        """Initialize."""
        self.init_info = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            unique_id = f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            try:
                await async_check_ebusd_connection(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                self.init_info = user_input
                return await self.async_step_monitored_conditions()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_monitored_conditions(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle monitored conditions step."""
        errors = {}
        if user_input is not None:
            selected_items = [x for x, y in user_input.items() if y]
            if len(selected_items) == 0:
                errors["base"] = "conditions_not_selected"
            else:
                config_data = dict(self.init_info)
                config_data[CONF_MONITORED_CONDITIONS] = selected_items
                return self.async_create_entry(
                    title=config_data[CONF_NAME], data=config_data
                )

        circuit = self.init_info[CONF_CIRCUIT]
        assert circuit in SENSOR_TYPES
        return self.async_show_form(
            step_id="monitored_conditions",
            data_schema=vol.Schema(
                {vol.Optional(mc): bool for mc in SENSOR_TYPES[circuit]}
            ),
            errors=errors,
            last_step=True,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
