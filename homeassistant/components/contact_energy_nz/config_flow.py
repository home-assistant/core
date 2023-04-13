"""Config flow for Contact Energy NZ integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import async_timeout
from contact_energy_nz import AuthException, ContactEnergyApi
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN
from .exceptions import CannotConnect, InvalidAuth

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_API_KEY, "z840P4lQCH9TqcjC9L2pP157DZcZJMcr5tVQCvyx"): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> bool:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    try:
        async with async_timeout.timeout(60):
            connector = await ContactEnergyApi.from_credentials(
                data[CONF_USERNAME], data[CONF_PASSWORD]
            )
    except asyncio.TimeoutError as err:
        raise CannotConnect() from err
    except AuthException as err:
        raise InvalidAuth() from err

    # Return info that you want to store in the config entry.
    return connector.token is not None


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Contact Energy NZ."""

    VERSION = 1

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
                await self.async_set_unique_id(
                    f"contact_energy_{user_input[CONF_USERNAME]}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Contact Energy: {user_input[CONF_USERNAME]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
