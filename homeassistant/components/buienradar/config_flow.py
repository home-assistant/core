"""Config flow for buienradar2 integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_CAMERA,
    CONF_COUNTRY,
    CONF_SENSOR,
    CONF_WEATHER,
    DOMAIN,
    HOME_LOCATION_NAME,
    SUPPORTED_COUNTRY_CODES,
)

_LOGGER = logging.getLogger(__name__)


@callback
def configured_instances(hass):
    """Return a set of configured SimpliSafe instances."""
    entries = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        entries.append(
            f"{entry.data.get(CONF_LATITUDE)}-{entry.data.get(CONF_LONGITUDE)}"
        )
    return set(entries)


class BuienradarFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for buienradar2."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            if (
                f"{user_input.get(CONF_LATITUDE)}-{user_input.get(CONF_LONGITUDE)}"
                not in configured_instances(self.hass)
            ):
                return await self.async_create_buienradar_entry(user_input)

            errors[CONF_NAME] = "name_exists"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=HOME_LOCATION_NAME): str,
                vol.Required(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): cv.latitude,
                vol.Required(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): cv.longitude,
                vol.Required(CONF_CAMERA, default=False): bool,
                vol.Required(CONF_COUNTRY, default="NL"): vol.All(
                    vol.Coerce(str), vol.In(SUPPORTED_COUNTRY_CODES)
                ),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors,
        )

    async def async_create_buienradar_entry(self, input_data):
        """Create a config entry."""
        name = input_data[CONF_NAME]

        # Always setup sensor and weather platform, camera is optional
        data = {
            CONF_NAME: name,
            CONF_LATITUDE: input_data[CONF_LATITUDE],
            CONF_LONGITUDE: input_data[CONF_LONGITUDE],
            CONF_CAMERA: input_data[CONF_CAMERA],
            CONF_SENSOR: True,
            CONF_WEATHER: True,
            CONF_COUNTRY: input_data[CONF_COUNTRY],
        }

        return self.async_create_entry(title=name, data=data)
