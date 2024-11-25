"""Config flow for LaCrosse View integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from lacrosse_view import LaCrosse, Location, LoginError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("username"): str,
        vol.Required("password"): str,
    }
)
_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> list[Location]:
    """Validate the user input allows us to connect."""

    api = LaCrosse(async_get_clientsession(hass))

    try:
        if await api.login(data["username"], data["password"]):
            _LOGGER.debug("Successfully logged in")

        locations = await api.get_locations()
        _LOGGER.debug(locations)
    except LoginError as error:
        raise InvalidAuth from error

    if not locations:
        raise NoLocations(f'No locations found for account {data["username"]}')

    return locations


class LaCrosseViewConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LaCrosse View."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, str] = {}
        self.locations: list[Location] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            _LOGGER.debug("Showing initial form")
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except InvalidAuth:
            _LOGGER.exception("Could not login")
            errors["base"] = "invalid_auth"
        except NoLocations:
            errors["base"] = "no_locations"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            self.data = user_input
            self.locations = info

            # Check if we are reauthenticating
            if self.source == SOURCE_REAUTH:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates=self.data
                )

            _LOGGER.debug("Moving on to location step")
            return await self.async_step_location()

        _LOGGER.debug("Showing errors")
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_location(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the location step."""

        if not user_input:
            _LOGGER.debug("Showing initial location selection")
            return self.async_show_form(
                step_id="location",
                data_schema=vol.Schema(
                    {
                        vol.Required("location"): vol.In(
                            {location.id: location.name for location in self.locations}
                        )
                    }
                ),
            )

        location_id = user_input["location"]

        location_name = next(
            location.name for location in self.locations if location.id == location_id
        )

        await self.async_set_unique_id(location_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=location_name,
            data={
                "id": location_id,
                "name": location_name,
                "username": self.data["username"],
                "password": self.data["password"],
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Reauth in case of a password change or other error."""
        return await self.async_step_user()


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class NoLocations(HomeAssistantError):
    """Error to indicate there are no locations."""


class NonExistentEntry(HomeAssistantError):
    """Error to indicate that the entry does not exist when it should."""
