import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from pyowm import OWM
from pyowm.exceptions.api_call_error import APICallError

from .const import DOMAIN  # pylint:disable=unused-import


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
                owm = OWM(user_input[CONF_API_KEY],)
            except APICallError as e:
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
