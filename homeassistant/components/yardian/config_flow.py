"""Config flow for Yardian integration."""
from __future__ import annotations

import logging
from typing import Any

from pyyardian import AsyncYardianClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_ACCESS_TOKEN): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Yardian."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                yarcli = AsyncYardianClient(
                    async_get_clientsession(self.hass),
                    user_input["host"],
                    user_input["access_token"],
                )
                device_info = await yarcli.fetch_device_info()
                if "iCode" in device_info and device_info["iCode"] == -1000:
                    raise InvalidAuth
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception as e:  # pylint: disable=broad-except
                _LOGGER.exception(e)
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(device_info["yid"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    data=user_input | device_info,
                    title=f"{device_info['name']} - {device_info['yid']}",
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
