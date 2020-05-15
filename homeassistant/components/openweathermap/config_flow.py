"""Config flow for OpenWeatherMap."""
import logging

from pyowm import OWM
from pyowm.exceptions.api_call_error import APICallError
from pyowm.exceptions.api_response_error import UnauthorizedError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_LANGUAGE,
    DEFAULT_FORECAST_MODE,
    DEFAULT_LANGUAGE,
    DEFAULT_NAME,
    FORECAST_MODES,
    LANGUAGES,
)
from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)


class OpenWeatherMapConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for OpenWeatherMap."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize."""
        self._errors = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OpenWeatherMapOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            latitude = user_input[CONF_LATITUDE]
            longitude = user_input[CONF_LONGITUDE]

            await self.async_set_unique_id(f"{latitude}-{longitude}")
            self._abort_if_unique_id_configured()

            api_key_valid = await _validate_api_key(self.hass, user_input[CONF_API_KEY])

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
                    FORECAST_MODES
                ),
                vol.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): vol.In(
                    LANGUAGES
                ),
            }
        )


class OpenWeatherMapOptionsFlow(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_MODE,
                        default=self.config_entry.options.get(
                            CONF_MODE, DEFAULT_FORECAST_MODE
                        ),
                    ): vol.In(FORECAST_MODES),
                    vol.Optional(
                        CONF_LANGUAGE,
                        default=self.config_entry.options.get(
                            CONF_LANGUAGE, DEFAULT_LANGUAGE
                        ),
                    ): vol.In(LANGUAGES),
                }
            ),
        )


async def _validate_api_key(hass, api_key):
    try:
        owm = OWM(api_key)
        return await hass.async_add_executor_job(owm.is_API_online)
    except (APICallError, UnauthorizedError):
        return False
