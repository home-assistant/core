"""Config flow for Switchbot."""
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_MAC, CONF_NAME, CONF_PASSWORD, CONF_SENSOR_TYPE

from .const import ATTR_BOT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SwitchbotConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Switchbot."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""

        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_MAC].replace(":", ""))
            self._abort_if_unique_id_configured()

            user_input[CONF_SENSOR_TYPE] = ATTR_BOT
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Optional(CONF_PASSWORD): str,
                vol.Required(CONF_MAC): str,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_import(self, import_config):
        """Handle config import from yaml."""
        _LOGGER.debug("import config: %s", import_config)

        await self.async_set_unique_id(import_config[CONF_MAC].replace(":", ""))
        self._abort_if_unique_id_configured()

        # Add type to import_config.
        # Currently integration only supports bot.
        # More than one type exists.
        import_config[CONF_SENSOR_TYPE] = ATTR_BOT

        return self.async_create_entry(
            title=import_config[CONF_NAME], data=import_config
        )
