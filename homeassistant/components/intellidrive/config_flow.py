"""Config flow for Intellidrive integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
from aiohttp import web
import reisingerdrive
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, STATUSDICT_SERIALNO

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_TOKEN): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    api_token = "None"
    if data.get(CONF_TOKEN) is not None:
        api_token = data[CONF_TOKEN]

    hub = reisingerdrive.ReisingerSlidingDoorDeviceApi(
        data[CONF_HOST], api_token, async_get_clientsession(hass)
    )

    try:
        result = await hub.authenticate()
    except web.HTTPUnauthorized as err:
        raise InvalidAuth from err
    except asyncio.TimeoutError as err:
        raise CannotConnect from err
    except aiohttp.ClientError as err:
        raise CannotConnect from err

    if result is False:
        raise InvalidAuth

    door_state_values = await hub.async_get_device_state()

    # Return info that you want to store in the config entry.
    return {
        "title": "Intellidrive ",
        STATUSDICT_SERIALNO: door_state_values[STATUSDICT_SERIALNO],
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Intellidrive."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

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
                await self.async_set_unique_id(info[STATUSDICT_SERIALNO])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info[STATUSDICT_SERIALNO], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
