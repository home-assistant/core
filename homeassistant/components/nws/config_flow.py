"""Config flow for National Weather Service integration."""
import logging

import aiohttp
from pynws import SimpleNWS
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import unique_id
from .const import CONF_STATION, DOMAIN

_LOGGER = logging.getLogger(__name__)


def configured_instances(hass):
    """Return a set of configured instances."""
    return {
        unique_id(entry.data[CONF_LATITUDE], entry.data[CONF_LONGITUDE])
        for entry in hass.config_entries.async_entries(DOMAIN)
    }


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.  Return station if successful and unique id.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    latitude = data[CONF_LATITUDE]
    longitude = data[CONF_LONGITUDE]
    api_key = data[CONF_API_KEY]

    if unique_id(latitude, longitude) in configured_instances(hass):
        raise AlreadyConfigured

    client_session = async_get_clientsession(hass)

    ha_api_key = f"{api_key} homeassistant"

    nws = SimpleNWS(latitude, longitude, ha_api_key, client_session)

    try:
        await nws.set_station()
    except aiohttp.ClientError:
        raise CannotConnect

    return nws.stations


class DomainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for National Weather Service."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialiaze variablea needed accross steps."""
        self.stations = None
        self.user_data = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): cv.latitude,
                vol.Required(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): cv.longitude,
                CONF_API_KEY: str,
            }
        )

        errors = {}
        if user_input is not None:
            try:
                stations = await validate_input(self.hass, user_input)
                self.stations = stations
            except AlreadyConfigured:
                _LOGGER.exception("Entry already configured")
                errors["base"] = "already_configured"
            except CannotConnect:
                _LOGGER.exception("Cannot connect")
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self.user_data = user_input
                return await self.async_step_station()
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_station(self, user_input=None):
        """Confirm station selection.."""
        errors = {}
        data_schema = vol.Schema({CONF_STATION: vol.In(self.stations)})
        if user_input is None:
            return self.async_show_form(
                step_id="station", data_schema=data_schema, errors=errors
            )
        self.user_data[CONF_STATION] = user_input[CONF_STATION]
        return self.async_create_entry(
            title=unique_id(
                self.user_data[CONF_LATITUDE], self.user_data[CONF_LONGITUDE]
            ),
            data=self.user_data,
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class AlreadyConfigured(exceptions.HomeAssistantError):
    """Error to indicate a duplicate entry."""
