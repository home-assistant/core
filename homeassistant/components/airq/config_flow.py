"""Config flow for air-Q integration."""
from __future__ import annotations

import logging
from typing import Any

from aioairq import AirQ, InvalidAuth, InvalidInput
from aiohttp.client_exceptions import ClientConnectionError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for air-Q."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial (authentication) configuration step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors: dict[str, str] = {}

        session = async_get_clientsession(self.hass)
        try:
            airq = AirQ(user_input[CONF_IP_ADDRESS], user_input[CONF_PASSWORD], session)
        except InvalidInput:
            _LOGGER.debug(
                "%s does not appear to be a valid IP address or mDNS name",
                user_input[CONF_IP_ADDRESS],
            )
            errors["base"] = "invalid_input"
        else:
            try:
                await airq.validate()
            except ClientConnectionError:
                _LOGGER.debug(
                    "Failed to connect to device %s. Check the IP address / device ID "
                    "as well as whether the device is connected to power and the WiFi",
                    user_input[CONF_IP_ADDRESS],
                )
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                _LOGGER.debug(
                    "Incorrect password for device %s", user_input[CONF_IP_ADDRESS]
                )
                errors["base"] = "invalid_auth"
            else:
                _LOGGER.debug(
                    "Successfully connected to %s", user_input[CONF_IP_ADDRESS]
                )

                device_info = await airq.fetch_device_info()
                await self.async_set_unique_id(device_info.pop("id"))
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=device_info["name"],
                    data=user_input | {"device_info": device_info},
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
