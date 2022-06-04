"""Config flow for saj integration."""
from __future__ import annotations

import logging
from typing import Any

import pysaj
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TYPE, CONF_USERNAME
from homeassistant.data_entry_flow import FlowError, FlowResult
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, INVERTER_TYPES
from .coordinator import CannotConnect, SAJDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SAJ."""

    VERSION = 1

    async def async_step_import(self, import_config: ConfigType) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        for entry in self._async_current_entries(include_ignore=True):
            if import_config[CONF_HOST] == entry.data[CONF_HOST]:
                return self.async_abort(reason="already_configured")
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input: dict[str, Any] = None) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                inverter = SAJDataUpdateCoordinator(self.hass, user_input)
                if self.context["source"] != config_entries.SOURCE_IMPORT:
                    await inverter.connect()
                await self.async_set_unique_id(inverter.serialnumber)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=inverter.name, data=user_input)
            except pysaj.UnauthorizedException:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except FlowError as error:
                raise error
            except Exception as error:  # pylint: disable=broad-except
                _LOGGER.error("Unexpected exception: %s", error)
                errors["base"] = "unknown"
        else:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
                    vol.Required(CONF_TYPE, default=user_input.get(CONF_TYPE)): vol.In(
                        INVERTER_TYPES
                    ),
                    vol.Optional(
                        CONF_USERNAME,
                        "credentials",
                        default=user_input.get(CONF_USERNAME, ""),
                    ): str,
                    vol.Optional(
                        CONF_PASSWORD,
                        "credentials",
                        default=user_input.get(CONF_PASSWORD, ""),
                    ): str,
                }
            ),
            errors=errors,
        )
