"""Config flow for here_weather integration."""
from __future__ import annotations

import herepy
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .const import DEFAULT_MODE, DOMAIN


async def async_validate_user_input(hass: HomeAssistant, user_input: dict) -> None:
    """Validate the user_input containing coordinates."""
    here_client = herepy.DestinationWeatherApi(user_input[CONF_API_KEY])
    await hass.async_add_executor_job(
        here_client.weather_for_coordinates,
        user_input[CONF_LATITUDE],
        user_input[CONF_LONGITUDE],
        herepy.WeatherProductType[DEFAULT_MODE],
    )


class HereWeatherConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for here_weather."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(_unique_id(user_input))
            self._abort_if_unique_id_configured()
            try:
                await async_validate_user_input(self.hass, user_input)
            except herepy.InvalidRequestError:
                errors["base"] = "invalid_request"
            except herepy.UnauthorizedError:
                errors["base"] = "unauthorized"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self._get_schema(user_input),
            errors=errors,
        )

    def _get_schema(self, user_input: dict | None) -> vol.Schema:
        if user_input is not None:
            return vol.Schema(
                {
                    vol.Required(CONF_API_KEY, default=user_input[CONF_API_KEY]): str,
                    vol.Required(CONF_NAME, default=user_input[CONF_NAME]): str,
                    vol.Required(
                        CONF_LATITUDE, default=user_input[CONF_LATITUDE]
                    ): cv.latitude,
                    vol.Required(
                        CONF_LONGITUDE, default=user_input[CONF_LONGITUDE]
                    ): cv.longitude,
                }
            )
        return vol.Schema(
            {
                vol.Required(CONF_API_KEY): str,
                vol.Required(CONF_NAME, default=DOMAIN): str,
                vol.Required(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): cv.latitude,
                vol.Required(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): cv.longitude,
            }
        )


def _unique_id(user_input: dict) -> str:
    return f"{user_input[CONF_LATITUDE]}_{user_input[CONF_LONGITUDE]}"
