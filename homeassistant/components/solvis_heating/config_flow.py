"""Config flow for Solvis Remote integration."""
from __future__ import annotations

import logging
from typing import Any

from sc2xmlreader.const import DEFAULT_PASSWORD, DEFAULT_USERNAME
from sc2xmlreader.sc2xmlreader_validator import SC2XMLReaderValidator
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_OPTION_OVEN,
    CONF_OPTION_SOLAR,
    CONF_OPTION_SOLAR_EAST_WEST,
    CONF_OPTION_TITEL,
    CONF_OPTION_WARMWATER_STATION,
    CONF_UPDATE_TIMESPAN,
    DOMAIN,
)
from .options_flow import OptionsFlowHandler

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD, default=DEFAULT_PASSWORD): str,
        vol.Required(CONF_OPTION_WARMWATER_STATION, default=True): bool,
        vol.Required(CONF_OPTION_SOLAR, default=True): bool,
        vol.Required(CONF_OPTION_SOLAR_EAST_WEST, default=False): bool,
        vol.Required(CONF_OPTION_OVEN, default=False): bool,
        vol.Required(CONF_UPDATE_TIMESPAN, default=10): int,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solvis Heating."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await self.validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def validate_input(
        self, hass: HomeAssistant, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate the user input allows us to connect."""

        hub = await self.hass.async_add_executor_job(
            SC2XMLReaderValidator, data[CONF_HOST]
        )

        if not await self.hass.async_add_executor_job(hub.validate_host):
            raise CannotConnect

        if not await self.hass.async_add_executor_job(
            hub.authenticate, data[CONF_USERNAME], data[CONF_PASSWORD]
        ):
            raise InvalidAuth

        if not await self.hass.async_add_executor_job(
            hub.validate_uri, data[CONF_USERNAME], data[CONF_PASSWORD]
        ):
            raise CannotConnect

        return {"title": CONF_OPTION_TITEL}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
