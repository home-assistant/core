"""Config flow for Environment Canada integration."""

import logging
from typing import Any
import xml.etree.ElementTree as ET

import aiohttp
from env_canada import ECWeather, ec_exc
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LANGUAGE, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.helpers import config_validation as cv

from .const import CONF_STATION, CONF_TITLE, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(data):
    """Validate the user input allows us to connect."""
    lat = data.get(CONF_LATITUDE)
    lon = data.get(CONF_LONGITUDE)
    station = data.get(CONF_STATION)
    lang = data.get(CONF_LANGUAGE).lower()

    if station:
        weather_data = ECWeather(station_id=station, language=lang)
    else:
        weather_data = ECWeather(coordinates=(lat, lon), language=lang)
    await weather_data.update()

    if lat is None or lon is None:
        lat = weather_data.lat
        lon = weather_data.lon

    return {
        CONF_TITLE: weather_data.metadata.location,
        CONF_STATION: weather_data.station_id,
        CONF_LATITUDE: lat,
        CONF_LONGITUDE: lon,
    }


class EnvironmentCanadaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Environment Canada weather."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(user_input)
            except (ET.ParseError, vol.MultipleInvalid, ec_exc.UnknownStationId):
                errors["base"] = "bad_station_id"
            except aiohttp.ClientConnectionError:
                errors["base"] = "cannot_connect"
            except aiohttp.ClientResponseError as err:
                if err.status == 404:
                    errors["base"] = "bad_station_id"
                else:
                    errors["base"] = "error_response"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                user_input[CONF_STATION] = info[CONF_STATION]
                user_input[CONF_LATITUDE] = info[CONF_LATITUDE]
                user_input[CONF_LONGITUDE] = info[CONF_LONGITUDE]

                # The combination of station and language are unique for all EC weather reporting
                await self.async_set_unique_id(
                    f"{user_input[CONF_STATION]}-{user_input[CONF_LANGUAGE].lower()}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info[CONF_TITLE], data=user_input)

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_STATION): str,
                vol.Optional(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): cv.latitude,
                vol.Optional(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): cv.longitude,
                vol.Required(CONF_LANGUAGE, default="English"): vol.In(
                    ["English", "French"]
                ),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )
