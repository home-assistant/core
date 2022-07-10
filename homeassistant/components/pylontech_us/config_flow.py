"""Config flow for pylontech_us integration."""
from __future__ import annotations

import logging

# from pickle import TRUE
from typing import Any

from pylontech import PylontechStack
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# TOODOP adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("port", default="/dev/ttyUSB0"): str,
        vol.Required("baud", default=115200): int,
        vol.Required("battery_count", default=7): int,
    }
)


class PylontechHub:
    """Communication to Pylontech Battery stack."""

    def __init__(self, config) -> None:
        """Initialize."""
        self._config = config

    def validate_config_input(self) -> None:
        """Validate config options. Raise exception on error."""
        # If you cannot connect:
        # throw CannotConnect
        # If the authentication is wrong:
        # InvalidAuth
        # config['port']

        stack = PylontechStack(
            device=self._config["port"],
            baud=self._config["baud"],
            manualBattcountLimit=self._config["battery_count"],
        )
        stack.update()

        if stack is None:
            raise CannotConnect("Connection Error, check Port and Baudrate")

        if stack.battcount != self._config["battery_count"]:
            self._config["battery_count"] = stack.battcount
            raise CannotConnect(
                "Wrong battery count will result in slow update please count again."
            )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for pylontech_us."""

    VERSION = 1

    hub = None

    async def validate_input(
        self, hass: HomeAssistant, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate the user input allows us to connect.

        Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
        """

        self.hub = PylontechHub(config=data)
        await hass.async_add_executor_job(
            self.hub.validate_config_input
        )  # !!! no Brackets !!!

        return_data = data
        return_data["title"] = "Pylontech"

        # Return info that you want to store in the config entry.
        return return_data

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:

            errors = {}

            try:
                await self.validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title="Pylontech " + user_input["port"], data=user_input
                )

        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
