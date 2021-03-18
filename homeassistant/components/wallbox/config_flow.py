"""Config flow for Wallbox integration."""
import logging

import voluptuous as vol
from wallbox import Wallbox

from homeassistant import config_entries, core, exceptions

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        "station": str,
        "username": str,
        "password": str,
    }
)


class PlaceholderHub:
    """Placeholder class to make tests pass.

    TODO Remove this placeholder class and replace with things from your PyPI package.
    """

    def __init__(self, station):
        """Initialize."""
        self.station = station

    def authenticate(self, username, password) -> bool:
        """Authenticate using Wallbox API."""
        try:
            w = Wallbox(username, password)
            w.authenticate()
            return True
        except Exception:
            raise InvalidAuth

    def getData(self, username, password) -> bool:
        """Get new sensor data for Wallbox component."""

        try:
            w = Wallbox(username, password)
            w.authenticate()
            w.getChargerStatus(self.station)
            return True
        except ConnectionError:
            raise CannotConnect


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    hub = PlaceholderHub(data["station"])

    await hass.async_add_executor_job(
        hub.authenticate, data["username"], data["password"]
    )

    await hass.async_add_executor_job(hub.getData, data["username"], data["password"])

    # Return info that you want to store in the config entry.
    return {"title": "Wallbox Portal"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Wallbox."""

    VERSION = 1
    # TODO pick one of the available connection classes in homeassistant/config_entries.py
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
            _LOGGER.error("Cannot get MyWallbox data, is station serial correct?.")
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
            _LOGGER.error("Cannot authenticate for MyWallbox.")
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
