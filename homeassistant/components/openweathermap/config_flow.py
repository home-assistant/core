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

SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Optional(CONF_LATITUDE): cv.latitude,
        vol.Optional(CONF_LONGITUDE): cv.longitude,
        vol.Optional(CONF_MODE, default=DEFAULT_FORECAST_MODE): vol.In(FORECAST_MODES),
        vol.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): vol.In(LANGUAGES),
    }
)

_LOGGER = logging.getLogger(__name__)


class OpenWeatherMapConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for OpenWeatherMap."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

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

            try:
                api_online = await _is_owm_api_online(
                    self.hass, user_input[CONF_API_KEY]
                )
                if not api_online:
                    errors["base"] = "auth"
            except UnauthorizedError:
                errors["base"] = "auth"
            except APICallError:
                errors["base"] = "connection"

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
        return self.async_show_form(step_id="user", data_schema=SCHEMA, errors=errors)

    async def async_step_import(self, import_input=None):
        """Set the config entry up from yaml."""
        config = import_input.copy()
        if CONF_NAME not in config:
            config[CONF_NAME] = DEFAULT_NAME
        if CONF_LATITUDE not in config:
            config[CONF_LATITUDE] = self.hass.config.latitude
        if CONF_LONGITUDE not in config:
            config[CONF_LONGITUDE] = self.hass.config.longitude
        if CONF_MODE not in config:
            config[CONF_MODE] = DEFAULT_LANGUAGE
        if CONF_LANGUAGE not in config:
            config[CONF_LANGUAGE] = DEFAULT_LANGUAGE
        return await self.async_step_user(config)


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
            data_schema=self._get_options_schema(),
        )

    def _get_options_schema(self):
        return vol.Schema(
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
        )


async def _is_owm_api_online(hass, api_key):
    owm = OWM(api_key)
    return await hass.async_add_executor_job(owm.is_API_online)
