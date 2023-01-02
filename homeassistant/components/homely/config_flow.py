"""Config flow for homely integration."""
from __future__ import annotations

import logging
from typing import Any

from homelypy.devices import Location
from homelypy.homely import (
    AuthenticationFailedException,
    ConnectionFailedException,
    Homely,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("username"): str,
        vol.Required("password"): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    try:
        homely = Homely(data["username"], data["password"])
        locations: list[Location] = await hass.async_add_executor_job(
            homely.get_locations
        )
    except (TimeoutError, ConnectionFailedException) as ex:
        raise CannotConnect from ex
    except AuthenticationFailedException as ex:
        raise InvalidAuth from ex

    return {
        "username": data["username"],
        "password": data["password"],
        "locations": locations,
    }


class HomelyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for homely."""

    VERSION = 1
    locations: list[Location] = []
    data: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            self.locations = info["locations"]
            self.data = user_input
            return await self.async_step_location()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_location(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Choose the correct location from the list provided by Homely."""

        if user_input is not None:
            location_id: str = user_input["location"]
            location = next(
                filter(
                    lambda location: (location.location_id == location_id),
                    self.locations,
                )
            )
            self.data["location_id"] = location.location_id
            # Do not allow multiple instances for the same location
            await self.async_set_unique_id(location.location_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"Homely {location.name}", data=self.data
            )
        schema = vol.Schema(
            {
                vol.Required("location"): vol.In(
                    {location.location_id: location.name for location in self.locations}
                )
            }
        )
        return self.async_show_form(step_id="location", data_schema=schema, errors={})


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
