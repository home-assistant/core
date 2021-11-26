"""Config flow for ecowitt."""
import logging

import voluptuous as vol
from homeassistant import config_entries, core, exceptions
from homeassistant.core import callback

from homeassistant.const import (
    CONF_PORT,
    CONF_UNIT_SYSTEM_METRIC,
    CONF_UNIT_SYSTEM_IMPERIAL,
)

from .const import (
    CONF_UNIT_BARO,
    CONF_UNIT_WIND,
    CONF_UNIT_RAIN,
    CONF_UNIT_WINDCHILL,
    CONF_UNIT_LIGHTNING,
    DOMAIN,
    W_TYPE_HYBRID,
    UNIT_OPTS,
    WIND_OPTS,
    WINDCHILL_OPTS
)

from .schemas import (
    DATA_SCHEMA,
)


_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate user input."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data[CONF_PORT] == data[CONF_PORT]:
            raise AlreadyConfigured
    return {"title": f"Ecowitt on port {data[CONF_PORT]}"}


class EcowittConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for the Ecowitt."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Give initial instructions for setup."""
        if user_input is not None:
            return await self.async_step_initial_options()

        return self.async_show_form(step_id="user")

    async def async_step_initial_options(self, user_input=None):
        """Ask the user for the setup options."""
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_PORT: user_input[CONF_PORT]})
            return self.async_create_entry(title=f"Ecowitt on port {user_input[CONF_PORT]}", data=user_input)

        return self.async_show_form(
            step_id="initial_options", data_schema=DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Call the options flow handler."""
        return EcowittOptionsFlowHandler(config_entry)


class AlreadyConfigured(exceptions.HomeAssistantError):
    """Error to indicate this device is already configured."""


class EcowittOptionsFlowHandler(config_entries.OptionsFlow):
    """Ecowitt config flow options handler."""

    def __init__(self, config_entry):
        """Initialize HASS options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_UNIT_BARO,
                    default=self.config_entry.options.get(
                        CONF_UNIT_BARO, CONF_UNIT_SYSTEM_METRIC,
                    ),
                ): vol.In(UNIT_OPTS),
                vol.Optional(
                    CONF_UNIT_WIND,
                    default=self.config_entry.options.get(
                        CONF_UNIT_WIND, CONF_UNIT_SYSTEM_IMPERIAL,
                    ),
                ): vol.In(WIND_OPTS),
                vol.Optional(
                    CONF_UNIT_RAIN,
                    default=self.config_entry.options.get(
                        CONF_UNIT_RAIN, CONF_UNIT_SYSTEM_IMPERIAL,
                    ),
                ): vol.In(UNIT_OPTS),
                vol.Optional(
                    CONF_UNIT_LIGHTNING,
                    default=self.config_entry.options.get(
                        CONF_UNIT_LIGHTNING, CONF_UNIT_SYSTEM_IMPERIAL,
                    ),
                ): vol.In(UNIT_OPTS),
                vol.Optional(
                    CONF_UNIT_WINDCHILL,
                    default=self.config_entry.options.get(
                        CONF_UNIT_WINDCHILL, W_TYPE_HYBRID,
                    ),
                ): vol.In(WINDCHILL_OPTS),
            }
        )
        return self.async_show_form(step_id="init", data_schema=options_schema)
