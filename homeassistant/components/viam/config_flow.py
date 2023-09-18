"""Config flow for viam integration."""
from __future__ import annotations

import logging
from typing import Any

from viam.app.viam_client import ViamClient
from viam.rpc.dial import Credentials, DialOptions
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("address"): str,
        vol.Required("secret"): str,
    }
)


class ViamHub:
    """Placeholder class to make tests pass.

    TODO Remove this placeholder class and replace with things from your PyPI package.
    """

    def __init__(self, address: str) -> None:
        """Initialize."""
        self.address = address
        self.client = None

    async def authenticate(self, secret: str) -> bool:
        """Test if we can authenticate with the host."""
        creds = Credentials(type="robot-location-secret", payload=secret)
        opts = DialOptions(auth_entity=self.address, credentials=creds)
        self.client = await ViamClient.create_from_dial_options(opts)
        return bool(self.client)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    hub = ViamHub(data["address"])

    if not await hub.authenticate(data["secret"]):
        raise InvalidAuth

    # If you cannot connect:
    # throw CannotConnect
    # If the authentication is wrong:
    # InvalidAuth
    if hub.client:
        location = await hub.client.app_client.get_location()
        hub.client.close()

        # Return info that you want to store in the config entry.
        return {"title": location.name}

    raise CannotConnect


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for viam."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
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
