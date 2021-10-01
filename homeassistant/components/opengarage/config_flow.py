"""Config flow for OpenGarage integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import opengarage
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from .const import CONF_DEVICE_KEY, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_KEY): str,
        vol.Required(CONF_HOST, default="http://"): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_VERIFY_SSL, default=False): bool,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    open_garage = opengarage.OpenGarage(
        f"{data[CONF_HOST]}:{data[CONF_PORT]}",
        data[CONF_DEVICE_KEY],
        data[CONF_VERIFY_SSL],
        async_get_clientsession(hass),
    )

    try:
        status = await open_garage.update_state()
    except aiohttp.ClientError as exp:
        raise CannotConnect from exp

    if status is None:
        raise InvalidAuth

    return {"title": status.get("name"), "unique_id": format_mac(status["mac"])}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenGarage."""

    VERSION = 1

    async def async_step_import(self, import_info):
        """Set the config entry up from yaml."""

        user_input = {
            CONF_DEVICE_KEY: import_info[CONF_DEVICE_KEY],
            CONF_HOST: f"{'https' if import_info.get(CONF_SSL, False) else 'http'}://{import_info[CONF_HOST]}",
            CONF_PORT: import_info.get(CONF_PORT, DEFAULT_PORT),
            CONF_VERIFY_SSL: import_info.get(CONF_VERIFY_SSL, False),
        }
        return await self.async_step_user(user_input)

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
            await self.async_set_unique_id(info["unique_id"])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
