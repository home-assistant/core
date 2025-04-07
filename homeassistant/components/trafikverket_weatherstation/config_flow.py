"""Adds config flow for Trafikverket Weather integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from pytrafikverket.exceptions import (
    InvalidAuthentication,
    MultipleWeatherStationsFound,
    NoWeatherStationFound,
)
from pytrafikverket.trafikverket_weather import TrafikverketWeather
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_STATION, DOMAIN

_LOGGER = logging.getLogger(__name__)


class TVWeatherConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Trafikverket Weatherstation integration."""

    VERSION = 1

    async def validate_input(self, sensor_api: str, station: str) -> None:
        """Validate input from user input."""
        web_session = async_get_clientsession(self.hass)
        weather_api = TrafikverketWeather(web_session, sensor_api)
        await weather_api.async_get_weather(station)

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            name = user_input[CONF_STATION]
            api_key = user_input[CONF_API_KEY]
            station = user_input[CONF_STATION]

            try:
                await self.validate_input(api_key, station)
            except InvalidAuthentication:
                errors["base"] = "invalid_auth"
            except NoWeatherStationFound:
                errors["base"] = "invalid_station"
            except MultipleWeatherStationsFound:
                errors["base"] = "more_stations"
            except Exception:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_API_KEY: api_key,
                        CONF_STATION: station,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): cv.string,
                    vol.Required(CONF_STATION): cv.string,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication with Trafikverket."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication with Trafikverket."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input:
            api_key = user_input[CONF_API_KEY]

            try:
                await self.validate_input(api_key, reauth_entry.data[CONF_STATION])
            except InvalidAuthentication:
                errors["base"] = "invalid_auth"
            except NoWeatherStationFound:
                errors["base"] = "invalid_station"
            except MultipleWeatherStationsFound:
                errors["base"] = "more_stations"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates={CONF_API_KEY: api_key}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): cv.string}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-configuration with Trafikverket."""
        errors: dict[str, str] = {}

        if user_input:
            try:
                await self.validate_input(
                    user_input[CONF_API_KEY], user_input[CONF_STATION]
                )
            except InvalidAuthentication:
                errors["base"] = "invalid_auth"
            except NoWeatherStationFound:
                errors["base"] = "invalid_station"
            except MultipleWeatherStationsFound:
                errors["base"] = "more_stations"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    title=user_input[CONF_STATION],
                    data=user_input,
                )

        schema = self.add_suggested_values_to_schema(
            vol.Schema(
                {
                    vol.Required(CONF_API_KEY): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                    vol.Required(CONF_STATION): TextSelector(),
                }
            ),
            {**self._get_reconfigure_entry().data, **(user_input or {})},
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            errors=errors,
        )
