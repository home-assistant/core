"""Config flow to configure the OpenUV component."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import (
    CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_SCAN_INTERVAL)
from homeassistant.helpers import aiohttp_client, config_validation as cv

from .const import (
    CONF_CITY, CONF_COORDINATES, CONF_COUNTRY, CONF_LOCATION, CONF_STATE,
    DEFAULT_SCAN_INTERVAL, DOMAIN)


# def _get_identifier_from_input(hass, user_input):
#     """Return a unique location identifier from the config entry input."""
#     if CONF_LOCATION in user_input:
#         return '{0}, {1}, {2}'.format(
#             user_input[CONF_CITY], user_input[CONF_STATE],
#             user_input[CONF_COUNTRY])

#     if CONF_COORDINATES in user_input:
#         return '{0}, {1}'.format(
#             user_input[CONF_LATITUDE], user_input[CONF_LONGITUDE])

#     return '{0}, {1}'.format(hass.config.latitude, hass.config.longitude)


@callback
def configured_instances(hass):
    """Return a set of configured OpenUV instances."""
    return set(
        '{0}, {1}'.format(
            entry.data.get(CONF_LATITUDE, hass.config.latitude),
            entry.data.get(CONF_LONGITUDE, hass.config.longitude))
        for entry in hass.config_entries.async_entries(DOMAIN))


@config_entries.HANDLERS.register(DOMAIN)
class OpenUvFlowHandler(config_entries.ConfigFlow):
    """Handle an OpenUV config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def _show_form(self, errors=None):
        """Show the form to the user."""
        data_schema = vol.Schema({
            vol.Required(CONF_API_KEY): str,
            vol.Optional(CONF_LATITUDE): cv.latitude,
            vol.Optional(CONF_LONGITUDE): cv.longitude,
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
        from pyairvisual import Client
        from pyairvisual.errors import AirVisualError

        # identifier = _get_identifier_from_input(self.hass, user_input)
        # if identifier in configured_instances(self.hass):
        #     return await self._show_form({'base': 'identifier_exists'})

        websession = aiohttp_client.async_get_clientsession(self.hass)
        client = Client(user_input[CONF_API_KEY], websession)

        try:
            await client.data.nearest_city()
        except AirVisualError:
            return await self._show_form({CONF_API_KEY: 'invalid_api_key'})

        scan_interval = user_input.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        user_input[CONF_SCAN_INTERVAL] = scan_interval.seconds

        return self.async_create_entry(
            title='{0}, {1}'.format(
                user_input.get(CONF_LATITUDE, self.hass.config.latitude),
                user_input.get(CONF_LONGITUDE, self.hass.config.longitude)),
            data=user_input)
