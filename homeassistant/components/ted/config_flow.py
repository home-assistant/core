"""Config flow for TED integration."""
from __future__ import annotations

import logging
from typing import Any

import httpx
import tedpy
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import (
    ConfigEntry,
    OptionsFlow,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.httpx_client import get_async_client

from .const import (
    CONF_MTU_ENERGY_DAILY,
    CONF_MTU_ENERGY_MTD,
    CONF_MTU_ENERGY_NOW,
    CONF_MTU_POWER_VOLTAGE,
    CONF_SPYDER_ENERGY_DAILY,
    CONF_SPYDER_ENERGY_MTD,
    CONF_SPYDER_ENERGY_NOW,
    DOMAIN,
    OPTION_DEFAULTS,
)

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TED."""

    VERSION = 1

    def __init__(self):
        """Initialize an TED flow."""
        self.name = None
        self.serial = None
        self.model = None

    @callback
    def _async_generate_schema(self):
        """Generate schema."""
        schema = {vol.Required(CONF_HOST): str}

        return vol.Schema(schema)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                reader = await tedpy.createTED(
                    user_input[CONF_HOST], async_client=get_async_client(self.hass)
                )
                await reader.update()
                self.serial = reader.gateway_id
                self.model = 5000 if isinstance(reader, tedpy.TED5000) else 6000
                await self.async_set_unique_id(self.serial)
                self._abort_if_unique_id_configured({CONF_HOST: user_input[CONF_HOST]})
            except httpx.HTTPError:
                errors["base"] = "cannot_connect"
            else:
                data = user_input.copy()
                data[CONF_NAME] = f"TED {self.model}"
                return self.async_create_entry(title=data[CONF_NAME], data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=self._async_generate_schema(),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get options flow for this handler."""
        return TedOptionsFlowHandler(config_entry)


class TedOptionsFlowHandler(OptionsFlowWithConfigEntry):
    """Config flow options for TED."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the TED options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    self.create_option_schema_field(CONF_SPYDER_ENERGY_NOW): bool,
                    self.create_option_schema_field(CONF_SPYDER_ENERGY_DAILY): bool,
                    self.create_option_schema_field(CONF_SPYDER_ENERGY_MTD): bool,
                    self.create_option_schema_field(CONF_MTU_POWER_VOLTAGE): bool,
                    self.create_option_schema_field(CONF_MTU_ENERGY_NOW): bool,
                    self.create_option_schema_field(CONF_MTU_ENERGY_DAILY): bool,
                    self.create_option_schema_field(CONF_MTU_ENERGY_MTD): bool,
                }
            ),
        )

    def create_option_schema_field(self, name: str):
        """Create the schema for a specific TED option with the appropriate default value."""
        return vol.Required(
            name, default=self.config_entry.options.get(name, OPTION_DEFAULTS[name])
        )
