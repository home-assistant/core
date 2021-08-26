"""Config flow for frigidaire integration."""
from __future__ import annotations

import logging
from typing import Any

import frigidaire
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({"username": str, "password": str})


async def validate_input(hass: HomeAssistant, data: dict[str, Any]):
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    def setup(username: str, password: str) -> list[frigidaire.Appliance]:
        try:
            client = frigidaire.Frigidaire(username, password, timeout=60)
            return client.get_appliances()
        except frigidaire.FrigidaireException as err:
            if "Failed to authenticate" in str(err):
                raise InvalidAuth from err

            raise CannotConnect from err

    appliances = await hass.async_add_executor_job(
        setup, data["username"], data["password"]
    )

    if len(appliances) == 0:
        raise NoAppliances

    # Validation Succeeded
    return True


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for frigidaire."""

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
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except NoAppliances:
            errors["base"] = "no_appliances"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=DOMAIN, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class NoAppliances(HomeAssistantError):
    """Error to indicate there are no appliances."""


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
