"""Config flow for HWAM Smart Control integration."""

from __future__ import annotations

import ipaddress
import logging
from typing import Any

import aiohttp
from pystove import Stove
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    try:
        ipaddress.ip_address(data[CONF_HOST])
    except ValueError as e:
        raise ConfigEntryError(e) from e

    try:
        stove: Stove = await Stove.create(data[CONF_HOST])
        name = stove.name
        await stove.destroy()
    except aiohttp.ClientError as e:
        raise CannotConnect(e) from e

    # Return info that you want to store in the config entry.
    return {"title": name}


class StoveConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HWAM Smart Control."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect as e:
                errors["base"] = str(e)
            except Exception as e:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = str(e)
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
