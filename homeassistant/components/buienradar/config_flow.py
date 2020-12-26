"""Config flow for buienradar integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_DOMAIN, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_CAMERA,
    CONF_COUNTRY,
    CONF_DIMENSION,
    CONF_SENSOR,
    CONF_WEATHER,
    DEFAULT_DIMENSION,
    DOMAIN,
    HOME_LOCATION_NAME,
    SUPPORTED_COUNTRY_CODES,
)

_LOGGER = logging.getLogger(__name__)


@callback
def configured_instances(hass):
    """Return a set of configured buienradar instances."""
    entries = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get(CONF_CAMERA):
            entries.append(
                f"{entry.data.get(CONF_DIMENSION)}-{entry.data.get(CONF_COUNTRY)}"
            )
        else:
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
        if user_input is not None:
            if user_input[CONF_DOMAIN] == "Camera":
                return await self.async_step_camera()

            return await self.async_step_weather()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_DOMAIN): vol.In(["Camera", "Weather"]),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors={},
        )

    async def async_step_camera(self, user_input=None):
        """Handle a flow to configure camera setup."""
        errors = {}

        if user_input is not None:
            if (
                f"{user_input.get(CONF_DIMENSION)}-{user_input.get(CONF_COUNTRY)}"
                not in configured_instances(self.hass)
            ):
                return await self.async_create_buienradar_entry(user_input, True)

            errors["base"] = "already_configured"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=HOME_LOCATION_NAME): str,
                vol.Required(CONF_DIMENSION, default=DEFAULT_DIMENSION): vol.All(
                    vol.Coerce(int), vol.Range(min=120, max=700)
                ),
                vol.Required(CONF_COUNTRY, default="NL"): vol.All(
                    vol.Coerce(str), vol.In(SUPPORTED_COUNTRY_CODES)
                ),
            }
        )

        return self.async_show_form(
            step_id="camera",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_weather(self, user_input=None):
        """Handle a flow to configure weather setup."""
        errors = {}

        if user_input is not None:
            if (
                f"{user_input.get(CONF_LATITUDE)}-{user_input.get(CONF_LONGITUDE)}"
                not in configured_instances(self.hass)
            ):
                return await self.async_create_buienradar_entry(user_input, False)

            errors["base"] = "already_configured"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=HOME_LOCATION_NAME): str,
                vol.Required(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): cv.latitude,
                vol.Required(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): cv.longitude,
            }
        )

        return self.async_show_form(
            step_id="weather",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_create_buienradar_entry(self, input_data, is_camera):
        """Create a config entry."""
        name = input_data[CONF_NAME]

        # Always setup sensor and weather platform, camera is optional
        data = {
            CONF_NAME: name,
            CONF_CAMERA: is_camera,
            CONF_SENSOR: (not is_camera),
            CONF_WEATHER: (not is_camera),
        }

        if is_camera:
            data[CONF_COUNTRY] = input_data[CONF_COUNTRY]
            data[CONF_DIMENSION] = input_data[CONF_DIMENSION]
        else:
            data[CONF_LATITUDE] = input_data[CONF_LATITUDE]
            data[CONF_LONGITUDE] = input_data[CONF_LONGITUDE]

        return self.async_create_entry(title=name, data=data)

    async def async_step_import(self, import_input=None):
        """Import a config entry."""
        if import_input[CONF_CAMERA]:
            if (
                f"{import_input[CONF_DIMENSION]}-{import_input[CONF_COUNTRY]}"
                in configured_instances(self.hass)
            ):
                return self.async_abort(reason="already_configured")
        elif (
            f"{import_input[CONF_LATITUDE]}-{import_input[CONF_LONGITUDE]}"
            in configured_instances(self.hass)
        ):
            return self.async_abort(reason="already_configured")

        name = import_input[CONF_NAME]

        return self.async_create_entry(title=name, data=import_input)
