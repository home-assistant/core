"""Config flow to configure Goodwe inverters using their local API."""
import logging

from goodwe import InverterError, connect
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_MODEL_FAMILY,
    CONF_NETWORK_RETRIES,
    CONF_NETWORK_TIMEOUT,
    DEFAULT_NAME,
    DEFAULT_NETWORK_RETRIES,
    DEFAULT_NETWORK_TIMEOUT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)

_LOGGER = logging.getLogger(__name__)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options for the component."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Init object."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        settings_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): int,
                vol.Optional(
                    CONF_NETWORK_RETRIES,
                    default=self.config_entry.options.get(
                        CONF_NETWORK_RETRIES, DEFAULT_NETWORK_RETRIES
                    ),
                ): cv.positive_int,
                vol.Optional(
                    CONF_NETWORK_TIMEOUT,
                    default=self.config_entry.options.get(
                        CONF_NETWORK_TIMEOUT, DEFAULT_NETWORK_TIMEOUT
                    ),
                ): cv.positive_int,
            }
        )

        return self.async_show_form(step_id="init", data_schema=settings_schema)


class GoodweFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Goodwe config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST]

            try:
                inverter = await connect(host=host)
            except InverterError as err:
                _LOGGER.error("Connection error during GoodWe config flow: %s", err)
                errors["base"] = "connection_error"

            if not errors:
                await self.async_set_unique_id(inverter.serial_number)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data={
                        CONF_HOST: host,
                        CONF_MODEL_FAMILY: type(inverter).__name__,
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )
