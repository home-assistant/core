"""Configuration via ui for OpenWeatherMap integration."""
from pyowm import OWM
from pyowm.exceptions.api_call_error import APICallError
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

from .const import DOMAIN, FORECAST_MODE  # pylint:disable=unused-import


class OpenWeatherMapConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """OpenWeatherMap config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        # Under the terms of use of the API, one user can use one free API key. Due to
        # the small number of requests allowed, we only allow one integration instance.
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors = {}

        if user_input is not None:
            try:
                OWM(user_input[CONF_API_KEY],)
            except APICallError:
                errors["base"] = "cannot_connect"
            else:

                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Optional(
                        CONF_LATITUDE, default=self.hass.config.latitude
                    ): cv.latitude,
                    vol.Optional(
                        CONF_LONGITUDE, default=self.hass.config.longitude
                    ): cv.longitude,
                    vol.Optional(CONF_NAME, default="OpenWeatherMap"): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Options callback for OpenWeatherMap."""
        return OpenWeatherMapOptionsConfigFlow(config_entry)


class OpenWeatherMapOptionsConfigFlow(config_entries.OptionsFlow):
    """Config flow options for OpenWeatherMap."""

    def __init__(self, config_entry):
        """Initialize OpenWeatherMap options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_MODE,
                        default=self.config_entry.options.get(
                            CONF_MODE, FORECAST_MODE[0]
                        ),
                    ): vol.In(FORECAST_MODE)
                }
            ),
        )
