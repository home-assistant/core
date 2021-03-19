"""Config flow for Wallbox integration."""
import logging

import requests
import voluptuous as vol
from wallbox import Wallbox

from homeassistant import config_entries, core, exceptions

from .const import DOMAIN

COMPONENT_DOMAIN = DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        "station": str,
        "username": str,
        "password": str,
    }
)


class PlaceholderHub:
    """Wallbox Hub class."""

    def __init__(self, station, username, password):
        """Initialize."""
        self._station = station
        self._username = username
        self._password = password

    def authenticate(self) -> bool:
        """Authenticate using Wallbox API."""
        try:
            wallbox = Wallbox(self._username, self._password)
            wallbox.authenticate()
            return True
        except requests.exceptions.HTTPError as wallbox_connection_error:
            if wallbox_connection_error.response.status_code == "403":
                raise InvalidAuth from wallbox_connection_error
            raise ConnectionError from wallbox_connection_error

    def get_data(self) -> bool:
        """Get new sensor data for Wallbox component."""

        try:
            wallbox = Wallbox(self._username, self._password)
            wallbox.authenticate()
            wallbox.getChargerStatus(self._station)
            return True
        except requests.exceptions.HTTPError as wallbox_connection_error:
            if wallbox_connection_error.response.status_code == "403":
                raise InvalidAuth from wallbox_connection_error
            raise ConnectionError from wallbox_connection_error


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    hub = PlaceholderHub(data["station"], data["username"], data["password"])

    await hass.async_add_executor_job(
        hub.authenticate,
    )

    await hass.async_add_executor_job(hub.get_data)

    # Return info that you want to store in the config entry.
    return {"title": "Wallbox Portal"}


class ConfigFlow(config_entries.ConfigFlow, domain=COMPONENT_DOMAIN):
    """Handle a config flow for Wallbox."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            _LOGGER.error("Cannot get MyWallbox data, is station serial correct?")
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
            _LOGGER.error("Cannot authenticate for MyWallbox")
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
