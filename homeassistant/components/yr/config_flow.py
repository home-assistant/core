"""Config flow to configure the Yr integration."""
import logging

import async_timeout

from homeassistant import config_entries
from homeassistant.const import CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import API_URL, CONF_FORECAST, DEFAULT_FORECAST, DEFAULT_NAME
from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


class YrFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Yr config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize Yr config flow."""

    def _configuration_exists(self, name: str) -> bool:
        """Return True if name exists in configuration."""
        for entry in self._async_current_entries():
            if entry.data.get(CONF_NAME) == name:
                return True
        return False

    async def _show_setup_form(self, user_input=None, errors=None):
        """Show the setup form to the user."""
        return self.async_show_form(step_id="user", errors=errors or {})

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is None:
            user_input = {}

        elevation = user_input.get(CONF_ELEVATION, self.hass.config.elevation or 0)
        forecast = user_input.get(CONF_FORECAST, DEFAULT_FORECAST)
        latitude = user_input.get(CONF_LATITUDE, self.hass.config.latitude)
        longitude = user_input.get(CONF_LONGITUDE, self.hass.config.longitude)
        name = user_input.get(CONF_NAME, DEFAULT_NAME)

        if self._configuration_exists(name):
            errors["base"] = "name_exists"
            return await self._show_setup_form(user_input, errors)

        if None in (latitude, longitude):
            _LOGGER.error("Latitude or longitude not set in Home Assistant config")
            errors["base"] = "coordinates_not_set"
            return await self._show_setup_form(user_input, errors)

        coordinates = {
            "lat": str(latitude),
            "lon": str(longitude),
            "msl": str(elevation),
        }

        try:
            websession = async_get_clientsession(self.hass)
            with async_timeout.timeout(10):
                resp = await websession.get(API_URL, params=coordinates)
            if resp.status != 200:
                raise Exception
            await resp.text()
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error("Unexpected error when feching Yr data %s", err)
            errors["base"] = "unknown"
            return await self._show_setup_form(user_input, errors)

        return self.async_create_entry(
            title=name,
            data={
                CONF_ELEVATION: elevation,
                CONF_FORECAST: forecast,
                CONF_LATITUDE: latitude,
                CONF_LONGITUDE: longitude,
                CONF_NAME: name,
            },
        )

    async def async_step_import(self, user_input):
        """Import a config entry."""
        latitude = user_input.get(CONF_LATITUDE, self.hass.config.latitude)
        longitude = user_input.get(CONF_LONGITUDE, self.hass.config.longitude)
        name = user_input.get(CONF_NAME, DEFAULT_NAME)

        if self._configuration_exists(name):
            return self.async_abort(reason="name_exists")
        if None in (latitude, longitude):
            _LOGGER.error("Latitude or longitude not set in Home Assistant config")
            return self.async_abort(reason="coordinates_not_set")

        return await self.async_step_user(user_input)
