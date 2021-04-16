"""Config flow to configure the GDACS integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
)
from homeassistant.helpers import config_validation as cv

from .const import CONF_CATEGORIES, DEFAULT_RADIUS, DEFAULT_SCAN_INTERVAL, DOMAIN

DATA_SCHEMA = vol.Schema(
    {vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS): cv.positive_int}
)

_LOGGER = logging.getLogger(__name__)


class GdacsFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a GDACS config flow."""

    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def _show_form(self, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors or {}
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        _LOGGER.debug("User input: %s", user_input)
        if not user_input:
            return await self._show_form()

        latitude = user_input.get(CONF_LATITUDE, self.hass.config.latitude)
        user_input[CONF_LATITUDE] = latitude
        longitude = user_input.get(CONF_LONGITUDE, self.hass.config.longitude)
        user_input[CONF_LONGITUDE] = longitude

        identifier = f"{user_input[CONF_LATITUDE]}, {user_input[CONF_LONGITUDE]}"

        await self.async_set_unique_id(identifier)
        self._abort_if_unique_id_configured()

        scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        user_input[CONF_SCAN_INTERVAL] = scan_interval.seconds

        categories = user_input.get(CONF_CATEGORIES, [])
        user_input[CONF_CATEGORIES] = categories

        return self.async_create_entry(title=identifier, data=user_input)
