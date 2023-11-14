"""Config flow for canvas integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .api_wrapper import ApiWrapper
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
HOST_PREFIX = "host_prefix" # consider adding a CONF prefix
ACCESS_TOKEN = "access_token"
CONF_COURSES = "courses"

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(HOST_PREFIX): str,
        vol.Required(ACCESS_TOKEN): str,
    }
)



class PlaceholderHub:
    """Placeholder class to make tests pass.

    TODO Remove this placeholder class and replace with things from your PyPI package.
    """

    def __init__(self, host_prefix: str) -> None:
        """Initialize."""
        self.host = f"https://{host_prefix}.instructure.com/api/v1"

    async def authenticate(self, access_token: str) -> bool:
        api = ApiWrapper(self.host, access_token)
        return await api.async_test_authentication()
    
    async def get_courses(self, access_token: str) -> list[{str, Any}]:
        api = ApiWrapper(self.host, access_token) # maybe self.api?
        courses = await api.async_get_courses()
        return courses
        


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any] | None:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    # TODO validate the data can be used to set up a connection.

    # If your PyPI package is not built with async, pass your methods
    # to the executor:
    # await hass.async_add_executor_job(
    #     your_validate_func, data["username"], data["password"]
    # )

    hub = PlaceholderHub(data[HOST_PREFIX])

    if not await hub.authenticate(data[ACCESS_TOKEN]):
        raise InvalidAuth

    # If you cannot connect:
    # throw CannotConnect
    # If the authentication is wrong:
    # InvalidAuth

    # Return info that you want to store in the config entry.
    # return {"title": "Canvas"}

async def get_courses_names(data: dict[str, Any]) -> list[str | None]:
    """Get the names of all courses for uses to select which to track"""
    # TODO - add try-except
    courses_name = []
    hub = PlaceholderHub(data[HOST_PREFIX])
    courses_info = await hub.get_courses(data[ACCESS_TOKEN])
    for info in courses_info:
        courses_name.append(info["name"])
    # TODO - sort courses, newly taken ones come first
    return courses_name


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for canvas."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize"""
        self.config_data = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self.config_data.update(user_input)
                return await self.async_step_courses()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_courses(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle courses step."""
        # not sure if it's necessary to check login status here

        if user_input is not None:
            self.config_data.update(user_input)
            return self.async_create_entry(
                title="Canvas-Course",
                data={HOST_PREFIX: self.config_data[HOST_PREFIX], ACCESS_TOKEN: self.config_data[ACCESS_TOKEN]},
                options={CONF_COURSES: self.config_data[CONF_COURSES]}
        )

        courses = await get_courses_names(self.config_data)
        return self.async_show_form(
            step_id="courses",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_COURSES): cv.multi_select(
                        {k: k for k in courses}
                    )
                }
            )
        )

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
