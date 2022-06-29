"""Config flow for Glances."""
from __future__ import annotations

import glances_api
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback

from . import get_api
from .const import (
    CONF_VERSION,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_VERSION,
    DOMAIN,
    SUPPORTED_VERSIONS,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_VERSION, default=DEFAULT_VERSION): int,
        vol.Optional(CONF_SSL, default=False): bool,
        vol.Optional(CONF_VERIFY_SSL, default=False): bool,
    }
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect."""
    if data[CONF_VERSION] not in SUPPORTED_VERSIONS:
        raise WrongVersion
    try:
        api = get_api(hass, data)
        await api.get_data("all")
    except glances_api.exceptions.GlancesApiConnectionError as err:
        raise CannotConnect from err


class GlancesFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Glances config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> GlancesOptionsFlowHandler:
        """Get the options flow for this handler."""
        return GlancesOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            try:
                await validate_input(self.hass, user_input)
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except WrongVersion:
                errors[CONF_VERSION] = "wrong_version"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class GlancesOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Glances client options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize Glances options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the Glances options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=self.config_entry.options.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                ),
            ): int
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class WrongVersion(exceptions.HomeAssistantError):
    """Error to indicate the selected version is wrong."""
