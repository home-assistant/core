"""Config flow for saj integration."""
import logging

import pysaj
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TYPE,
    CONF_USERNAME,
)

from .const import DOMAIN, INVERTER_TYPES  # pylint:disable=unused-import
from .sensor import CannotConnect, SAJInverter

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SAJ."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            host = user_input["host"]

            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            try:
                inverter = SAJInverter(user_input)
                await inverter.connect()

                return self.async_create_entry(title=host, data=user_input)
            except pysaj.UnauthorizedException:
                errors["base"] = "unauthorised"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception as error:  # pylint: disable=broad-except
                _LOGGER.error("Unexpected exception: %s", error)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_TYPE): vol.In(INVERTER_TYPES),
                    vol.Optional(CONF_NAME, default=""): str,
                    vol.Optional(CONF_USERNAME, "credentials"): str,
                    vol.Optional(CONF_PASSWORD, "credentials"): str,
                }
            ),
            errors=errors,
        )
