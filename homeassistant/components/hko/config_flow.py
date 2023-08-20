"""Config flow for Hong Kong Observatory integration."""
from __future__ import annotations

from typing import Any

from async_timeout import timeout
from hko import HKO, LOCATIONS, HKOError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_LOCATION
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_LOCATION, DOMAIN


def get_loc_name(item):
    """Return an array of supported locations."""
    return item["LOCATION"]


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LOCATION, default=DEFAULT_LOCATION): vol.In(
            list(map(get_loc_name, LOCATIONS))  # Select Location
        )
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect."""

    if data[CONF_LOCATION] not in list(map(get_loc_name, LOCATIONS)):
        raise InvalidLocation

    websession = async_get_clientsession(hass)
    hko = HKO(websession)

    try:
        async with timeout(60):
            await hko.weather("rhrread")
    except HKOError as error:
        raise CannotConnect from error
    except Exception as error:
        raise UnknownError from error


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hong Kong Observatory."""

    VERSION = 1

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
            await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidLocation:
            errors["base"] = "invalid_location"
        except UnknownError:
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(
                user_input[CONF_LOCATION], raise_on_progress=False
            )
            return self.async_create_entry(
                title=user_input[CONF_LOCATION], data=user_input
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidLocation(HomeAssistantError):
    """Error to indicate an invalid location has been selected."""


class UnknownError(HomeAssistantError):
    """Error for an unknown_exception."""
