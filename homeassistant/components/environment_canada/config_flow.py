"""Config flow for Environment Canada integration."""
from functools import partial
import logging
import xml.etree.ElementTree as et

import aiohttp
from env_canada import ECData
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import config_validation as cv

from .const import CONF_LANGUAGE, CONF_STATION, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass, data):
    """Validate the user input allows us to connect."""
    lat = data.get(CONF_LATITUDE)
    lon = data.get(CONF_LONGITUDE)
    station = data.get(CONF_STATION)
    lang = data.get(CONF_LANGUAGE)

    weather_init = partial(
        ECData, station_id=station, coordinates=(lat, lon), language=lang.lower()
    )
    weather_data = await hass.async_add_executor_job(weather_init)
    if weather_data.metadata.get("location") is None:
        raise TooManyAttempts

    return {
        "title": weather_data.station_id,
        "name": weather_data.metadata.get("location"),
    }


class EnvironmentCanadaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Environment Canada weather."""

    VERSION = 1

    def __init__(self):
        """Place to store data between steps."""
        self._data = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                user_input[CONF_STATION] = info["title"]
                user_input[CONF_NAME] = info["name"]

                await self.async_set_unique_id(
                    f"{user_input[CONF_STATION]}-{user_input[CONF_LANGUAGE]}"
                )
                self._abort_if_unique_id_configured()
                self._data = user_input
                return await self.async_step_name()

            except TooManyAttempts:
                errors["base"] = "too_many_attempts"
            except AbortFlow:
                errors["base"] = "already_configured"
            except et.ParseError:
                errors["base"] = "bad_station_id"
            except aiohttp.ClientConnectionError:
                errors["base"] = "cannot_connect"
            except aiohttp.ClientResponseError as err:
                if err.status == 404:
                    errors["base"] = "bad_station_id"
                else:
                    _LOGGER.exception("Error response from EC")
                    errors["base"] = "error_response"
            except vol.MultipleInvalid:
                errors["base"] = "config_error"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_STATION): str,
                vol.Optional(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): cv.latitude,
                vol.Optional(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): cv.longitude,
                vol.Optional(CONF_LANGUAGE, default="English"): vol.In(
                    ["English", "French"]
                ),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_name(self, user_input=None):
        """Handle the name step."""
        errors = {}
        if user_input is not None:
            self._data[CONF_NAME] = user_input[CONF_NAME]
            return self.async_create_entry(title=user_input[CONF_NAME], data=self._data)

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=self._data[CONF_NAME]): str,
            }
        )

        return self.async_show_form(
            step_id="name", data_schema=data_schema, errors=errors
        )

    async def async_step_import(self, import_data):
        """Import entry from configuration.yaml."""
        existing = await self.async_set_unique_id(
            f"{import_data[CONF_STATION]}-{import_data[CONF_LANGUAGE]}"
        )
        if existing:
            _LOGGER.warn(
                "Environment Canada config is imported only for the first "
                "Environment Canada platform in your configuration.yaml"
            )
            self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=import_data[CONF_NAME],
            data=import_data,
        )


class TooManyAttempts(exceptions.HomeAssistantError):
    """Error to indicate station ID is missing, invalid, or not in EC database."""
