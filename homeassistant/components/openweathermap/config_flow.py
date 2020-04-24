"""Config flow for OpenWeatherMap."""
from pyowm import OWM
from pyowm.exceptions.api_call_error import APICallError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
)
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_LANGUAGE,
    DEFAULT_FORECAST_MODE,
    DEFAULT_LANGUAGE,
    DEFAULT_NAME,
    FORECAST_MODE,
)
from .const import DOMAIN  # pylint:disable=unused-import


class OpenWeatherMapConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for OpenWeatherMap."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            latitude = user_input[CONF_LATITUDE]
            longitude = user_input[CONF_LONGITUDE]

            await self.async_set_unique_id(f"{latitude}-{longitude}")
            self._abort_if_unique_id_configured()
            api_key_valid = await self._validate_api_key(user_input[CONF_API_KEY])
            if not api_key_valid:
                errors["base"] = "auth"

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=self._get_schema(), errors=errors,
        )

    def _get_schema(self):
        return vol.Schema(
            {
                vol.Required(CONF_API_KEY): str,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Optional(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): cv.latitude,
                vol.Optional(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): cv.longitude,
                vol.Optional(CONF_MODE, default=DEFAULT_FORECAST_MODE): vol.In(
                    FORECAST_MODE
                ),
                vol.Optional(CONF_MONITORED_CONDITIONS, default=""): str,
                # vol.Optional(CONF_MONITORED_CONDITIONS, default=[]): vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
                vol.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): str,
            }
        )

    @staticmethod
    async def _validate_api_key(api_key):
        try:
            OWM(api_key)
        except APICallError:
            return False
        return True
