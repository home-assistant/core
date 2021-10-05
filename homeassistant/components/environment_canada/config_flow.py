"""Config flow for Environment Canada integration."""
import logging
import re
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


def validate_input(data):
    """Validate the user input allows us to connect."""
    latitude = data.get(CONF_LATITUDE)
    longitude = data.get(CONF_LONGITUDE)
    station = data.get(CONF_STATION)
    language = data.get(CONF_LANGUAGE)

    try:
        env_canada = ECData(
            station_id=station,
            coordinates=(latitude, longitude),
            language=language.lower(),
        )
    except et.ParseError:
        raise BadStationId

    return {"title": env_canada.station_id, "name": env_canada.metadata.get("location")}


def validate_station(station):
    """Check that the station ID is well-formed."""
    if station is None:
        return
    if not re.fullmatch(r"[A-Z]{2}/s0000\d{3}", station):
        raise vol.Invalid('Station ID must be of the form "XX/s0000###"')
    return station


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
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
                info = await self.hass.async_add_executor_job(
                    validate_input, user_input
                )
                # info = await validate_input(user_input)
                user_input[CONF_STATION] = info["title"]
                user_input[CONF_NAME] = info["name"]

                await self.async_set_unique_id(
                    f"{user_input[CONF_STATION]}-{user_input[CONF_LANGUAGE]}"
                )
                self._abort_if_unique_id_configured()
                self._data = user_input
                return await self.async_step_name()

            except AbortFlow:
                errors["base"] = "already_configured"
            except BadStationId:
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
                vol.Required(CONF_NAME, default=self._data[CONF_NAME]): str,
            }
        )

        return self.async_show_form(
            step_id="name", data_schema=data_schema, errors=errors
        )


class BadStationId(exceptions.HomeAssistantError):
    """Error to indicate station ID is missing, invalid, or not in EC database."""
