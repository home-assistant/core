"""Config flow for Aqvify integration."""
from __future__ import annotations

import logging
from typing import Any

from aqvify import AqvifyAPI, DevicesAPI
from requests.exceptions import ConnectionError as ConnectError, HTTPError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_DEVICES, CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default="My Account"): str,
        vol.Required(CONF_HOST, default="https://public.aqvify.com"): str,
        vol.Required(CONF_API_KEY): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aqvify."""

    VERSION = 1

    name: str
    host: str
    api_key: str
    devices: list

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input:
            self.name = user_input[CONF_NAME]
            self.host = user_input[CONF_HOST]
            self.api_key = user_input[CONF_API_KEY]

            api = AqvifyAPI(self.host, self.api_key)
            devices_api = DevicesAPI(api)

            try:
                self.devices = await self.hass.async_add_executor_job(
                    devices_api.get_devices
                )
            except ConnectError:
                errors["base"] = "cannot_connect"
            except HTTPError:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return await self.async_step_devices()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select Aqvify devices to configure."""

        if not user_input:
            return self.async_show_form(
                step_id="devices",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_DEVICES, default=[]): cv.multi_select(
                            {
                                device["deviceKey"]: device["name"]
                                for device in self.devices
                            }
                        )
                    }
                ),
            )

        selected_devices = user_input[CONF_DEVICES]

        await self.async_set_unique_id(self.api_key[3:8])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=self.name,
            data={
                CONF_HOST: self.host,
                CONF_API_KEY: self.api_key,
                CONF_DEVICES: [
                    {"device_key": device["deviceKey"], "name": device["name"]}
                    for device in self.devices
                    if device["deviceKey"] in selected_devices
                ],
            },
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
