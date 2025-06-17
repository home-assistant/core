"""Config flow for the Google Weather integration."""

from __future__ import annotations

import logging
from typing import Any

from google_weather_api import GoogleWeatherApi, GoogleWeatherApiError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import LocationSelector, LocationSelectorConfig

from .const import CONF_REFERRER, DOMAIN

_LOGGER = logging.getLogger(__name__)


class GoogleWeatherConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Google Weather."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {
            "api_key_url": "https://developers.google.com/maps/documentation/weather/get-api-key",
        }
        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            referrer = user_input.get(CONF_REFERRER)
            latitude = user_input[CONF_LOCATION][CONF_LATITUDE]
            longitude = user_input[CONF_LOCATION][CONF_LONGITUDE]
            await self.async_set_unique_id(f"{latitude}-{longitude}")
            self._abort_if_unique_id_configured()
            api = GoogleWeatherApi(
                session=async_get_clientsession(self.hass),
                api_key=api_key,
                referrer=referrer,
                latitude=latitude,
                longitude=longitude,
                language_code=self.hass.config.language,
            )
            try:
                await api.async_get_current_conditions()
            except GoogleWeatherApiError as err:
                _LOGGER.error("Error connecting to Google Weather: %s", str(err))
                errors["base"] = "cannot_connect"
                description_placeholders["error_message"] = str(err)
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                data = {
                    CONF_API_KEY: api_key,
                    CONF_LATITUDE: latitude,
                    CONF_LONGITUDE: longitude,
                    CONF_REFERRER: referrer,
                }
                return self.async_create_entry(title=user_input[CONF_NAME], data=data)
        else:
            user_input = {}
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_NAME,
                    default=user_input.get(CONF_NAME, self.hass.config.location_name),
                ): str,
                vol.Required(
                    CONF_API_KEY, default=user_input.get(CONF_API_KEY, vol.UNDEFINED)
                ): str,
                vol.Optional(
                    CONF_REFERRER, default=user_input.get(CONF_REFERRER, vol.UNDEFINED)
                ): str,
                vol.Required(
                    CONF_LOCATION,
                    default=user_input.get(
                        CONF_LOCATION,
                        {
                            CONF_LATITUDE: self.hass.config.latitude,
                            CONF_LONGITUDE: self.hass.config.longitude,
                        },
                    ),
                ): LocationSelector(LocationSelectorConfig(radius=False)),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )
