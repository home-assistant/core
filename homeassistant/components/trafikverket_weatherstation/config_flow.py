"""Adds config flow for Trafikverket Weather integration."""
from __future__ import annotations

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

    async def validate_input(self, sensor_api: str, station: str) -> str:
        """Validate input from user input."""
        web_session = async_get_clientsession(self.hass)
        weather_api = TrafikverketWeather(web_session, sensor_api)
        try:
            await weather_api.async_get_weather(station)
        except ValueError as err:
            return str(err)
        return "connected"

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            name = user_input[CONF_STATION]
            api_key = user_input[CONF_API_KEY]
            station = user_input[CONF_STATION]

            validate = await self.validate_input(api_key, station)
            if validate == "connected":
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_API_KEY: api_key,
                        CONF_STATION: station,
                    },
                )
            if validate == "Source: Security, message: Invalid authentication":
                errors["base"] = "invalid_auth"
            elif validate == "Could not find a weather station with the specified name":
                errors["base"] = "invalid_station"
            elif validate == "Found multiple weather stations with the specified name":
                errors["base"] = "more_stations"
            else:
                errors["base"] = "cannot_connect"

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
