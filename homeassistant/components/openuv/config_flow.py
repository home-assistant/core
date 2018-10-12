"""Config flow to configure the OpenUV component."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import (
    CONF_API_KEY, CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE,
    CONF_SCAN_INTERVAL)
from homeassistant.helpers import aiohttp_client, config_validation as cv

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN


@callback
def configured_instances(hass):
    """Return a set of configured OpenUV instances."""
    return set(
        '{0}, {1}'.format(
            entry.data[CONF_LATITUDE], entry.data[CONF_LONGITUDE])
        for entry in hass.config_entries.async_entries(DOMAIN))


@config_entries.HANDLERS.register(DOMAIN)
class OpenUvFlowHandler(config_entries.ConfigFlow):
    """Handle an OpenUV config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the config flow."""
        pass

    async def _show_form(self, errors=None):
        """Show the form to the user."""
        data_schema = vol.Schema({
            vol.Required(CONF_API_KEY): str,
            vol.Optional(CONF_LATITUDE, default=self.hass.config.latitude):
                cv.latitude,
            vol.Optional(CONF_LONGITUDE, default=self.hass.config.longitude):
                cv.longitude,
            vol.Optional(CONF_ELEVATION, default=self.hass.config.elevation):
                vol.Coerce(float),
        })

        return self.async_show_form(
            step_id='user',
            data_schema=data_schema,
            errors=errors if errors else {},
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        from pyopenuv.util import validate_api_key

        if not user_input:
            return await self._show_form()

        latitude = user_input[CONF_LATITUDE]
        longitude = user_input[CONF_LONGITUDE]
        elevation = user_input[CONF_ELEVATION]

        identifier = '{0}, {1}'.format(latitude, longitude)
        if identifier in configured_instances(self.hass):
            return await self._show_form({CONF_LATITUDE: 'identifier_exists'})

        websession = aiohttp_client.async_get_clientsession(self.hass)
        api_key_validation = await validate_api_key(
            user_input[CONF_API_KEY], websession)

        if not api_key_validation:
            return await self._show_form({CONF_API_KEY: 'invalid_api_key'})

        scan_interval = user_input.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        user_input.update({
            CONF_LATITUDE: latitude,
            CONF_LONGITUDE: longitude,
            CONF_ELEVATION: elevation,
            CONF_SCAN_INTERVAL: scan_interval.seconds,
        })

        return self.async_create_entry(title=identifier, data=user_input)
