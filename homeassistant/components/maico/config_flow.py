"""Config flow for Maico integration."""
from __future__ import annotations

import logging
from typing import Any

from httpx import codes
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import httpx_client

from .const import DOMAIN
from .maico import Maico

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("host"): str,
        vol.Optional("username", default="admin"): str,
        vol.Optional("password", default=""): str,
    }
)


# class PlaceholderHub:
#     """Placeholder class to make tests pass.

#     Remove this placeholder class and replace with things from your PyPI package.
#     """

#     def __init__(self, host: str) -> None:
#         """Initialize."""
#         self.host = host

#     async def authenticate(self, username: str, password: str) -> bool:
#         """Test if we can authenticate with the host."""
#         return True


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    # validate the data can be used to set up a connection.

    # If your PyPI package is not built with async, pass your methods
    # to the executor:
    # await hass.async_add_executor_job(
    #     your_validate_func, data["username"], data["password"]
    # )
    # hub = PlaceholderHub(data["host"])
    # if not await hub.authenticate(data["username"], data["password"]):
    # raise InvalidAuth

    hub = Maico(
        "",
        data["host"],
        httpx_client.get_async_client(hass),
        data["username"],
        data["password"]
        # data.get("username", "admin"),
        # data.get("password", ""),
    )

    conn_status_code = await hub.connect()
    if conn_status_code in [codes.UNAUTHORIZED, codes.FORBIDDEN]:
        raise InvalidAuth
    if conn_status_code != codes.OK:
        raise CannotConnect

    # Return info that you want to store in the config entry.
    return {"title": "Maico"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Maico."""

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
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
