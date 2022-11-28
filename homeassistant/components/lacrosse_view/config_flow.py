"""Config flow for LaCrosse View integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from lacrosse_view import LaCrosse, Location, LoginError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("username"): str,
        vol.Required("password"): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> list[Location]:
    """Validate the user input allows us to connect."""

    api = LaCrosse(async_get_clientsession(hass))

    try:
        await api.login(data["username"], data["password"])

        locations = await api.get_locations()
    except LoginError as error:
        raise InvalidAuth from error

    if not locations:
        raise NoLocations("No locations found for account {}".format(data["username"]))

    return locations


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LaCrosse View."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, str] = {}
        self.locations: list[Location] = []
        self._reauth_entry: config_entries.ConfigEntry | None = None

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
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except NoLocations:
            errors["base"] = "no_locations"
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            self.data = user_input
            self.locations = info

            # Check if we are reauthenticating
            if self._reauth_entry is not None:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry, data=self._reauth_entry.data | self.data
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            return await self.async_step_location()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_location(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the location step."""

        if not user_input:
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

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Reauth in case of a password change or other error."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_user()


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class NoLocations(HomeAssistantError):
    """Error to indicate there are no locations."""


class NonExistentEntry(HomeAssistantError):
    """Error to indicate that the entry does not exist when it should."""
