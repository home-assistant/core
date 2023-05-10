"""Adds config flow for Trafikverket Weather integration."""
from __future__ import annotations

from pytrafikverket.exceptions import (
    InvalidAuthentication,
    MultipleWeatherStationsFound,
    NoWeatherStationFound,
)
from pytrafikverket.trafikverket_weather import TrafikverketWeather
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import CONF_STATION, DOMAIN


class TVWeatherConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Trafikverket Weatherstation integration."""

    VERSION = 1

    entry: config_entries.ConfigEntry

    async def validate_input(self, sensor_api: str, station: str) -> None:
        """Validate input from user input."""
        web_session = async_get_clientsession(self.hass)
        weather_api = TrafikverketWeather(web_session, sensor_api)
        await weather_api.async_get_weather(station)

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
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
            except Exception:  # pylint: disable=broad-exception-caught
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
