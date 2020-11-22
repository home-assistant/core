"""Config flow for Google Maps Travel Time integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_NAME
from homeassistant.util import slugify

from .const import (
    CONF_DESTINATION,
    CONF_OPTIONS,
    CONF_ORIGIN,
    DEFAULT_NAME,
    DOMAIN,
    GOOGLE_OPTIONS_SCHEMA,
    GOOGLE_SCHEMA,
)

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Google Maps Travel Time."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize config flow."""
        self._data = None
        self._options = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            await self.async_set_unique_id(
                slugify(
                    f"{DOMAIN}_{user_input[CONF_ORIGIN]}_{user_input[CONF_DESTINATION]}"
                )
            )
            self._abort_if_unique_id_configured()
            self._data = user_input.copy()
            return await self.async_step_options()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(GOOGLE_SCHEMA),
        )

    async def async_step_options(self, user_input=None):
        """Handle the options data."""
        if user_input is not None or self.source == SOURCE_IMPORT:
            if user_input:
                self._data[CONF_OPTIONS] = user_input.copy()
            elif self._options is not None:
                self._data[CONF_OPTIONS] = self._options

            return self.async_create_entry(
                title=self._data.get(CONF_NAME, DEFAULT_NAME), data=self._data
            )

        return self.async_show_form(
            step_id="options",
            data_schema=vol.Schema(GOOGLE_OPTIONS_SCHEMA),
        )

    async def async_step_import(self, import_config=None):
        """Handle import flow."""
        if import_config.get(CONF_OPTIONS) is not None:
            self._options = import_config[CONF_OPTIONS].copy()
            import_config.pop(CONF_OPTIONS)

        return await self.async_step_user(import_config)
