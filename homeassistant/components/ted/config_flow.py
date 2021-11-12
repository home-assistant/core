"""Config flow for TED integration."""
from __future__ import annotations

import logging
from typing import Any

import httpx
import tedpy
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_IP_ADDRESS, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN, OPTION_DEFAULTS

_LOGGER = logging.getLogger(__name__)

CONF_SERIAL = "serial"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TED."""

    VERSION = 1

    def __init__(self):
        """Initialize an TED flow."""
        self.ip_address = None
        self.name = None
        self.serial = None
        self.model = None

    @callback
    def _async_generate_schema(self):
        """Generate schema."""
        schema = {}

        if self.ip_address:
            schema[vol.Required(CONF_HOST, default=self.ip_address)] = vol.In(
                [self.ip_address]
            )
        else:
            schema[vol.Required(CONF_HOST)] = str

        return vol.Schema(schema)

    async def async_step_import(self, import_config):
        """Handle a flow import."""
        self.ip_address = import_config[CONF_IP_ADDRESS]
        self.name = import_config[CONF_NAME]
        return await self.async_step_user(
            {
                CONF_HOST: import_config[CONF_IP_ADDRESS],
            }
        )

    @callback
    def _async_current_hosts(self):
        """Return a set of hosts."""
        return {
            entry.data[CONF_HOST]
            for entry in self._async_current_entries(include_ignore=False)
            if CONF_HOST in entry.data
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            if user_input[CONF_HOST] in self._async_current_hosts():
                return self.async_abort(reason="already_configured")

            try:
                reader = await tedpy.createTED(
                    user_input[CONF_HOST], async_client=get_async_client(self.hass)
                )
                await reader.update()
                self.serial = reader.gateway_id
                self.model = 5000 if isinstance(reader, tedpy.TED5000) else 6000
                await self.async_set_unique_id(self.serial)
            except httpx.HTTPError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
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
    def async_get_options_flow(config_entry):
        """Get options flow for this handler."""
        return TedOptionsFlowHandler(config_entry)


class TedOptionsFlowHandler(config_entries.OptionsFlow):
    """Config flow options for TED."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize TED options flow."""
        self.config_entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the TED options."""
        return await self.async_step_options()

    def create_option_schema_field(self, name):
        """Create the schema for a specific TED option with the appropriate default value."""
        return vol.Required(
            name, default=self.config_entry.options.get(name, OPTION_DEFAULTS[name])
        )

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="options",
            data_schema=vol.Schema(
                {
                    self.create_option_schema_field("show_spyder_energy_now"): bool,
                    self.create_option_schema_field("show_spyder_energy_daily"): bool,
                    self.create_option_schema_field("show_spyder_energy_mtd"): bool,
                    self.create_option_schema_field("show_mtu_power_voltage"): bool,
                    self.create_option_schema_field("show_mtu_energy_now"): bool,
                    self.create_option_schema_field("show_mtu_energy_daily"): bool,
                    self.create_option_schema_field("show_mtu_energy_mtd"): bool,
                }
            ),
        )
